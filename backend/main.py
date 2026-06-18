import asyncio
import json
import os
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from .agent import AgentHub
from .memory import load_memory, remember
from .response import AppError, error_handler, fail, http_error_handler, ok
from . import auth
from . import approvals
from . import model_registry
from . import model_catalog
from . import model_providers
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
from . import warsat
from . import tool_relay
from . import mcp_relay
from . import archive
from . import trials
from . import settings_api
from . import model_acquisition

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


def _ui_preview_enabled():
    return str(os.environ.get("RASPUTIN_UI_PREVIEW", "")).strip().lower() in {"1", "true", "yes", "on"}


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


def _setup_status():
    auth_state = auth.load_public()
    security_state = security.load()
    workspace_state = workspace.get_active()
    output_state = output.get_config()
    prefs = preferences.load()
    all_models = model_registry.all_models()
    active_key = prefs.get("selectedModel") or "main-vllm"
    active_model = next((item for item in all_models if item.get("key") == active_key), None)
    chat_models = [
        item for item in all_models
        if item.get("enabled", True) and item.get("role") != "embeddings" and item.get("provider") != "hash-vector"
    ]
    real_reachable = [
        item for item in chat_models
        if item.get("provider") != "mock" and item.get("runtime_status") == "reachable"
    ]
    dry_run_ready = any(item.get("key") == "dry-run" and item.get("runtime_status") == "reachable" for item in all_models)
    password_changed = False
    try:
        auth_data = auth.load()
        user = (auth_data.get("users") or [{}])[0]
        password_changed = bool(user.get("password_changed_at")) or bool(os.environ.get("RASPUTIN_ADMIN_PASSWORD"))
    except Exception:
        password_changed = False

    steps = [
        {
            "id": "admin",
            "title": "Secure local admin login",
            "status": "done" if password_changed else "attention",
            "detail": "Admin password has been changed." if password_changed else "Use the first-run password from container logs, then change it in Admin settings.",
            "action": "Open Admin settings",
        },
        {
            "id": "model",
            "title": "Connect a chat model",
            "status": "done" if real_reachable else "attention" if dry_run_ready else "blocked",
            "detail": f"{len(real_reachable)} real model endpoint(s) are reachable." if real_reachable else "Testing Mode is available; connect or test a local model in Models when ready.",
            "action": "Open Models",
        },
        {
            "id": "workspace",
            "title": "Choose an approved workspace",
            "status": "done" if workspace_state.get("active_path") else "attention",
            "detail": f"Active workspace: {workspace_state.get('active_name') or workspace_state.get('active_path') or 'Project Root'}.",
            "action": "Open Workspaces",
        },
        {
            "id": "privacy",
            "title": "Confirm local privacy defaults",
            "status": "done" if security_state.get("privacy_lock", True) and not security_state.get("allow_remote_models", False) else "attention",
            "detail": "Privacy lock is on and remote model endpoints are blocked." if security_state.get("privacy_lock", True) and not security_state.get("allow_remote_models", False) else "Review Safety before using remote model endpoints.",
            "action": "Open Safety",
        },
        {
            "id": "output",
            "title": "Check output folder",
            "status": "done" if output_state.get("markdown_folder") else "attention",
            "detail": f"Markdown exports target {output_state.get('markdown_folder') or 'workspace/markdown-output'}.",
            "action": "Open Output",
        },
    ]
    completed = sum(1 for item in steps if item["status"] == "done")
    return {
        "complete": completed == len(steps),
        "completed_steps": completed,
        "total_steps": len(steps),
        "auth": {
            "configured": bool(auth_state.get("configured")),
            "username": auth_state.get("username", "admin"),
            "password_changed": password_changed,
            "test_bypass": bool(auth_state.get("test_bypass")),
            "localhost_bypass": bool(auth_state.get("localhost_bypass")),
        },
        "model": {
            "active_key": active_key,
            "active_name": active_model.get("model") if active_model else active_key,
            "active_status": active_model.get("runtime_status") if active_model else "missing",
            "reachable_real_models": len(real_reachable),
            "testing_mode_available": dry_run_ready,
        },
        "workspace": {
            "active_path": workspace_state.get("active_path"),
            "active_name": workspace_state.get("active_name"),
            "approved_count": len(workspace_state.get("workspaces") or []),
        },
        "privacy": security.offline_status(),
        "output": {
            "markdown_folder": output_state.get("markdown_folder"),
        },
        "steps": steps,
    }


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
        elif request.url.path == "/api/warsat/deploy":
            response = await asyncio.wait_for(call_next(request), timeout=float(os.environ.get("WARSAT_DEPLOY_HTTP_TIMEOUT", "1900")))
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
    return {"username": "admin", "role": "admin"}


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
    session_id: str | None = None


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


