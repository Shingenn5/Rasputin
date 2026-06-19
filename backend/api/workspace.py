from fastapi import APIRouter, Depends
from backend.core.response import ok
from backend.api.common import CamelModel, current_user
from backend.core import security
from backend.core import audit
from backend import workspace

router = APIRouter(prefix="/api", tags=["workspace"])

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

@router.get("/workspace")
async def workspace_get(_user=Depends(current_user)):
    return ok(workspace.get_active())

@router.get("/workspaces")
async def workspaces_get(_user=Depends(current_user)):
    return ok(workspace.all_workspaces())

@router.get("/workspace/roots")
async def workspace_roots(_user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(workspace.approved_roots())

@router.post("/workspace/browse")
async def workspace_browse(req: WorkspaceBrowseIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(workspace.browse(req.root_id, req.path))

@router.post("/workspace/preview-file")
async def workspace_preview_file(req: WorkspacePreviewIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(workspace.preview_file(req.root_id, req.path, req.max_bytes))

@router.post("/workspace/search")
async def workspace_search(req: WorkspaceSearchIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(workspace.search_files(req.root_id, req.path, req.query, req.max_results, req.include_content))

@router.post("/workspace/approve")
async def workspace_approve(req: WorkspaceApproveIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    item = workspace.approve(req.path, req.name, req.read_only)
    audit.log("workspace_approved", {"path": req.path, "name": req.name, "read_only": req.read_only})
    return ok(item)

@router.post("/workspace/mount-plan")
async def workspace_mount_plan(req: WorkspaceMountIn, _user=Depends(current_user)):
    return ok(workspace.mount_plan(req.host_path, req.name, req.read_only))

@router.post("/workspace/mount-apply")
async def workspace_mount_apply(req: WorkspaceMountIn, _user=Depends(current_user)):
    security.require("allow_docker_control")
    plan = workspace.save_mount_request(req.host_path, req.name, req.read_only)
    audit.log("workspace_mount_requested", plan)
    return ok(plan)

@router.post("/workspace/mutation-preview")
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

@router.post("/workspace/add")
async def workspace_add(req: WorkspaceIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    profile = {"read": True, "write": not bool(req.read_only), "reorganize": False}
    return ok(workspace.add(req.path, req.name, profile))

@router.post("/workspace/remove")
async def workspace_remove(req: WorkspaceRemoveIn, _user=Depends(current_user)):
    return ok(workspace.remove(req.workspace_id))

@router.post("/workspace/select")
async def workspace_select(req: WorkspaceIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(workspace.select(req.path))

@router.post("/workspace/list")
async def workspace_list(req: WorkspaceIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(workspace.list_dirs(req.path))
