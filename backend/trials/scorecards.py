"""Scorecards with explicit measurement provenance, rather than quality guesses."""

import math

from . import store
from .models import SCORECARD_CATEGORIES
from backend.core import audit


SCORECARD_EVIDENCE_VERSION = 1
UNMEASURED_REASONS = {
    "accuracy": "No ground-truth answers or objective accuracy rubric were evaluated.",
    "reasoning": "No reasoning evaluation was performed.",
    "reliability": "No request outcome counts were recorded.",
    "performance": "Elapsed time is recorded separately; no normalized performance scoring rubric was evaluated.",
    "efficiency": "No resource-use or token-efficiency evaluation was performed.",
    "safety": "No safety evaluation was performed.",
    "usability": "No usability evaluation was performed.",
    "overall": "No dimensions were measured.",
}


def _finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return value if math.isfinite(value) else None
    except OverflowError:
        return None


def _count(value):
    value = _finite_number(value)
    return int(value) if value is not None and value >= 0 and int(value) == value else None


def _request_counts(metrics, runs):
    success = _count(metrics.get("successCount"))
    errors = _count(metrics.get("errorCount"))
    if success is not None and errors is not None:
        return success, errors, "experiment.metrics.successCount/errorCount", None

    # An experiment can be rerun: previous runs must not inflate the current sample.
    completed = [run for run in runs if isinstance(run, dict) and run.get("status") == "completed"]
    latest = max(completed, key=lambda run: _finite_number(run.get("createdAt")) or 0, default=None)
    if not latest:
        return None
    outputs = latest.get("outputs")
    if not isinstance(outputs, list):
        return None
    outcomes = []
    for output in outputs:
        if not isinstance(output, dict):
            return None
        children = output.get("outputs")
        if children is not None and not isinstance(children, list):
            return None
        outcomes.extend(children if isinstance(children, list) else [output])
    if any(not isinstance(output, dict) for output in outcomes):
        return None
    statuses = [output.get("status") for output in outcomes]
    if not statuses or any(status not in ("done", "error") for status in statuses):
        return None
    return statuses.count("done"), statuses.count("error"), "latest completed run output statuses", latest.get("id")


def normalize_scorecard(scores, evidence):
    """Fail closed on legacy scores without provenance; preserve valid measured zero."""
    scores = scores if isinstance(scores, dict) else {}
    evidence = dict(evidence) if isinstance(evidence, dict) else {}
    current = evidence.get("schemaVersion") == SCORECARD_EVIDENCE_VERSION
    dimensions = evidence.get("dimensions") if current else {}
    dimensions = dimensions if isinstance(dimensions, dict) else {}
    normalized = {}
    measurements = {}
    for category in SCORECARD_CATEGORIES:
        if category == "overall":
            continue
        detail = dimensions.get(category)
        detail = dict(detail) if isinstance(detail, dict) else {}
        value = _finite_number(scores.get(category))
        measured = current and detail.get("state") == "measured" and value is not None
        normalized[category] = round(min(100, max(0, value)), 2) if measured else None
        measurements[category] = detail if measured else {
            "state": "not_measured",
            "reason": detail.get("reason") or UNMEASURED_REASONS[category],
        }

    measured_categories = [cat for cat, value in normalized.items() if value is not None]
    normalized["overall"] = round(sum(normalized[cat] for cat in measured_categories) / len(measured_categories), 2) if measured_categories else None
    measurements["overall"] = {
        "state": "derived" if measured_categories else "not_measured",
        "method": "Arithmetic mean of measured dimensions only; not a general model quality rating.",
        "includedDimensions": measured_categories,
        "reason": None if measured_categories else UNMEASURED_REASONS["overall"],
    }
    evidence.update({
        "state": "measured" if measured_categories else "not_measured" if current else "legacy_unverified",
        "dimensions": measurements,
    })
    if not current:
        evidence["notice"] = "This older scorecard has no measurement provenance. Regenerate it to use recorded experiment evidence."
    return normalized, evidence


def generate_scorecard(experiment_id, name=None):
    """Measure request completion only; leave unsupported quality dimensions empty."""
    exp = store.get_experiment(experiment_id)
    if not exp:
        raise ValueError("Experiment not found")
    if exp["status"] != "completed":
        raise ValueError("Experiment must be completed to generate a scorecard")

    metrics = exp.get("metrics") or {}
    runs = exp.get("runs") or store.list_runs(experiment_id)
    scores = {category: None for category in SCORECARD_CATEGORIES}
    dimensions = {category: {"state": "not_measured", "reason": reason} for category, reason in UNMEASURED_REASONS.items()}
    config = exp.get("config") or {}
    evidence = {
        "schemaVersion": SCORECARD_EVIDENCE_VERSION,
        "experimentId": experiment_id,
        "experimentUpdatedAt": exp.get("updatedAt"),
        "configuredDatasetId": config.get("datasetId") or config.get("dataset_id") or None,
        "datasetVersion": None,
        "datasetNotice": "Dataset identity comes from experiment configuration; its evaluated version was not captured.",
        "dimensions": dimensions,
        "limitations": [
            "Request completion does not measure answer correctness, coding ability, or safety.",
            "These observations apply to this experiment, which may include dry-run responses; exact model and runtime artifacts were not certified.",
        ],
    }
    elapsed = _finite_number(metrics.get("totalDurationMs"))
    if elapsed is not None and elapsed >= 0:
        evidence["observations"] = {"totalDurationMs": elapsed}
    counts = _request_counts(metrics, runs)
    if counts and counts[0] + counts[1] > 0:
        success, errors, source, run_id = counts
        total = success + errors
        scores["reliability"] = round(success / total * 100, 2)
        dimensions["reliability"] = {
            "state": "measured",
            "label": "Request completion",
            "method": "100 × successful requests / (successful + failed requests)",
            "source": source,
            "runId": run_id,
            "sampleCount": total,
            "successCount": success,
            "errorCount": errors,
            "uncertainty": "Not estimated; this sample is not evidence of future reliability or semantic quality.",
        }
    scores, evidence = normalize_scorecard(scores, evidence)
    scorecard = store.create_scorecard(
        name=name or f"Scorecard: {exp['name']}",
        subject_type=exp.get("type", "model"),
        subject_id=experiment_id,
        scores=scores,
        evidence=evidence,
    )
    audit.log("trial_scorecard_generated", {"scorecardId": scorecard["id"], "experimentId": experiment_id})
    return scorecard