class WorkspacePreviewIn(CamelModel):
    root_id: str | None = None
    path: str
    max_bytes: int = 131072


class WorkspaceSearchIn(CamelModel):
    root_id: str | None = None
    path: str | None = None
    query: str
    max_results: int = 40
    include_content: bool = False


class WorkspaceApproveIn(CamelModel):
    path: str
    name: str | None = None
    read_only: bool = True


class WorkspaceMountIn(CamelModel):
    host_path: str
    name: str | None = None
    read_only: bool = True


class WorkspaceMutationPreviewIn(CamelModel):
    kind: str
    workspace_path: str | None = "."
    path: str | None = None
    source: str | None = None
    target: str | None = None
    content: str | None = None
    max_items: int = 40


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
    api_key: str | None = None
    api_key_env: str | None = None
    anthropic_version: str | None = None
    clear_api_key: bool = False
    runtime: str | None = None
    context_window: int | None = None
    max_tokens: int | None = None
    port: int | None = None
    container: str | None = None
    image: str | None = None
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


class ChatFolderIn(CamelModel):
    name: str
    color: str | None = ""


class SessionFolderIn(CamelModel):
    folder: str | None = None
    folder_id: str | None = None


class SessionCreateIn(CamelModel):
    title: str | None = "New chat"
    workspace: str | None = "."
    model: str | None = "dry-run"
    mode: str | None = "chat"
    skill: str | None = "general"
    folder: str | None = ""



class ModelCatalogRefreshIn(CamelModel):
    force: bool = False


class HfSearchIn(CamelModel):
    query: str = ""
    model_type: str = ""
    sort: str = "downloads"
    direction: int = -1
    limit: int = 100


class WarsatPlanIn(CamelModel):
    protocol_id: str
    model_ref: str | None = None
    model_path: str | None = None
    strength_profile: str | None = None
    context_window: int | None = None
    max_model_len: int | None = None
    gpu_memory_utilization: float | None = None
    gpu_layers: int | None = None
    tensor_parallel_size: int | None = None
    cpu_threads: int | None = None
    batch_size: int | None = None
    max_num_seqs: int | None = None
    dtype: str | None = None
    quantization: str | None = None
    kv_cache_dtype: str | None = None
    swap_space_gb: int | None = None
    memory_limit_gb: int | None = None
    cpu_limit: float | None = None
    shm_size_gb: int | None = None
    gpu_device: str | None = None
    host_port: int | None = None
    role: str | None = None
    container_name: str | None = None


class WarsatDeployIn(CamelModel):
    plan: dict
    approval_id: str | None = None


class WarsatContainerIn(CamelModel):
    container_name: str
    approval_id: str | None = None
    limit: int = 120


class McpRelayIn(CamelModel):
    id: str | None = None
    name: str | None = None
    transport: str = "stdio"
    command: str | None = None
    args: list[str] | str | None = None
    env: dict | None = None
    cwd: str | None = None
    enabled: bool = False


class McpServerActionIn(CamelModel):
    approval_id: str | None = None


class McpToolClassifyIn(CamelModel):
    risk: str = "approval_required"
    permission_flag: str | None = None
    enabled: bool = True


class McpToolTestCallIn(CamelModel):
    message: str = "operator fixture ok"


class ArchiveSessionIn(CamelModel):
    id: str | None = None
    title: str = "Untitled archive draft"
    content: str = ""


class ArchiveExportIn(CamelModel):
    id: str
    folder: str | None = None

class ArchiveItemIn(CamelModel):
    id: str | None = None
    name: str
    type: str
    source: str
    workspace: str | None = None
    size: int = 0
    tags: list[str] = []
    metadata: dict = {}


class ArchiveCitationIn(CamelModel):
    query: str
    path: str | None = None
    limit: int = 6


class TrialCompareIn(CamelModel):
    prompt: str
    model_keys: list[str] | None = None


class TrialRoutingIn(CamelModel):
    output_id: str
    mode: str


