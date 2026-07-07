from fastapi import APIRouter, Depends, HTTPException
from backend.api.core import CamelModel, current_user, hub
from backend import archive
from backend import trials
from backend import warsat
from backend.core import workspace
from backend.core import host_fs
from backend.core import audit
from backend.core import security
from backend.core.response import ok, fail, camelize, AppError, _camel_code
from fastapi.responses import StreamingResponse
import asyncio
import json

router = APIRouter()

warsat_router = APIRouter(prefix="/api/warsat", tags=["warsat"])


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

@warsat_router.get("/status")

async def warsat_status(_user=Depends(current_user)):
    return ok(warsat.summary())

@warsat_router.get("/protocols")

async def warsat_protocols(_user=Depends(current_user)):
    return ok(warsat.list_protocols())

@warsat_router.get("/runtimes")

async def warsat_runtimes(_user=Depends(current_user)):
    return ok(await asyncio.to_thread(warsat.containers))

@warsat_router.get("/hardware")

async def warsat_hardware(_user=Depends(current_user)):
    return ok(await asyncio.to_thread(warsat.hardware_probe))

@warsat_router.post("/plan")

async def warsat_plan(req: WarsatPlanIn, _user=Depends(current_user)):
    return ok(await asyncio.to_thread(warsat.make_plan, req.model_dump()))

@warsat_router.post("/deploy")

async def warsat_deploy(req: WarsatDeployIn, _user=Depends(current_user)):
    # Deploys that will actually execute (fresh approval in hand, or a prior
    # approval grant for the identical deployment) pull images and boot
    # containers, which can take minutes: stream NDJSON progress so the UI
    # never sits on a silent request. Otherwise this only creates the
    # approval request — fast, so answer synchronously.
    will_execute = bool(req.approval_id) or await asyncio.to_thread(warsat.has_deploy_grant, req.plan)
    if not will_execute:
        return ok(await asyncio.to_thread(warsat.deploy, req.plan, req.approval_id))

    def gen():
        try:
            for update in warsat.deploy_stream(req.plan, req.approval_id):
                yield json.dumps({**update, "data": camelize(update.get("data"))}) + "\n"
        except AppError as exc:
            yield json.dumps({
                "ok": False,
                "final": True,
                "data": None,
                "error": {"code": _camel_code(exc.code), "message": exc.message},
            }) + "\n"
        except Exception as exc:  # noqa: BLE001 — surface anything to the stream
            yield json.dumps({
                "ok": False,
                "final": True,
                "data": None,
                "error": {"code": "warsatDeployFailed", "message": str(exc)},
            }) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")

@warsat_router.post("/logs")

async def warsat_logs(req: WarsatContainerIn, _user=Depends(current_user)):
    return ok(await asyncio.to_thread(warsat.logs, req.container_name, req.limit))

@warsat_router.post("/stop")

async def warsat_stop(req: WarsatContainerIn, _user=Depends(current_user)):
    return ok(await asyncio.to_thread(warsat.stop, req.container_name, req.approval_id))

@warsat_router.post("/restart")

async def warsat_restart(req: WarsatContainerIn, _user=Depends(current_user)):
    return ok(await asyncio.to_thread(warsat.restart, req.container_name, req.approval_id))

@warsat_router.get("/discover")

async def warsat_discover(_user=Depends(current_user)):
    """Scan all running Docker containers for OpenAI/Ollama-compatible AI model endpoints."""
    return ok(await asyncio.to_thread(warsat.discover))

class WarsatImportDiscoveredIn(CamelModel):
    model_id: str
    base_url: str
    container_name: str
    protocol_hint: str = "openai-compatible"

@warsat_router.post("/import-discovered")

async def warsat_import_discovered(req: WarsatImportDiscoveredIn, _user=Depends(current_user)):
    """Register a discovered container model endpoint into the model registry."""
    return ok(await asyncio.to_thread(
        warsat.import_discovered,
        req.model_id, req.base_url, req.container_name, req.protocol_hint,
    ))

@warsat_router.get("/system-metrics")

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

        if not gpu_metrics:
            # Containerized wrapper: no local nvidia-smi — read GPU stats
            # through Docker instead.
            try:
                gpu_metrics = warsat.gpu_live_metrics_via_docker()
            except Exception:
                gpu_metrics = []

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

@warsat_router.get("/agent-state")

async def warsat_agent_state(_user=Depends(current_user)):
    active_tasks = [t for t in hub.all_tasks(limit=50) if t.get("status") in ("queued", "running", "paused")]
    return ok({
        "active_agents": len(active_tasks),
        "tasks": active_tasks
    })

