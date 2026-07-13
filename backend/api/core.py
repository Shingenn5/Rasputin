from fastapi import APIRouter, Depends, Request, Response, HTTPException
from backend import archive
from backend import trials
from backend import warsat
from backend.core import workspace
from backend.core import approvals
from backend.core import audit
from backend.core import auth
from backend.core import preferences
from backend.core import schedules
from backend.core import security
from backend.core import telegram
from backend.core.response import ok, AppError
from backend.engine import output
from backend.engine.agent import AgentHub
from backend.mcp import relay as mcp_relay
from backend.mcp import skills as skill_store
from backend.mcp import tools as tool_relay
from backend.models import acquisition as model_acquisition
from backend.models import catalog as model_catalog
from backend.models import providers as model_providers
from backend.models import registry as model_registry
from backend.rag import graph as graphify
from backend.rag import memory as memory_store
from backend.rag import vector as rag
from backend.rag.memory import load_memory
from pydantic import BaseModel, ConfigDict
import asyncio
import os

router = APIRouter()

def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])

class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

def current_user(request: Request):
    host = request.client.host if request.client else ""
    token = request.cookies.get(auth.COOKIE_NAME)
    session = auth.public_session(token, host)
    if not session.get("authenticated"):
        raise PermissionError("login required")
    return {"username": session.get("username"), "role": session.get("role")}


def require_admin(user=Depends(current_user)):
    if user.get("role") != "admin":
        raise PermissionError("administrator access required")
    return user


def require_member(user=Depends(current_user)):
    if user.get("role") not in {"admin", "member"}:
        raise PermissionError("member access required")
    return user

hub = AgentHub()


auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(CamelModel):
    username: str = "admin"
    password: str

class PasswordChangeIn(CamelModel):
    current_password: str
    new_password: str

class UserCreateIn(CamelModel):
    username: str
    password: str
    role: str = "member"

class UserUpdateIn(CamelModel):
    role: str | None = None
    enabled: bool | None = None

class UserResetPasswordIn(CamelModel):
    new_password: str | None = None

@auth_router.get("/session")

async def auth_session(request: Request):
    host = request.client.host if request.client else ""
    token = request.cookies.get(auth.COOKIE_NAME)
    return ok(auth.public_session(token, host))

@auth_router.post("/login")

async def auth_login(req: LoginIn, response: Response, request: Request):
    host = request.client.host if request.client else "local"
    token, info = auth.login(req.username, req.password, host)
    response.set_cookie(
        auth.COOKIE_NAME,
        token,
        httponly=True,
        secure=auth.cookie_secure(),
        samesite="strict",
        max_age=auth.session_ttl_seconds(),
        path="/",
    )
    return ok(info)

@auth_router.post("/logout")

async def auth_logout(response: Response, request: Request):
    token = request.cookies.get(auth.COOKIE_NAME)
    out = auth.logout(token)
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return ok(out)

@auth_router.post("/change-password")

async def auth_change_password(req: PasswordChangeIn, request: Request, user=Depends(current_user)):
    username = user.get("username")
    if username == "localhost":
        username = auth.load_public().get("username", "admin")
    return ok(auth.change_password(username, req.current_password, req.new_password))

@auth_router.get("/users")
async def auth_users(_user=Depends(require_admin)):
    return ok({"users": auth.list_users()})

@auth_router.post("/users")
async def auth_users_create(req: UserCreateIn, user=Depends(require_admin)):
    created = auth.create_user(req.username, req.password, req.role)
    audit.log("auth_user_created_by_admin", {"username": created["username"], "role": created["role"]}, actor=user["username"])
    return ok(created)

@auth_router.patch("/users/{username}")
async def auth_users_update(username: str, req: UserUpdateIn, user=Depends(require_admin)):
    updated = auth.update_user(username, req.role, req.enabled)
    audit.log("auth_user_updated_by_admin", {"username": username}, actor=user["username"])
    return ok(updated)

@auth_router.delete("/users/{username}")
async def auth_users_delete(username: str, user=Depends(require_admin)):
    if username == user.get("username"):
        raise ValueError("you cannot delete your own account")
    return ok(auth.delete_user(username))

@auth_router.post("/users/{username}/reset-password")
async def auth_users_reset_password(username: str, req: UserResetPasswordIn, user=Depends(require_admin)):
    result = auth.reset_password(username, req.new_password)
    audit.log("auth_password_reset_by_admin", {"username": username}, actor=user["username"])
    return ok(result)

system_router = APIRouter(prefix="/api", tags=["system"])


class TelegramConfigIn(CamelModel):
    bot_token: str | None = None
    allowed_chat_id: str | None = None
    enabled: bool = True
    redaction_mode: str = "summary"

class ExportTaskIn(CamelModel):
    task_id: str
    folder: str | None = None

def _ui_preview_enabled():
    return str(os.environ.get("RASPUTIN_UI_PREVIEW", "")).strip().lower() in {"1", "true", "yes", "on"}