class ExperimentIn(CamelModel):
    name: str
    type: str = "model"
    config: dict | None = None
    workspace: str = ""
    tags: list[str] | None = None


class DatasetIn(CamelModel):
    name: str
    type: str = "questions"
    entries: list[dict] | None = None
    tags: list[str] | None = None


class BenchmarkIn(CamelModel):
    name: str
    experiment_ids: list[str] | None = None
    config: dict | None = None


class ComparisonIn(CamelModel):
    name: str = ""
    experiment_ids: list[str] | None = None


class ReportIn(CamelModel):
    name: str
    type: str = "experiment"
    experiment_ids: list[str] | None = None


class ScorecardIn(CamelModel):
    experiment_id: str
    name: str | None = None


@app.get("/")
async def index():
    return FileResponse(FRONTEND / "index.html")


@app.get("/preview")
@app.get("/preview/{path:path}")
async def preview_index(path: str = ""):
    if not _ui_preview_enabled():
        raise HTTPException(status_code=404, detail="Preview UI is disabled.")
    return FileResponse(FRONTEND / "index.html")


@app.get("/api/health")
async def health():
    return ok({
        "name": "Rasputin",
        "status": "ready",
        "privacy": security.offline_status(),
    })


@app.get("/api/ui/config")
async def ui_config():
    return ok({
        "ui_preview_enabled": _ui_preview_enabled(),
        "environment": os.environ.get("RASPUTIN_ENV", "local"),
    })


@app.get("/api/ui/bootstrap")
async def ui_bootstrap(_user=Depends(current_user)):
    warsat_runtime_state = await asyncio.to_thread(warsat.containers)
    return ok({
        "models": model_registry.all_models(),
        "model_providers": model_providers.public_provider_options(),
        "model_catalog": model_catalog.catalog(refresh=False),
        "skills": skill_store.enabled_names(),
        "tasks": hub.all_tasks(limit=80, include_details=False),
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
        "warsat": {**warsat.list_protocols(), "runtimes": warsat_runtime_state},
        "chat_folders": hub.chat_folders(),
        "tools": tool_relay.catalog(),
        "mcp_relays": mcp_relay.servers(),
        "archive": archive.sessions(),
        "trials": trials.runs(),
        "setup": _setup_status(),
        "ui_preview_enabled": _ui_preview_enabled(),
    })


@app.get("/api/setup/status")
async def setup_status(_user=Depends(current_user)):
    return ok(_setup_status())


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


class ModelDownloadReq(BaseModel):
    modelId: str

@app.post("/api/models/download")
async def start_model_download(req: ModelDownloadReq, _user=Depends(current_user)):
    state = model_acquisition.start_download(req.modelId)
    return ok(state)


@app.get("/api/models/downloads/active")
async def get_active_downloads(_user=Depends(current_user)):
    return ok(model_acquisition.get_active_downloads())



@app.get("/api/model-registry")
async def model_registry_list(_user=Depends(current_user)):
    return ok({"models": model_registry.all_models(), "providers": model_providers.public_provider_options()})


@app.get("/api/model-providers")
async def model_provider_list(_user=Depends(current_user)):
    return ok({"providers": model_providers.public_provider_options()})


@app.get("/api/model-catalog")
async def model_catalog_get(fit: bool = False, _user=Depends(current_user)):
    hardware = await asyncio.to_thread(warsat.hardware_probe) if fit else None
    return ok(model_catalog.catalog(refresh=False, hardware=hardware))


@app.post("/api/model-catalog/refresh")
async def model_catalog_refresh(req: ModelCatalogRefreshIn | None = None, _user=Depends(current_user)):
    return ok(model_catalog.catalog(refresh=True, force=bool(req.force if req else False)))


@app.get("/api/model-catalog/search")
async def model_catalog_search(
    q: str = "", type: str = "", sort: str = "downloads",
    direction: int = -1, limit: int = 100, fit: bool = False, _user=Depends(current_user)
):
    hardware = await asyncio.to_thread(warsat.hardware_probe) if fit else None
    return ok(model_catalog.search_hf(query=q, model_type=type, sort=sort, direction=direction, limit=limit, hardware=hardware))


@app.get("/api/model-catalog/model/{model_id:path}")
async def model_catalog_detail(model_id: str, _user=Depends(current_user)):
    return ok(model_catalog.hf_model_detail(model_id))


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


