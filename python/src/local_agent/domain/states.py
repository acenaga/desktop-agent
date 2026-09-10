"""
states.py: Definición de estados de tarea, acciones y eventos.
"""

from enum import Enum


class TaskState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    AWAITING_INPUT = "awaiting_input"
    PAUSED = "paused"
    CANCELLING = "cancelling"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"

    @property
    def is_terminal(self) -> bool:
        return self in (
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELLED,
            TaskState.INTERRUPTED,
        )

    @property
    def is_active(self) -> bool:
        return self in (
            TaskState.RUNNING,
            TaskState.AWAITING_APPROVAL,
            TaskState.AWAITING_INPUT,
            TaskState.PAUSED,
            TaskState.CANCELLING,
        )


class ActionState(str, Enum):
    PROPOSED = "proposed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EventType(str, Enum):
    TASK_CREATED = "task_created"
    TASK_STATE_CHANGED = "task_state_changed"
    TASK_PLAN_EXPLAINED = "task_plan_explained"
    ACTION_PROPOSED = "action_proposed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RESOLVED = "approval_resolved"
    INPUT_REQUESTED = "input_requested"
    INPUT_RESOLVED = "input_resolved"
    ACTION_STARTED = "action_started"
    ACTION_COMPLETED = "action_completed"
    ACTION_FAILED = "action_failed"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_PAUSED = "task_paused"
    TASK_RESUMED = "task_resumed"
    TASK_CANCELLED = "task_cancelled"
    TASK_INTERRUPTED = "task_interrupted"
    LOG_MESSAGE = "log_message"
