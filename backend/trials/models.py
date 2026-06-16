"""Domain model definitions for the Trials system."""

EXPERIMENT_TYPES = [
    "model",
    "prompt",
    "agent",
    "workflow",
    "rag",
    "tool",
    "custom",
    "quick_compare",
]

EXPERIMENT_STATUSES = [
    "draft",
    "running",
    "completed",
    "failed",
    "cancelled",
]

DATASET_TYPES = [
    "questions",
    "tasks",
    "documents",
    "knowledge",
    "evaluation",
    "scenarios",
]

REPORT_TYPES = [
    "benchmark",
    "evaluation",
    "comparison",
    "experiment",
    "optimization",
]

SCORECARD_CATEGORIES = [
    "accuracy",
    "reasoning",
    "reliability",
    "performance",
    "efficiency",
    "safety",
    "usability",
    "overall",
]

ROUTABLE_MODES = {"chat", "analyze", "research", "code", "write", "organize", "review"}