@app.post("/api/model-registry/delete")
async def model_registry_delete(req: ModelKeyIn, _user=Depends(current_user)):
    return ok(model_registry.delete_model(req.key))


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


@app.get("/api/tools")
async def tools_get(_user=Depends(current_user)):
    return ok(tool_relay.catalog())


@app.get("/api/mcp/servers")
async def mcp_servers(_user=Depends(current_user)):
    return ok(mcp_relay.servers())


@app.post("/api/mcp/servers")
async def mcp_servers_create(req: McpRelayIn, _user=Depends(current_user)):
    return ok(mcp_relay.register(req.model_dump()))


@app.post("/api/mcp/fixtures/operator/register")
async def mcp_operator_fixture_register(_user=Depends(current_user)):
    return ok(mcp_relay.register_operator_fixture())


@app.post("/api/mcp/servers/{server_id}/enable")
async def mcp_servers_enable(server_id: str, _user=Depends(current_user)):
    return ok(mcp_relay.set_enabled(server_id, True))


@app.post("/api/mcp/servers/{server_id}/disable")
async def mcp_servers_disable(server_id: str, _user=Depends(current_user)):
    return ok(mcp_relay.set_enabled(server_id, False))


@app.post("/api/mcp/servers/{server_id}/discover")
async def mcp_servers_discover(server_id: str, _user=Depends(current_user)):
    return ok(await mcp_relay.discover(server_id))


@app.post("/api/mcp/servers/{server_id}/start")
async def mcp_servers_start(server_id: str, req: McpServerActionIn | None = None, _user=Depends(current_user)):
    return ok(await mcp_relay.start(server_id, approval_id=req.approval_id if req else None))


@app.post("/api/mcp/servers/{server_id}/stop")
async def mcp_servers_stop(server_id: str, _user=Depends(current_user)):
    return ok(await mcp_relay.stop(server_id))


@app.post("/api/mcp/servers/{server_id}/restart")
async def mcp_servers_restart(server_id: str, req: McpServerActionIn | None = None, _user=Depends(current_user)):
    return ok(await mcp_relay.restart(server_id, approval_id=req.approval_id if req else None))


@app.post("/api/mcp/servers/{server_id}/test")
async def mcp_servers_test(server_id: str, _user=Depends(current_user)):
    return ok(await mcp_relay.test_server(server_id))


@app.get("/api/mcp/servers/{server_id}/tools")
async def mcp_server_tools(server_id: str, _user=Depends(current_user)):
    return ok(mcp_relay.server_tools(server_id))


@app.post("/api/mcp/tools/{tool_id:path}/classify")
async def mcp_tool_classify(tool_id: str, req: McpToolClassifyIn, _user=Depends(current_user)):
    return ok(mcp_relay.classify_tool(tool_id, req.model_dump()))


@app.post("/api/mcp/tools/{tool_id:path}/test-call")
async def mcp_tool_test_call(tool_id: str, req: McpToolTestCallIn, _user=Depends(current_user)):
    detail = await hub.run_tool_test(tool_id, {"message": req.message})
    return ok(detail)


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


@app.post("/api/sessions")
async def sessions_create(req: SessionCreateIn, _user=Depends(current_user)):
    detail = hub.create_session(req.title, req.workspace, req.model, req.mode, req.skill, req.folder)
    audit.log("session_created", {"session_id": detail["session"]["id"], "title": detail["session"]["title"]})
    return ok(detail)


@app.get("/api/sessions/{session_id}")
async def session_get(session_id: str, _user=Depends(current_user)):
    return ok(hub.session(session_id))


@app.get("/api/chat-folders")
async def chat_folders_get(_user=Depends(current_user)):
    return ok(hub.chat_folders())


@app.post("/api/chat-folders")
async def chat_folders_post(req: ChatFolderIn, _user=Depends(current_user)):
    audit.log("chat_folder_created", {"name": req.name})
    return ok(hub.create_chat_folder(req.name, req.color or ""))


@app.post("/api/sessions/{session_id}/folder")
async def session_folder_post(session_id: str, req: SessionFolderIn, _user=Depends(current_user)):
    folder = req.folder if req.folder is not None else req.folder_id
    audit.log("session_folder_changed", {"session_id": session_id, "folder": folder})
    return ok(hub.assign_session_folder(session_id, folder))


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
    task = hub.start(req.objective, req.model, req.skill, max(0, min(req.subagents, 4)), req.workspace_path, req.mode, req.session_id)
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
async def tasks(limit: int = 100, details: bool = False, _user=Depends(current_user)):
    return ok(hub.all_tasks(limit=limit, include_details=details))


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


