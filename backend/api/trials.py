from fastapi import APIRouter, Depends, HTTPException
from backend.core.response import ok
from backend.api.common import CamelModel, current_user
from backend import trials
from backend.core import audit

router = APIRouter(prefix="/api/trials", tags=["trials"])

class TrialCompareIn(CamelModel):
    prompt: str
    model_keys: list[str] | None = None

class TrialRoutingIn(CamelModel):
    output_id: str
    mode: str

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

@router.get("")
async def trials_get(_user=Depends(current_user)):
    return ok(trials.runs())

@router.post("/compare")
async def trials_compare(req: TrialCompareIn, _user=Depends(current_user)):
    return ok(await trials.compare(req.prompt, req.model_keys or []))

@router.post("/{run_id}/reveal")
async def trials_reveal(run_id: str, _user=Depends(current_user)):
    return ok(trials.reveal(run_id))

@router.post("/{run_id}/routing")
async def trials_routing(run_id: str, req: TrialRoutingIn, _user=Depends(current_user)):
    result = trials.save_routing(run_id, req.output_id, req.mode)
    audit.log("trial_route_saved", result["route"])
    return ok(result)


# ── Trials V3: Experiments ──

@router.get("/experiments")
async def trials_experiments(type: str | None = None, status: str | None = None, _user=Depends(current_user)):
    return ok(trials.list_experiments(type_filter=type, status_filter=status))

@router.post("/experiments")
async def trials_create_experiment(req: ExperimentIn, _user=Depends(current_user)):
    exp = trials.create_experiment(
        name=req.name, exp_type=req.type, config=req.config,
        workspace=req.workspace, owner=_user.get("username", "admin"), tags=req.tags,
    )
    audit.log("trial_experiment_created", {"id": exp["id"], "type": req.type})
    return ok(exp)

@router.get("/experiments/{experiment_id}")
async def trials_get_experiment(experiment_id: str, _user=Depends(current_user)):
    exp = trials.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return ok(exp)

@router.post("/experiments/{experiment_id}/run")
async def trials_run_experiment(experiment_id: str, _user=Depends(current_user)):
    result = await trials.run_experiment(experiment_id)
    return ok(result)

@router.post("/experiments/{experiment_id}/cancel")
async def trials_cancel_experiment(experiment_id: str, _user=Depends(current_user)):
    result = trials.cancel_experiment(experiment_id)
    return ok(result)

@router.delete("/experiments/{experiment_id}")
async def trials_delete_experiment(experiment_id: str, _user=Depends(current_user)):
    return ok(trials.delete_experiment(experiment_id))


# ── Trials V3: Datasets ──

@router.get("/datasets")
async def trials_datasets(_user=Depends(current_user)):
    return ok(trials.list_datasets())

@router.post("/datasets")
async def trials_create_dataset(req: DatasetIn, _user=Depends(current_user)):
    ds = trials.create_dataset(name=req.name, ds_type=req.type, entries=req.entries, tags=req.tags)
    audit.log("trial_dataset_created", {"id": ds["id"], "name": req.name})
    return ok(ds)

@router.get("/datasets/{dataset_id}")
async def trials_get_dataset(dataset_id: str, _user=Depends(current_user)):
    ds = trials.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return ok(ds)

@router.delete("/datasets/{dataset_id}")
async def trials_delete_dataset(dataset_id: str, _user=Depends(current_user)):
    return ok(trials.delete_dataset(dataset_id))

@router.post("/datasets/seed")
async def trials_seed_datasets(_user=Depends(current_user)):
    return ok(trials.seed_datasets())


# ── Trials V3: Benchmarks ──

@router.get("/benchmarks")
async def trials_benchmarks(_user=Depends(current_user)):
    return ok(trials.list_benchmarks())

@router.post("/benchmarks")
async def trials_create_benchmark(req: BenchmarkIn, _user=Depends(current_user)):
    bm = trials.create_benchmark(name=req.name, experiment_ids=req.experiment_ids, config=req.config)
    audit.log("trial_benchmark_created", {"id": bm["id"], "name": req.name})
    return ok(bm)

@router.get("/benchmarks/{benchmark_id}")
async def trials_get_benchmark(benchmark_id: str, _user=Depends(current_user)):
    bm = trials.get_benchmark(benchmark_id)
    if not bm:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return ok(bm)


# ── Trials V3: Comparisons ──

@router.get("/comparisons")
async def trials_comparisons(_user=Depends(current_user)):
    return ok(trials.list_comparisons())

@router.post("/comparisons")
async def trials_create_comparison(req: ComparisonIn, _user=Depends(current_user)):
    name = req.name or f"Comparison {len(trials.list_comparisons()) + 1}"
    comp = trials.create_comparison(name=name, experiment_ids=req.experiment_ids)
    audit.log("trial_comparison_created", {"id": comp["id"]})
    return ok(comp)


# ── Trials V3: Scorecards ──

@router.get("/scorecards")
async def trials_scorecards(_user=Depends(current_user)):
    return ok(trials.list_scorecards())

@router.post("/scorecards")
async def trials_create_scorecard(req: ScorecardIn, _user=Depends(current_user)):
    sc = trials.generate_scorecard(req.experiment_id, name=req.name)
    return ok(sc)


# ── Trials V3: Reports ──

@router.get("/reports")
async def trials_reports(_user=Depends(current_user)):
    return ok(trials.list_reports())

@router.post("/reports")
async def trials_create_report(req: ReportIn, _user=Depends(current_user)):
    rpt = trials.generate_report(name=req.name, report_type=req.type, experiment_ids=req.experiment_ids)
    return ok(rpt)

@router.get("/reports/{report_id}")
async def trials_get_report(report_id: str, _user=Depends(current_user)):
    rpt = trials.get_report(report_id)
    if not rpt:
        raise HTTPException(status_code=404, detail="Report not found")
    return ok(rpt)
