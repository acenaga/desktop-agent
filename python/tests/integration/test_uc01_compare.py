"""
tests/integration/test_uc01_compare.py: Recorrido completo UC-01 (Sección 3.2 y 14.2).
"Compara estas dos propuestas y guarda las diferencias en mi carpeta de salida."
Lee dos archivos (MD y DOCX) y genera un Markdown con diferencias y referencias a fuentes.
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
from local_agent.tools.files import FilesReadTool, FilesWriteTool
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
async def test_uc01_document_comparison(tmp_path):
    fixtures_dir = Path("fixtures/uc01").resolve()
    doc_a = fixtures_dir / "propuesta_alfa.md"
    doc_b = fixtures_dir / "propuesta_beta.docx"
    assert doc_a.exists(), "Fixture propuesta_alfa.md no existe"
    assert doc_b.exists(), "Fixture propuesta_beta.docx no existe"

    output_dir = tmp_path / "salida"
    output_dir.mkdir()
    comparison_file = output_dir / "comparacion_propuestas.md"

    # Base de datos y repositorios
    db = Database(tmp_path / "uc01_test.db")
    await db.migrate()

    task_repo = TaskRepository(db)
    event_repo = EventRepository(db)
    action_repo = ActionRepository(db)
    appr_repo = ApprovalRepository(db)
    art_repo = ArtifactRepository(db)
    scope_repo = ScopeRepository(db)

    scope = TaskScope(
        scope_id="scope_uc01",
        name="Scope UC-01",
        read_roots=[str(fixtures_dir)],
        write_roots=[str(output_dir)],
    )
    await scope_repo.save_scope(scope)

    registry = ToolRegistry()
    registry.register(FilesReadTool())
    registry.register(FilesWriteTool())

    # Emulación del comportamiento del modelo para UC-01
    # Paso 1: Leer propuesta A
    # Paso 2: Leer propuesta B
    # Paso 3: Escribir comparacion_propuestas.md
    # Paso 4: Finalizar
    step1_read_a = ModelResponse(
        tool_calls=[
            TaskProposal(
                tool="files.read",
                arguments={"path": str(doc_a)},
                brief_reason="Leer primera propuesta (Opción Alfa)",
                expected_result="Contenido de propuesta_alfa.md",
            )
        ]
    )

    step2_read_b = ModelResponse(
        tool_calls=[
            TaskProposal(
                tool="files.read",
                arguments={"path": str(doc_b)},
                brief_reason="Leer segunda propuesta (Opción Beta)",
                expected_result="Contenido de propuesta_beta.docx",
            )
        ]
    )

    report_content = (
        "# Comparación de Propuestas de Desarrollo\n\n"
        "## 1. Fechas de Entrega\n"
        "- **Opción Alfa:** 15 de marzo de 2026 (ref: `propuesta_alfa.md`, sección Plazos)\n"
        "- **Opción Beta:** 28 de abril de 2026 (ref: `propuesta_beta.docx`, encabezado y cronograma)\n\n"
        "## 2. Presupuesto y Monto Total\n"
        "- **Opción Alfa:** $45.000 USD (ref: `propuesta_alfa.md`)\n"
        "- **Opción Beta:** $62.000 USD (ref: `propuesta_beta.docx`)\n\n"
        "## 3. Alcance y Garantía\n"
        "- **Opción Alfa:** UI escritorio/web, backend REST, garantía de 30 días.\n"
        "- **Opción Beta:** UI React/TS, backend Python, automatización nativa, CI/CD y soporte 24/7 por 12 meses.\n"
    )

    step3_write_diff = ModelResponse(
        tool_calls=[
            TaskProposal(
                tool="files.write",
                arguments={"path": str(comparison_file), "content": report_content},
                brief_reason="Guardar informe comparativo con referencias",
                expected_result="Existe comparacion_propuestas.md",
            )
        ]
    )

    step4_done = ModelResponse(
        content="He comparado ambas propuestas y guardé el reporte con diferencias en comparacion_propuestas.md.",
        tool_calls=[],
    )

    provider = FakeModelProvider([step1_read_a, step2_read_b, step3_write_diff, step4_done])

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
        instruction="Compara estas dos propuestas y guarda las diferencias en mi carpeta de salida.",
        scope_id="scope_uc01",
        input_refs=[str(doc_a), str(doc_b)],
        output_name="comparacion_propuestas.md",
    )
    await task_repo.create_task(task)

    completed = await core.execute_task(task.task_id)

    assert completed.state == TaskState.COMPLETED
    assert comparison_file.exists()

    content = comparison_file.read_text(encoding="utf-8")
    # Validar que identifica diferencias de fecha, monto y alcance
    assert "15 de marzo de 2026" in content
    assert "28 de abril de 2026" in content
    assert "$45.000 USD" in content
    assert "$62.000 USD" in content
    assert "30 días" in content
    assert "24/7" in content

    # Validar evidencia de artefacto en base de datos
    artifacts = await art_repo.get_artifacts_for_task(task.task_id)
    assert len(artifacts) == 1
    assert artifacts[0].file_name == "comparacion_propuestas.md"
    assert artifacts[0].size_bytes > 0
    assert len(artifacts[0].sha256) == 64

    await db.close()
