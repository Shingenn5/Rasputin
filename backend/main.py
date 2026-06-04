import asyncio
import json
import os
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from .agent import AgentHub
from .memory import load_memory, remember
from .response import AppError, error_handler, fail, http_error_handler, ok
from . import auth
from . import approvals
from . import model_registry
from . import rag
from . import graphify
from . import workspace
from . import security
from . import audit
from . import output
from . import preferences
from . import memory as memory_store
from . import schedules
from . import skill_store
from . import telegram

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"

app = FastAPI(title="Rasputin", version="0.2.0")
hub = AgentHub()

app.add_exception_handler(Exception, error_handler)
app.add_exception_handler(HTTPException, http_error_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


def _known_exception(exc):
    if isinstance(exc, (AppError, PermissionError, ValueError, HTTPException)):
        return exc
    children = getattr(exc, "exceptions", None)
    if children:
        for child in children:
            found = _known_exception(child)
            if found:
                return found
    return exc


def _error_response(exc):
    exc = _known_exception(exc)
    if isinstance(exc, AppError):
        return fail(exc.code, exc.message, exc.status)
    if isinstance(exc, HTTPException):
        code = "auth_required" if exc.status_code == 401 else "http_error"
        return fail(code, exc.detail, exc.status_code)
    if isinstance(exc, PermissionError):
        return fail("permission_denied", exc, 403)
    if isinstance(exc, ValueError):
        return fail("bad_request", exc, 400)
    return fail("internal_error", "server error", 500)


def _security_headers(response, request_id):
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.on_event("startup")
async def startup():
    auth.bootstrap()
    memory_store.init_memory()
    skill_store.init_skills()
    telegram.start_polling()
    try:
        model_registry.auto_repair_obvious()
    except Exception as exc:
        audit.log("model_auto_repair_startup_failed", {"error": str(exc)})


@app.middleware("http")
async def production_headers(request: Request, call_next):
    request_id = str(uuid.uuid4())[:12]
    timeout = float(os.environ.get("RASPUTIN_REQUEST_TIMEOUT", "90"))
    try:
        if request.url.path == "/api/events":
            response = await call_next(request)
        else:
            response = await asyncio.wait_for(call_next(request), timeout=timeout)
    except asyncio.TimeoutError:
        return _security_headers(fail("request_timeout", "request timed out", 504), request_id)
    except Exception as exc:
        return _security_headers(_error_response(exc), request_id)
    return _security_headers(response, request_id)


def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def current_user(request: Request):
    host = request.client.host if request.client else ""
    token = request.cookies.get(auth.COOKIE_NAME)
    try:
        return auth.require_user(token, host)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


class LoginIn(CamelModel):
    username: str = "admin"
    password: str


class PasswordChangeIn(CamelModel):
    current_password: str
    new_password: str


class TaskIn(CamelModel):
    objective: str
    model: str = "dry-run"
    skill: str = "general"
    mode: str = "chat"
    subagents: int = 0
    workspace_path: str | None = None


class MemoryIn(CamelModel):
    kind: str = "fact"
    value: object


class MemorySearchIn(CamelModel):
    query: str
    limit: int = 10


class MemoryReviewIn(CamelModel):
    id: str
    action: str = "approve"


class RagIn(CamelModel):
    path: str = "."
    label: str | None = None


class RagSearchIn(CamelModel):
    query: str
    limit: int = 6
    path: str | None = None


class WorkspaceIn(CamelModel):
    path: str = "."
    name: str | None = None
    read_only: bool = True


class WorkspaceRemoveIn(CamelModel):
    workspace_id: str


class WorkspaceBrowseIn(CamelModel):
    root_id: str | None = None
    path: str | None = None


class WorkspaceApproveIn(CamelModel):
    path: str
    name: str | None = None
    read_only: bool = True


class WorkspaceMountIn(CamelModel):
    host_path: str
    name: str | None = None
    read_only: bool = True


class GraphSearchIn(CamelModel):
    query: str
    limit: int = 12


class GraphBuildIn(CamelModel):
    path: str | None = None


class ModelIn(CamelModel):
    key: str | None = None
    name: str | None = None
    provider: str = "openai-compatible"
    role: str = "helper"
    base_url: str = ""
    model: str = ""
    enabled: bool = True
    managed: bool = False
    notes: str | None = None


class GgufImportIn(CamelModel):
    path: str
    key: str | None = None
    name: str | None = None
    role: str = "helper"
    port: int | None = None
    context: int = 4096
    n_gpu_layers: int = 0
    image: str | None = None
    notes: str | None = None


class GgufScanIn(CamelModel):
    root: str | None = None


class ModelKeyIn(CamelModel):
    key: str


class ModelLogsIn(CamelModel):
    key: str
    limit: int = 120


class ExportTaskIn(CamelModel):
    task_id: str
    folder: str | None = None


class SkillImportIn(CamelModel):
    name: str
    content: str
    metadata: dict | None = None


class SkillFromSessionIn(CamelModel):
    session_id: str
    name: str | None = None
    save: bool = False


class TelegramConfigIn(CamelModel):
    bot_token: str | None = None
    allowed_chat_id: str | None = None
    enabled: bool = True
    redaction_mode: str = "summary"


class ScheduleIn(CamelModel):
    name: str
    prompt: str
    interval_seconds: int = 0
    enabled: bool = False


@app.get("/")
async def index():
    return FileResponse(FRONTEND / "index.html")


@app.get("/api/health")
async def health():
    return ok({
        "name": "Rasputin",
        "status": "ready",
        "privacy": security.offline_status(),
    })


@app.get("/api/ui/bootstrap")
async def ui_bootstrap(_user=Depends(current_user)):
    return ok({
        "models": model_registry.all_models(),
        "skills": skill_store.enabled_names(),
        "tasks": hub.all_tasks(),
        "memory": load_memory(),
        "memory_review": memory_store.pending_review(),
        "rag_stats": rag.stats(),
        "workspace": workspace.get_active(),
        "graph_stats": graphify.stats(),
        "security": security.load(),
        "audit": {"events": audit.recent(100)},
        "output": output.get_config(),
        "preferences": preferences.load(),
        "sessions": hub.sessions(),
        "approvals": approvals.list_approvals(),
        "skill_registry": skill_store.list_skills(),
        "telegram": telegram.public_config(),
        "schedules": schedules.list_schedules(),
    })


@app.get("/api/auth/session")
async def auth_session(request: Request):
    host = request.client.host if request.client else ""
    token = request.cookies.get(auth.COOKIE_NAME)
    return ok(auth.public_session(token, host))


@app.post("/api/auth/login")
async def auth_login(req: LoginIn, response: Response, request: Request):
    host = request.client.host if request.client else "local"
    token, info = auth.login(req.username, req.password, host)
    response.set_cookie(
        auth.COOKIE_NAME,
        token,
        httponly=True,
        secure=auth.cookie_secure(),
        samesite="strict",
        max_age=60 * 60 * 12,
        path="/",
    )
    return ok(info)


@app.post("/api/auth/logout")
async def auth_logout(response: Response, request: Request):
    token = request.cookies.get(auth.COOKIE_NAME)
    out = auth.logout(token)
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return ok(out)


@app.post("/api/auth/change-password")
async def auth_change_password(req: PasswordChangeIn, request: Request, user=Depends(current_user)):
    username = user.get("username")
    if username == "localhost":
        username = auth.load_public().get("username", "admin")
    return ok(auth.change_password(username, req.current_password, req.new_password))


@app.get("/api/models")
async def models(_user=Depends(current_user)):
    return ok(model_registry.enabled_models())


@app.get("/api/model-registry")
async def model_registry_list(_user=Depends(current_user)):
    return ok({"models": model_registry.all_models()})


@app.post("/api/model-registry/upsert")
async def model_registry_upsert(req: ModelIn, _user=Depends(current_user)):
    return ok(model_registry.upsert(req.model_dump()))


@app.post("/api/model-registry/import-gguf")
async def model_registry_import_gguf(req: GgufImportIn, _user=Depends(current_user)):
    return ok(model_registry.import_gguf(req.model_dump()))


@app.post("/api/model-registry/scan-gguf")
async def model_registry_scan_gguf(req: GgufScanIn | None = None, _user=Depends(current_user)):
    return ok(model_registry.scan_gguf(req.root if req else None))


@app.post("/api/model-registry/start")
async def model_registry_start(req: ModelKeyIn, _user=Depends(current_user)):
    return ok(model_registry.start_model(req.key))


@app.post("/api/model-registry/stop")
async def model_registry_stop(req: ModelKeyIn, _user=Depends(current_user)):
    return ok(model_registry.stop_model(req.key))


@app.post("/api/model-registry/test")
async def model_registry_test(req: ModelKeyIn, _user=Depends(current_user)):
    return ok(model_registry.test_model(req.key))


@app.post("/api/model-registry/discover")
async def model_registry_discover(req: ModelKeyIn, _user=Depends(current_user)):
    return ok(model_registry.discover_model(req.key))


@app.post("/api/model-registry/repair")
async def model_registry_repair(req: ModelKeyIn, _user=Depends(current_user)):
    return ok(model_registry.repair_model(req.key))


@app.post("/api/model-registry/logs")
async def model_registry_logs(req: ModelLogsIn, _user=Depends(current_user)):
    return ok(model_registry.logs_model(req.key, req.limit))


@app.get("/api/security")
async def security_get(_user=Depends(current_user)):
    return ok(security.load())


@app.post("/api/security")
async def security_post(req: dict, _user=Depends(current_user)):
    return ok(security.save(req))


@app.get("/api/preferences")
async def preferences_get(_user=Depends(current_user)):
    return ok(preferences.load())


@app.post("/api/preferences")
async def preferences_post(req: dict, _user=Depends(current_user)):
    return ok(preferences.save(req))


@app.get("/api/audit")
async def audit_get(limit: int = 100, _user=Depends(current_user)):
    return ok({"events": audit.recent(limit)})


@app.get("/api/skills")
async def skills(_user=Depends(current_user)):
    return ok(skill_store.list_skills())


@app.post("/api/skills/create-from-session")
async def skills_create_from_session(req: SkillFromSessionIn, _user=Depends(current_user)):
    return ok(skill_store.create_from_session(req.session_id, req.name, req.save))


@app.post("/api/skills/import")
async def skills_import(req: SkillImportIn, _user=Depends(current_user)):
    return ok(skill_store.import_skill(req.name, req.content, req.metadata or {}))


@app.get("/api/skills/{name}")
async def skills_get(name: str, _user=Depends(current_user)):
    return ok(skill_store.get_skill(name))


@app.post("/api/skills/{name}/enable")
async def skills_enable(name: str, _user=Depends(current_user)):
    return ok(skill_store.set_enabled(name, True))


@app.post("/api/skills/{name}/disable")
async def skills_disable(name: str, _user=Depends(current_user)):
    return ok(skill_store.set_enabled(name, False))


@app.get("/api/sessions")
async def sessions_get(limit: int = 100, _user=Depends(current_user)):
    return ok(hub.sessions(limit))


@app.get("/api/sessions/{session_id}")
async def session_get(session_id: str, _user=Depends(current_user)):
    return ok(hub.session(session_id))


@app.get("/api/approvals")
async def approvals_get(status: str | None = None, limit: int = 100, _user=Depends(current_user)):
    return ok(approvals.list_approvals(status, limit))


@app.post("/api/approvals/{approval_id}/approve")
async def approvals_approve(approval_id: str, _user=Depends(current_user)):
    return ok(approvals.approve(approval_id))


@app.post("/api/approvals/{approval_id}/deny")
async def approvals_deny(approval_id: str, _user=Depends(current_user)):
    return ok(approvals.deny(approval_id))


@app.post("/api/approvals/{approval_id}/expire")
async def approvals_expire(approval_id: str, _user=Depends(current_user)):
    return ok(approvals.expire(approval_id))


@app.post("/api/tasks")
async def create_task(req: TaskIn, _user=Depends(current_user)):
    task = hub.start(req.objective, req.model, req.skill, max(0, min(req.subagents, 4)), req.workspace_path, req.mode)
    return ok(hub.snapshot_task(task))


@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, _user=Depends(current_user)):
    return ok(await hub.cancel(task_id))


