import math
import time

from backend.models import registry as model_registry

DEFAULT_CONTEXT_WINDOW = 4096
MIN_CONTEXT_WINDOW = 1024
DEFAULT_MAX_TOKENS = 1024
MAX_OUTPUT_TOKENS = 8192
SAFETY_TOKENS = 96
CHARS_PER_TOKEN = 2
MAX_MEMORY_TOKENS = 800
MIN_MEMORY_TOKENS = 128
MEMORY_CONTEXT_FRACTION = 0.08
MAX_SESSION_SUMMARY_TOKENS = 1200
MIN_SESSION_SUMMARY_TOKENS = 256
SESSION_SUMMARY_CONTEXT_FRACTION = 0.12
MAX_ADAPTIVE_SUBAGENTS = 4
MAX_ADAPTIVE_CONTEXT_WINDOW = 262144


def _as_int(value, fallback):
    try:
        parsed = int(value)
        return parsed if parsed > 0 else fallback
    except Exception:
        return fallback


def normalize_limits(cfg=None):
    cfg = cfg or {}
    context_window = _as_int(cfg.get("context_window") or cfg.get("contextWindow"), DEFAULT_CONTEXT_WINDOW)
    context_window = max(MIN_CONTEXT_WINDOW, context_window)
    max_tokens = _as_int(cfg.get("max_tokens") or cfg.get("maxTokens"), DEFAULT_MAX_TOKENS)
    max_tokens = max(1, min(max_tokens, MAX_OUTPUT_TOKENS))
    if context_window - max_tokens - SAFETY_TOKENS < 128:
        max_tokens = max(1, min(DEFAULT_MAX_TOKENS, context_window // 4))
    return {"contextWindow": context_window, "maxTokens": max_tokens}


def adaptive_profile(cfg=None, role="chat"):
    """Derive bounded context/output/child budgets from explicit evidence.

    Catalog estimates and stale certificates are deliberately ignored. A
    caller may attach a fresh ``benchmarkCertificate`` and/or a
    ``resourceManifest`` to a registry model. The hard limits remain in force
    even when the evidence recommends a larger budget.
    """

    cfg = dict(cfg or {})
    limits = normalize_limits(cfg)
    reasons = []
    evidence = []
    max_subagents = max(0, min(MAX_ADAPTIVE_SUBAGENTS, _as_int(
        cfg.get("max_subagents") or cfg.get("maxSubagents"), MAX_ADAPTIVE_SUBAGENTS,
    )))
    manifest = cfg.get("resourceManifest") or cfg.get("resource_manifest") or {}
    if isinstance(manifest, dict):
        kv_cache = manifest.get("kvCache") or manifest.get("kv_cache") or {}
        fit = manifest.get("fit") or {}
        weights = manifest.get("weights") or {}
        status = str(kv_cache.get("status") or "unmeasured").lower()
        per_token_mb = _as_int(kv_cache.get("perTokenMb") or kv_cache.get("per_token_mb"), 0)
        # _as_int is intentionally conservative for sub-megabyte/token values;
        # preserve the fractional measurement when one is present.
        try:
            per_token_mb = float(kv_cache.get("perTokenMb") or kv_cache.get("per_token_mb") or 0)
        except (TypeError, ValueError):
            per_token_mb = 0.0
        available_gb = cfg.get("availableVramGb") or cfg.get("available_vram_gb") or fit.get("availableVramGb")
        try:
            available_gb = float(available_gb) if available_gb not in (None, "") else None
        except (TypeError, ValueError):
            available_gb = None
        try:
            weight_gb = float(weights.get("estimatedVramGb") or 0)
        except (TypeError, ValueError):
            weight_gb = 0.0
        if status == "measured" and per_token_mb > 0 and available_gb is not None:
            kv_budget_tokens = int(max(0.0, available_gb - weight_gb - 1.0) * 1024 / per_token_mb)
            if kv_budget_tokens >= MIN_CONTEXT_WINDOW:
                before = limits["contextWindow"]
                limits["contextWindow"] = min(before, kv_budget_tokens, MAX_ADAPTIVE_CONTEXT_WINDOW)
                reasons.append(f"measured KV-cache budget caps context at {limits['contextWindow']} tokens")
                evidence.append("resourceManifest.kvCache")
        elif status not in {"measured"}:
            reasons.append("KV-cache envelope is unmeasured; static context limits remain")

    certificate = cfg.get("benchmarkCertificate") or cfg.get("benchmark_certificate") or {}
    certificate_fresh = False
    if isinstance(certificate, dict):
        try:
            age = time.time() - float(certificate.get("createdAt") or 0)
            certificate_fresh = certificate.get("status") in {"measured", "partial"} and 0 <= age <= 30 * 24 * 60 * 60
        except (TypeError, ValueError):
            certificate_fresh = False
        if certificate_fresh:
            spec = certificate.get("spec") or {}
            summary = certificate.get("summary") or {}
            measured_context = _as_int(spec.get("contextWindow") or spec.get("maxModelLen"), 0)
            if measured_context:
                limits["contextWindow"] = min(limits["contextWindow"], measured_context, MAX_ADAPTIVE_CONTEXT_WINDOW)
                reasons.append(f"fresh benchmark certificate caps context at {limits['contextWindow']} tokens")
                evidence.append("benchmarkCertificate.spec.contextWindow")
            measured_concurrency = _as_int(spec.get("concurrency"), 0)
            if measured_concurrency:
                max_subagents = max(0, min(MAX_ADAPTIVE_SUBAGENTS, measured_concurrency - 1))
                reasons.append(f"child work is capped at {max_subagents} for measured concurrency {measured_concurrency}")
                evidence.append("benchmarkCertificate.spec.concurrency")
            success_rate = summary.get("successRate")
            try:
                p95_ttft = float((summary.get("ttftMs") or {}).get("p95") or 0)
            except (TypeError, ValueError):
                p95_ttft = 0.0
            try:
                success_rate = float(success_rate)
            except (TypeError, ValueError):
                success_rate = 1.0
            if success_rate < 1.0 or p95_ttft > 5000:
                limits["maxTokens"] = min(limits["maxTokens"], max(256, limits["contextWindow"] // 8))
                reasons.append("partial/slow benchmark evidence lowers the output ceiling")
                evidence.append("benchmarkCertificate.summary")
        elif certificate:
            reasons.append("benchmark certificate is stale or invalid; it is not used for adaptation")

    # Re-run the hard context/output relationship after an evidence-based cap.
    if limits["contextWindow"] - limits["maxTokens"] - SAFETY_TOKENS < 128:
        limits["maxTokens"] = max(1, min(DEFAULT_MAX_TOKENS, limits["contextWindow"] // 4))
    return {
        "limits": limits,
        "maxSubagents": max_subagents,
        "role": str(role or "chat"),
        "evidence": evidence,
        "reasons": reasons,
        "certificateFresh": certificate_fresh,
    }


def limits_for_model(model_key):
    cfg = model_registry.get_model(model_key) or {}
    compatibility = cfg.get("compatibility") or {}
    reliable = compatibility.get("reliableContextWindow")
    if reliable:
        cfg = {**cfg, "context_window": min(int(cfg.get("context_window") or cfg.get("context") or reliable), int(reliable))}
    return adaptive_profile(cfg, role=cfg.get("role") or "chat")["limits"]


def estimate_tokens(text):
    return int(math.ceil(len(str(text or "")) / CHARS_PER_TOKEN))


def output_budget(cfg, messages):
    """Choose a per-request ceiling from the runtime's remaining context.

    An explicitly configured max_tokens remains a hard operator preference.
    Auto-detected local runtimes instead receive all context left after the
    actual request, so a small planning reserve does not become an arbitrary
    response cutoff.
    """
    cfg = cfg or {}
    limits = adaptive_profile(cfg)["limits"]
    estimated_input = 8
    for message in messages or []:
        estimated_input += 4
        if isinstance(message, dict):
            estimated_input += estimate_tokens(message.get("content"))
            estimated_input += estimate_tokens(message.get("name"))
        else:
            estimated_input += estimate_tokens(message)
    available = max(1, limits["contextWindow"] - estimated_input - SAFETY_TOKENS)
    explicit = cfg.get("max_tokens") or cfg.get("maxTokens")
    if explicit:
        return min(limits["maxTokens"], available)
    if cfg.get("context_auto") or cfg.get("contextAuto"):
        return available
    return min(limits["maxTokens"], available)


def needs_compaction(model_key, current_tokens):
    limits = limits_for_model(model_key)
    max_input_tokens = max(128, limits["contextWindow"] - limits["maxTokens"] - SAFETY_TOKENS)
    threshold = int(max_input_tokens * 0.70)
    return current_tokens > threshold


def memory_budget(model_key):
    """Bound saved-memory recall without starving the live conversation."""
    context_window = limits_for_model(model_key)["contextWindow"]
    proportional = int(context_window * MEMORY_CONTEXT_FRACTION)
    return max(MIN_MEMORY_TOKENS, min(MAX_MEMORY_TOKENS, proportional))


def session_summary_budget(model_key):
    """Cap the rolling checkpoint so it cannot grow with every compaction."""
    context_window = limits_for_model(model_key)["contextWindow"]
    proportional = int(context_window * SESSION_SUMMARY_CONTEXT_FRACTION)
    return max(MIN_SESSION_SUMMARY_TOKENS, min(MAX_SESSION_SUMMARY_TOKENS, proportional))


def section(key, title, content, priority=50, required=False, min_chars=220):
    return {
        "key": key,
        "title": title,
        "content": str(content or "").strip(),
        "priority": int(priority),
        "required": bool(required),
        "minChars": int(min_chars),
    }


def _trim_text(text, max_chars):
    text = str(text or "")
    if len(text) <= max_chars:
        return text
    if max_chars <= 120:
        return text[:max_chars].rstrip()
    head = max(40, max_chars // 3)
    marker = "\n\n[rasputin: context section shortened]\n\n"
    tail = max(40, max_chars - head - len(marker))
    return text[:head].rstrip() + marker + text[-tail:].lstrip()


def _render(title, content):
    if not title:
        return content
    return f"{title}:\n{content}"


def _record(item, content, status):
    original = item["content"]
    return {
        "key": item["key"],
        "title": item["title"],
        "status": status,
        "required": item["required"],
        "originalChars": len(original),
        "finalChars": len(content),
        "estimatedTokens": estimate_tokens(_render(item["title"], content)),
    }


def compose_prompt(model_key, phase, sections):
    limits = limits_for_model(model_key)
    max_input_tokens = max(128, limits["contextWindow"] - limits["maxTokens"] - SAFETY_TOKENS)
    char_budget = max_input_tokens * CHARS_PER_TOKEN
    prepared = [item for item in sections if item.get("content")]
    selected = {}
    records = []
    remaining = char_budget

    required = [item for item in prepared if item["required"]]
    optional = sorted([item for item in prepared if not item["required"]], key=lambda item: item["priority"])

    for item in required:
        rendered_overhead = len(_render(item["title"], ""))
        allowed = max(80, remaining - rendered_overhead)
        content = _trim_text(item["content"], allowed)
        status = "trimmed" if len(content) < len(item["content"]) else "included"
        selected[item["key"]] = content
        records.append(_record(item, content, status))
        remaining -= len(_render(item["title"], content)) + 2

    for item in optional:
        if remaining <= item["minChars"]:
            records.append(_record(item, "", "omitted"))
            continue
        rendered = _render(item["title"], item["content"])
        if len(rendered) <= remaining:
            selected[item["key"]] = item["content"]
            records.append(_record(item, item["content"], "included"))
            remaining -= len(rendered) + 2
            continue
        allowed = remaining - len(_render(item["title"], "")) - 2
        if allowed < item["minChars"]:
            records.append(_record(item, "", "omitted"))
            continue
        content = _trim_text(item["content"], allowed)
        selected[item["key"]] = content
        records.append(_record(item, content, "trimmed"))
        remaining -= len(_render(item["title"], content)) + 2

    parts = []
    for item in prepared:
        if item["key"] not in selected:
            continue
        parts.append(_render(item["title"], selected[item["key"]]))
    prompt = "\n\n".join(parts).strip()
    trace = {
        "phase": phase,
        "modelKey": model_key,
        "contextWindow": limits["contextWindow"],
        "maxTokens": limits["maxTokens"],
        "inputBudgetTokens": max_input_tokens,
        "estimatedInputTokens": estimate_tokens(prompt),
        "sections": records,
        "trimmed": [item["key"] for item in records if item["status"] == "trimmed"],
        "omitted": [item["key"] for item in records if item["status"] == "omitted"],
    }
    return {"prompt": prompt, "trace": trace, "limits": limits}
