"""
repository.py: Implementación de repositorios SQLite para LocalDesk.
"""

import json
from typing import Any, Optional, List
from local_agent.domain.models import (
    Task,
    TaskEvent,
    Action,
    Approval,
    Artifact,
    TaskScope,
    UserPreference,
    now_utc_iso,
    new_id,
)
from local_agent.domain.states import TaskState, ActionState, EventType
from .database import Database


class TaskRepository:
    def __init__(self, db: Database):
        self.db = db

    async def create_task(self, task: Task) -> Task:
        async with self.db._lock:
            conn = await self.db.connect()
            # If idempotency_key is provided, check if existing
            if task.idempotency_key:
                cur = await conn.execute(
                    "SELECT * FROM tasks WHERE idempotency_key = ?",
                    (task.idempotency_key,),
                )
                row = await cur.fetchone()
                if row:
                    return self._row_to_task(row)

            await conn.execute(
                """
                INSERT INTO tasks (
                    task_id, instruction, state, scope_id, input_refs, output_name,
                    idempotency_key, plan_explanation, error_message, steps_count,
                    active_duration_seconds, created_at, updated_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.instruction,
                    task.state.value,
                    task.scope_id,
                    json.dumps(task.input_refs),
                    task.output_name,
                    task.idempotency_key,
                    task.plan_explanation,
                    task.error_message,
                    task.steps_count,
                    task.active_duration_seconds,
                    task.created_at,
                    task.updated_at,
                    task.completed_at,
                ),
            )
            await conn.commit()
            return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        async with self.db._lock:
            conn = await self.db.connect()
            cur = await conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            row = await cur.fetchone()
            if not row:
                return None
            return self._row_to_task(row)

    async def get_active_task(self) -> Optional[Task]:
        active_states = [
            TaskState.RUNNING.value,
            TaskState.AWAITING_APPROVAL.value,
            TaskState.AWAITING_INPUT.value,
            TaskState.PAUSED.value,
            TaskState.CANCELLING.value,
        ]
        placeholders = ",".join("?" for _ in active_states)
        async with self.db._lock:
            conn = await self.db.connect()
            cur = await conn.execute(
                f"SELECT * FROM tasks WHERE state IN ({placeholders}) LIMIT 1",
                active_states,
            )
            row = await cur.fetchone()
            if not row:
                return None
            return self._row_to_task(row)

    async def update_task_state(
        self, task_id: str, state: TaskState, error_message: Optional[str] = None
    ) -> None:
        async with self.db._lock:
            conn = await self.db.connect()
            completed_at = now_utc_iso() if state.is_terminal else None
            await conn.execute(
                """
                UPDATE tasks
                SET state = ?, error_message = COALESCE(?, error_message),
                    updated_at = ?, completed_at = COALESCE(?, completed_at)
                WHERE task_id = ?
                """,
                (state.value, error_message, now_utc_iso(), completed_at, task_id),
            )
            await conn.commit()

    async def update_task_plan(self, task_id: str, plan_explanation: str) -> None:
        async with self.db._lock:
            conn = await self.db.connect()
            await conn.execute(
                "UPDATE tasks SET plan_explanation = ?, updated_at = ? WHERE task_id = ?",
                (plan_explanation, now_utc_iso(), task_id),
            )
            await conn.commit()

    async def increment_step(self, task_id: str, duration_seconds: float) -> None:
        async with self.db._lock:
            conn = await self.db.connect()
            await conn.execute(
                """
                UPDATE tasks
                SET steps_count = steps_count + 1,
                    active_duration_seconds = active_duration_seconds + ?,
                    updated_at = ?
                WHERE task_id = ?
                """,
                (duration_seconds, now_utc_iso(), task_id),
            )
            await conn.commit()

    async def list_tasks(self, limit: int = 50, offset: int = 0) -> List[Task]:
        async with self.db._lock:
            conn = await self.db.connect()
            cur = await conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = await cur.fetchall()
            return [self._row_to_task(r) for r in rows]

    def _row_to_task(self, row: Any) -> Task:
        return Task(
            task_id=row["task_id"],
            instruction=row["instruction"],
            state=TaskState(row["state"]),
            scope_id=row["scope_id"],
            input_refs=json.loads(row["input_refs"]),
            output_name=row["output_name"],
            idempotency_key=row["idempotency_key"],
            plan_explanation=row["plan_explanation"],
            error_message=row["error_message"],
            steps_count=row["steps_count"],
            active_duration_seconds=row["active_duration_seconds"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
        )


class EventRepository:
    def __init__(self, db: Database):
        self.db = db

    async def add_event(
        self, task_id: str, event_type: EventType, payload: dict[str, Any]
    ) -> TaskEvent:
        async with self.db._lock:
            conn = await self.db.connect()
            cur = await conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM task_events WHERE task_id = ?",
                (task_id,),
            )
            row = await cur.fetchone()
            seq = row[0] if row else 1

            event = TaskEvent(
                event_id=new_id("evt"),
                task_id=task_id,
                sequence=seq,
                event_type=event_type,
                payload=payload,
                created_at=now_utc_iso(),
            )

            await conn.execute(
                """
                INSERT INTO task_events (event_id, task_id, sequence, event_type, payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.task_id,
                    event.sequence,
                    event.event_type.value,
                    json.dumps(event.payload),
                    event.created_at,
                ),
            )
            await conn.commit()
            return event

    async def get_events(self, task_id: str, after_seq: int = 0) -> List[TaskEvent]:
        async with self.db._lock:
            conn = await self.db.connect()
            cur = await conn.execute(
                """
                SELECT * FROM task_events
                WHERE task_id = ? AND sequence > ?
                ORDER BY sequence ASC
                """,
                (task_id, after_seq),
            )
            rows = await cur.fetchall()
            return [
                TaskEvent(
                    event_id=r["event_id"],
                    task_id=r["task_id"],
                    sequence=r["sequence"],
                    event_type=EventType(r["event_type"]),
                    payload=json.loads(r["payload"]),
                    created_at=r["created_at"],
                )
                for r in rows
            ]


