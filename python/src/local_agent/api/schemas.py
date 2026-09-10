"""
api/schemas.py: Esquemas de solicitud y respuesta para la API /v1 de LocalDesk.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from local_agent.domain.models import Task, Action, Artifact, TaskScope


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    os_platform: str
    inference_available: bool
    model_id: Optional[str]
    desktop_adapter: str
    active_tasks_count: int


class ModelItem(BaseModel):
    name: str
    supports_tools: bool
    supports_vision: bool
    context_length: int
    quantization: Optional[str] = None
    tested: bool = False
    is_simulation: bool = False


class ModelsResponse(BaseModel):
    models: List[ModelItem]


class CreateTaskRequest(BaseModel):
    instruction: str
    scope_id: str
    input_refs: List[str] = Field(default_factory=list)
    output_name: Optional[str] = None


class CreateTaskResponse(BaseModel):
    task_id: str
    state: str
    instruction: str
    scope_id: str
    created_at: str


class TaskDetailResponse(BaseModel):
    task: Task
    actions: List[Action] = Field(default_factory=list)
    artifacts: List[Artifact] = Field(default_factory=list)


class ApprovalResolutionRequest(BaseModel):
    approved: bool


class UserInputRequest(BaseModel):
    response: str


class CreateScopeRequest(BaseModel):
    name: str
    read_roots: List[str] = Field(default_factory=list)
    write_roots: List[str] = Field(default_factory=list)
    allowed_apps: List[str] = Field(default_factory=list)
    allowed_domains: List[str] = Field(default_factory=list)


class PreferenceRequest(BaseModel):
    key: str
    value: Any
