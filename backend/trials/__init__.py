"""Trials V3 — Experimentation & Evaluation Center for Rasputin."""

from .store import (
    init_db,
    list_experiments,
    get_experiment,
    create_experiment,
    update_experiment,
    delete_experiment,
    list_runs,
    get_run,
    create_run,
    update_run,
    list_datasets,
    get_dataset,
    create_dataset,
    delete_dataset,
    list_benchmarks,
    get_benchmark,
    create_benchmark,
    update_benchmark,
    list_comparisons,
    get_comparison,
    create_comparison,
    list_scorecards,
    get_scorecard,
    create_scorecard,
    list_reports,
    get_report,
    create_report,
)
from .engine import (
    run_experiment,
    cancel_experiment,
    run_quick_compare,
)
from .datasets import seed_datasets
from .scorecards import generate_scorecard
from .reports import generate_report

# Legacy compat re-exports
from .legacy import runs, compare, reveal, save_routing

# Initialize database on import
init_db()
