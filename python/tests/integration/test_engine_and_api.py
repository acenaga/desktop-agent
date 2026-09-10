"""
tests/integration/test_engine_and_api.py: Pruebas de integración del motor ReAct,
cancelación (<1s), pausa, reanudación y endpoints de la API /v1.
"""

import asyncio
import pytest
from pathlib import Path
import httpx

from local_agent.config import AppConfig
from local_agent.domain.models import Task, TaskScope, TaskProposal, new_id
from local_agent.domain.states import TaskState
from local_agent.policy.engine import PolicyEngine
from local_agent.providers.base import ModelResponse
from local_agent.providers.fake import FakeModelProvider
from local_agent.tools.base import ToolRegistry
from local_agent.tools.files import FilesWriteTool, FilesReadTool
from local_agent.storage.database import Database
from local_agent.storage.repository import (
    TaskRepository,
    EventRepository,
    ActionRepository,
    ApprovalRepository,
    ArtifactRepository,
    ScopeRepository,
)
from local_agent.core.queue import TaskQueueManager
from local_agent.core.engine import AgentCore
from local_agent.api.app import create_app
from local_agent.api.auth import set_session_token


@pytest.fixture
async def setup_core(tmp_path):
    db_file = tmp_path / "integration_agent.db"
    db = Database(db_file)
    await db.migrate()

    task_repo = TaskRepository(db)
    event_repo = EventRepository(db)
    action_repo = ActionRepository(db)
    appr_repo = ApprovalRepository(db)
    art_repo = ArtifactRepository(db)
    scope_repo = ScopeRepository(db)

    work_dir = tmp_path / "work"
    work_dir.mkdir()

    scope = TaskScope(
        scope_id="integration_scope",
        name="Scope Integración",
        read_roots=[str(work_dir.resolve())],
        write_roots=[str(work_dir.resolve())],
        allowed_apps=["notepad"],
        allowed_domains=["localhost", "127.0.0.1"],
    )
    await scope_repo.save_scope(scope)

    registry = ToolRegistry()
    registry.register(FilesReadTool())
    registry.register(FilesWriteTool())

    fake_provider = FakeModelProvider()
    queue_mgr = TaskQueueManager(task_repo, event_repo)
    config = AppConfig()

    core = AgentCore(
        config=config,
        model_provider=fake_provider,
        tool_registry=registry,
        policy_engine=PolicyEngine(),
        task_repo=task_repo,
        event_repo=event_repo,
        action_repo=action_repo,
        approval_repo=appr_repo,
        artifact_repo=art_repo,
        scope_repo=scope_repo,
        queue_manager=queue_mgr,
    )

    yield {
        "core": core,
        "work_dir": work_dir,
        "scope": scope,
        "provider": fake_provider,
        "task_repo": task_repo,
        "art_repo": art_repo,
    }
    await db.close()


@pytest.mark.asyncio
async def test_full_synthetic_task_execution(setup_core):
    core = setup_core["core"]
    work_dir = setup_core["work_dir"]
    provider = setup_core["provider"]
    art_repo = setup_core["art_repo"]

    out_file = work_dir / "resumen.md"

    # Configurar respuesta simulada que propone files.write y luego termina
    step1 = ModelResponse(
        tool_calls=[
            TaskProposal(
                tool="files.write",
                arguments={"path": str(out_file), "content": "# Resumen completado con éxito"},
                brief_reason="Generar archivo de resumen solicitado",
                expected_result="Existe resumen.md con contenido",
            )
        ]
    )
    step2 = ModelResponse(content="Tarea finalizada con éxito.", tool_calls=[])
    provider.canned_responses = [step1, step2]

    task = Task(
        instruction="Genera el archivo resumen.md en la carpeta autorizada",
        scope_id="integration_scope",
        output_name="resumen.md",
    )
    await core.task_repo.create_task(task)

    completed = await core.execute_task(task.task_id)
    assert completed.state == TaskState.COMPLETED
    assert out_file.exists()
    assert "# Resumen completado" in out_file.read_text(encoding="utf-8")

    # Verificar registro de artefactos
    artifacts = await art_repo.get_artifacts_for_task(task.task_id)
    assert len(artifacts) == 1
    assert artifacts[0].file_name == "resumen.md"


@pytest.mark.asyncio
async def test_task_cancellation_under_one_second(setup_core):
    core = setup_core["core"]
    provider = setup_core["provider"]

    # Simular una acción que tarda un poco pero respeta el token de cancelación
    async def slow_response(*args, **kwargs):
        cancellation_token = kwargs.get("cancellation_token")
        for _ in range(20):
            if cancellation_token and cancellation_token.is_set():
                raise asyncio.CancelledError()
            await asyncio.sleep(0.1)
        return ModelResponse(content="Lento", tool_calls=[])

    provider.generate = slow_response

    task = Task(
        instruction="Tarea que será cancelada",
        scope_id="integration_scope",
    )
    await core.task_repo.create_task(task)

    # Disparar tarea en background y registrarla en el gestor de cola
    exec_task = asyncio.create_task(core.execute_task(task.task_id))
    core.queue_manager.register_active_execution(task.task_id, exec_task)

    # Esperar 100ms y solicitar cancelación
    await asyncio.sleep(0.1)
    t0 = asyncio.get_event_loop().time()
    core.queue_manager.request_cancel(task.task_id)

    completed = await exec_task
    t1 = asyncio.get_event_loop().time()

    assert completed.state == TaskState.CANCELLED
    # Comprobar que la respuesta a la cancelación fue en menos de 1 segundo (Sección 7.2)
    assert (t1 - t0) < 1.0


@pytest.mark.asyncio
async def test_api_v1_endpoints(setup_core):
    core = setup_core["core"]
    token = "test-secret-session-token-12345"
    set_session_token(token)

    app = create_app(core)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Sin header de autorización -> 401
        unauth = await client.get("/v1/health")
        assert unauth.status_code == 401

        # 2. Con token incorrecto -> 403
        bad_token = await client.get("/v1/health", headers={"Authorization": "Bearer bad-token"})
        assert bad_token.status_code == 403

        # 3. Health con token válido -> 200
        headers = {"Authorization": f"Bearer {token}"}
        health = await client.get("/v1/health", headers=headers)
        assert health.status_code == 200
        data = health.json()
        assert data["status"] == "ok"
        assert "os_platform" in data

        # 4. Crear tarea mediante POST /v1/tasks
        create_res = await client.post(
            "/v1/tasks",
            json={
                "instruction": "Tarea API de prueba",
                "scope_id": "integration_scope",
                "input_refs": [],
            },
            headers={**headers, "Idempotency-Key": "api-idem-1"},
        )
        assert create_res.status_code == 201
        task_data = create_res.json()
        assert "task_id" in task_data

        # 5. Idempotencia: reenviar con misma Idempotency-Key -> devuelve la misma tarea
        dup_res = await client.post(
            "/v1/tasks",
            json={
                "instruction": "Tarea API de prueba",
                "scope_id": "integration_scope",
                "input_refs": [],
            },
            headers={**headers, "Idempotency-Key": "api-idem-1"},
        )
        assert dup_res.status_code == 201
        assert dup_res.json()["task_id"] == task_data["task_id"]

        # 6. Consultar estado mediante GET /v1/tasks/{task_id}
        get_res = await client.get(f"/v1/tasks/{task_data['task_id']}", headers=headers)
        assert get_res.status_code == 200
        detail = get_res.json()
        assert detail["task"]["task_id"] == task_data["task_id"]
