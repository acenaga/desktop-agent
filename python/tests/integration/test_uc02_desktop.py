"""
tests/integration/test_uc02_desktop.py: Recorrido completo UC-02 (Sección 3.2 y 14.2).
"Abre el Bloc de notas, escribe este texto y guárdalo como nota.txt en la carpeta autorizada."
Utiliza el DesktopAdapter con texto con tildes, eñes, puntuación y saltos de línea.
Comprueba que el archivo final contiene exactamente el texto pedido.
"""

import pytest
from pathlib import Path
from local_agent.config import AppConfig
from local_agent.domain.models import Task, TaskScope, TaskProposal
from local_agent.domain.states import TaskState
from local_agent.policy.engine import PolicyEngine
from local_agent.providers.base import ModelResponse
from local_agent.providers.fake import FakeModelProvider
from local_agent.tools.base import ToolRegistry
from local_agent.tools.desktop import (
    SimulatedDesktopAdapter,
    DesktopOpenAppTool,
    DesktopObserveTool,
    DesktopTypeTextTool,
    DesktopKeyTool,
)
from local_agent.tools.files import FilesWriteTool
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


@pytest.mark.asyncio
async def test_uc02_notepad_automation(tmp_path):
    output_dir = tmp_path / "carpeta_autorizada"
    output_dir.mkdir()
    note_path = output_dir / "nota.txt"

    db = Database(tmp_path / "uc02_test.db")
    await db.migrate()

    task_repo = TaskRepository(db)
    event_repo = EventRepository(db)
    action_repo = ActionRepository(db)
    appr_repo = ApprovalRepository(db)
    art_repo = ArtifactRepository(db)
    scope_repo = ScopeRepository(db)

    scope = TaskScope(
        scope_id="scope_uc02",
        name="Scope UC-02 Desktop",
        read_roots=[str(output_dir)],
        write_roots=[str(output_dir)],
        allowed_apps=["notepad", "bloc de notas"],
    )
    await scope_repo.save_scope(scope)

    # Usar adapter de escritorio
    desktop_adapter = SimulatedDesktopAdapter()
    registry = ToolRegistry()
    registry.register(DesktopOpenAppTool(desktop_adapter))
    registry.register(DesktopObserveTool(desktop_adapter))
    registry.register(DesktopTypeTextTool(desktop_adapter))
    registry.register(DesktopKeyTool(desktop_adapter))
    registry.register(FilesWriteTool())

    # Texto con tildes, eñes, saltos de línea y puntuación (Sección 14.2)
    sample_text = (
        "Notas del día:\n"
        "- Revisión de diseño para la versión 1.0 del agente.\n"
        "- Confirmación de reunión con el área técnica a las 15:30 hrs.\n"
        "- ¡Atención!: Comprobar configuración de la red local y contraseñas."
    )

    # Secuencia ReAct para UC-02
    step1 = ModelResponse(
        tool_calls=[
            TaskProposal(
                tool="desktop.open_app",
                arguments={"app_name": "notepad"},
                brief_reason="Abrir el Bloc de notas",
                expected_result="Ventana de Bloc de notas activa",
            )
        ]
    )
    step2 = ModelResponse(
        tool_calls=[
            TaskProposal(
                tool="desktop.type_text",
                arguments={"text": sample_text, "window_title": "notepad - Sin título"},
                brief_reason="Escribir el texto solicitado en el documento",
                expected_result="Texto escrito en el Bloc de notas",
            )
        ]
    )
    step3 = ModelResponse(
        tool_calls=[
            TaskProposal(
                tool="files.write",
                arguments={"path": str(note_path), "content": sample_text},
                brief_reason="Guardar el contenido como nota.txt en la carpeta autorizada",
                expected_result="Existe nota.txt con el texto exacto",
            )
        ]
    )
    step4 = ModelResponse(
        content="He abierto el Bloc de notas, escrito las notas y guardado el archivo como nota.txt.",
        tool_calls=[],
    )

    provider = FakeModelProvider([step1, step2, step3, step4])

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
        instruction="Abre el Bloc de notas, escribe este texto y guárdalo como nota.txt en la carpeta autorizada.",
        scope_id="scope_uc02",
        output_name="nota.txt",
    )
    await task_repo.create_task(task)

    completed = await core.execute_task(task.task_id)
    assert completed.state == TaskState.COMPLETED

    # 1. Comprobar que en la aplicación se escribió el texto
    observed = await desktop_adapter.observe_window("notepad - Sin título")
    assert observed["text_content"] == sample_text

    # 2. Comprobar que el archivo existe y contiene exactamente el texto (tildes, eñes, saltos de línea)
    assert note_path.exists()
    final_file_text = note_path.read_text(encoding="utf-8")
    assert final_file_text == sample_text

    # 3. Comprobar evidencia de artefacto en DB
    artifacts = await art_repo.get_artifacts_for_task(task.task_id)
    assert len(artifacts) == 1
    assert artifacts[0].file_name == "nota.txt"

    await db.close()
