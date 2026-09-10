"""
api/routes.py: Rutas FastAPI versionadas bajo /v1 para LocalDesk.
"""

import asyncio
import json
import platform
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from local_agent.domain.models import Task, TaskScope, new_id, now_utc_iso
from local_agent.domain.states import TaskState
from local_agent.core.engine import AgentCore
from .auth import verify_bearer_token
from .schemas import (
    HealthResponse,
    ModelsResponse,
    ModelItem,
    CreateTaskRequest,
    CreateTaskResponse,
    TaskDetailResponse,
    ApprovalResolutionRequest,
    CreateScopeRequest,
    PreferenceRequest,
)

router = APIRouter(prefix="/v1")


def get_core(request: Request) -> AgentCore:
    return request.app.state.core


@router.get("/health", response_model=HealthResponse)
async def health(
    core: AgentCore = Depends(get_core),
    _: str = Depends(verify_bearer_token),
):
    inference_ok = await core.model_provider.health()
    active = await core.task_repo.get_active_task()
    return HealthResponse(
        status="ok",
        version="0.1.0",
        os_platform=platform.system(),
        inference_available=inference_ok,
        model_id=core.config.inference.model_id,
        desktop_adapter=core.config.execution.desktop_adapter,
        active_tasks_count=1 if active else 0,
    )


@router.get("/models", response_model=ModelsResponse)
async def list_models(
    core: AgentCore = Depends(get_core),
    _: str = Depends(verify_bearer_token),
):
    model_names = await core.model_provider.list_models()
    items: List[ModelItem] = []
    for m in model_names:
        caps = await core.model_provider.get_capabilities(m)
        items.append(
            ModelItem(
                name=m,
                supports_tools=caps.supports_tools,
                supports_vision=caps.supports_vision,
                context_length=caps.context_length,
                quantization=caps.quantization,
                tested=caps.tested_locally,
                is_simulation=caps.is_simulation,
            )
        )
    return ModelsResponse(models=items)


@router.post("/tasks", response_model=CreateTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    req: CreateTaskRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    core: AgentCore = Depends(get_core),
    _: str = Depends(verify_bearer_token),
):
    # Validar scope existente
    scope = await core.scope_repo.get_scope(req.scope_id)
    if not scope:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El scope_id '{req.scope_id}' no existe.",
        )

    task = Task(
        instruction=req.instruction,
        scope_id=req.scope_id,
        input_refs=req.input_refs,
        output_name=req.output_name,
        idempotency_key=idempotency_key,
    )

    created = await core.task_repo.create_task(task)

    # Si hay slot disponible y es nueva, disparar en background
    if created.state == TaskState.QUEUED:
        slot_free = await core.queue_manager.is_slot_available()
        if slot_free:
            async_t = asyncio.create_task(core.execute_task(created.task_id))
            core.queue_manager.register_active_execution(created.task_id, async_t)

    return CreateTaskResponse(
        task_id=created.task_id,
        state=created.state.value,
        instruction=created.instruction,
        scope_id=created.scope_id,
        created_at=created.created_at,
    )


@router.get("/tasks")
async def list_tasks(
    limit: int = 50,
    offset: int = 0,
    core: AgentCore = Depends(get_core),
    _: str = Depends(verify_bearer_token),
):
    return await core.task_repo.list_tasks(limit=limit, offset=offset)


@router.get("/tasks/{task_id}", response_model=TaskDetailResponse)
async def get_task(
    task_id: str,
    core: AgentCore = Depends(get_core),
    _: str = Depends(verify_bearer_token),
):
    task = await core.task_repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada.")
    actions = await core.action_repo.get_actions_for_task(task_id)
    artifacts = await core.artifact_repo.get_artifacts_for_task(task_id)
    return TaskDetailResponse(task=task, actions=actions, artifacts=artifacts)


