import json
import re
import urllib.request


CONTEXT_FIELDS = (
    "context_window",
    "contextWindow",
    "context_length",
    "contextLength",
    "max_context_length",
    "maxContextLength",
    "max_model_len",
    "maxModelLen",
)


def _positive_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _server_root(base_url):
    base = str(base_url or "").strip().rstrip("/")
    return base[:-3] if base.endswith("/v1") else base


def _request_json(url, *, payload=None, timeout=2.0):
    body = None
    headers = {"Accept": "application/json", "User-Agent": "rasputin-context-probe/0.1"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read(1_000_000).decode("utf-8", "replace") or "{}")


def _request_text(url, *, timeout=2.0):
    request = urllib.request.Request(
        url,
        headers={"Accept": "text/plain", "User-Agent": "rasputin-context-probe/0.1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(2_000_000).decode("utf-8", "replace")


def _first_context_value(payload):
    if not isinstance(payload, dict):
        return None
    for field in CONTEXT_FIELDS:
        value = _positive_int(payload.get(field))
        if value:
            return value
    return None


def parse_runtime_logs(logs_text, runtime=""):
    """Extract effective and advertised context sizes from common local runtimes."""
    text = str(logs_text or "")
    runtime_name = str(runtime or "").lower()
    result = {}

    if "llama" in runtime_name or "n_ctx" in text:
        effective = None
        for pattern in (
            r"llama_context:\s+n_ctx\s*=\s*(\d+)",
            r"n_ctx_seq\s*=\s*(\d+)",
            r"slot\s+load_model:.*?\bn_ctx\s*=\s*(\d+)",
        ):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                effective = _positive_int(match.group(1))
                break
        maximum_match = re.search(r"\bn_ctx_train\s*=\s*(\d+)", text, re.IGNORECASE)
        if effective:
            result.update({"context_window": effective, "context_source": "llama.cpp logs"})
        if maximum_match:
            result["model_context_window"] = _positive_int(maximum_match.group(1))

    if "vllm" in runtime_name:
        effective = None
        for pattern in (
            r"\bmax_seq_len\s*=\s*(\d+)",
            r"\bmax_model_len\s*[=:]\s*(\d+)",
            r"""["']max_model_len["']\s*:\s*(\d+)""",
            r"Maximum concurrency for\s+([\d,]+)\s+tokens per request",
        ):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                effective = _positive_int(match.group(1).replace(",", ""))
                break
        if effective:
            result.update({"context_window": effective, "context_source": "vLLM logs"})

    return result


def _probe_llama_cpp(root, timeout):
    data = _request_json(f"{root}/props", timeout=timeout)
    settings = data.get("default_generation_settings") or {}
    context = _positive_int(settings.get("n_ctx"))
    if not context:
        return {}
    return {"context_window": context, "context_source": "llama.cpp /props"}


def _ollama_model_match(item, model_name):
    expected = str(model_name or "").strip()
    values = {
        str(item.get("name") or "").strip(),
        str(item.get("model") or "").strip(),
    }
    return not expected or expected in values or expected.split(":", 1)[0] in {
        value.split(":", 1)[0] for value in values if value
    }


def _probe_ollama(root, model_name, timeout):
    result = {}
    try:
        running = _request_json(f"{root}/api/ps", timeout=timeout)
        for item in running.get("models") or []:
            if isinstance(item, dict) and _ollama_model_match(item, model_name):
                context = _positive_int(item.get("context_length"))
                if context:
                    result.update({"context_window": context, "context_source": "Ollama /api/ps"})
                    break
    except Exception:
        pass

    if model_name:
        try:
            shown = _request_json(
                f"{root}/api/show",
                payload={"model": model_name, "verbose": False},
                timeout=timeout,
            )
            for key, value in (shown.get("model_info") or {}).items():
                if str(key).endswith(".context_length"):
                    maximum = _positive_int(value)
                    if maximum:
                        result["model_context_window"] = maximum
                        break
        except Exception:
            pass
    return result


def _probe_model_cards(base_url, model_name, timeout):
    data = _request_json(f"{base_url.rstrip('/')}/models", timeout=timeout)
    cards = data.get("data") or data.get("models") or []
    expected = str(model_name or "").strip()
    for card in cards:
        if not isinstance(card, dict):
            continue
        card_id = str(card.get("id") or card.get("name") or card.get("model") or "").strip()
        if expected and card_id and card_id != expected:
            continue
        context = _first_context_value(card)
        if context:
            return {
                "context_window": context,
                "model_context_window": context,
                "context_source": "OpenAI-compatible model card",
            }
    return {}


def _probe_vllm_metrics(root, timeout):
    metrics = _request_text(f"{root}/metrics", timeout=timeout)
    for pattern in (
        r'\bmax_model_len="(\d+)"',
        r'\bmax_model_len\s*[:=]\s*(\d+)',
    ):
        match = re.search(pattern, metrics, re.IGNORECASE)
        if match:
            context = _positive_int(match.group(1))
            if context:
                return {"context_window": context, "context_source": "vLLM /metrics"}
    return {}


def detect_runtime_context(model, *, logs_text="", timeout=2.0, allow_network=True):
    """Return the runtime's effective context and, when exposed, model maximum.

    The effective context is safe for request budgeting. The model maximum is
    informational only because it may be much larger than available VRAM.
    """
    model = dict(model or {})
    identity = " ".join(
        str(value or "") for value in (
            model.get("provider"),
            model.get("runtime"),
            model.get("runtime_family"),
            " ".join(model.get("tags") or []),
        )
    ).lower()
    detected = parse_runtime_logs(logs_text, identity)
    if not allow_network:
        return detected

    base_url = str(model.get("base_url") or model.get("baseUrl") or "").strip().rstrip("/")
    if not base_url:
        return detected
    root = _server_root(base_url)
    model_name = model.get("model")

    probes = []
    if "ollama" in identity:
        probes = [lambda: _probe_ollama(root, model_name, timeout)]
    elif "llama" in identity or "gguf" in identity:
        probes = [lambda: _probe_llama_cpp(root, timeout)]
    elif "vllm" in identity:
        probes = [
            lambda: _probe_vllm_metrics(root, timeout),
            lambda: _probe_model_cards(base_url, model_name, timeout),
        ]
    else:
        probes = [
            lambda: _probe_llama_cpp(root, timeout),
            lambda: _probe_vllm_metrics(root, timeout),
            lambda: _probe_model_cards(base_url, model_name, timeout),
        ]

    for probe in probes:
        try:
            probed = probe()
        except Exception:
            continue
        for key, value in probed.items():
            if value and key not in detected:
                detected[key] = value
        if detected.get("context_window"):
            break
    return detected
