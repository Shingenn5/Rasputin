import asyncio
from fastapi import APIRouter, Depends
from backend.core.response import ok, fail
from backend.api.common import CamelModel, current_user, hub
from backend import warsat

router = APIRouter(prefix="/api/warsat", tags=["warsat"])

class WarsatPlanIn(CamelModel):
    protocol_id: str
    model_ref: str | None = None
    model_path: str | None = None
    strength_profile: str | None = None
    context_window: int | None = None
    max_model_len: int | None = None
    gpu_memory_utilization: float | None = None
    gpu_layers: int | None = None
    tensor_parallel_size: int | None = None
    cpu_threads: int | None = None
    batch_size: int | None = None
    max_num_seqs: int | None = None
    dtype: str | None = None
    quantization: str | None = None
    kv_cache_dtype: str | None = None
    swap_space_gb: int | None = None
    memory_limit_gb: int | None = None
    cpu_limit: float | None = None
    shm_size_gb: int | None = None
    gpu_device: str | None = None
    host_port: int | None = None
    role: str | None = None
    container_name: str | None = None

class WarsatDeployIn(CamelModel):
    plan: dict
    approval_id: str | None = None

class WarsatContainerIn(CamelModel):
    container_name: str
    approval_id: str | None = None
    limit: int = 120

@router.get("/status")
async def warsat_status(_user=Depends(current_user)):
    return ok(warsat.summary())

@router.get("/protocols")
async def warsat_protocols(_user=Depends(current_user)):
    return ok(warsat.list_protocols())

@router.get("/runtimes")
async def warsat_runtimes(_user=Depends(current_user)):
    return ok(await asyncio.to_thread(warsat.containers))

@router.get("/hardware")
async def warsat_hardware(_user=Depends(current_user)):
    return ok(await asyncio.to_thread(warsat.hardware_probe))

@router.post("/plan")
async def warsat_plan(req: WarsatPlanIn, _user=Depends(current_user)):
    return ok(await asyncio.to_thread(warsat.make_plan, req.model_dump()))

@router.post("/deploy")
async def warsat_deploy(req: WarsatDeployIn, _user=Depends(current_user)):
    return ok(await asyncio.to_thread(warsat.deploy, req.plan, req.approval_id))

@router.post("/logs")
async def warsat_logs(req: WarsatContainerIn, _user=Depends(current_user)):
    return ok(await asyncio.to_thread(warsat.logs, req.container_name, req.limit))

@router.post("/stop")
async def warsat_stop(req: WarsatContainerIn, _user=Depends(current_user)):
    return ok(await asyncio.to_thread(warsat.stop, req.container_name, req.approval_id))

@router.post("/restart")
async def warsat_restart(req: WarsatContainerIn, _user=Depends(current_user)):
    return ok(await asyncio.to_thread(warsat.restart, req.container_name, req.approval_id))

@router.get("/system-metrics")
async def warsat_system_metrics(_user=Depends(current_user)):
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        gpu_metrics = []
        import shutil, subprocess
        if shutil.which("nvidia-smi"):
            try:
                res = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"],
                    text=True, timeout=2
                )
                for line in res.strip().split("\n"):
                    if not line: continue
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 6:
                        gpu_metrics.append({
                            "index": int(parts[0]),
                            "name": parts[1],
                            "utilization": float(parts[2]),
                            "memory_used_mb": float(parts[3]),
                            "memory_total_mb": float(parts[4]),
                            "temperature": float(parts[5])
                        })
            except Exception:
                pass

        return ok({
            "cpu": {"percent": cpu},
            "ram": {
                "percent": ram.percent,
                "used_gb": round(ram.used / (1024**3), 2),
                "total_gb": round(ram.total / (1024**3), 2)
            },
            "disk": {
                "percent": disk.percent,
                "used_gb": round(disk.used / (1024**3), 2),
                "total_gb": round(disk.total / (1024**3), 2)
            },
            "gpus": gpu_metrics
        })
    except ImportError:
        return fail("dependency_missing", "psutil is not installed", 500)
    except Exception as e:
        return fail("metrics_error", str(e), 500)

@router.get("/agent-state")
async def warsat_agent_state(_user=Depends(current_user)):
    active_tasks = [t for t in hub.all_tasks(limit=50) if t.get("status") in ("queued", "running", "paused")]
    return ok({
        "active_agents": len(active_tasks),
        "tasks": active_tasks
    })
