import asyncio

from fastapi import APIRouter, Depends
from backend.api.core import CamelModel, current_user, require_admin, require_member, hub
from backend.core import audit
from backend.core import schedules
from backend.core import security
from backend.core import workspace
from backend.core.response import ok, AppError
from backend.mcp import skills as skill_store
from backend.rag import graph as graphify
from backend.rag import memory as memory_store
from backend.rag import vector as rag
from backend.rag.memory import load_memory, remember

router = APIRouter()

sessions_router = APIRouter(prefix="/api", tags=["sessions"])


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

@sessions_router.get("/sessions")

async def sessions_get(limit: int = 100, _user=Depends(current_user)):
    return ok(hub.sessions(limit, _user["username"]))

@sessions_router.post("/sessions")

async def sessions_create(req: SessionCreateIn, _user=Depends(require_member)):
    workspace_ref = req.workspace or workspace.get_active(_user["username"], _user["role"] == "admin").get("active_path") or "."
    workspace.require_user_access(workspace_ref, _user["username"], "viewer", _user["role"] == "admin")
    detail = hub.create_session(req.title, workspace_ref, req.model, req.mode, req.skill, req.folder, _user["username"])
    audit.log("session_created", {"session_id": detail["session"]["id"], "title": detail["session"]["title"]})
    return ok(detail)

@sessions_router.get("/sessions/{session_id}")

async def session_get(session_id: str, _user=Depends(current_user)):
    return ok(hub.session(session_id, _user["username"]))

@sessions_router.get("/chat-folders")

async def chat_folders_get(_user=Depends(current_user)):
    return ok(hub.chat_folders(_user["username"]))

@sessions_router.post("/chat-folders")

async def chat_folders_post(req: ChatFolderIn, _user=Depends(require_member)):
    audit.log("chat_folder_created", {"name": req.name})
    return ok(hub.create_chat_folder(req.name, req.color or "", _user["username"]))

@sessions_router.post("/sessions/{session_id}/folder")

async def session_folder_post(session_id: str, req: SessionFolderIn, _user=Depends(require_member)):
    folder = req.folder if req.folder is not None else req.folder_id
    audit.log("session_folder_changed", {"session_id": session_id, "folder": folder})
    return ok(hub.assign_session_folder(session_id, folder, _user["username"]))

tasks_router = APIRouter(prefix="/api", tags=["tasks", "schedules"])


class TaskIn(CamelModel):
    objective: str
    model: str = "dry-run"
    skill: str = "general"
    mode: str = "chat"
    reasoning: str = "auto"
    subagents: int = 0
    workspace_path: str | None = None
    session_id: str | None = None

class ScheduleIn(CamelModel):
    name: str
    prompt: str
    interval_seconds: int = 0
    enabled: bool = False

@tasks_router.post("/tasks")

async def create_task(req: TaskIn, _user=Depends(require_member)):
    workspace_ref = req.workspace_path or workspace.get_active(_user["username"], _user["role"] == "admin").get("active_path") or "."
    workspace.require_user_access(workspace_ref, _user["username"], "contributor", _user["role"] == "admin")
    task = hub.start(req.objective, req.model, req.skill, max(0, min(req.subagents, 4)), workspace_ref, req.mode, req.session_id, reasoning=req.reasoning, owner_id=_user["username"])
    return ok(hub.snapshot_task(task))

@tasks_router.post("/tasks/{task_id}/cancel")

async def cancel_task(task_id: str, _user=Depends(require_member)):
    if not hub.get_task(task_id, _user["username"]):
        raise AppError("task_not_found", "Task was not found.", 404)
    return ok(await hub.cancel(task_id))

@tasks_router.post("/tasks/{task_id}/pause")

async def pause_task(task_id: str, _user=Depends(require_member)):
    if not hub.get_task(task_id, _user["username"]):
        raise AppError("task_not_found", "Task was not found.", 404)
    return ok(await hub.pause(task_id))

@tasks_router.post("/tasks/{task_id}/resume")

async def resume_task(task_id: str, _user=Depends(require_member)):
    if not hub.get_task(task_id, _user["username"]):
        raise AppError("task_not_found", "Task was not found.", 404)
    return ok(await hub.resume(task_id))

@tasks_router.get("/tasks")

async def tasks(limit: int = 100, details: bool = False, _user=Depends(current_user)):
    return ok(hub.all_tasks(limit=limit, include_details=details, owner_id=_user["username"]))

@tasks_router.get("/tasks/{task_id}")

async def task_detail(task_id: str, _user=Depends(current_user)):
    detail = hub.task_detail(task_id, None if _user.get("role") == "admin" else _user["username"])
    if not detail:
        raise AppError("task_not_found", "Task was not found.", 404)
    return ok(detail)

@tasks_router.get("/schedules")

async def schedules_get(_user=Depends(current_user)):
    return ok(schedules.list_schedules())

@tasks_router.post("/schedules")

