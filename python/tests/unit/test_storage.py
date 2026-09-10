"""
tests/unit/test_storage.py: Pruebas unitarias de almacenamiento SQLite y recuperación.
"""

import pytest
from local_agent.domain.models import Task, TaskScope, TaskEvent, Approval, new_id
from local_agent.domain.states import TaskState, EventType
from local_agent.storage.database import Database
from local_agent.storage.repository import (
    TaskRepository,
    EventRepository,
    ApprovalRepository,
    ScopeRepository,
)


@pytest.fixture
async def db_repos(tmp_path):
    db_file = tmp_path / "test_local_agent.db"
    db = Database(db_file)
    await db.migrate()

    task_repo = TaskRepository(db)
    event_repo = EventRepository(db)
    appr_repo = ApprovalRepository(db)
    scope_repo = ScopeRepository(db)

    # Crear scope inicial
    scope = TaskScope(
        scope_id="test_scope",
        name="Scope Inicial",
        read_roots=[str(tmp_path)],
        write_roots=[str(tmp_path)],
    )
    await scope_repo.save_scope(scope)

    yield {
        "db": db,
        "task_repo": task_repo,
        "event_repo": event_repo,
        "appr_repo": appr_repo,
        "scope_repo": scope_repo,
    }
    await db.close()


@pytest.mark.asyncio
async def test_task_idempotency_key(db_repos):
    task_repo = db_repos["task_repo"]
    key = "unique-client-key-12345"

    task1 = Task(
        instruction="Procesar informe",
        scope_id="test_scope",
        idempotency_key=key,
    )
    created1 = await task_repo.create_task(task1)

    task2 = Task(
        instruction="Procesar informe (duplicado)",
        scope_id="test_scope",
        idempotency_key=key,
    )
    created2 = await task_repo.create_task(task2)

    # Debe devolver la misma tarea sin crear una nueva
    assert created1.task_id == created2.task_id
    assert created2.instruction == "Procesar informe"


@pytest.mark.asyncio
async def test_recover_interrupted_tasks(db_repos):
    db = db_repos["db"]
    task_repo = db_repos["task_repo"]

    # Crear una tarea en ejecución
    t1 = Task(instruction="Tarea interrumpida", state=TaskState.RUNNING, scope_id="test_scope")
    await task_repo.create_task(t1)

    # Simular cierre inesperado y reinicio
    recovered = await db.recover_interrupted_tasks()
    assert recovered == 1

    t1_after = await task_repo.get_task(t1.task_id)
    assert t1_after.state == TaskState.INTERRUPTED


@pytest.mark.asyncio
async def test_events_sequence_ordering(db_repos):
    task_repo = db_repos["task_repo"]
    event_repo = db_repos["event_repo"]
    task_id = "test_task_seq"

    # Insertar tarea padre para cumplir la restricción de clave foránea
    parent_task = Task(task_id=task_id, instruction="Tarea para eventos", scope_id="test_scope")
    await task_repo.create_task(parent_task)

    e1 = await event_repo.add_event(task_id, EventType.TASK_CREATED, {"info": "step1"})
    e2 = await event_repo.add_event(task_id, EventType.ACTION_STARTED, {"info": "step2"})
    e3 = await event_repo.add_event(task_id, EventType.TASK_COMPLETED, {"info": "step3"})

    assert e1.sequence == 1
    assert e2.sequence == 2
    assert e3.sequence == 3

    # Obtener eventos después de sequence 1
    subsequent = await event_repo.get_events(task_id, after_seq=1)
    assert len(subsequent) == 2
    assert subsequent[0].sequence == 2
    assert subsequent[1].sequence == 3


@pytest.mark.asyncio
async def test_one_time_approval_resolution(db_repos):
    task_repo = db_repos["task_repo"]
    from local_agent.storage.repository import ActionRepository
    from local_agent.domain.models import Action
    action_repo = ActionRepository(db_repos["db"])
    appr_repo = db_repos["appr_repo"]

    # Insertar tarea y acción padre para cumplir claves foráneas
    t1 = Task(task_id="t1", instruction="Tarea para aprobación", scope_id="test_scope")
    await task_repo.create_task(t1)

    a1 = Action(
        action_id="a1",
        task_id="t1",
        tool="files.write",
        brief_reason="Sobrescribir archivo",
        expected_result="Archivo sobrescrito",
    )
    await action_repo.record_action(a1)

    approval = Approval(
        task_id="t1",
        action_id="a1",
        action_summary="Aprobar sobreescritura",
        canonical_arguments={"path": "/out.txt"},
    )
    await appr_repo.create_approval(approval)

    # Primera resolución: éxito
    ok1 = await appr_repo.resolve_approval(approval.approval_id, "approved")
    assert ok1 is True

    # Segunda resolución: falla porque ya no está pendiente (es de un solo uso)
    ok2 = await appr_repo.resolve_approval(approval.approval_id, "approved")
    assert ok2 is False