@app.post("/api/tasks/{task_id}/pause")
async def pause_task(task_id: str, _user=Depends(current_user)):
    return ok(await hub.pause(task_id))


@app.post("/api/tasks/{task_id}/resume")
async def resume_task(task_id: str, _user=Depends(current_user)):
    return ok(await hub.resume(task_id))


@app.get("/api/tasks")
async def tasks(_user=Depends(current_user)):
    return ok(hub.all_tasks())


@app.get("/api/tasks/{task_id}")
async def task_detail(task_id: str, _user=Depends(current_user)):
    detail = hub.task_detail(task_id)
    if not detail:
        raise AppError("task_not_found", "Task was not found.", 404)
    return ok(detail)


@app.get("/api/memory")
async def memory(_user=Depends(current_user)):
    return ok(load_memory())


@app.post("/api/memory")
async def add_memory(req: MemoryIn, _user=Depends(current_user)):
    return ok(remember(req.kind, req.value))


@app.get("/api/memory/review")
async def memory_review(_user=Depends(current_user)):
    return ok(memory_store.pending_review())


@app.post("/api/memory/review")
async def memory_review_decide(req: MemoryReviewIn, _user=Depends(current_user)):
    if req.action == "approve":
        return ok(memory_store.approve_item(req.id))
    if req.action in {"deny", "reject"}:
        return ok(memory_store.reject_item(req.id))
    raise ValueError("memory review action must be approve or reject")


