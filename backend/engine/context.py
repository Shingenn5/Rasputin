import math

from backend.models import registry as model_registry

DEFAULT_CONTEXT_WINDOW = 4096
MIN_CONTEXT_WINDOW = 1024
DEFAULT_MAX_TOKENS = 160
MAX_OUTPUT_TOKENS = 512
SAFETY_TOKENS = 96
CHARS_PER_TOKEN = 2


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


def limits_for_model(model_key):
    cfg = model_registry.get_model(model_key) or {}
    compatibility = cfg.get("compatibility") or {}
    reliable = compatibility.get("reliableContextWindow")
    if reliable:
        cfg = {**cfg, "context_window": min(int(cfg.get("context_window") or cfg.get("context") or reliable), int(reliable))}
    return normalize_limits(cfg)


def estimate_tokens(text):
    return int(math.ceil(len(str(text or "")) / CHARS_PER_TOKEN))


def needs_compaction(model_key, current_tokens):
    limits = limits_for_model(model_key)
    max_input_tokens = max(128, limits["contextWindow"] - limits["maxTokens"] - SAFETY_TOKENS)
    threshold = int(max_input_tokens * 0.70)
    return current_tokens > threshold


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
