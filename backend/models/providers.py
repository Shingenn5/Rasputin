import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request

from backend.models import secrets as model_secrets
from backend.core import security as security
from backend.core.response import AppError

OPENAI_COMPATIBLE_API_PROVIDERS = {"openai", "openai-compatible-remote"}
NATIVE_API_PROVIDERS = {"anthropic", "gemini"}
API_PROVIDERS = OPENAI_COMPATIBLE_API_PROVIDERS | NATIVE_API_PROVIDERS

DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "openai-compatible-remote": "",
    "anthropic": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
}

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-20241022",
    "gemini": "gemini-2.5-flash",
}


def provider_key(provider):
    return str(provider or "").strip().lower()


def is_api_provider(model_or_provider):
    provider = model_or_provider if isinstance(model_or_provider, str) else (model_or_provider or {}).get("provider")
    return provider_key(provider) in API_PROVIDERS


def is_openai_compatible_api(model_or_provider):
    provider = model_or_provider if isinstance(model_or_provider, str) else (model_or_provider or {}).get("provider")
    return provider_key(provider) in OPENAI_COMPATIBLE_API_PROVIDERS


def default_base_url(provider):
    return DEFAULT_BASE_URLS.get(provider_key(provider), "")


def default_model(provider):
    return DEFAULT_MODELS.get(provider_key(provider), "")


def public_provider_options():
    return [
        {
            "id": "openai",
            "name": "OpenAI",
            "apiStyle": "openai-compatible",
            "defaultBaseUrl": DEFAULT_BASE_URLS["openai"],
            "defaultKeyEnv": "OPENAI_API_KEY",
        },
        {
            "id": "anthropic",
            "name": "Anthropic",
            "apiStyle": "anthropic-messages",
            "defaultBaseUrl": DEFAULT_BASE_URLS["anthropic"],
            "defaultKeyEnv": "ANTHROPIC_API_KEY",
        },
        {
            "id": "gemini",
            "name": "Google Gemini",
            "apiStyle": "gemini-generate-content",
            "defaultBaseUrl": DEFAULT_BASE_URLS["gemini"],
            "defaultKeyEnv": "GEMINI_API_KEY",
        },
        {
            "id": "openai-compatible-remote",
            "name": "Other OpenAI-compatible API",
            "apiStyle": "openai-compatible",
            "defaultBaseUrl": "",
            "defaultKeyEnv": "",
        },
    ]


def _base(model):
    base = str((model or {}).get("base_url") or (model or {}).get("baseUrl") or default_base_url((model or {}).get("provider"))).strip().rstrip("/")
    return base


def _key(model):
    api_key, source = model_secrets.api_key_for(model)
    if not api_key:
        raise AppError(
            "model_api_key_missing",
            f"{model.get('name') or model.get('key') or 'This model'} needs an API key from env or the local secret store.",
            400,
        )
    return api_key, source


def _request_json(url, method="GET", payload=None, headers=None, timeout=45):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req_headers = {"Accept": "application/json", **(headers or {})}
    if data is not None:
        req_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    raw = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8")
    return json.loads(raw)


def _openai_headers(model):
    api_key, _source = _key(model)
    return {"Authorization": f"Bearer {api_key}"}


def _anthropic_headers(model):
    api_key, _source = _key(model)
    return {
        "x-api-key": api_key,
        "anthropic-version": str(model.get("anthropic_version") or model.get("anthropicVersion") or "2023-06-01"),
    }


def _gemini_headers(model):
    api_key, _source = _key(model)
    return {"x-goog-api-key": api_key}


def chat_url(model):
    provider = provider_key(model.get("provider"))
    base = _base(model)
    if provider in OPENAI_COMPATIBLE_API_PROVIDERS:
        return base.rstrip("/") + "/chat/completions"
    if provider == "anthropic":
        return base.rstrip("/") + "/messages"
    if provider == "gemini":
        model_id = str(model.get("model") or default_model("gemini")).removeprefix("models/")
        return base.rstrip("/") + f"/models/{urllib.parse.quote(model_id, safe='.-_')}:generateContent"
    return ""


def models_url(model):
    provider = provider_key(model.get("provider"))
    base = _base(model)
    if provider in API_PROVIDERS:
        return base.rstrip("/") + "/models"
    return ""


