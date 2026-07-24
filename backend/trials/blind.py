"""Repeatable blinded comparison and evidence-backed fitness certificates."""

import random
import re
import time

from backend.core import audit
from backend.models import registry as model_registry
from . import store
from .engine import _chat


def _redact_identity(text, model_key, label):
    value = str(text or "")
    model = model_registry.get_model(model_key) or {}
    candidates = {str(model_key), str(model.get("name") or ""), str(model.get("model") or "")}
    for candidate in sorted((item for item in candidates if len(item) >= 3), key=len, reverse=True):
        value = re.sub(re.escape(candidate), f"Candidate {label}", value, flags=re.IGNORECASE)
    return value


def public_experiment(experiment, reveal=None):
    if not experiment or experiment.get("type") != "blind_compare":
        return experiment
    item = dict(experiment)
    config = dict(item.get("config") or {})
    revealed = bool(config.get("revealed")) if reveal is None else bool(reveal)
    mapping = dict(config.get("labelMap") or {})
    config.pop("modelKeys", None)
    config.pop("labelMap", None)
    config["revealed"] = revealed
    item["config"] = config
    safe_runs = []
    for run in item.get("runs") or []:
        safe_run = dict(run)
        inputs = dict(safe_run.get("inputs") or {})
        inputs.pop("modelKeys", None)
        safe_run["inputs"] = inputs
        safe_outputs = []
        for output in safe_run.get("outputs") or []:
            safe = {key: value for key, value in output.items() if key != "modelKey"}
            if revealed:
                safe["modelKey"] = output.get("modelKey") or mapping.get(output.get("label"))
            safe_outputs.append(safe)
        safe_run["outputs"] = safe_outputs
        safe_runs.append(safe_run)
    item["runs"] = safe_runs
    metrics = dict(item.get("metrics") or {})
    if not revealed:
        metrics.pop("modelMetrics", None)
    item["metrics"] = metrics
    return item


async def run(name, prompts, model_keys, repetitions=3, seed="rasputin", mission="chat", owner="admin"):
    prompts = [str(value).strip() for value in (prompts or []) if str(value).strip()][:20]
    chosen = [key for key in (model_keys or []) if model_registry.get_model(key)][:8]
    repetitions = max(2, min(int(repetitions or 3), 10))
    if not prompts:
        raise ValueError("At least one comparison prompt is required")
    if len(chosen) < 2:
        raise ValueError("At least two registered models are required")

    labels = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:len(chosen)])
    label_map = dict(zip(labels, chosen))
    generation = {"temperature": 0.2, "maxOutputTokens": 2048, "tools": False}
    exp = store.create_experiment(
        name=name or "Blind model comparison",
        exp_type="blind_compare",
        owner=owner,
        config={
            "prompts": prompts, "modelKeys": chosen, "repetitions": repetitions,
            "seed": str(seed), "mission": str(mission or "chat"),
            "labelMap": label_map, "revealed": False, "generation": generation,
        },
        tags=["blind", "repeatable", str(mission or "chat")],
    )
    store.update_experiment(exp["id"], status="running")
    totals = {key: [] for key in chosen}
    total_start = time.perf_counter()
    try:
        for repetition in range(repetitions):
            order = list(chosen)
            random.Random(f"{seed}:{repetition}").shuffle(order)
            run_row = store.create_run(exp["id"], inputs={
                "prompts": prompts, "modelKeys": chosen, "repetition": repetition + 1,
                "seed": str(seed), "generation": generation,
            })
            outputs = []
            for prompt_index, prompt in enumerate(prompts):
                for model_key in order:
                    started = time.perf_counter()
                    try:
                        text = await _chat(model_key, [{"role": "user", "content": prompt}], temperature=0.2, tools=None)
                        status, error = "done", ""
                    except Exception as exc:
                        text, status, error = "", "error", str(exc)
                    latency = round((time.perf_counter() - started) * 1000)
                    label = next(label for label, key in label_map.items() if key == model_key)
                    outputs.append({
                        "label": label, "promptIndex": prompt_index, "text": _redact_identity(text, model_key, label),
                        "status": status, "error": error, "latencyMs": latency, "modelKey": model_key,
                    })
                    totals[model_key].append({"status": status, "latencyMs": latency})
            store.update_run(run_row["id"], status="completed", outputs=outputs)

        model_metrics = {}
        for model_key, rows in totals.items():
            successful = [row for row in rows if row["status"] == "done"]
            model_metrics[model_key] = {
                "sampleCount": len(rows),
                "successCount": len(successful),
                "successRate": round(len(successful) / max(len(rows), 1), 4),
                "avgLatencyMs": round(sum(row["latencyMs"] for row in successful) / max(len(successful), 1)),
            }
        metrics = {
            "repetitions": repetitions, "promptCount": len(prompts),
            "sampleCount": sum(value["sampleCount"] for value in model_metrics.values()),
            "totalDurationMs": round((time.perf_counter() - total_start) * 1000),
            "modelMetrics": model_metrics, "identityHidden": True,
        }
        store.update_experiment(exp["id"], status="completed", metrics=metrics)
        audit.log("trial_blind_comparison_completed", {"experimentId": exp["id"], "owner": owner})
        return public_experiment(store.get_experiment(exp["id"]))
    except Exception:
        store.update_experiment(exp["id"], status="failed")
        raise


def reveal(experiment_id, owner):
    exp = store.get_experiment(experiment_id)
    if not exp or exp.get("type") != "blind_compare" or exp.get("owner") != owner:
        raise ValueError("Blind comparison not found")
    config = dict(exp.get("config") or {})
    config["revealed"] = True
    store.update_experiment(experiment_id, config=config)
    audit.log("trial_blind_comparison_revealed", {"experimentId": experiment_id, "owner": owner})
    return public_experiment(store.get_experiment(experiment_id), reveal=True)


def promote_certificate(experiment_id, model_key, owner, mission=""):
    exp = store.get_experiment(experiment_id)
    if not exp or exp.get("type") != "blind_compare" or exp.get("owner") != owner:
        raise ValueError("Blind comparison not found")
    config = exp.get("config") or {}
    if exp.get("status") != "completed" or not config.get("revealed"):
        raise ValueError("Reveal a completed blind comparison before promotion")
    measured = (exp.get("metrics") or {}).get("modelMetrics", {}).get(model_key)
    if not measured:
        raise ValueError("Selected model did not participate in this comparison")
    certificate = store.create_scorecard(
        name=f"Fitness certificate: {model_key}",
        subject_type="fitness_certificate",
        subject_id=experiment_id,
        scores={
            "kind": "fitnessCertificate", "modelKey": model_key,
            "owner": owner,
            "mission": mission or config.get("mission") or "chat", "measured": measured,
            "evidence": {
                "experimentId": experiment_id, "repetitions": config.get("repetitions"),
                "promptCount": len(config.get("prompts") or []), "seed": config.get("seed"),
                "generation": config.get("generation"), "identityHiddenDuringRun": True,
            },
            "limitations": ["No semantic quality claim is made unless the dataset contains an objective rubric."],
        },
    )
    audit.log("trial_fitness_certificate_created", {"experimentId": experiment_id, "modelKey": model_key, "owner": owner})
    return certificate