trials_router = APIRouter(prefix="/api/trials", tags=["trials"])


class TrialCompareIn(CamelModel):
    prompt: str
    model_keys: list[str] | None = None

class TrialRoutingIn(CamelModel):
    output_id: str
    mode: str

class CodingTrialIn(CamelModel):
    objective: str
    code: str | None = ""
    tests: str | None = ""
    expect: list[str] | None = None
    model_keys: list[str] | None = None

class TrialPinRoleIn(CamelModel):
    output_id: str
    role: str = "coder"

class ExperimentIn(CamelModel):
    name: str
    type: str = "model"
    config: dict | None = None
    workspace: str = ""
    tags: list[str] | None = None

class DatasetIn(CamelModel):
    name: str
    type: str = "questions"
    entries: list[dict] | None = None
    tags: list[str] | None = None

class BenchmarkIn(CamelModel):
    name: str
    experiment_ids: list[str] | None = None
    config: dict | None = None

class ComparisonIn(CamelModel):
    name: str = ""
    experiment_ids: list[str] | None = None

class ReportIn(CamelModel):
    name: str
    type: str = "experiment"
    experiment_ids: list[str] | None = None

class ScorecardIn(CamelModel):
    experiment_id: str
    name: str | None = None

@trials_router.get("")

async def trials_get(_user=Depends(current_user)):
    return ok(trials.runs())

@trials_router.post("/compare")

async def trials_compare(req: TrialCompareIn, _user=Depends(current_user)):
    return ok(await trials.compare(req.prompt, req.model_keys or []))

@trials_router.post("/coding-compare")

async def trials_coding_compare(req: CodingTrialIn, _user=Depends(current_user)):
    return ok(await trials.coding_compare(
        req.objective, req.code or "", req.tests or "", req.expect, req.model_keys or [],
    ))

@trials_router.post("/{run_id}/reveal")

async def trials_reveal(run_id: str, _user=Depends(current_user)):
    return ok(trials.reveal(run_id))

@trials_router.post("/{run_id}/routing")

async def trials_routing(run_id: str, req: TrialRoutingIn, _user=Depends(current_user)):
    result = trials.save_routing(run_id, req.output_id, req.mode)
    audit.log("trial_route_saved", result["route"])
    return ok(result)

@trials_router.post("/{run_id}/pin-role")

async def trials_pin_role(run_id: str, req: TrialPinRoleIn, _user=Depends(current_user)):
    return ok(trials.pin_role(run_id, req.output_id, req.role))


# ── Trials V3: Experiments ──

@trials_router.get("/experiments")

async def trials_experiments(type: str | None = None, status: str | None = None, _user=Depends(current_user)):
    return ok(trials.list_experiments(type_filter=type, status_filter=status))

@trials_router.post("/experiments")

async def trials_create_experiment(req: ExperimentIn, _user=Depends(current_user)):
    exp = trials.create_experiment(
        name=req.name, exp_type=req.type, config=req.config,
        workspace=req.workspace, owner=_user.get("username", "admin"), tags=req.tags,
    )
    audit.log("trial_experiment_created", {"id": exp["id"], "type": req.type})
    return ok(exp)

@trials_router.get("/experiments/{experiment_id}")

async def trials_get_experiment(experiment_id: str, _user=Depends(current_user)):
    exp = trials.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return ok(exp)

@trials_router.post("/experiments/{experiment_id}/run")

async def trials_run_experiment(experiment_id: str, _user=Depends(current_user)):
    result = await trials.run_experiment(experiment_id)
    return ok(result)

@trials_router.post("/experiments/{experiment_id}/cancel")

async def trials_cancel_experiment(experiment_id: str, _user=Depends(current_user)):
    result = trials.cancel_experiment(experiment_id)
    return ok(result)

@trials_router.delete("/experiments/{experiment_id}")

async def trials_delete_experiment(experiment_id: str, _user=Depends(current_user)):
    return ok(trials.delete_experiment(experiment_id))


# ── Trials V3: Datasets ──

@trials_router.get("/datasets")

async def trials_datasets(_user=Depends(current_user)):
    return ok(trials.list_datasets())

@trials_router.post("/datasets")

async def trials_create_dataset(req: DatasetIn, _user=Depends(current_user)):
    ds = trials.create_dataset(name=req.name, ds_type=req.type, entries=req.entries, tags=req.tags)
    audit.log("trial_dataset_created", {"id": ds["id"], "name": req.name})
    return ok(ds)

@trials_router.get("/datasets/{dataset_id}")