@app.post("/api/memory/search")
async def memory_search(req: MemorySearchIn, _user=Depends(current_user)):
    return ok(memory_store.search(req.query, req.limit))


@app.get("/api/integrations/telegram")
async def telegram_get(_user=Depends(current_user)):
    return ok(telegram.public_config())


@app.post("/api/integrations/telegram/configure")
async def telegram_configure(req: TelegramConfigIn, _user=Depends(current_user)):
    return ok(telegram.configure(req.bot_token, req.allowed_chat_id, req.enabled, req.redaction_mode))


@app.post("/api/integrations/telegram/test")
async def telegram_test(_user=Depends(current_user)):
    return ok(telegram.test_message())


@app.post("/api/integrations/telegram/disable")
async def telegram_disable(_user=Depends(current_user)):
    return ok(telegram.disable())


@app.get("/api/schedules")
async def schedules_get(_user=Depends(current_user)):
    return ok(schedules.list_schedules())


@app.post("/api/schedules")
async def schedules_create(req: ScheduleIn, _user=Depends(current_user)):
    return ok(schedules.create(req.name, req.prompt, req.interval_seconds, req.enabled))


@app.get("/api/rag/stats")
async def rag_stats(_user=Depends(current_user)):
    return ok(rag.stats())


@app.post("/api/rag/ingest")
async def rag_ingest(req: RagIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(rag.ingest(req.path, req.label))


@app.post("/api/rag/search")
async def rag_search(req: RagSearchIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(rag.search(req.query, req.limit, req.path))


@app.get("/api/workspace")
async def workspace_get(_user=Depends(current_user)):
    return ok(workspace.get_active())


@app.get("/api/workspaces")
async def workspaces_get(_user=Depends(current_user)):
    return ok(workspace.all_workspaces())


@app.get("/api/workspace/roots")
async def workspace_roots(_user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(workspace.approved_roots())


@app.post("/api/workspace/browse")
async def workspace_browse(req: WorkspaceBrowseIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(workspace.browse(req.root_id, req.path))


@app.post("/api/workspace/approve")
async def workspace_approve(req: WorkspaceApproveIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    item = workspace.approve(req.path, req.name, req.read_only)
    audit.log("workspace_approved", {"path": req.path, "name": req.name, "read_only": req.read_only})
    return ok(item)


@app.post("/api/workspace/mount-plan")
async def workspace_mount_plan(req: WorkspaceMountIn, _user=Depends(current_user)):
    return ok(workspace.mount_plan(req.host_path, req.name, req.read_only))


@app.post("/api/workspace/mount-apply")
async def workspace_mount_apply(req: WorkspaceMountIn, _user=Depends(current_user)):
    security.require("allow_docker_control")
    plan = workspace.save_mount_request(req.host_path, req.name, req.read_only)
    audit.log("workspace_mount_requested", plan)
    return ok(plan)


@app.post("/api/workspace/add")
async def workspace_add(req: WorkspaceIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    profile = {"read": True, "write": not bool(req.read_only), "reorganize": False}
    return ok(workspace.add(req.path, req.name, profile))


@app.post("/api/workspace/remove")
async def workspace_remove(req: WorkspaceRemoveIn, _user=Depends(current_user)):
    return ok(workspace.remove(req.workspace_id))


@app.post("/api/workspace/select")
async def workspace_select(req: WorkspaceIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(workspace.select(req.path))


@app.post("/api/workspace/list")
async def workspace_list(req: WorkspaceIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(workspace.list_dirs(req.path))


@app.get("/api/graph/stats")
async def graph_stats(_user=Depends(current_user)):
    return ok(graphify.stats())


@app.post("/api/graph/build")
async def graph_build(req: GraphBuildIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(graphify.build(req.path))


@app.post("/api/graph/search")
async def graph_search(req: GraphSearchIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(graphify.search(req.query, req.limit))


@app.get("/api/output")
async def output_get(_user=Depends(current_user)):
    return ok(output.get_config())


@app.post("/api/output")
async def output_post(req: dict, _user=Depends(current_user)):
    security.require("allow_file_write")
    return ok(output.save_config(req))


@app.post("/api/output/export-task")
async def output_export_task(req: ExportTaskIn, _user=Depends(current_user)):
    security.require("allow_file_write")
    task = hub.get_task(req.task_id)
    return ok(output.export_markdown(task, req.folder))


@app.get("/api/events")
async def events(request: Request, _user=Depends(current_user)):
    q = await hub.subscribe()

    async def gen():
        yield f"data: {json.dumps({'hello': True, 'tasks': hub.all_tasks(), 'approvals': approvals.list_approvals('pending'), 'memoryReview': memory_store.pending_review(), 'telegram': telegram.public_config()})}\n\n"
        while True:
            if await request.is_disconnected():
                break
            item = await q.get()
            yield f"data: {json.dumps({'task': item})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