def _system_and_messages(messages):
    system = []
    kept = []
    for message in messages or []:
        role = str(message.get("role") or "user").lower()
        content = str(message.get("content") or "")
        if role in {"system", "developer"}:
            if content:
                system.append(content)
            continue
        kept.append({"role": "assistant" if role == "assistant" else "user", "content": content})
    return "\n\n".join(system), kept or [{"role": "user", "content": ""}]


def _merge_same_role(messages):
    merged = []
    for message in messages:
        if merged and merged[-1]["role"] == message["role"]:
            merged[-1]["content"] = (merged[-1]["content"] + "\n\n" + message["content"]).strip()
        else:
            merged.append(dict(message))
    return merged


def _anthropic_payload(model, messages, max_tokens, temperature):
    system, kept = _system_and_messages(messages)
    payload = {
        "model": model.get("model") or default_model("anthropic"),
        "max_tokens": max_tokens,
        "messages": _merge_same_role(kept),
        "temperature": temperature,
    }
    if system:
        payload["system"] = system
    return payload


def _gemini_payload(model, messages, max_tokens, temperature):
    system, kept = _system_and_messages(messages)
    contents = []
    for message in kept:
        role = "model" if message["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": message["content"]}]})
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    return payload


def _openai_payload(model, messages, max_tokens, temperature):
    return {
        "model": model.get("model") or default_model(model.get("provider")),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }


def _parse_anthropic_text(data):
    parts = []
    for item in data.get("content", []) if isinstance(data, dict) else []:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text") or ""))
    return "\n".join(part for part in parts if part).strip()


def _parse_gemini_text(data):
    candidates = data.get("candidates", []) if isinstance(data, dict) else []
    if not candidates:
        return ""
    content = candidates[0].get("content", {})
    parts = content.get("parts", [])
    return "\n".join(str(part.get("text") or "") for part in parts if isinstance(part, dict) and part.get("text")).strip()


def chat_sync(model, messages, max_tokens, temperature):
    provider = provider_key(model.get("provider"))
    url = chat_url(model)
    security.require_local_url(url)
    if provider in OPENAI_COMPATIBLE_API_PROVIDERS:
        payload = _openai_payload(model, messages, max_tokens, temperature)
        headers = _openai_headers(model)
        parser = lambda data: data["choices"][0]["message"]["content"]
    elif provider == "anthropic":
        payload = _anthropic_payload(model, messages, max_tokens, temperature)
        headers = _anthropic_headers(model)
        parser = _parse_anthropic_text
    elif provider == "gemini":
        payload = _gemini_payload(model, messages, max_tokens, temperature)
        headers = _gemini_headers(model)
        parser = _parse_gemini_text
    else:
        raise AppError("model_provider_unsupported", f"Provider {provider or 'unknown'} is not supported.", 400)

    data = _request_json(url, "POST", payload, headers, 60)
    text = parser(data)
    if not text:
        raise AppError("model_response_empty", "Provider returned no text response.", 502)
    return text


async def chat(model, messages, max_tokens, temperature):
    return await asyncio.to_thread(chat_sync, model, messages, max_tokens, temperature)


def _parse_model_ids(payload, provider):
    if provider == "gemini":
        models = payload.get("models", []) if isinstance(payload, dict) else []
        ids = []
        for item in models:
            if not isinstance(item, dict):
                continue
            ids.append(item.get("baseModelId") or str(item.get("name") or "").removeprefix("models/"))
        return [item for item in ids if item]
    items = payload.get("data", payload) if isinstance(payload, dict) else payload
    ids = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and item.get("id"):
                ids.append(str(item["id"]))
            elif isinstance(item, dict) and item.get("name"):
                ids.append(str(item["name"]).removeprefix("models/"))
            elif isinstance(item, str):
                ids.append(item)
    return ids


def discover_models(model):
    provider = provider_key(model.get("provider"))
    url = models_url(model)
    security.require_local_url(url)
    headers = _gemini_headers(model) if provider == "gemini" else _anthropic_headers(model) if provider == "anthropic" else _openai_headers(model)
    payload = _request_json(url, headers=headers, timeout=15)
    return _parse_model_ids(payload, provider)


def test_payload(model, max_tokens=8):
    provider = provider_key(model.get("provider"))
    if provider == "anthropic":
        return _anthropic_payload(model, [{"role": "user", "content": "Say ok."}], max_tokens, 0)
    if provider == "gemini":
        return _gemini_payload(model, [{"role": "user", "content": "Say ok."}], max_tokens, 0)
    return _openai_payload(model, [{"role": "user", "content": "Say ok."}], max_tokens, 0)
