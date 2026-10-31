"""Authenticated approval-bound execution of explicit workspace snapshots."""
import asyncio

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from backend.api.core import CamelModel, current_user, require_admin, require_member
from backend.core import sandbox_execution as execution
from backend.core import sandbox_runtime
from backend.core.response import ok

router = APIRouter(prefix="/api/execution", tags=["execution"])


def _public_request(request):
    # Artifact paths are values so the application's camel-case serializer does
    # not rename filenames containing underscores.
    plan = request["plan"]
    return {**request, "plan": {**plan, "files": [{"path": path, **metadata} for path, metadata in plan["files"].items()]}}


class ToolchainInput(CamelModel):
    executable: str = Field(min_length=1, max_length=4096)


class ExecutionInput(CamelModel):
    workspace: str = Field(min_length=1, max_length=4096)
    files: list[str] = Field(min_length=1, max_length=256)
    arguments: list[str] = Field(min_length=1, max_length=64)
    task_id: str | None = None
    timeout: int = Field(default=30, ge=1, le=60)


@router.get("")
async def capability(_user=Depends(current_user)):
    return ok(execution.capability())


@router.post("/toolchain")
async def configure(req: ToolchainInput, user=Depends(require_admin)):
    return ok(await asyncio.to_thread(execution.configure_toolchain, req.executable, user["username"]))


@router.get("/runtime")
async def runtime_status(_user=Depends(current_user)):
    return ok(await asyncio.to_thread(sandbox_runtime.status))


@router.post("/runtime/install")
async def runtime_install(user=Depends(require_admin)):
    return ok(await asyncio.to_thread(sandbox_runtime.start, user["username"]))


@router.post("/runtime/cancel")
async def runtime_cancel(user=Depends(require_admin)):
    return ok(sandbox_runtime.cancel(user["username"]))


@router.post("/requests")
async def create(req: ExecutionInput, user=Depends(require_member)):
    return ok(_public_request(await asyncio.to_thread(execution.create_request, user["username"], req.workspace,
                                                     req.files, req.arguments, task_id=req.task_id, timeout=req.timeout)))


@router.get("/approvals/{approval_id}")
async def review(approval_id: str, user=Depends(require_admin)):
    return ok(_public_request(await asyncio.to_thread(execution.review_approval, approval_id, user["username"])))


@router.get("/approvals/{approval_id}/file")
async def review_file(approval_id: str, path: str = Query(min_length=1, max_length=4096), user=Depends(require_admin)):
    return ok(await asyncio.to_thread(execution.review_file, approval_id, user["username"], path))


@router.get("/requests/{request_id}")
async def get(request_id: str, user=Depends(current_user)):
    return ok(_public_request(execution.get_request(request_id, user["username"])))


@router.post("/requests/{request_id}/execute")
async def execute(request_id: str, user=Depends(require_member)):
    return ok(await asyncio.to_thread(execution.execute_request, request_id, user["username"]))


@router.post("/requests/{request_id}/cancel")
async def cancel(request_id: str, user=Depends(require_member)):
    return ok(_public_request(execution.cancel_request(request_id, user["username"])))
