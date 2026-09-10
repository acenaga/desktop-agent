"""
database.py: Conexión SQLite y migraciones para LocalDesk.
"""

import asyncio
from pathlib import Path
import aiosqlite
from local_agent.domain.states import TaskState


MIGRATION_V1 = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scopes (
    scope_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    read_roots TEXT NOT NULL,       -- JSON array
    write_roots TEXT NOT NULL,      -- JSON array
    allowed_apps TEXT NOT NULL,     -- JSON array
    allowed_domains TEXT NOT NULL,  -- JSON array
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    instruction TEXT NOT NULL,
    state TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    input_refs TEXT NOT NULL,       -- JSON array
    output_name TEXT,
    idempotency_key TEXT UNIQUE,
    plan_explanation TEXT,
    error_message TEXT,
    steps_count INTEGER DEFAULT 0,
    active_duration_seconds REAL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY(scope_id) REFERENCES scopes(scope_id)
);

CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks(state);
CREATE INDEX IF NOT EXISTS idx_tasks_idempotency ON tasks(idempotency_key);

CREATE TABLE IF NOT EXISTS task_events (
    event_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,          -- JSON object
    created_at TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
);

CREATE INDEX IF NOT EXISTS idx_events_task_seq ON task_events(task_id, sequence);

CREATE TABLE IF NOT EXISTS actions (
    action_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    tool TEXT NOT NULL,
    arguments TEXT NOT NULL,         -- JSON object
    canonical_arguments TEXT NOT NULL, -- JSON object
    brief_reason TEXT NOT NULL,
    expected_result TEXT NOT NULL,
    state TEXT NOT NULL,
    scope_version INTEGER DEFAULT 1,
    observation_id TEXT,
    result TEXT,                     -- JSON object
    error TEXT,
    created_at TEXT NOT NULL,
    executed_at TEXT,
    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
);

CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    action_summary TEXT NOT NULL,
    canonical_arguments TEXT NOT NULL, -- JSON object
    scope_version INTEGER DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    expires_at TEXT,
    FOREIGN KEY(task_id) REFERENCES tasks(task_id),
    FOREIGN KEY(action_id) REFERENCES actions(action_id)
);

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
);

CREATE TABLE IF NOT EXISTS user_preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,             -- JSON encoded value
    updated_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> aiosqlite.Connection:
        if self._conn is None:
            self._conn = await aiosqlite.connect(self.db_path)
            self._conn.row_factory = aiosqlite.Row
            await self._conn.execute("PRAGMA foreign_keys = ON;")
            await self._conn.execute("PRAGMA journal_mode = WAL;")
        return self._conn

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def migrate(self) -> None:
        async with self._lock:
            conn = await self.connect()
            await conn.executescript(MIGRATION_V1)
            # Record migration version if not recorded
            cur = await conn.execute("SELECT version FROM schema_migrations WHERE version = 1")
            row = await cur.fetchone()
            if not row:
                await conn.execute("INSERT INTO schema_migrations (version) VALUES (1)")
            await conn.commit()

    async def recover_interrupted_tasks(self) -> int:
        """
        Recuperación tras reinicio: marca tareas 'running' o 'cancelling' como 'interrupted'.
        """
        async with self._lock:
            conn = await self.connect()
            cur = await conn.execute(
                """
                UPDATE tasks
                SET state = ?, updated_at = datetime('now')
                WHERE state IN (?, ?)
                """,
                (TaskState.INTERRUPTED.value, TaskState.RUNNING.value, TaskState.CANCELLING.value),
            )
            affected = cur.rowcount
            await conn.commit()
            return affected
