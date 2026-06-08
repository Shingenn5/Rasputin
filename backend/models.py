import asyncio
import json
import os
import urllib.error
import urllib.request

from . import audit
from . import context_governor
from . import model_registry
from . import model_providers


def LOCAL_MODELS():
    return {m["key"]: {"url": m.get("url", ""), "model": m.get("model", "")} for m in model_registry.all_models()}


def _read_http_error(exc):
    try:
        raw = exc.read().decode("utf-8")
    except Exception:
        raw = ""
    message = raw.strip() or str(exc)
    try:
        body = json.loads(raw)
        if isinstance(body, dict):
            err = body.get("error")
            if isinstance(err, dict):
                message = err.get("message") or message
            elif isinstance(err, str):
                message = err
            elif body.get("message"):
                message = body["message"]
    except Exception:
        body = None
    return {"status_code": getattr(exc, "code", None), "message": message, "body": body}


def _model_failure_message(model_key, cfg, url, exc):
    if isinstance(exc, urllib.error.HTTPError):
        err = _read_http_error(exc)
        status = err["status_code"]
        available = []
        try:
            discovery = model_registry.discover_model(model_key, require_permission=False)
            available = discovery.get("models") or []
        except Exception:
            pass
        if status == 404:
            if available:
                label = "Available model" if len(available) == 1 else "Available models"
                return f"Model {model_key} returned 404. Configured model {cfg.get('model')} was not found. {label}: {', '.join(available)}."
            return f"Model {model_key} returned 404. Configured model {cfg.get('model')} was not found at {url}."
        return f"Model {model_key} returned HTTP {status}: {err['message']}"
    return f"Model {model_key} failed: {exc}"


def _extract_task(text):
    for marker in ["Task:", "Task: "]:
        if marker in text:
            value = text.split(marker, 1)[1].splitlines()[0].strip()
            if value:
                return value
    return text.strip().splitlines()[0][:180] if text.strip() else "this task"


def _dry_run_response(text):
    task = _extract_task(text)
    if text.startswith("Plan this task"):
        return (
            "1. Confirm the workspace and available local context.\n"
            "2. Break the request into the smallest useful steps.\n"
            "3. Use only approved local tools and saved knowledge.\n"
            "4. Report what was done, what was not done, and what needs approval."
        )
    if text.startswith("Execute this plan"):
        return (
            f"Dry-run execution preview for: {task}\n\n"
            "No model endpoint, file mutation, web request, or system command was used. "
            "A real run would use the selected local model and approved tools only."
        )
    if text.startswith("Write the final user-facing answer"):
        return (
            f"Dry-run complete for: {task}\n\n"
            "This was a safe preview run. Rasputin did not call a real model, change files, "
            "or use external tools. Select a healthy local model when you want an actual answer."
        )
    return f"Dry-run preview for: {task}"


def _as_int(value, fallback):
    try:
        parsed = int(value)
        return parsed if parsed > 0 else fallback
    except Exception:
        return fallback


def _trim_text(text, max_chars):
    text = str(text or "")
    if len(text) <= max_chars:
        return text
    if max_chars < 300:
        return text[:max_chars]
    head = max_chars // 3
    tail = max_chars - head - 76
    return (
        text[:head].rstrip()
        + "\n\n[rasputin: prompt context shortened to fit the selected local model]\n\n"
        + text[-tail:].lstrip()
    )


def _fit_messages(messages, cfg, max_tokens):
    cfg = dict(cfg or {})
    if os.environ.get("RASPUTIN_CONTEXT_WINDOW") and not (cfg.get("context_window") or cfg.get("contextWindow")):
        cfg["context_window"] = os.environ.get("RASPUTIN_CONTEXT_WINDOW")
    context_window = context_governor.normalize_limits(cfg)["contextWindow"]
    max_input_tokens = max(128, context_window - max_tokens - 64)
    char_budget = max_input_tokens * 2
    fitted = []
    remaining = char_budget
    for message in reversed(messages or []):
        content = str(message.get("content", ""))
        if remaining <= 0:
            break
        next_content = _trim_text(content, remaining)
        fitted.insert(0, {**message, "content": next_content})
        remaining -= len(next_content)
    return fitted or [{"role": "user", "content": ""}]


async def chat(model_key, messages, temperature=0.2):
    cfg = model_registry.get_model(model_key) or model_registry.get_model("dry-run")
    url = model_registry.chat_url(cfg)
    if model_key == "dry-run" or cfg.get("provider") == "mock" or not url:
        user_msg = messages[-1]["content"] if messages else ""
        return _dry_run_response(user_msg)

    cfg_for_limits = dict(cfg or {})
    if os.environ.get("RASPUTIN_MAX_OUTPUT_TOKENS") and not (cfg_for_limits.get("max_tokens") or cfg_for_limits.get("maxTokens")):
        cfg_for_limits["max_tokens"] = os.environ.get("RASPUTIN_MAX_OUTPUT_TOKENS")
    max_tokens = context_governor.normalize_limits(cfg_for_limits)["maxTokens"]
    fitted_messages = _fit_messages(messages, cfg, max_tokens)

    if model_providers.is_api_provider(cfg):
        try:
            return await model_providers.chat(cfg, fitted_messages, max_tokens, temperature)
        except Exception as exc:
            message = _model_failure_message(model_key, cfg, url, exc)
            audit.log("model_chat_failed", {
                "key": model_key,
                "model": cfg.get("model"),
                "url": url,
                "provider": cfg.get("provider"),
                "error": message,
            })
            raise RuntimeError(message) from None

    from . import security
    security.require_local_url(url)

    payload = {
        "model": cfg["model"],
        "messages": fitted_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    def post_it():
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8")
        return json.loads(raw)

    try:
        data = await asyncio.to_thread(post_it)
    except Exception as exc:
        message = _model_failure_message(model_key, cfg, url, exc)
        audit.log("model_chat_failed", {
            "key": model_key,
            "model": cfg.get("model"),
            "url": url,
            "error": message,
        })
        raise RuntimeError(message) from None
    return data["choices"][0]["message"]["content"]