app.include_router(settings_api.router)


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


@app.get("/api/warsat/status")
async def warsat_status(_user=Depends(current_user)):
    return ok(warsat.summary())


@app.get("/api/warsat/protocols")
async def warsat_protocols(_user=Depends(current_user)):
    return ok(warsat.list_protocols())


@app.get("/api/warsat/runtimes")
async def warsat_runtimes(_user=Depends(current_user)):
    return ok(await asyncio.to_thread(warsat.containers))


@app.get("/api/warsat/hardware")
async def warsat_hardware(_user=Depends(current_user)):
    return ok(await asyncio.to_thread(warsat.hardware_probe))


@app.post("/api/warsat/plan")
async def warsat_plan(req: WarsatPlanIn, _user=Depends(current_user)):
    return ok(warsat.make_plan(req.model_dump()))


@app.post("/api/warsat/deploy")
async def warsat_deploy(req: WarsatDeployIn, _user=Depends(current_user)):
    if req.approval_id:
        async def event_stream():
            try:
                for chunk in warsat.deploy_stream(req.plan, req.approval_id):
                    yield json.dumps(chunk) + "\n"
            except AppError as e:
                yield json.dumps({"ok": False, "error": e.message, "code": e.code}) + "\n"
            except Exception as e:
                yield json.dumps({"ok": False, "error": str(e)}) + "\n"
        return StreamingResponse(event_stream(), media_type="application/x-ndjson")
    else:
        return ok(await asyncio.to_thread(warsat.deploy, req.plan, req.approval_id))


@app.post("/api/warsat/logs")
async def warsat_logs(req: WarsatContainerIn, _user=Depends(current_user)):
    return ok(await asyncio.to_thread(warsat.logs, req.container_name, req.limit))


@app.post("/api/warsat/stop")
async def warsat_stop(req: WarsatContainerIn, _user=Depends(current_user)):
    return ok(await asyncio.to_thread(warsat.stop, req.container_name, req.approval_id))


@app.post("/api/warsat/restart")
async def warsat_restart(req: WarsatContainerIn, _user=Depends(current_user)):
    return ok(await asyncio.to_thread(warsat.restart, req.container_name, req.approval_id))


@app.get("/api/warsat/system-metrics")
async def warsat_system_metrics(_user=Depends(current_user)):
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get GPU metrics if nvidia-smi exists
        gpu_metrics = []
        import shutil, subprocess
        if shutil.which("nvidia-smi"):
            try:
                res = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"],
                    text=True, timeout=2
                )
                for line in res.strip().split("\n"):
                    if not line: continue
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 6:
                        gpu_metrics.append({
                            "index": int(parts[0]),
                            "name": parts[1],
                            "utilization": float(parts[2]),
                            "memory_used_mb": float(parts[3]),
                            "memory_total_mb": float(parts[4]),
                            "temperature": float(parts[5])
                        })
            except Exception:
                pass

        return ok({
            "cpu": {"percent": cpu},
            "ram": {
                "percent": ram.percent,
                "used_gb": round(ram.used / (1024**3), 2),
                "total_gb": round(ram.total / (1024**3), 2)
            },
            "disk": {
                "percent": disk.percent,
                "used_gb": round(disk.used / (1024**3), 2),
                "total_gb": round(disk.total / (1024**3), 2)
            },
            "gpus": gpu_metrics
        })
    except ImportError:
        return fail("dependency_missing", "psutil is not installed", 500)
    except Exception as e:
        return fail("metrics_error", str(e), 500)


@app.get("/api/warsat/agent-state")
async def warsat_agent_state(_user=Depends(current_user)):
    # Pull active tasks from the AgentHub
    active_tasks = [t for t in hub.all_tasks(limit=50) if t.get("status") in ("queued", "running", "paused")]
    return ok({
        "active_agents": len(active_tasks),
        "tasks": active_tasks
    })


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


