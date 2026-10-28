import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import Field

from backend.api.core import CamelModel, require_admin
from backend.core import training
from backend.core.response import ok

router = APIRouter(prefix="/api/training", tags=["training"])


class TrainingInput(CamelModel):
    name: str = Field(default="LoRA fine-tune", min_length=1, max_length=100)
    model_path: str = Field(min_length=1, max_length=4096)
    dataset: str = Field(min_length=1, max_length=4 * 1024 * 1024)
    max_steps: int = Field(default=60, ge=1, le=10000)
    learning_rate: float = Field(default=0.0002, gt=0, le=0.01)
    rank: int = Field(default=16, ge=4, le=64)
    max_length: int = Field(default=1024, ge=128, le=8192)


@router.get("")
async def status(_user=Depends(require_admin)):
    return ok({"capability": await asyncio.to_thread(training.capability), "jobs": training.jobs()})


@router.post("/preflight")
async def preflight(req: TrainingInput, _user=Depends(require_admin)):
    return ok(await asyncio.to_thread(training.preflight, req.model_path, req.dataset))


@router.get("/jobs")
async def list_jobs(_user=Depends(require_admin)):
    return ok({"jobs": training.jobs()})


@router.post("/jobs")
async def start(req: TrainingInput, user=Depends(require_admin)):
    return ok(await asyncio.to_thread(training.start, user["username"], req.model_dump()))


@router.post("/jobs/{job_id}/cancel")
async def cancel(job_id: str, _user=Depends(require_admin)):
    return ok(training.cancel(job_id))


@router.get("/jobs/{job_id}/adapter")
async def export_adapter(job_id: str, _user=Depends(require_admin)):
    path = await asyncio.to_thread(training.export_adapter, job_id)
    return FileResponse(path, filename=f"{job_id}-adapter.zip", media_type="application/zip")
