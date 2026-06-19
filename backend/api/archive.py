from fastapi import APIRouter, Depends
from backend.core.response import ok, fail
from backend.api.common import CamelModel, current_user
from backend import archive
from backend.core import security

router = APIRouter(prefix="/api/archive", tags=["archive"])

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


@router.get("/sessions")
async def archive_sessions(_user=Depends(current_user)):
    return ok(archive.sessions())

@router.get("/items")
async def archive_items_get(type: str = None, workspace: str = None, search: str = None, _user=Depends(current_user)):
    return ok([item.model_dump() for item in archive.ArchiveService.get_items({"type": type, "workspace": workspace, "search": search})])

@router.post("/items")
async def archive_items_post(req: ArchiveItemIn, _user=Depends(current_user)):
    import time
    from backend.core import runtime_store as store
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

@router.delete("/items/{item_id}")
async def archive_items_delete(item_id: str, _user=Depends(current_user)):
    archive.ArchiveService.delete_item(item_id)
    return ok()

@router.post("/items/{item_id}/restore")
async def archive_items_restore(item_id: str, _user=Depends(current_user)):
    success = archive.ArchiveService.restore_item(item_id)
    if not success:
        return fail("Item not found or could not be restored")
    return ok()

@router.post("/sessions")
async def archive_sessions_save(req: ArchiveSessionIn, _user=Depends(current_user)):
    return ok(archive.save_session(req.model_dump()))

@router.post("/export")
async def archive_export(req: ArchiveExportIn, _user=Depends(current_user)):
    security.require("allow_file_write")
    return ok(archive.export_session(req.id, req.folder))

@router.post("/citations")
async def archive_citations(req: ArchiveCitationIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(archive.citation_search(req.query, req.path, req.limit))
