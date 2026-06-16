"""Report generation for Trials."""

import time
from . import store
from .. import audit


def generate_report(name, report_type="experiment", experiment_ids=None):
    """Generate a markdown report from experiment results."""
    experiment_ids = experiment_ids or []
    experiments = [store.get_experiment(eid) for eid in experiment_ids]
    experiments = [e for e in experiments if e]

    if not experiments:
        raise ValueError("At least one valid experiment ID is required")

    content_md = _build_report(report_type, experiments)

    report = store.create_report(
        name=name,
        report_type=report_type,
        content_md=content_md,
        experiment_ids=experiment_ids,
    )

    audit.log("trial_report_generated", {
        "reportId": report["id"],
        "type": report_type,
        "experimentCount": len(experiments),
    })

    return report


def _build_report(report_type, experiments):
    """Build markdown report content."""
    lines = []
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    if report_type == "benchmark":
        lines.append("# Benchmark Report")
        lines.append(f"\n*Generated: {timestamp}*\n")
        lines.append("## Summary\n")
        lines.append(f"Benchmarked {len(experiments)} experiment(s).\n")
        lines.append("## Results\n")
        lines.append("| Experiment | Type | Status | Duration | Models |")
        lines.append("|---|---|---|---|---|")
        for exp in experiments:
            metrics = exp.get("metrics") or {}
            duration = metrics.get("totalDurationMs", 0)
            model_count = metrics.get("modelCount", 0)
            lines.append(f"| {exp['name']} | {exp['type']} | {exp['status']} | {duration}ms | {model_count} |")
        lines.append("\n## Detailed Metrics\n")
        for exp in experiments:
            lines.append(f"### {exp['name']}\n")
            metrics = exp.get("metrics") or {}
            for key, value in metrics.items():
                if key == "results":
                    lines.append("\n**Per-Model Results:**\n")
                    lines.append("| Model | Avg Latency | Success Rate |")
                    lines.append("|---|---|---|")
                    for r in value:
                        lines.append(f"| {r.get('modelKey', 'unknown')} | {r.get('avgLatencyMs', 0)}ms | {r.get('successRate', 0):.1%} |")
                else:
                    lines.append(f"- **{key}**: {value}")
            lines.append("")

    elif report_type == "comparison":
        lines.append("# Comparison Report")
        lines.append(f"\n*Generated: {timestamp}*\n")
        lines.append("## Experiments Compared\n")
        for exp in experiments:
            lines.append(f"- **{exp['name']}** ({exp['type']}) — {exp['status']}")
        lines.append("\n## Metrics Comparison\n")
        lines.append("| Metric | " + " | ".join(e["name"][:30] for e in experiments) + " |")
        lines.append("|---" + "|---" * len(experiments) + "|")
        all_keys = set()
        for exp in experiments:
            all_keys.update((exp.get("metrics") or {}).keys())
        for key in sorted(all_keys):
            if key == "results":
                continue
            values = [str((e.get("metrics") or {}).get(key, "—")) for e in experiments]
            lines.append(f"| {key} | " + " | ".join(values) + " |")

    elif report_type == "evaluation":
        lines.append("# Evaluation Report")
        lines.append(f"\n*Generated: {timestamp}*\n")
        lines.append("## Summary\n")
        lines.append(f"Evaluated {len(experiments)} experiment(s).\n")
        for exp in experiments:
            lines.append(f"### {exp['name']}\n")
            lines.append(f"- **Type**: {exp['type']}")
            lines.append(f"- **Status**: {exp['status']}")
            metrics = exp.get("metrics") or {}
            if metrics:
                lines.append(f"- **Duration**: {metrics.get('totalDurationMs', 0)}ms")
                lines.append(f"- **Models**: {metrics.get('modelCount', 0)}")
                lines.append(f"- **Success**: {metrics.get('successCount', 0)}")
                lines.append(f"- **Errors**: {metrics.get('errorCount', 0)}")
            lines.append("")

    else:  # experiment / optimization
        lines.append("# Experiment Report")
        lines.append(f"\n*Generated: {timestamp}*\n")
        for exp in experiments:
            lines.append(f"## {exp['name']}\n")
            lines.append(f"- **ID**: `{exp['id']}`")
            lines.append(f"- **Type**: {exp['type']}")
            lines.append(f"- **Status**: {exp['status']}")
            lines.append(f"- **Created**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(exp.get('createdAt', 0)))}")
            metrics = exp.get("metrics") or {}
            if metrics:
                lines.append("\n### Metrics\n")
                for key, value in metrics.items():
                    if isinstance(value, list):
                        lines.append(f"- **{key}**: {len(value)} entries")
                    else:
                        lines.append(f"- **{key}**: {value}")
            runs = exp.get("runs") or []
            if runs:
                lines.append(f"\n### Runs ({len(runs)})\n")
                for run in runs[:5]:
                    lines.append(f"- `{run['id']}` — {run['status']} ({run.get('durationMs', 0)}ms)")
            lines.append("")

    lines.append(f"\n---\n*Report generated by Rasputin Trials at {timestamp}*\n")
    return "\n".join(lines)
