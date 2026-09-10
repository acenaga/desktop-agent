"""
core/queue.py: Gestor de cola y concurrencia de tareas (Sección 2: una tarea activa a la vez).
"""

import asyncio
from typing import Dict, Optional
from local_agent.domain.states import TaskState
from local_agent.storage.repository import TaskRepository, EventRepository


class TaskQueueManager:
    def __init__(
        self,
        task_repo: TaskRepository,
        event_repo: EventRepository,
        max_active_tasks: int = 1,
    ):
        self.task_repo = task_repo
        self.event_repo = event_repo
        self.max_active_tasks = max_active_tasks
        self._lock = asyncio.Lock()
        self._cancellation_tokens: Dict[str, asyncio.Event] = {}
        self._active_async_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

    def get_cancellation_token(self, task_id: str) -> asyncio.Event:
        if task_id not in self._cancellation_tokens:
            self._cancellation_tokens[task_id] = asyncio.Event()
        return self._cancellation_tokens[task_id]

    def request_cancel(self, task_id: str) -> bool:
        """Solicita la cancelación inmediata de una tarea en <1s."""
        token = self._cancellation_tokens.get(task_id)
        if token:
            token.set()
        async_t = self._active_async_tasks.get(task_id)
        if async_t and not async_t.done():
            async_t.cancel()
        # Si la tarea está en cola (queued), se cancela directamente
        asyncio.create_task(self._cancel_queued_task(task_id))
        return True

    async def _cancel_queued_task(self, task_id: str):
        async with self._lock:
            task = await self.task_repo.get_task(task_id)
            if task and task.state == TaskState.QUEUED:
                await self.task_repo.update_task_state(task_id, TaskState.CANCELLED)

    def register_active_execution(self, task_id: str, async_task: asyncio.Task) -> None:
        self._active_async_tasks[task_id] = async_task

    def unregister_active_execution(self, task_id: str) -> None:
        self._active_async_tasks.pop(task_id, None)
        self._cancellation_tokens.pop(task_id, None)

    async def is_slot_available(self) -> bool:
        async with self._lock:
            active = await self.task_repo.get_active_task()
            return active is None
