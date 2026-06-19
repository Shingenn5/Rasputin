from fastapi import APIRouter, Depends
from backend.core.response import ok
from backend.api.common import CamelModel, current_user
from backend.mcp import skills as skill_store

router = APIRouter(prefix="/api/skills", tags=["skills"])

class SkillImportIn(CamelModel):
    name: str
    content: str
    metadata: dict | None = None

class SkillFromSessionIn(CamelModel):
    session_id: str
    name: str | None = None
    save: bool = False

@router.get("")
async def skills(_user=Depends(current_user)):
    return ok(skill_store.list_skills())

@router.post("/create-from-session")
async def skills_create_from_session(req: SkillFromSessionIn, _user=Depends(current_user)):
    return ok(skill_store.create_from_session(req.session_id, req.name, req.save))

@router.post("/import")
async def skills_import(req: SkillImportIn, _user=Depends(current_user)):
    return ok(skill_store.import_skill(req.name, req.content, req.metadata or {}))

@router.get("/{name}")
async def skills_get(name: str, _user=Depends(current_user)):
    return ok(skill_store.get_skill(name))

@router.post("/{name}/enable")
async def skills_enable(name: str, _user=Depends(current_user)):
    return ok(skill_store.set_enabled(name, True))

@router.post("/{name}/disable")
async def skills_disable(name: str, _user=Depends(current_user)):
    return ok(skill_store.set_enabled(name, False))