async def trials_get_dataset(dataset_id: str, _user=Depends(current_user)):
    ds = trials.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return ok(ds)

@trials_router.delete("/datasets/{dataset_id}")

async def trials_delete_dataset(dataset_id: str, _user=Depends(current_user)):
    return ok(trials.delete_dataset(dataset_id))

@trials_router.post("/datasets/seed")

async def trials_seed_datasets(_user=Depends(current_user)):
    return ok(trials.seed_datasets())


# ── Trials V3: Benchmarks ──

@trials_router.get("/benchmarks")

async def trials_benchmarks(_user=Depends(current_user)):
    return ok(trials.list_benchmarks())

@trials_router.post("/benchmarks")

async def trials_create_benchmark(req: BenchmarkIn, _user=Depends(current_user)):
    bm = trials.create_benchmark(name=req.name, experiment_ids=req.experiment_ids, config=req.config)
    audit.log("trial_benchmark_created", {"id": bm["id"], "name": req.name})
    return ok(bm)

@trials_router.get("/benchmarks/{benchmark_id}")

async def trials_get_benchmark(benchmark_id: str, _user=Depends(current_user)):
    bm = trials.get_benchmark(benchmark_id)
    if not bm:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return ok(bm)


# ── Trials V3: Comparisons ──

@trials_router.get("/comparisons")

async def trials_comparisons(_user=Depends(current_user)):
    return ok(trials.list_comparisons())

@trials_router.post("/comparisons")

async def trials_create_comparison(req: ComparisonIn, _user=Depends(current_user)):
    name = req.name or f"Comparison {len(trials.list_comparisons()) + 1}"
    comp = trials.create_comparison(name=name, experiment_ids=req.experiment_ids)
    audit.log("trial_comparison_created", {"id": comp["id"]})
    return ok(comp)


# ── Trials V3: Scorecards ──

@trials_router.get("/scorecards")

async def trials_scorecards(_user=Depends(current_user)):
    return ok(trials.list_scorecards())

@trials_router.post("/scorecards")

async def trials_create_scorecard(req: ScorecardIn, _user=Depends(current_user)):
    sc = trials.generate_scorecard(req.experiment_id, name=req.name)
    return ok(sc)


# ── Trials V3: Reports ──

@trials_router.get("/reports")

async def trials_reports(_user=Depends(current_user)):
    return ok(trials.list_reports())

@trials_router.post("/reports")

async def trials_create_report(req: ReportIn, _user=Depends(current_user)):
    rpt = trials.generate_report(name=req.name, report_type=req.type, experiment_ids=req.experiment_ids)
    return ok(rpt)

@trials_router.get("/reports/{report_id}")

async def trials_get_report(report_id: str, _user=Depends(current_user)):
    rpt = trials.get_report(report_id)
    if not rpt:
        raise HTTPException(status_code=404, detail="Report not found")
    return ok(rpt)

workspace_router = APIRouter(prefix="/api", tags=["workspace"])


class WorkspaceIn(CamelModel):
    path: str = "."
    name: str | None = None
    read_only: bool = True

class WorkspaceRemoveIn(CamelModel):
    workspace_id: str

class WorkspaceTrustIn(CamelModel):
    workspace_id: str
    trusted: bool

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

class HostBrowseIn(CamelModel):
    path: str | None = None

class MountRequestRemoveIn(CamelModel):
    host_path: str

class WorkspaceMutationPreviewIn(CamelModel):
    kind: str
    workspace_path: str | None = "."
    path: str | None = None
    source: str | None = None
    target: str | None = None
    content: str | None = None
    max_items: int = 40

@workspace_router.get("/workspace")

async def workspace_get(_user=Depends(current_user)):
    return ok(workspace.get_active())

@workspace_router.get("/workspaces")

async def workspaces_get(_user=Depends(current_user)):
    return ok(workspace.all_workspaces())

@workspace_router.get("/workspace/roots")

