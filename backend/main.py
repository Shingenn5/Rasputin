import asyncio
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.core.response import AppError, error_handler, fail, http_error_handler
from backend.core import auth
from backend.core import settings_api
from backend.models import registry as model_registry
from backend.rag import memory as memory_store
from backend.mcp import skills as skill_store
from backend.core import telegram
from backend.core import audit
from backend.api.core import router as core_router
from backend.api.agent import router as agent_router
from backend.api.warsat_api import router as warsat_router
from backend.api.mcp_routes import router as mcp_api_router

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"

app = FastAPI(title="Rasputin", version="0.2.0")

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


# Indexing a real, approved workspace (RAG ingest + Graphify build) walks and
# parses every file under it; a large repo through a slow Docker Desktop
# bind mount can genuinely take minutes, well past the general API timeout.
LONG_INDEX_PATHS = {"/api/rag/ingest", "/api/graph/build"}


@app.middleware("http")
async def production_headers(request: Request, call_next):
    request_id = str(uuid.uuid4())[:12]
    timeout = float(os.environ.get("RASPUTIN_REQUEST_TIMEOUT", "90"))
    try:
        if request.url.path == "/api/events":
            response = await call_next(request)
        elif request.url.path == "/api/warsat/deploy":
            response = await asyncio.wait_for(call_next(request), timeout=float(os.environ.get("WARSAT_DEPLOY_HTTP_TIMEOUT", "1900")))
        elif request.url.path in LONG_INDEX_PATHS:
            response = await asyncio.wait_for(call_next(request), timeout=float(os.environ.get("RASPUTIN_INDEX_TIMEOUT", "900")))
        else:
            response = await asyncio.wait_for(call_next(request), timeout=timeout)
    except asyncio.TimeoutError:
        return _security_headers(fail("request_timeout", "request timed out", 504), request_id)
    except Exception as exc:
        return _security_headers(_error_response(exc), request_id)
    return _security_headers(response, request_id)



app.include_router(core_router)
app.include_router(agent_router)
app.include_router(warsat_router)
app.include_router(mcp_api_router)
app.include_router(settings_api.router)

# index.html must never be cached by the browser: it points at content-hashed
# JS/CSS, so caching it means the browser keeps loading stale bundles after a
# rebuild. The hashed assets under /static can (and do) cache forever.
_INDEX_NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate"}


@app.get("/")
async def index():
    return FileResponse(FRONTEND / "index.html", headers=_INDEX_NO_CACHE)

@app.get("/preview")
@app.get("/preview/{path:path}")
async def preview_index(path: str = ""):
    if not _ui_preview_enabled():
        raise HTTPException(status_code=404, detail="Preview UI is disabled.")
    return FileResponse(FRONTEND / "index.html", headers=_INDEX_NO_CACHE)
