"""
models.py: Modelos de dominio Pydantic para LocalDesk.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid

from .states import TaskState, ActionState, EventType


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str = "") -> str:
    unique = uuid.uuid4().hex[:12]
    return f"{prefix}_{unique}" if prefix else unique


class TaskScope(BaseModel):
    scope_id: str = Field(default_factory=lambda: new_id("scope"))
    name: str = "default_scope"
    read_roots: list[str] = Field(default_factory=list)
    write_roots: list[str] = Field(default_factory=list)
    allowed_apps: list[str] = Field(default_factory=list)
    allowed_domains: list[str] = Field(default_factory=list)
    version: int = 1
    created_at: str = Field(default_factory=now_utc_iso)


class TaskProposal(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    brief_reason: str
    expected_result: str


class Action(BaseModel):
    action_id: str = Field(default_factory=lambda: new_id("act"))
    task_id: str
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    canonical_arguments: dict[str, Any] = Field(default_factory=dict)
    brief_reason: str
    expected_result: str
    state: ActionState = ActionState.PROPOSED
    scope_version: int = 1
    observation_id: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str = Field(default_factory=now_utc_iso)
    executed_at: Optional[str] = None


class Approval(BaseModel):
    approval_id: str = Field(default_factory=lambda: new_id("appr"))
    task_id: str
    action_id: str
    action_summary: str
    canonical_arguments: dict[str, Any]
    scope_version: int = 1
    status: str = "pending"  # pending, approved, rejected, expired
    created_at: str = Field(default_factory=now_utc_iso)
    resolved_at: Optional[str] = None
    expires_at: Optional[str] = None


class Artifact(BaseModel):
    artifact_id: str = Field(default_factory=lambda: new_id("art"))
    task_id: str
    file_path: str
    file_name: str
    size_bytes: int
    sha256: str
    created_at: str = Field(default_factory=now_utc_iso)


class TaskEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: new_id("evt"))
    task_id: str
    sequence: int
    event_type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_utc_iso)


class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: new_id("task"))
    instruction: str
    state: TaskState = TaskState.QUEUED
    scope_id: str
    input_refs: list[str] = Field(default_factory=list)
    output_name: Optional[str] = None
    idempotency_key: Optional[str] = None
    plan_explanation: Optional[str] = None
    error_message: Optional[str] = None
    steps_count: int = 0
    active_duration_seconds: float = 0.0
    created_at: str = Field(default_factory=now_utc_iso)
    updated_at: str = Field(default_factory=now_utc_iso)
    completed_at: Optional[str] = None


class UserPreference(BaseModel):
    key: str
    value: Any
    updated_at: str = Field(default_factory=now_utc_iso)
