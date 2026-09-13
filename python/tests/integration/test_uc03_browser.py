"""
tests/integration/test_uc03_browser.py: Recorrido completo UC-03 (Sección 3.2 y 14.2).
"Completa este formulario de prueba con los datos que te indico."
Utiliza Playwright sobre un servidor HTTP local y verifica la recepción en el servidor.
"""

import pytest
from pathlib import Path
import sys

# Añadir raíz al sys.path para importar fixture server
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from fixtures.uc03.server import LocalFormServer, RECEIVED_SUBMISSIONS
from local_agent.config import AppConfig
from local_agent.domain.models import Task, TaskScope, TaskProposal
from local_agent.domain.states import TaskState, ActionState
from local_agent.policy.engine import PolicyEngine
from local_agent.providers.base import ModelResponse
from local_agent.providers.fake import FakeModelProvider
from local_agent.tools.base import ToolRegistry
from local_agent.tools.browser import (
    BrowserAdapter,
    BrowserOpenTool,
    BrowserObserveTool,
    BrowserFillTool,
    BrowserClickTool,
)
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


@pytest.fixture
def local_server():
    server = LocalFormServer(port=8765)
    server.start()
    yield server
    server.stop()


@pytest.mark.asyncio
async def test_uc03_browser_form_submission(tmp_path, local_server):
    db = Database(tmp_path / "uc03_test.db")
    await db.migrate()

    task_repo = TaskRepository(db)
    event_repo = EventRepository(db)
    action_repo = ActionRepository(db)
    appr_repo = ApprovalRepository(db)
    art_repo = ArtifactRepository(db)
    scope_repo = ScopeRepository(db)

    scope = TaskScope(
        scope_id="scope_uc03",
        name="Scope UC-03 Web",
        allowed_domains=["127.0.0.1", "localhost"],
    )
    await scope_repo.save_scope(scope)

    browser_adapter = BrowserAdapter(headless=True)
    registry = ToolRegistry()
    registry.register(BrowserOpenTool(browser_adapter))
    registry.register(BrowserObserveTool(browser_adapter))
    registry.register(BrowserFillTool(browser_adapter))
    registry.register(BrowserClickTool(browser_adapter))

    target_url = "http://127.0.0.1:8765/"

    # Secuencia ReAct para UC-03
    step1 = ModelResponse(
        tool_calls=[
            TaskProposal(
                tool="browser.open",
                arguments={"url": target_url},
                brief_reason="Abrir página de formulario",
                expected_result="Página cargada",
            )
        ]
    )
    step2 = ModelResponse(
        tool_calls=[
            TaskProposal(
                tool="browser.fill",
                arguments={"selector": "#nombre", "value": "Carlos Pérez"},
                brief_reason="Completar campo nombre",
                expected_result="Nombre ingresado",
            )
        ]
    )
    step3 = ModelResponse(
        tool_calls=[
            TaskProposal(
                tool="browser.fill",
                arguments={"selector": "#email", "value": "carlos@ejemplo.local"},
                brief_reason="Completar campo correo",
                expected_result="Email ingresado",
            )
        ]
    )
    step4 = ModelResponse(
        tool_calls=[
            TaskProposal(
                tool="browser.fill",
                arguments={"selector": "#comentarios", "value": "Comentarios de prueba automatizada."},
                brief_reason="Completar comentarios",
                expected_result="Comentarios ingresados",
            )
        ]
    )
    step5 = ModelResponse(
        tool_calls=[
            TaskProposal(
                tool="browser.click",
                arguments={"selector": "#btn-enviar"},
                brief_reason="Enviar formulario",
                expected_result="Confirmación en pantalla",
            )
        ]
    )
    step6 = ModelResponse(
        content="El formulario ha sido enviado satisfactoriamente y la confirmación fue verificada.",
        tool_calls=[],
    )

    provider = FakeModelProvider([step1, step2, step3, step4, step5, step6])

    core = AgentCore(
        config=AppConfig(),
        model_provider=provider,
        tool_registry=registry,
        policy_engine=PolicyEngine(),
        task_repo=task_repo,
        event_repo=event_repo,
        action_repo=action_repo,
        approval_repo=appr_repo,
        artifact_repo=art_repo,
        scope_repo=scope_repo,
        queue_manager=TaskQueueManager(task_repo, event_repo),
    )

    task = Task(
        instruction="Completa este formulario de prueba con los datos que te indico.",
        scope_id="scope_uc03",
    )
    await task_repo.create_task(task)

    try:
        completed = await core.execute_task(task.task_id)
        assert completed.state == TaskState.COMPLETED

        # Ninguna acción del navegador debe haber fallado. El estado final de la
        # tarea lo determina el guion del proveedor simulado, no el éxito real de
        # las herramientas, así que revisamos las acciones para obtener el error
        # concreto (p. ej. Chromium sin instalar) en lugar de un "recibidos: 0".
        actions = await action_repo.get_actions_for_task(task.task_id)
        failed = [a for a in actions if a.state == ActionState.FAILED]
        assert not failed, (
            f"{len(failed)} de {len(actions)} acciones fallaron. "
            f"Primer fallo -> {failed[0].tool}: {failed[0].error}"
        )

        # Verificación independiente en el servidor HTTP
        assert len(RECEIVED_SUBMISSIONS) == 1, f"Se esperaba 1 envío en el servidor, recibidos: {len(RECEIVED_SUBMISSIONS)}"
        submission = RECEIVED_SUBMISSIONS[0]
        assert submission["nombre"] == "Carlos Pérez"
        assert submission["email"] == "carlos@ejemplo.local"
        assert submission["comentarios"] == "Comentarios de prueba automatizada."

    finally:
        await browser_adapter.close()
        await db.close()