@router.get("/tasks/{task_id}/events")
async def stream_task_events(
    task_id: str,
    after_seq: int = 0,
    core: AgentCore = Depends(get_core),
    token: Optional[str] = None,
):
    """
    Stream SSE de eventos ordenados.
    Admite token en query param 'token' para facilitar EventSource en navegadores.
    """
    from .auth import get_current_session_token
    if token and token != get_current_session_token():
        raise HTTPException(status_code=403, detail="Token SSE no válido.")

    task = await core.task_repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada.")

    async def event_generator():
        last_seq = after_seq
        while True:
            events = await core.event_repo.get_events(task_id, after_seq=last_seq)
            for ev in events:
                last_seq = ev.sequence
                data = {
                    "event_id": ev.event_id,
                    "task_id": ev.task_id,
                    "sequence": ev.sequence,
                    "event_type": ev.event_type.value,
                    "payload": ev.payload,
                    "created_at": ev.created_at,
                }
                yield f"event: {ev.event_type.value}\ndata: {json.dumps(data)}\n\n"

            # Si la tarea concluyó en un estado terminal, cerramos el stream
            current_task = await core.task_repo.get_task(task_id)
            if current_task and current_task.state.is_terminal:
                # Enviar último lote de eventos si los hubiera antes de salir
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/tasks/{task_id}/pause")
async def pause_task(
    task_id: str,
    core: AgentCore = Depends(get_core),
    _: str = Depends(verify_bearer_token),
):
    ok = core.pause_task(task_id)
    if not ok:
        raise HTTPException(status_code=400, detail="No se pudo pausar la tarea (puede que no esté activa).")
    return {"status": "paused", "task_id": task_id}


@router.post("/tasks/{task_id}/resume")
async def resume_task(
    task_id: str,
    core: AgentCore = Depends(get_core),
    _: str = Depends(verify_bearer_token),
):
    ok = core.resume_task(task_id)
    if not ok:
        raise HTTPException(status_code=400, detail="No se pudo reanudar la tarea.")
    return {"status": "resumed", "task_id": task_id}


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    core: AgentCore = Depends(get_core),
    _: str = Depends(verify_bearer_token),
):
    core.queue_manager.request_cancel(task_id)
    return {"status": "cancelling", "task_id": task_id}


@router.post("/tasks/{task_id}/approvals/{approval_id}")
async def resolve_approval(
    task_id: str,
    approval_id: str,
    req: ApprovalResolutionRequest,
    core: AgentCore = Depends(get_core),
    _: str = Depends(verify_bearer_token),
):
    approval = await core.approval_repo.get_approval(approval_id)
    if not approval or approval.task_id != task_id:
        raise HTTPException(status_code=404, detail="Aprobación no encontrada.")
    if approval.status != "pending":
        raise HTTPException(status_code=400, detail=f"La aprobación ya fue resuelta como '{approval.status}'.")

    ok = await core.resolve_approval(approval_id, req.approved)
    return {"approval_id": approval_id, "resolved": ok, "approved": req.approved}


@router.get("/scopes")
async def list_scopes(
    core: AgentCore = Depends(get_core),
    _: str = Depends(verify_bearer_token),
):
    default_scope = await core.scope_repo.get_scope("default_scope")
    return [default_scope] if default_scope else []


@router.post("/scopes")
async def create_scope(
    req: CreateScopeRequest,
    core: AgentCore = Depends(get_core),
    _: str = Depends(verify_bearer_token),
):
    scope = TaskScope(
        name=req.name,
        read_roots=req.read_roots,
        write_roots=req.write_roots,
        allowed_apps=req.allowed_apps,
        allowed_domains=req.allowed_domains,
    )
    saved = await core.scope_repo.save_scope(scope)
    return saved


@router.get("/preferences")
async def get_preferences(
    core: AgentCore = Depends(get_core),
    _: str = Depends(verify_bearer_token),
):
    from local_agent.storage.repository import PreferenceRepository
    pref_repo = PreferenceRepository(core.task_repo.db)
    return await pref_repo.list_all()


@router.post("/preferences")
async def set_preference(
    req: PreferenceRequest,
    core: AgentCore = Depends(get_core),
    _: str = Depends(verify_bearer_token),
):
    from local_agent.storage.repository import PreferenceRepository
    pref_repo = PreferenceRepository(core.task_repo.db)
    await pref_repo.set(req.key, req.value)
    return {"key": req.key, "value": req.value, "status": "saved"}