def _setup_status(username="admin", is_admin=True):
    auth_state = auth.load_public()
    security_state = security.load()
    workspace_state = workspace.get_active(username, is_admin)
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


@system_router.get("/health")

async def health():
    return ok({
        "name": "Rasputin",
        "status": "ready",
        "privacy": security.offline_status(),
    })


@system_router.get("/ui/config")

async def ui_config():
    return ok({
        "ui_preview_enabled": _ui_preview_enabled(),
        "environment": os.environ.get("RASPUTIN_ENV", "local"),
    })


@system_router.get("/ui/bootstrap")

async def ui_bootstrap(_user=Depends(current_user)):
    username = _user.get("username", "admin")
    is_admin = _user.get("role") == "admin"
    try:
        warsat_runtime_state = await asyncio.to_thread(warsat.containers)
    except AppError:
        warsat_runtime_state = {"containers": [], "enabled": False, "message": "Docker unreachable."}
    return ok({
        "models": model_registry.all_models(),
        "model_providers": model_providers.public_provider_options(),
        "model_catalog": model_catalog.catalog(refresh=False),
        "skills": skill_store.enabled_names(),
        "tasks": hub.all_tasks(limit=80, include_details=False, owner_id=username),
        "memory": load_memory(username),
        "memory_review": memory_store.pending_review(username),
        "rag_stats": rag.stats(),
        "workspace": workspace.get_active(username, is_admin),
        "graph_stats": graphify.stats(),
        "security": {**security.load(), "native": workspace.is_native()},
        "audit": {"events": audit.recent(100) if is_admin else []},
        "output": output.get_config(),
        "preferences": preferences.load(username),
        "sessions": hub.sessions(owner_id=username),
        "approvals": approvals.list_approvals() if is_admin else [],
        "skill_registry": skill_store.list_skills(),
        "telegram": telegram.public_config(),
        "schedules": schedules.list_schedules(),
        "warsat": {**warsat.list_protocols(), "runtimes": warsat_runtime_state},
        "chat_folders": hub.chat_folders(username),
        "tools": tool_relay.catalog(),
        "mcp_relays": mcp_relay.servers(),
        "archive": archive.sessions(),
        "trials": trials.runs(),
        "setup": _setup_status(username, is_admin),
        "ui_preview_enabled": _ui_preview_enabled(),
        "account": {**_user, "can_administer": is_admin},
    })


@system_router.get("/setup/status")

async def setup_status(_user=Depends(current_user)):
    return ok(_setup_status(_user.get("username", "admin"), _user.get("role") == "admin"))

@system_router.get("/security")

async def security_get(_user=Depends(current_user)):
    return ok({**security.load(), "native": workspace.is_native()})

@system_router.post("/security")

async def security_post(req: dict, _user=Depends(require_admin)):
    return ok(security.save(req))

@system_router.get("/preferences")

async def preferences_get(_user=Depends(current_user)):
    return ok(preferences.load(_user.get("username")))

@system_router.post("/preferences")

async def preferences_post(req: dict, _user=Depends(current_user)):
    return ok(preferences.save(req, _user.get("username")))

@system_router.get("/audit")

async def audit_get(limit: int = 100, _user=Depends(require_admin)):
    return ok({"events": audit.recent(limit)})

@system_router.get("/approvals")

async def approvals_get(status: str | None = None, limit: int = 100, _user=Depends(require_admin)):
    return ok(approvals.list_approvals(status, limit))

@system_router.post("/approvals/{approval_id}/approve")

async def approvals_approve(approval_id: str, _user=Depends(require_admin)):
    return ok(approvals.approve(approval_id))

@system_router.post("/approvals/{approval_id}/deny")

async def approvals_deny(approval_id: str, _user=Depends(require_admin)):
    return ok(approvals.deny(approval_id))

@system_router.post("/approvals/{approval_id}/expire")

async def approvals_expire(approval_id: str, _user=Depends(require_admin)):
    return ok(approvals.expire(approval_id))

@system_router.get("/integrations/telegram")

async def telegram_get(_user=Depends(current_user)):
    return ok(telegram.public_config())

@system_router.post("/integrations/telegram/configure")

async def telegram_configure(req: TelegramConfigIn, _user=Depends(require_admin)):
    return ok(telegram.configure(req.bot_token, req.allowed_chat_id, req.enabled, req.redaction_mode))

@system_router.post("/integrations/telegram/test")

async def telegram_test(_user=Depends(require_admin)):
    return ok(telegram.test_message())

@system_router.post("/integrations/telegram/disable")

async def telegram_disable(_user=Depends(require_admin)):
    return ok(telegram.disable())

@system_router.get("/output")

async def output_get(_user=Depends(current_user)):
    return ok(output.get_config())

@system_router.post("/output")

async def output_post(req: dict, _user=Depends(require_admin)):
    security.require("allow_file_write")
    return ok(output.save_config(req))

@system_router.post("/output/export-task")

