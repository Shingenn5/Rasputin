import os
import asyncio
from fastapi import APIRouter, Depends, Request
from backend.core.response import ok, AppError
from backend.api.common import CamelModel, current_user, hub
from backend.core import security
from backend.core import preferences
from backend.core import audit
from backend.core import auth
from backend.engine import output
from backend.core import telegram
from backend.core import approvals
from backend.models import registry as model_registry
from backend.models import catalog as model_catalog
from backend.models import providers as model_providers
from backend.mcp import skills as skill_store
from backend.mcp import tools as tool_relay
from backend.mcp import relay as mcp_relay
from backend.rag.memory import load_memory
from backend.rag import memory as memory_store
from backend.rag import vector as rag
from backend.rag import graph as graphify
from backend.core import schedules
from backend import workspace
from backend import warsat
from backend import archive
from backend import trials

router = APIRouter(prefix="/api", tags=["system"])

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


@router.get("/health")
async def health():
    return ok({
        "name": "Rasputin",
        "status": "ready",
        "privacy": security.offline_status(),
    })


@router.get("/ui/config")
async def ui_config():
    return ok({
        "ui_preview_enabled": _ui_preview_enabled(),
        "environment": os.environ.get("RASPUTIN_ENV", "local"),
    })


@router.get("/ui/bootstrap")
async def ui_bootstrap(_user=Depends(current_user)):
    try:
        warsat_runtime_state = await asyncio.to_thread(warsat.containers)
    except AppError:
        warsat_runtime_state = {"containers": [], "enabled": False, "message": "Docker unreachable."}
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


@router.get("/setup/status")
async def setup_status(_user=Depends(current_user)):
    return ok(_setup_status())

@router.get("/security")
async def security_get(_user=Depends(current_user)):
    return ok(security.load())

@router.post("/security")
async def security_post(req: dict, _user=Depends(current_user)):
    return ok(security.save(req))

@router.get("/preferences")
async def preferences_get(_user=Depends(current_user)):
    return ok(preferences.load())

@router.post("/preferences")
async def preferences_post(req: dict, _user=Depends(current_user)):
    return ok(preferences.save(req))

@router.get("/audit")
async def audit_get(limit: int = 100, _user=Depends(current_user)):
    return ok({"events": audit.recent(limit)})

@router.get("/approvals")
async def approvals_get(status: str | None = None, limit: int = 100, _user=Depends(current_user)):
    return ok(approvals.list_approvals(status, limit))

@router.post("/approvals/{approval_id}/approve")
async def approvals_approve(approval_id: str, _user=Depends(current_user)):
    return ok(approvals.approve(approval_id))

@router.post("/approvals/{approval_id}/deny")
async def approvals_deny(approval_id: str, _user=Depends(current_user)):
    return ok(approvals.deny(approval_id))

@router.post("/approvals/{approval_id}/expire")
async def approvals_expire(approval_id: str, _user=Depends(current_user)):
    return ok(approvals.expire(approval_id))

@router.get("/integrations/telegram")
async def telegram_get(_user=Depends(current_user)):
    return ok(telegram.public_config())

@router.post("/integrations/telegram/configure")
async def telegram_configure(req: TelegramConfigIn, _user=Depends(current_user)):
    return ok(telegram.configure(req.bot_token, req.allowed_chat_id, req.enabled, req.redaction_mode))

@router.post("/integrations/telegram/test")
async def telegram_test(_user=Depends(current_user)):
    return ok(telegram.test_message())

@router.post("/integrations/telegram/disable")
async def telegram_disable(_user=Depends(current_user)):
    return ok(telegram.disable())

@router.get("/output")
async def output_get(_user=Depends(current_user)):
    return ok(output.get_config())

@router.post("/output")
async def output_post(req: dict, _user=Depends(current_user)):
    security.require("allow_file_write")
    return ok(output.save_config(req))

@router.post("/output/export-task")
async def output_export_task(req: ExportTaskIn, _user=Depends(current_user)):
    security.require("allow_file_write")
    task = hub.get_task(req.task_id)
    return ok(output.export_markdown(task, req.folder))

@router.get("/events")
async def events(request: Request, _user=Depends(current_user)):
    from fastapi.responses import StreamingResponse
    q = await hub.subscribe()

    async def gen():
        while True:
            if await request.is_disconnected():
                hub.listeners.discard(q)
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
