"""Experiment execution engine for Trials."""

import asyncio
import time

from backend.models import providers as model_providers
from backend.models import registry as model_registry

async def _chat(model_key, messages, temperature=0.2, tools=None):
    cfg = model_registry.get_model(model_key) or model_registry.get_model("dry-run")
    if model_key == "dry-run" or not cfg or cfg.get("provider") == "mock":
        user_msg = messages[-1]["content"] if messages else ""
        return f"This is a dry-run response to: {user_msg}", []
        
    try:
        text, calls = await model_providers.chat(cfg, messages, 2048, temperature, tools=tools)
        return text
    except Exception as exc:
        raise RuntimeError(str(exc)) from None

from backend.models import registry as model_registry
from backend.core import runtime_store as rts
from backend.core import audit
from . import store
from .models import EXPERIMENT_TYPES


async def run_experiment(experiment_id):
    """Run an experiment: execute each model against the prompt/dataset and collect metrics."""
    exp = store.get_experiment(experiment_id)
    if not exp:
        raise ValueError("Experiment not found")
    if exp["status"] not in ("draft", "completed", "failed"):
        raise ValueError(f"Cannot run experiment in '{exp['status']}' state")

    store.update_experiment(experiment_id, status="running")
    config = exp.get("config") or {}
    exp_type = exp.get("type", "model")

    try:
        if exp_type == "quick_compare":
            result = await _run_quick_compare(experiment_id, config)
        elif exp_type == "model":
            result = await _run_model_experiment(experiment_id, config)
        elif exp_type == "prompt":
            result = await _run_prompt_experiment(experiment_id, config)
        else:
            result = await _run_model_experiment(experiment_id, config)

        # Aggregate metrics from the run
        store.update_experiment(experiment_id, status="completed", metrics=result.get("metrics", {}))
        audit.log("trial_experiment_completed", {"experimentId": experiment_id, "type": exp_type})
        return store.get_experiment(experiment_id)

    except Exception as exc:
        store.update_experiment(experiment_id, status="failed", metrics={"error": str(exc)})
        audit.log("trial_experiment_failed", {"experimentId": experiment_id, "error": str(exc)})
        raise


def cancel_experiment(experiment_id):
    """Cancel a running experiment."""
    exp = store.get_experiment(experiment_id)
    if not exp:
        raise ValueError("Experiment not found")
    store.update_experiment(experiment_id, status="cancelled")
    audit.log("trial_experiment_cancelled", {"experimentId": experiment_id})
    return store.get_experiment(experiment_id)


async def run_quick_compare(prompt, model_keys=None):
    """Legacy quick-compare: create an experiment, run it, return the run."""
    prompt = str(prompt or "").strip()
    if not prompt:
        raise ValueError("Trial prompt required")

    chosen = [key for key in (model_keys or []) if model_registry.get_model(key)]
    if not chosen:
        chosen = ["dry-run"]
    chosen = chosen[:4]

    exp = store.create_experiment(
        name=f"Quick compare: {prompt[:60]}",
        exp_type="quick_compare",
        config={"prompt": prompt, "modelKeys": chosen},
    )

    store.update_experiment(exp["id"], status="running")
    run = store.create_run(exp["id"], inputs={"prompt": prompt, "modelKeys": chosen})

    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    outputs = []
    total_start = time.perf_counter()

    for index, key in enumerate(chosen):
        started = time.perf_counter()
        try:
            text = await _chat(key, [{"role": "user", "content": prompt}], temperature=0.2)
            status = "done"
            error = ""
        except Exception as exc:
            text = ""
            status = "error"
            error = str(exc)
        outputs.append({
            "id": rts.new_id("trialout"),
            "label": labels[index],
            "model_key": key,
            "status": status,
            "text": text,
            "error": error,
            "latency_ms": round((time.perf_counter() - started) * 1000),
        })
        await asyncio.sleep(0)

    total_ms = round((time.perf_counter() - total_start) * 1000)
    metrics = {
        "totalDurationMs": total_ms,
        "modelCount": len(chosen),
        "successCount": sum(1 for o in outputs if o["status"] == "done"),
        "errorCount": sum(1 for o in outputs if o["status"] == "error"),
    }

    store.update_run(
        run["id"],
        status="completed",
        outputs=outputs,
        metrics=metrics,
        duration_ms=total_ms,
    )
    store.update_experiment(exp["id"], status="completed", metrics=metrics)
    audit.log("trial_quick_compare", {"experimentId": exp["id"], "models": chosen})

    return {
        "experiment": store.get_experiment(exp["id"]),
        "run": store.get_run(run["id"]),
    }


