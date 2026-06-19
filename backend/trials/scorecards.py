"""Scorecard generation for Trials."""

from . import store
from .models import SCORECARD_CATEGORIES
from backend.core import audit


def generate_scorecard(experiment_id, name=None):
    """Generate a scorecard from experiment results."""
    exp = store.get_experiment(experiment_id)
    if not exp:
        raise ValueError("Experiment not found")
    if exp["status"] != "completed":
        raise ValueError("Experiment must be completed to generate a scorecard")

    metrics = exp.get("metrics") or {}
    runs = exp.get("runs") or store.list_runs(experiment_id)

    # Compute scores from available metrics
    scores = {}
    for cat in SCORECARD_CATEGORIES:
        scores[cat] = _compute_score(cat, metrics, runs, exp)

    sc_name = name or f"Scorecard: {exp['name']}"
    scorecard = store.create_scorecard(
        name=sc_name,
        subject_type=exp.get("type", "model"),
        subject_id=experiment_id,
        scores=scores,
    )

    audit.log("trial_scorecard_generated", {
        "scorecardId": scorecard["id"],
        "experimentId": experiment_id,
    })

    return scorecard


def _compute_score(category, metrics, runs, experiment):
    """Compute a 0-100 score for a category from available metrics."""
    if category == "performance":
        # Based on latency: faster = better
        total_ms = metrics.get("totalDurationMs", 0)
        if total_ms <= 0:
            return 50
        if total_ms < 1000:
            return 95
        if total_ms < 5000:
            return 80
        if total_ms < 15000:
            return 60
        if total_ms < 30000:
            return 40
        return 20

    if category == "reliability":
        # Based on success rate
        success = metrics.get("successCount", 0)
        errors = metrics.get("errorCount", 0)
        total = success + errors
        if total == 0:
            return 50
        return round((success / total) * 100)

    if category == "efficiency":
        # Based on model count vs success
        model_count = metrics.get("modelCount", 1)
        success = metrics.get("successCount", 0)
        if model_count == 0:
            return 50
        rate = success / model_count
        return round(rate * 100)

    if category == "accuracy":
        # Placeholder - would need ground truth comparison
        results = metrics.get("results", [])
        if results:
            avg_success = sum(r.get("successRate", 0) for r in results) / len(results)
            return round(avg_success * 100)
        success = metrics.get("successCount", 0)
        total = success + metrics.get("errorCount", 0)
        return round((success / max(total, 1)) * 100)

    if category == "reasoning":
        # Placeholder - requires semantic evaluation
        return 50

    if category == "safety":
        # Default to high - no unsafe outputs detected (placeholder)
        return 85

    if category == "usability":
        # Placeholder
        return 70

    if category == "overall":
        # Average of other scores
        others = [_compute_score(c, metrics, runs, experiment) for c in SCORECARD_CATEGORIES if c != "overall"]
        return round(sum(others) / max(len(others), 1))

    return 50
