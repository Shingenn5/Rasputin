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

from backend.engine.agent import AgentHub
from backend.rag.memory import load_memory, remember
from backend.core.response import AppError, error_handler, fail, http_error_handler, ok
from backend.core import auth as auth
from backend.core import approvals as approvals
from backend.models import registry as model_registry
from backend.models import catalog as model_catalog
from backend.models import providers as model_providers
from backend.rag import vector as rag
from backend.rag import graph as graphify
from backend import workspace
from backend.core import security as security
from backend.core import audit as audit
from backend.engine import output as output
from backend.core import preferences as preferences
from backend.rag import memory as memory_store
from backend.core import schedules as schedules
from backend.mcp import skills as skill_store
from backend.core import telegram as telegram
from backend import warsat
from backend.mcp import tools as tool_relay
from backend.mcp import relay as mcp_relay
from . import archive
from backend import trials
from backend.core import settings_api as settings_api
from backend.models import acquisition as model_acquisition

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"

app = FastAPI(title="Rasputin", version="0.2.0")
from backend.api.common import hub, current_user

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
    import traceback; traceback.print_exc()
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



from backend.api.auth import router as auth_router
from backend.api.models import router as models_router
from backend.api.mcp import router as mcp_router
from backend.api.skills import router as skills_router
from backend.api.sessions import router as sessions_router
from backend.api.tasks import router as tasks_router
from backend.api.memory import router as memory_router
from backend.api.workspace import router as workspace_router
from backend.api.warsat import router as warsat_router
from backend.api.rag import router as rag_router
from backend.api.trials import router as trials_router
from backend.api.archive import router as archive_router
from backend.api.system import router as system_router

from backend.api.sandbox import router as sandbox_router

app.include_router(auth_router)
app.include_router(models_router)
app.include_router(mcp_router)
app.include_router(skills_router)
app.include_router(sessions_router)
app.include_router(tasks_router)
app.include_router(memory_router)
app.include_router(workspace_router)
app.include_router(warsat_router)
app.include_router(rag_router)
app.include_router(trials_router)
app.include_router(archive_router)
app.include_router(system_router)
app.include_router(sandbox_router)
app.include_router(settings_api.router)

@app.get("/")
async def index():
    return FileResponse(FRONTEND / "index.html")

@app.get("/preview")
@app.get("/preview/{path:path}")
async def preview_index(path: str = ""):
    if not _ui_preview_enabled():
        raise HTTPException(status_code=404, detail="Preview UI is disabled.")
    return FileResponse(FRONTEND / "index.html")