async def _run_model_experiment(experiment_id, config):
    """Benchmark one or more models against a prompt or dataset."""
    prompt = config.get("prompt", "")
    model_keys = config.get("modelKeys") or config.get("model_keys") or []
    dataset_id = config.get("datasetId") or config.get("dataset_id")

    # Get prompts from dataset if specified
    prompts = []
    if dataset_id:
        ds = store.get_dataset(dataset_id)
        if ds:
            prompts = [e.get("prompt") or e.get("question") or str(e) for e in (ds.get("entries") or []) if e]
    if not prompts and prompt:
        prompts = [prompt]
    if not prompts:
        prompts = ["Hello, what is 2+2?"]

    chosen = [key for key in model_keys if model_registry.get_model(key)]
    if not chosen:
        chosen = ["dry-run"]
    chosen = chosen[:8]

    run = store.create_run(experiment_id, inputs={"prompts": prompts, "modelKeys": chosen})
    all_outputs = []
    total_start = time.perf_counter()

    for model_key in chosen:
        model_outputs = []
        for p in prompts[:20]:  # cap at 20 prompts
            started = time.perf_counter()
            try:
                text = await _chat(model_key, [{"role": "user", "content": p}], temperature=0.2)
                status = "done"
                error = ""
            except Exception as exc:
                text = ""
                status = "error"
                error = str(exc)
            latency = round((time.perf_counter() - started) * 1000)
            model_outputs.append({
                "prompt": p,
                "text": text,
                "status": status,
                "error": error,
                "latencyMs": latency,
            })
            await asyncio.sleep(0)

        avg_latency = round(sum(o["latencyMs"] for o in model_outputs) / max(len(model_outputs), 1))
        success_rate = sum(1 for o in model_outputs if o["status"] == "done") / max(len(model_outputs), 1)
        all_outputs.append({
            "modelKey": model_key,
            "modelName": (model_registry.get_model(model_key) or {}).get("name", model_key),
            "outputs": model_outputs,
            "avgLatencyMs": avg_latency,
            "successRate": round(success_rate, 3),
            "totalPrompts": len(model_outputs),
        })

    total_ms = round((time.perf_counter() - total_start) * 1000)
    metrics = {
        "totalDurationMs": total_ms,
        "modelCount": len(chosen),
        "promptCount": len(prompts),
        "results": [{
            "modelKey": o["modelKey"],
            "avgLatencyMs": o["avgLatencyMs"],
            "successRate": o["successRate"],
        } for o in all_outputs],
    }

    store.update_run(run["id"], status="completed", outputs=all_outputs, metrics=metrics, duration_ms=total_ms)
    return {"metrics": metrics}


async def _run_prompt_experiment(experiment_id, config):
    """A/B prompt testing: run two prompts against the same model, compare outputs."""
    prompt_a = config.get("promptA") or config.get("prompt_a") or ""
    prompt_b = config.get("promptB") or config.get("prompt_b") or ""
    model_key = config.get("modelKey") or config.get("model_key") or "dry-run"

    if not prompt_a or not prompt_b:
        raise ValueError("Prompt A and Prompt B are both required for prompt experiments")

    run = store.create_run(experiment_id, inputs={"promptA": prompt_a, "promptB": prompt_b, "modelKey": model_key})
    outputs = []

    for label, prompt in [("A", prompt_a), ("B", prompt_b)]:
        started = time.perf_counter()
        try:
            text = await _chat(model_key, [{"role": "user", "content": prompt}], temperature=0.2)
            status = "done"
            error = ""
        except Exception as exc:
            text = ""
            status = "error"
            error = str(exc)
        latency = round((time.perf_counter() - started) * 1000)
        outputs.append({
            "label": label,
            "prompt": prompt,
            "text": text,
            "status": status,
            "error": error,
            "latencyMs": latency,
        })
        await asyncio.sleep(0)

    total_ms = sum(o["latencyMs"] for o in outputs)
    metrics = {
        "totalDurationMs": total_ms,
        "outputA": {"latencyMs": outputs[0]["latencyMs"], "status": outputs[0]["status"], "charCount": len(outputs[0]["text"])},
        "outputB": {"latencyMs": outputs[1]["latencyMs"], "status": outputs[1]["status"], "charCount": len(outputs[1]["text"])},
    }

    store.update_run(run["id"], status="completed", outputs=outputs, metrics=metrics, duration_ms=total_ms)
    return {"metrics": metrics}


async def _run_quick_compare(experiment_id, config):
    """Internal: run the quick-compare logic for an already-created experiment."""
    prompt = config.get("prompt", "")
    model_keys = config.get("modelKeys") or config.get("model_keys") or ["dry-run"]
    chosen = [key for key in model_keys if model_registry.get_model(key)] or ["dry-run"]

    run = store.create_run(experiment_id, inputs={"prompt": prompt, "modelKeys": chosen})
    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    outputs = []
    total_start = time.perf_counter()

    for index, key in enumerate(chosen):
        started = time.perf_counter()
        try:
            text = await _chat(key, [{"role": "user", "content": prompt}], temperature=0.2)
            status = "done"
            error = ""
        except Exception as exc:
            text = ""
            status = "error"
            error = str(exc)
        outputs.append({
            "id": rts.new_id("trialout"),
            "label": labels[index],
            "model_key": key,
            "status": status,
            "text": text,
            "error": error,
            "latency_ms": round((time.perf_counter() - started) * 1000),
        })
        await asyncio.sleep(0)

    total_ms = round((time.perf_counter() - total_start) * 1000)
    metrics = {
        "totalDurationMs": total_ms,
        "modelCount": len(chosen),
        "successCount": sum(1 for o in outputs if o["status"] == "done"),
        "errorCount": sum(1 for o in outputs if o["status"] == "error"),
    }

    store.update_run(run["id"], status="completed", outputs=outputs, metrics=metrics, duration_ms=total_ms)
    return {"metrics": metrics}