async def workspace_roots(_user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(workspace.approved_roots())

@workspace_router.post("/workspace/browse")

async def workspace_browse(req: WorkspaceBrowseIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(workspace.browse(req.root_id, req.path))

@workspace_router.post("/workspace/preview-file")

async def workspace_preview_file(req: WorkspacePreviewIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(workspace.preview_file(req.root_id, req.path, req.max_bytes))

@workspace_router.post("/workspace/search")

async def workspace_search(req: WorkspaceSearchIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(workspace.search_files(req.root_id, req.path, req.query, req.max_results, req.include_content))

@workspace_router.post("/workspace/approve")

async def workspace_approve(req: WorkspaceApproveIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    item = workspace.approve(req.path, req.name, req.read_only)
    audit.log("workspace_approved", {"path": req.path, "name": req.name, "read_only": req.read_only})
    return ok(item)

@workspace_router.post("/workspace/host-browse")

async def workspace_host_browse(req: HostBrowseIn, _user=Depends(current_user)):
    # Same grant as mount-apply: picking a host folder to mount is only
    # possible when the wrapper may drive Docker, and every listing is audited.
    security.require("allow_docker_control")
    if not req.path:
        return ok(host_fs.roots())
    listing = host_fs.browse(req.path)
    audit.log("workspace_host_browse", {"path": listing["path"], "entries": len(listing["entries"])})
    return ok(listing)

@workspace_router.post("/workspace/mount-plan")

async def workspace_mount_plan(req: WorkspaceMountIn, _user=Depends(current_user)):
    return ok(workspace.mount_plan(req.host_path, req.name, req.read_only))

@workspace_router.post("/workspace/mount-apply")

async def workspace_mount_apply(req: WorkspaceMountIn, _user=Depends(current_user)):
    security.require("allow_docker_control")
    plan = workspace.save_mount_request(req.host_path, req.name, req.read_only)
    audit.log("workspace_mount_requested", plan)
    return ok(plan)

@workspace_router.get("/workspace/mount-requests")

async def workspace_mount_requests_get(_user=Depends(current_user)):
    security.require("allow_docker_control")
    return ok(workspace.list_mount_requests())

@workspace_router.post("/workspace/mount-requests/remove")

async def workspace_mount_requests_remove(req: MountRequestRemoveIn, _user=Depends(current_user)):
    security.require("allow_docker_control")
    result = workspace.remove_mount_request(req.host_path)
    audit.log("workspace_mount_request_removed", {"hostPath": req.host_path})
    return ok(result)

@workspace_router.post("/workspace/mutation-preview")

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

@workspace_router.post("/workspace/add")

async def workspace_add(req: WorkspaceIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    profile = {"read": True, "write": not bool(req.read_only), "reorganize": False}
    return ok(workspace.add(req.path, req.name, profile))

@workspace_router.post("/workspace/remove")

async def workspace_remove(req: WorkspaceRemoveIn, _user=Depends(current_user)):
    return ok(workspace.remove(req.workspace_id))

@workspace_router.post("/workspace/trust")

async def workspace_trust(req: WorkspaceTrustIn, _user=Depends(current_user)):
    security.require("allow_file_write")
    item = workspace.set_trusted(req.workspace_id, req.trusted)
    audit.log("workspace_trust_changed", {"workspace_id": req.workspace_id, "trusted": req.trusted})
    return ok(item)

@workspace_router.post("/workspace/select")

async def workspace_select(req: WorkspaceIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(workspace.select(req.path))

@workspace_router.post("/workspace/list")

async def workspace_list(req: WorkspaceIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(workspace.list_dirs(req.path))

archive_router = APIRouter(prefix="/api/archive", tags=["archive"])


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


@archive_router.get("/sessions")

async def archive_sessions(_user=Depends(current_user)):
    return ok(archive.sessions())

@archive_router.get("/items")

async def archive_items_get(type: str = None, workspace: str = None, search: str = None, _user=Depends(current_user)):
    return ok([item.model_dump() for item in archive.ArchiveService.get_items({"type": type, "workspace": workspace, "search": search})])

@archive_router.post("/items")

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

@archive_router.delete("/items/{item_id}")

async def archive_items_delete(item_id: str, _user=Depends(current_user)):
    archive.ArchiveService.delete_item(item_id)
    return ok()

@archive_router.post("/items/{item_id}/restore")

async def archive_items_restore(item_id: str, _user=Depends(current_user)):
    success = archive.ArchiveService.restore_item(item_id)
    if not success:
        return fail("Item not found or could not be restored")
    return ok()

@archive_router.post("/sessions")

async def archive_sessions_save(req: ArchiveSessionIn, _user=Depends(current_user)):
    return ok(archive.save_session(req.model_dump()))

@archive_router.post("/export")

async def archive_export(req: ArchiveExportIn, _user=Depends(current_user)):
    security.require("allow_file_write")
    return ok(archive.export_session(req.id, req.folder))

@archive_router.post("/citations")

async def archive_citations(req: ArchiveCitationIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(archive.citation_search(req.query, req.path, req.limit))

router.include_router(warsat_router)
router.include_router(trials_router)
router.include_router(workspace_router)
router.include_router(archive_router)