async def output_export_task(req: ExportTaskIn, _user=Depends(require_member)):
    security.require("allow_file_write")
    task = hub.get_task(req.task_id, _user["username"])
    if not task:
        raise AppError("task_not_found", "Task was not found.", 404)
    return ok(output.export_markdown(task, req.folder))

@system_router.get("/events")

async def events(request: Request, _user=Depends(current_user)):
    from fastapi.responses import StreamingResponse
    q = await hub.subscribe(_user.get("username", "admin"))

    async def gen():
        while True:
            if await request.is_disconnected():
                hub.listeners.pop(q, None)
                break
            try:
                data = await q.get()
                import json
                yield f"data: {json.dumps(data)}\n\n"
            except asyncio.CancelledError:
                break
            except Exception:
                pass
    return StreamingResponse(gen(), media_type="text/event-stream")

models_router = APIRouter(prefix="/api", tags=["models"])


class ModelDownloadReq(BaseModel):
    modelId: str

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

class ModelCatalogRefreshIn(CamelModel):
    force: bool = False

@models_router.get("/models")

async def models(_user=Depends(current_user)):
    return ok(model_registry.enabled_models())

@models_router.post("/models/download")

async def start_model_download(req: ModelDownloadReq, _user=Depends(require_admin)):
    state = model_acquisition.start_download(req.modelId)
    return ok(state)

@models_router.get("/models/downloads/active")

async def get_active_downloads(_user=Depends(current_user)):
    return ok(model_acquisition.get_active_downloads())

@models_router.get("/model-registry")

async def model_registry_list(_user=Depends(current_user)):
    return ok({"models": model_registry.all_models(), "providers": model_providers.public_provider_options()})

@models_router.get("/model-providers")

async def model_provider_list(_user=Depends(current_user)):
    return ok({"providers": model_providers.public_provider_options()})

@models_router.get("/model-catalog")

async def model_catalog_get(fit: bool = False, _user=Depends(current_user)):
    hardware = await asyncio.to_thread(warsat.hardware_probe) if fit else None
    return ok(model_catalog.catalog(refresh=False, hardware=hardware))

@models_router.post("/model-catalog/refresh")

async def model_catalog_refresh(req: ModelCatalogRefreshIn | None = None, _user=Depends(require_admin)):
    return ok(model_catalog.catalog(refresh=True, force=bool(req.force if req else False)))

@models_router.get("/model-catalog/search")

async def model_catalog_search(
    q: str = "", type: str = "", sort: str = "downloads",
    direction: int = -1, limit: int = 100, fit: bool = False, _user=Depends(current_user)
):
    hardware = await asyncio.to_thread(warsat.hardware_probe) if fit else None
    return ok(model_catalog.search_hf(query=q, model_type=type, sort=sort, direction=direction, limit=limit, hardware=hardware))

@models_router.get("/model-catalog/model/{model_id:path}")

async def model_catalog_detail(model_id: str, _user=Depends(current_user)):
    return ok(model_catalog.hf_model_detail(model_id))

@models_router.post("/model-registry/upsert")

async def model_registry_upsert(req: ModelIn, _user=Depends(require_admin)):
    return ok(model_registry.upsert(req.model_dump()))

@models_router.post("/model-registry/import-gguf")

async def model_registry_import_gguf(req: GgufImportIn, _user=Depends(require_admin)):
    return ok(model_registry.import_gguf(req.model_dump()))

@models_router.post("/model-registry/scan-gguf")

async def model_registry_scan_gguf(req: GgufScanIn | None = None, _user=Depends(require_admin)):
    return ok(model_registry.scan_gguf(req.root if req else None))

@models_router.post("/model-registry/start")

async def model_registry_start(req: ModelKeyIn, _user=Depends(require_admin)):
    return ok(model_registry.start_model(req.key))

@models_router.post("/model-registry/stop")

async def model_registry_stop(req: ModelKeyIn, _user=Depends(require_admin)):
    return ok(model_registry.stop_model(req.key))

@models_router.post("/model-registry/test")

async def model_registry_test(req: ModelKeyIn, _user=Depends(require_admin)):
    return ok(model_registry.test_model(req.key))

@models_router.post("/model-registry/discover")

async def model_registry_discover(req: ModelKeyIn, _user=Depends(require_admin)):
    return ok(model_registry.discover_model(req.key))

@models_router.post("/model-registry/repair")

async def model_registry_repair(req: ModelKeyIn, _user=Depends(require_admin)):
    return ok(model_registry.repair_model(req.key))

@models_router.post("/model-registry/logs")

async def model_registry_logs(req: ModelLogsIn, _user=Depends(require_admin)):
    return ok(model_registry.logs_model(req.key, req.limit))

@models_router.post("/model-registry/delete")

async def model_registry_delete(req: ModelKeyIn, _user=Depends(require_admin)):
    return ok(model_registry.delete_model(req.key))

router.include_router(auth_router)
router.include_router(system_router)
router.include_router(models_router)