class ActionRepository:
    def __init__(self, db: Database):
        self.db = db

    async def record_action(self, action: Action) -> Action:
        async with self.db._lock:
            conn = await self.db.connect()
            await conn.execute(
                """
                INSERT INTO actions (
                    action_id, task_id, tool, arguments, canonical_arguments,
                    brief_reason, expected_result, state, scope_version,
                    observation_id, result, error, created_at, executed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action.action_id,
                    action.task_id,
                    action.tool,
                    json.dumps(action.arguments),
                    json.dumps(action.canonical_arguments),
                    action.brief_reason,
                    action.expected_result,
                    action.state.value,
                    action.scope_version,
                    action.observation_id,
                    json.dumps(action.result) if action.result is not None else None,
                    action.error,
                    action.created_at,
                    action.executed_at,
                ),
            )
            await conn.commit()
            return action

    async def update_action(
        self,
        action_id: str,
        state: ActionState,
        result: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        async with self.db._lock:
            conn = await self.db.connect()
            await conn.execute(
                """
                UPDATE actions
                SET state = ?, result = ?, error = ?, executed_at = ?
                WHERE action_id = ?
                """,
                (
                    state.value,
                    json.dumps(result) if result is not None else None,
                    error,
                    now_utc_iso(),
                    action_id,
                ),
            )
            await conn.commit()

    async def get_actions_for_task(self, task_id: str) -> List[Action]:
        async with self.db._lock:
            conn = await self.db.connect()
            cur = await conn.execute(
                "SELECT * FROM actions WHERE task_id = ? ORDER BY created_at ASC",
                (task_id,),
            )
            rows = await cur.fetchall()
            return [
                Action(
                    action_id=r["action_id"],
                    task_id=r["task_id"],
                    tool=r["tool"],
                    arguments=json.loads(r["arguments"]),
                    canonical_arguments=json.loads(r["canonical_arguments"]),
                    brief_reason=r["brief_reason"],
                    expected_result=r["expected_result"],
                    state=ActionState(r["state"]),
                    scope_version=r["scope_version"],
                    observation_id=r["observation_id"],
                    result=json.loads(r["result"]) if r["result"] else None,
                    error=r["error"],
                    created_at=r["created_at"],
                    executed_at=r["executed_at"],
                )
                for r in rows
            ]


class ApprovalRepository:
    def __init__(self, db: Database):
        self.db = db

    async def create_approval(self, approval: Approval) -> Approval:
        async with self.db._lock:
            conn = await self.db.connect()
            await conn.execute(
                """
                INSERT INTO approvals (
                    approval_id, task_id, action_id, action_summary, canonical_arguments,
                    scope_version, status, created_at, resolved_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval.approval_id,
                    approval.task_id,
                    approval.action_id,
                    approval.action_summary,
                    json.dumps(approval.canonical_arguments),
                    approval.scope_version,
                    approval.status,
                    approval.created_at,
                    approval.resolved_at,
                    approval.expires_at,
                ),
            )
            await conn.commit()
            return approval

    async def get_approval(self, approval_id: str) -> Optional[Approval]:
        async with self.db._lock:
            conn = await self.db.connect()
            cur = await conn.execute(
                "SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)
            )
            r = await cur.fetchone()
            if not r:
                return None
            return Approval(
                approval_id=r["approval_id"],
                task_id=r["task_id"],
                action_id=r["action_id"],
                action_summary=r["action_summary"],
                canonical_arguments=json.loads(r["canonical_arguments"]),
                scope_version=r["scope_version"],
                status=r["status"],
                created_at=r["created_at"],
                resolved_at=r["resolved_at"],
                expires_at=r["expires_at"],
            )

    async def resolve_approval(self, approval_id: str, status: str) -> bool:
        async with self.db._lock:
            conn = await self.db.connect()
            cur = await conn.execute(
                """
                UPDATE approvals
                SET status = ?, resolved_at = ?
                WHERE approval_id = ? AND status = 'pending'
                """,
                (status, now_utc_iso(), approval_id),
            )
            await conn.commit()
            return cur.rowcount > 0