async def schedules_create(req: ScheduleIn, _user=Depends(require_admin)):
    return ok(schedules.create(req.name, req.prompt, req.interval_seconds, req.enabled))

skills_router = APIRouter(prefix="/api/skills", tags=["skills"])


class SkillImportIn(CamelModel):
    name: str
    content: str
    metadata: dict | None = None

class SkillFromSessionIn(CamelModel):
    session_id: str
    name: str | None = None
    save: bool = False

@skills_router.get("")

async def skills(_user=Depends(current_user)):
    return ok(skill_store.list_skills())

@skills_router.post("/create-from-session")

async def skills_create_from_session(req: SkillFromSessionIn, _user=Depends(require_admin)):
    return ok(skill_store.create_from_session(req.session_id, req.name, req.save))

@skills_router.post("/import")

async def skills_import(req: SkillImportIn, _user=Depends(require_admin)):
    return ok(skill_store.import_skill(req.name, req.content, req.metadata or {}))

@skills_router.get("/{name}")

async def skills_get(name: str, _user=Depends(current_user)):
    return ok(skill_store.get_skill(name))

@skills_router.post("/{name}/enable")

async def skills_enable(name: str, _user=Depends(require_admin)):
    return ok(skill_store.set_enabled(name, True))

@skills_router.post("/{name}/disable")

async def skills_disable(name: str, _user=Depends(require_admin)):
    return ok(skill_store.set_enabled(name, False))

memory_router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryIn(CamelModel):
    kind: str = "fact"
    value: object

class MemorySearchIn(CamelModel):
    query: str
    limit: int = 10

class MemoryReviewIn(CamelModel):
    id: str
    action: str = "approve"

@memory_router.get("")

async def memory(_user=Depends(current_user)):
    return ok(load_memory(_user["username"]))

@memory_router.post("")

async def add_memory(req: MemoryIn, _user=Depends(current_user)):
    return ok(remember(req.kind, req.value, _user["username"]))

@memory_router.get("/review")

async def memory_review(_user=Depends(current_user)):
    return ok(memory_store.pending_review(_user["username"]))

@memory_router.post("/review")

async def memory_review_decide(req: MemoryReviewIn, _user=Depends(current_user)):
    if req.action == "approve":
        return ok(memory_store.approve_item(req.id, _user["username"]))
    if req.action in {"deny", "reject"}:
        return ok(memory_store.reject_item(req.id, _user["username"]))
    raise ValueError("memory review action must be approve or reject")

@memory_router.post("/search")

async def memory_search(req: MemorySearchIn, _user=Depends(current_user)):
    return ok(memory_store.search(req.query, req.limit, _user["username"]))

rag_router = APIRouter(prefix="/api", tags=["rag", "graph"])


class RagIn(CamelModel):
    path: str = "."
    label: str | None = None

class RagSearchIn(CamelModel):
    query: str
    limit: int = 6
    path: str | None = None

class GraphSearchIn(CamelModel):
    query: str
    limit: int = 12

class GraphBuildIn(CamelModel):
    path: str | None = None

class GraphRelationsIn(CamelModel):
    entity: str
    relation: str | None = None
    direction: str = "both"
    limit: int = 25


@rag_router.get("/rag/stats")

async def rag_stats(workspace_id: str | None = None, _user=Depends(current_user)):
    # stats() is cheap once the summary cache is warm, but the first call
    # after a cache-format change (see STATS_SUMMARY_VERSION) rebuilds it
    # from the full index -- multiple seconds on a real workspace. Run off
    # the event loop so that one-time cost can't stall every other request,
    # same reasoning as rag_ingest below.
    return ok(await asyncio.to_thread(rag.stats, workspace_id))

@rag_router.post("/rag/ingest")

async def rag_ingest(req: RagIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    # Walking + parsing a real workspace can take a while even after
    # SKIP_DIRS pruning; run it off the event loop so it can't stall every
    # other request (health checks included) for the duration.
    return ok(await asyncio.to_thread(rag.ingest, req.path, req.label))

@rag_router.post("/rag/search")

async def rag_search(req: RagSearchIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(rag.search(req.query, req.limit, req.path))

@rag_router.get("/graph/stats")

async def graph_stats(_user=Depends(current_user)):
    return ok(graphify.stats())

@rag_router.post("/graph/build")

async def graph_build(req: GraphBuildIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    # build() calls rag.ingest() itself when the index is empty -- same
    # reasoning as /rag/ingest above.
    return ok(await asyncio.to_thread(graphify.build, req.path))

@rag_router.post("/graph/search")

async def graph_search(req: GraphSearchIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(graphify.search(req.query, req.limit))

@rag_router.post("/graph/relations")

async def graph_relations(req: GraphRelationsIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(graphify.query_relations(req.entity, req.relation, req.direction, req.limit))

router.include_router(sessions_router)
router.include_router(tasks_router)
router.include_router(skills_router)
router.include_router(memory_router)
router.include_router(rag_router)
