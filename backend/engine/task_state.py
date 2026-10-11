"""Task state, bounded history and generation-metric normalization."""

import math
import time
import uuid

from backend.core import runtime_store as store
from backend.core import security, workspace


MEMORY_MODES = {"auto", "include", "suppress"}


GENERATION_PHASES = {"chat", "planning", "execution", "reflection"}


GENERATION_TOKEN_SOURCES = {"estimated", "exact"}


MAX_GENERATION_TOKENS_PER_SECOND = 100_000.0


def _empty_generation_metrics():
    return {
        "outputTokens": 0,
        "generationSeconds": 0.0,
        "tokensPerSecond": None,
        "tokenCountSource": "estimated",
        "turns": 0,
        "lastPhase": None,
        "lastOutputTokens": 0,
        "lastGenerationSeconds": 0.0,
        "lastTokensPerSecond": None,
        "lastTimeToFirstTokenSeconds": None,
        "lastPromptSeconds": None,
        "lastDecodeTokensPerSecond": None,
    }


def _nonnegative_metric_float(value):
    if isinstance(value, bool):
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number) or number < 0:
        return 0.0
    return number


def _nonnegative_metric_int(value):
    number = _nonnegative_metric_float(value)
    return int(number) if number.is_integer() else 0


def _metric_seconds(value):
    number = _nonnegative_metric_float(value)
    return round(number, 3) if number > 0 else 0.0


def _metric_tokens_per_second(output_tokens, generation_seconds):
    if output_tokens <= 0 or generation_seconds <= 0:
        return None
    rate = output_tokens / generation_seconds
    if not math.isfinite(rate):
        return None
    rate = min(rate, MAX_GENERATION_TOKENS_PER_SECOND)
    return rate


def _normalize_generation_metrics(value):
    metrics = _empty_generation_metrics()
    raw = value if isinstance(value, dict) else {}
    output_tokens = _nonnegative_metric_int(raw.get("outputTokens"))
    generation_seconds = _metric_seconds(raw.get("generationSeconds"))
    last_output_tokens = _nonnegative_metric_int(raw.get("lastOutputTokens"))
    last_generation_seconds = _metric_seconds(raw.get("lastGenerationSeconds"))
    token_count_source = raw.get("tokenCountSource")
    if token_count_source not in GENERATION_TOKEN_SOURCES:
        token_count_source = "estimated"
    last_phase = raw.get("lastPhase")
    if last_phase not in GENERATION_PHASES:
        last_phase = None
    metrics.update({
        "outputTokens": output_tokens,
        "generationSeconds": generation_seconds,
        "tokensPerSecond": _metric_tokens_per_second(output_tokens, generation_seconds),
        "tokenCountSource": token_count_source,
        "turns": _nonnegative_metric_int(raw.get("turns")),
        "lastPhase": last_phase,
        "lastOutputTokens": last_output_tokens,
        "lastGenerationSeconds": last_generation_seconds,
        "lastTokensPerSecond": _metric_tokens_per_second(last_output_tokens, last_generation_seconds),
    })
    for key in ("lastTimeToFirstTokenSeconds", "lastPromptSeconds", "lastDecodeTokensPerSecond"):
        number = _nonnegative_metric_float(raw.get(key))
        if number > 0:
            metrics[key] = min(number, MAX_GENERATION_TOKENS_PER_SECOND) if key == "lastDecodeTokensPerSecond" else _metric_seconds(number)
    return metrics


def normalize_memory_mode(value):
    mode = str(value or "auto").strip().lower()
    return mode if mode in MEMORY_MODES else "auto"


class AgentTask:
    def __init__(self, objective, model, skill, parent_id=None, workspace_path=None, mode="chat", task_id=None, session_id=None, reasoning="auto", priority=0, scheduled_for=None, subagents=0, max_attempts=1, source_task_id=None, isolate_workspace=False, isolation_state="none", execution_workspace="", isolation_metadata=None, context_capsule_id=None, memory_mode="auto", deployment_profile=None, requested_mode=None):
        self.id = task_id or str(uuid.uuid4())[:8]
        self.session_id = session_id or store.new_id("sess")
        self.objective = objective
        self.model = model
        self.deployment_profile = dict(deployment_profile or {})
        self.skill = skill or "general"
        self.mode = mode or "chat"
        self.requested_mode = requested_mode or self.mode
        self.memory_mode = normalize_memory_mode(memory_mode)
        self.reasoning = reasoning if reasoning in {"auto", "off", "low", "medium", "high"} else "auto"
        self.priority = max(-10, min(int(priority or 0), 10))
        self.scheduled_for = float(scheduled_for) if scheduled_for else None
        self.subagents = max(0, min(int(subagents or 0), 4))
        self.max_attempts = max(1, min(int(max_attempts or 1), 5))
        self.attempt_count = 0
        self.source_task_id = source_task_id
        self.context_capsule_id = str(context_capsule_id or "") or None
        self.context_capsule = None
        self.context_capsule_receipt = None
        self.queue_order = time.time()
        self.started_at = None
        self.completed_at = None
        self.parent_id = parent_id
        self.status = "queued"
        self.progress = 0
        self.logs = []
        self.result = ""
        self.sources = []
        self.graph = []
        self.outputs = []
        self.trace = []
        # Live-streaming state: current phase's partial model output and the
        # running step list (phases + tool calls). Written from the provider
        # worker thread; plain field assignment keeps it GIL-safe.
        self.stream_text = ""
        self.steps = []
        self.generation_metrics = _empty_generation_metrics()
        self.cancel_requested = False
        self.paused_requested = False
        self.workspace = workspace_path or workspace.get_active()["active_path"]
        self.isolate_workspace = bool(isolate_workspace and self.mode == "code")
        self.isolation_state = str(isolation_state or ("none" if not self.isolate_workspace else "requested"))
        self.execution_workspace = str(execution_workspace or "")
        self.isolation_metadata = dict(isolation_metadata or {})
        self.permission_snapshot = security.load()
        self.created_at = time.time()
        self.event_sink = None
        self.output_sink = None
        self.trace_sink = None

    def log(self, msg):
        stamp = time.strftime("%H:%M:%S")
        line = f"[{stamp}] {msg}"
        self.logs.append(line)
        self.logs = self.logs[-500:]
        if self.event_sink:
            self.event_sink(self.id, "log", {"message": line})

    def seen(self, kind, detail):
        item = {"at": time.time(), "kind": kind, "detail": detail}
        self.trace.append(item)
        self.trace = self.trace[-120:]
        if self.trace_sink:
            self.trace_sink(self.id, kind, detail)

    def output(self, kind, title, content):
        item = {"kind": kind, "title": title, "content": content, "createdAt": time.time()}
        self.outputs.append(item)
        self.outputs = self.outputs[-40:]
        if self.output_sink:
            self.output_sink(self.id, kind, title, content)
