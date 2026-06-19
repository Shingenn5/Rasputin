from fastapi import APIRouter, Depends
from backend.core.response import ok, AppError
from backend.api.common import CamelModel, current_user, hub
from backend.core import schedules as schedules

router = APIRouter(prefix="/api", tags=["tasks", "schedules"])

class TaskIn(CamelModel):
    objective: str
    model: str = "dry-run"
    skill: str = "general"
    mode: str = "chat"
    subagents: int = 0
    workspace_path: str | None = None
    session_id: str | None = None

class ScheduleIn(CamelModel):
    name: str
    prompt: str
    interval_seconds: int = 0
    enabled: bool = False

@router.post("/tasks")
async def create_task(req: TaskIn, _user=Depends(current_user)):
    task = hub.start(req.objective, req.model, req.skill, max(0, min(req.subagents, 4)), req.workspace_path, req.mode, req.session_id)
    return ok(hub.snapshot_task(task))

@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, _user=Depends(current_user)):
    return ok(await hub.cancel(task_id))

@router.post("/tasks/{task_id}/pause")
async def pause_task(task_id: str, _user=Depends(current_user)):
    return ok(await hub.pause(task_id))

@router.post("/tasks/{task_id}/resume")
async def resume_task(task_id: str, _user=Depends(current_user)):
    return ok(await hub.resume(task_id))

@router.get("/tasks")
async def tasks(limit: int = 100, details: bool = False, _user=Depends(current_user)):
    return ok(hub.all_tasks(limit=limit, include_details=details))

@router.get("/tasks/{task_id}")
async def task_detail(task_id: str, _user=Depends(current_user)):
    detail = hub.task_detail(task_id)
    if not detail:
        raise AppError("task_not_found", "Task was not found.", 404)
    return ok(detail)

@router.get("/schedules")
async def schedules_get(_user=Depends(current_user)):
    return ok(schedules.list_schedules())

@router.post("/schedules")
async def schedules_create(req: ScheduleIn, _user=Depends(current_user)):
    return ok(schedules.create(req.name, req.prompt, req.interval_seconds, req.enabled))