class ArtifactRepository:
    def __init__(self, db: Database):
        self.db = db

    async def record_artifact(self, artifact: Artifact) -> Artifact:
        async with self.db._lock:
            conn = await self.db.connect()
            await conn.execute(
                """
                INSERT INTO artifacts (artifact_id, task_id, file_path, file_name, size_bytes, sha256, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.artifact_id,
                    artifact.task_id,
                    artifact.file_path,
                    artifact.file_name,
                    artifact.size_bytes,
                    artifact.sha256,
                    artifact.created_at,
                ),
            )
            await conn.commit()
            return artifact

    async def get_artifacts_for_task(self, task_id: str) -> List[Artifact]:
        async with self.db._lock:
            conn = await self.db.connect()
            cur = await conn.execute(
                "SELECT * FROM artifacts WHERE task_id = ? ORDER BY created_at ASC",
                (task_id,),
            )
            rows = await cur.fetchall()
            return [
                Artifact(
                    artifact_id=r["artifact_id"],
                    task_id=r["task_id"],
                    file_path=r["file_path"],
                    file_name=r["file_name"],
                    size_bytes=r["size_bytes"],
                    sha256=r["sha256"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]


class ScopeRepository:
    def __init__(self, db: Database):
        self.db = db

    async def save_scope(self, scope: TaskScope) -> TaskScope:
        async with self.db._lock:
            conn = await self.db.connect()
            await conn.execute(
                """
                INSERT OR REPLACE INTO scopes (
                    scope_id, name, read_roots, write_roots, allowed_apps, allowed_domains, version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scope.scope_id,
                    scope.name,
                    json.dumps(scope.read_roots),
                    json.dumps(scope.write_roots),
                    json.dumps(scope.allowed_apps),
                    json.dumps(scope.allowed_domains),
                    scope.version,
                    scope.created_at,
                ),
            )
            await conn.commit()
            return scope

    async def get_scope(self, scope_id: str) -> Optional[TaskScope]:
        async with self.db._lock:
            conn = await self.db.connect()
            cur = await conn.execute("SELECT * FROM scopes WHERE scope_id = ?", (scope_id,))
            r = await cur.fetchone()
            if not r:
                return None
            return TaskScope(
                scope_id=r["scope_id"],
                name=r["name"],
                read_roots=json.loads(r["read_roots"]),
                write_roots=json.loads(r["write_roots"]),
                allowed_apps=json.loads(r["allowed_apps"]),
                allowed_domains=json.loads(r["allowed_domains"]),
                version=r["version"],
                created_at=r["created_at"],
            )


class PreferenceRepository:
    def __init__(self, db: Database):
        self.db = db

    async def get(self, key: str, default: Any = None) -> Any:
        async with self.db._lock:
            conn = await self.db.connect()
            cur = await conn.execute("SELECT value FROM user_preferences WHERE key = ?", (key,))
            r = await cur.fetchone()
            if not r:
                return default
            return json.loads(r["value"])

    async def set(self, key: str, value: Any) -> None:
        async with self.db._lock:
            conn = await self.db.connect()
            await conn.execute(
                """
                INSERT OR REPLACE INTO user_preferences (key, value, updated_at)
                VALUES (?, ?, ?)
                """,
                (key, json.dumps(value), now_utc_iso()),
            )
            await conn.commit()

    async def list_all(self) -> dict[str, Any]:
        async with self.db._lock:
            conn = await self.db.connect()
            cur = await conn.execute("SELECT key, value FROM user_preferences")
            rows = await cur.fetchall()
            return {r["key"]: json.loads(r["value"]) for r in rows}