@app.post("/api/workspace/preview-file")
async def workspace_preview_file(req: WorkspacePreviewIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(workspace.preview_file(req.root_id, req.path, req.max_bytes))


@app.post("/api/workspace/search")
async def workspace_search(req: WorkspaceSearchIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(workspace.search_files(req.root_id, req.path, req.query, req.max_results, req.include_content))


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


@app.post("/api/workspace/mutation-preview")
async def workspace_mutation_preview(req: WorkspaceMutationPreviewIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    plan = workspace.mutation_preview(req.kind, req.workspace_path, req.path, req.source, req.target, req.content, req.max_items)
    audit.log("workspace_mutation_preview", {
        "kind": plan["kind"],
        "workspace": plan["workspace"],
        "affected_paths": len(plan["affected_paths"]),
        "will_mutate": False,
    })
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


@app.get("/api/archive/sessions")
async def archive_sessions(_user=Depends(current_user)):
    return ok(archive.sessions())

@app.get("/api/archive/items")
async def archive_items_get(type: str = None, workspace: str = None, search: str = None, _user=Depends(current_user)):
    return ok([item.model_dump() for item in archive.ArchiveService.get_items({"type": type, "workspace": workspace, "search": search})])

@app.post("/api/archive/items")
async def archive_items_post(req: ArchiveItemIn, _user=Depends(current_user)):
    import time
    from . import runtime_store as store
    item = archive.ArchiveItem(
        id=req.id or store.new_id("arc_item"),
        name=req.name,
        type=req.type,
        source=req.source,
        workspace=req.workspace,
        created_at=time.time(),
        archived_at=time.time(),
        size=req.size,
        tags=req.tags,
        retention_policy_id=None,
        metadata=req.metadata
    )
    archive.ArchiveService.add_item(item)
    return ok(item.model_dump())

@app.delete("/api/archive/items/{item_id}")
async def archive_items_delete(item_id: str, _user=Depends(current_user)):
    archive.ArchiveService.delete_item(item_id)
    return ok()


@app.post("/api/archive/items/{item_id}/restore")
async def archive_items_restore(item_id: str, _user=Depends(current_user)):
    success = archive.ArchiveService.restore_item(item_id)
    if not success:
        return fail("Item not found or could not be restored")
    return ok()

@app.post("/api/archive/sessions")
async def archive_sessions_save(req: ArchiveSessionIn, _user=Depends(current_user)):
    return ok(archive.save_session(req.model_dump()))


@app.post("/api/archive/export")
async def archive_export(req: ArchiveExportIn, _user=Depends(current_user)):
    security.require("allow_file_write")
    return ok(archive.export_session(req.id, req.folder))


@app.post("/api/archive/citations")
async def archive_citations(req: ArchiveCitationIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(archive.citation_search(req.query, req.path, req.limit))


@app.get("/api/trials")
async def trials_get(_user=Depends(current_user)):
    return ok(trials.runs())


@app.post("/api/trials/compare")
async def trials_compare(req: TrialCompareIn, _user=Depends(current_user)):
    return ok(await trials.compare(req.prompt, req.model_keys or []))


@app.post("/api/trials/{run_id}/reveal")
async def trials_reveal(run_id: str, _user=Depends(current_user)):
    return ok(trials.reveal(run_id))


@app.post("/api/trials/{run_id}/routing")
async def trials_routing(run_id: str, req: TrialRoutingIn, _user=Depends(current_user)):
    result = trials.save_routing(run_id, req.output_id, req.mode)
    audit.log("trial_route_saved", result["route"])
    return ok(result)


# ── Trials V3: Experiments ──

@app.get("/api/trials/experiments")
async def trials_experiments(type: str | None = None, status: str | None = None, _user=Depends(current_user)):
    return ok(trials.list_experiments(type_filter=type, status_filter=status))


@app.post("/api/trials/experiments")
async def trials_create_experiment(req: ExperimentIn, _user=Depends(current_user)):
    exp = trials.create_experiment(
        name=req.name, exp_type=req.type, config=req.config,
        workspace=req.workspace, owner=_user.get("username", "admin"), tags=req.tags,
    )
    audit.log("trial_experiment_created", {"id": exp["id"], "type": req.type})
    return ok(exp)


@app.get("/api/trials/experiments/{experiment_id}")
async def trials_get_experiment(experiment_id: str, _user=Depends(current_user)):
    exp = trials.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return ok(exp)


@app.post("/api/trials/experiments/{experiment_id}/run")
async def trials_run_experiment(experiment_id: str, _user=Depends(current_user)):
    result = await trials.run_experiment(experiment_id)
    return ok(result)


@app.post("/api/trials/experiments/{experiment_id}/cancel")
async def trials_cancel_experiment(experiment_id: str, _user=Depends(current_user)):
    result = trials.cancel_experiment(experiment_id)
    return ok(result)


@app.delete("/api/trials/experiments/{experiment_id}")
async def trials_delete_experiment(experiment_id: str, _user=Depends(current_user)):
    return ok(trials.delete_experiment(experiment_id))


# ── Trials V3: Datasets ──

@app.get("/api/trials/datasets")
async def trials_datasets(_user=Depends(current_user)):
    return ok(trials.list_datasets())


@app.post("/api/trials/datasets")
async def trials_create_dataset(req: DatasetIn, _user=Depends(current_user)):
    ds = trials.create_dataset(name=req.name, ds_type=req.type, entries=req.entries, tags=req.tags)
    audit.log("trial_dataset_created", {"id": ds["id"], "name": req.name})
    return ok(ds)


@app.get("/api/trials/datasets/{dataset_id}")
async def trials_get_dataset(dataset_id: str, _user=Depends(current_user)):
    ds = trials.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return ok(ds)


@app.delete("/api/trials/datasets/{dataset_id}")
async def trials_delete_dataset(dataset_id: str, _user=Depends(current_user)):
    return ok(trials.delete_dataset(dataset_id))


@app.post("/api/trials/datasets/seed")
async def trials_seed_datasets(_user=Depends(current_user)):
    return ok(trials.seed_datasets())


# ── Trials V3: Benchmarks ──

@app.get("/api/trials/benchmarks")
async def trials_benchmarks(_user=Depends(current_user)):
    return ok(trials.list_benchmarks())


@app.post("/api/trials/benchmarks")
async def trials_create_benchmark(req: BenchmarkIn, _user=Depends(current_user)):
    bm = trials.create_benchmark(name=req.name, experiment_ids=req.experiment_ids, config=req.config)
    audit.log("trial_benchmark_created", {"id": bm["id"], "name": req.name})
    return ok(bm)


@app.get("/api/trials/benchmarks/{benchmark_id}")
async def trials_get_benchmark(benchmark_id: str, _user=Depends(current_user)):
    bm = trials.get_benchmark(benchmark_id)
    if not bm:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return ok(bm)


# ── Trials V3: Comparisons ──

@app.get("/api/trials/comparisons")
async def trials_comparisons(_user=Depends(current_user)):
    return ok(trials.list_comparisons())


@app.post("/api/trials/comparisons")
async def trials_create_comparison(req: ComparisonIn, _user=Depends(current_user)):
    name = req.name or f"Comparison {len(trials.list_comparisons()) + 1}"
    comp = trials.create_comparison(name=name, experiment_ids=req.experiment_ids)
    audit.log("trial_comparison_created", {"id": comp["id"]})
    return ok(comp)


# ── Trials V3: Scorecards ──

@app.get("/api/trials/scorecards")
async def trials_scorecards(_user=Depends(current_user)):
    return ok(trials.list_scorecards())


@app.post("/api/trials/scorecards")
async def trials_create_scorecard(req: ScorecardIn, _user=Depends(current_user)):
    sc = trials.generate_scorecard(req.experiment_id, name=req.name)
    return ok(sc)


# ── Trials V3: Reports ──

@app.get("/api/trials/reports")
async def trials_reports(_user=Depends(current_user)):
    return ok(trials.list_reports())


@app.post("/api/trials/reports")
async def trials_create_report(req: ReportIn, _user=Depends(current_user)):
    rpt = trials.generate_report(name=req.name, report_type=req.type, experiment_ids=req.experiment_ids)
    return ok(rpt)


@app.get("/api/trials/reports/{report_id}")
async def trials_get_report(report_id: str, _user=Depends(current_user)):
    rpt = trials.get_report(report_id)
    if not rpt:
        raise HTTPException(status_code=404, detail="Report not found")
    return ok(rpt)


@app.get("/api/events")
async def events(request: Request, _user=Depends(current_user)):
    q = await hub.subscribe()

    async def gen():
        yield f"data: {json.dumps({'hello': True, 'tasks': hub.all_tasks(limit=100, include_details=False), 'approvals': approvals.list_approvals('pending'), 'memoryReview': memory_store.pending_review(), 'telegram': telegram.public_config()})}\n\n"
        while True:
            if await request.is_disconnected():
                break
            item = await q.get()
            yield f"data: {json.dumps({'task': item})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
