import asyncio
import json
import os
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agent import AgentHub
from .memory import load_memory, remember
from .response import error_handler, http_error_handler, ok
from . import auth
from . import model_registry
from . import rag
from . import graphify
from . import workspace
from . import security
from . import audit
from . import output

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


@app.on_event("startup")
async def startup():
    auth.bootstrap()


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
        from .response import fail
        return fail("request_timeout", "request timed out", 504)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    return response


def current_user(request: Request):
    host = request.client.host if request.client else ""
    token = request.cookies.get(auth.COOKIE_NAME)
    try:
        return auth.require_user(token, host)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


class LoginIn(BaseModel):
    username: str = "admin"
    password: str


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str


class TaskIn(BaseModel):
    objective: str
    model: str = "dry-run"
    skill: str = "general"
    mode: str = "chat"
    subagents: int = 0
    workspace_path: str | None = None


class MemoryIn(BaseModel):
    kind: str = "fact"
    value: object


class RagIn(BaseModel):
    path: str = "."
    label: str | None = None


class RagSearchIn(BaseModel):
    query: str
    limit: int = 6
    path: str | None = None


class WorkspaceIn(BaseModel):
    path: str = "."
    name: str | None = None


class WorkspaceRemoveIn(BaseModel):
    workspace_id: str


class GraphSearchIn(BaseModel):
    query: str
    limit: int = 12


class GraphBuildIn(BaseModel):
    path: str | None = None


class ModelIn(BaseModel):
    key: str | None = None
    name: str | None = None
    provider: str = "openai-compatible"
    role: str = "helper"
    base_url: str = ""
    model: str = ""
    enabled: bool = True
    managed: bool = False
    notes: str | None = None


class GgufImportIn(BaseModel):
    path: str
    key: str | None = None
    name: str | None = None
    role: str = "helper"
    port: int | None = None
    context: int = 4096
    n_gpu_layers: int = 0
    image: str | None = None
    notes: str | None = None


class ModelKeyIn(BaseModel):
    key: str


class ModelLogsIn(BaseModel):
    key: str
    limit: int = 120


class ExportTaskIn(BaseModel):
    task_id: str
    folder: str | None = None


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


@app.post("/api/model-registry/start")
async def model_registry_start(req: ModelKeyIn, _user=Depends(current_user)):
    return ok(model_registry.start_model(req.key))


@app.post("/api/model-registry/stop")
async def model_registry_stop(req: ModelKeyIn, _user=Depends(current_user)):
    return ok(model_registry.stop_model(req.key))


@app.post("/api/model-registry/test")
async def model_registry_test(req: ModelKeyIn, _user=Depends(current_user)):
    return ok(model_registry.test_model(req.key))


@app.post("/api/model-registry/logs")
async def model_registry_logs(req: ModelLogsIn, _user=Depends(current_user)):
    return ok(model_registry.logs_model(req.key, req.limit))


@app.get("/api/security")
async def security_get(_user=Depends(current_user)):
    return ok(security.load())


@app.post("/api/security")
async def security_post(req: dict, _user=Depends(current_user)):
    return ok(security.save(req))


@app.get("/api/audit")
async def audit_get(limit: int = 100, _user=Depends(current_user)):
    return ok({"events": audit.recent(limit)})


@app.get("/api/skills")
async def skills(_user=Depends(current_user)):
    return ok(["general", "folder_organizer", "web_research", "paper_writer", "excel_data_entry"])


@app.post("/api/tasks")
async def create_task(req: TaskIn, _user=Depends(current_user)):
    task = hub.start(req.objective, req.model, req.skill, max(0, min(req.subagents, 4)), req.workspace_path, req.mode)
    return ok(hub.snapshot_task(task))


@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, _user=Depends(current_user)):
    return ok(await hub.cancel(task_id))


@app.get("/api/tasks")
async def tasks(_user=Depends(current_user)):
    return ok(hub.all_tasks())


@app.get("/api/memory")
async def memory(_user=Depends(current_user)):
    return ok(load_memory())


@app.post("/api/memory")
async def add_memory(req: MemoryIn, _user=Depends(current_user)):
    return ok(remember(req.kind, req.value))


@app.get("/api/rag/stats")
async def rag_stats(_user=Depends(current_user)):
    return ok(rag.stats())


@app.post("/api/rag/ingest")
async def rag_ingest(req: RagIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(rag.ingest(req.path, req.label))


@app.post("/api/rag/search")
async def rag_search(req: RagSearchIn, _user=Depends(current_user)):
    return ok(rag.search(req.query, req.limit, req.path))


@app.get("/api/workspace")
async def workspace_get(_user=Depends(current_user)):
    return ok(workspace.get_active())


@app.get("/api/workspaces")
async def workspaces_get(_user=Depends(current_user)):
    return ok(workspace.all_workspaces())


@app.post("/api/workspace/add")
async def workspace_add(req: WorkspaceIn, _user=Depends(current_user)):
    return ok(workspace.add(req.path, req.name))


@app.post("/api/workspace/remove")
async def workspace_remove(req: WorkspaceRemoveIn, _user=Depends(current_user)):
    return ok(workspace.remove(req.workspace_id))


@app.post("/api/workspace/select")
async def workspace_select(req: WorkspaceIn, _user=Depends(current_user)):
    return ok(workspace.select(req.path))


@app.post("/api/workspace/list")
async def workspace_list(req: WorkspaceIn, _user=Depends(current_user)):
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
    return ok(graphify.search(req.query, req.limit))


@app.get("/api/output")
async def output_get(_user=Depends(current_user)):
    return ok(output.get_config())


@app.post("/api/output")
async def output_post(req: dict, _user=Depends(current_user)):
    return ok(output.save_config(req))


@app.post("/api/output/export-task")
async def output_export_task(req: ExportTaskIn, _user=Depends(current_user)):
    task = hub.get_task(req.task_id)
    return ok(output.export_markdown(task, req.folder))


@app.get("/api/events")
async def events(request: Request, _user=Depends(current_user)):
    q = await hub.subscribe()

    async def gen():
        yield f"data: {json.dumps({'hello': True, 'tasks': hub.all_tasks()})}\n\n"
        while True:
            if await request.is_disconnected():
                break
            item = await q.get()
            yield f"data: {json.dumps({'task': item})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
