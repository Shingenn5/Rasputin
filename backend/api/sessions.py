from fastapi import APIRouter, Depends
from backend.core.response import ok
from backend.api.common import CamelModel, current_user, hub
from backend.core import audit

router = APIRouter(prefix="/api", tags=["sessions"])

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

@router.get("/sessions")
async def sessions_get(limit: int = 100, _user=Depends(current_user)):
    return ok(hub.sessions(limit))

@router.post("/sessions")
async def sessions_create(req: SessionCreateIn, _user=Depends(current_user)):
    detail = hub.create_session(req.title, req.workspace, req.model, req.mode, req.skill, req.folder)
    audit.log("session_created", {"session_id": detail["session"]["id"], "title": detail["session"]["title"]})
    return ok(detail)

@router.get("/sessions/{session_id}")
async def session_get(session_id: str, _user=Depends(current_user)):
    return ok(hub.session(session_id))

@router.get("/chat-folders")
async def chat_folders_get(_user=Depends(current_user)):
    return ok(hub.chat_folders())

@router.post("/chat-folders")
async def chat_folders_post(req: ChatFolderIn, _user=Depends(current_user)):
    audit.log("chat_folder_created", {"name": req.name})
    return ok(hub.create_chat_folder(req.name, req.color or ""))

@router.post("/sessions/{session_id}/folder")
async def session_folder_post(session_id: str, req: SessionFolderIn, _user=Depends(current_user)):
    folder = req.folder if req.folder is not None else req.folder_id
    audit.log("session_folder_changed", {"session_id": session_id, "folder": folder})
    return ok(hub.assign_session_folder(session_id, folder))
