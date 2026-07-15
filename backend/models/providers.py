import asyncio
import json
import re
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
    # Remote API providers must have a key; local OpenAI-compatible runtimes
    # (vLLM, llama.cpp server, Ollama) usually run without auth, so a missing
    # key is only an error when the provider is a remote API.
    if is_api_provider(model):
        api_key, _source = _key(model)
        return {"Authorization": f"Bearer {api_key}"}
    api_key, _source = model_secrets.api_key_for(model)
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def _anthropic_headers(model):
    api_key, _source = _key(model)
    return {
        "x-api-key": api_key,
        "anthropic-version": str(model.get("anthropic_version") or model.get("anthropicVersion") or "2023-06-01"),
    }


def _gemini_headers(model):
    api_key, _source = _key(model)
    return {"x-goog-api-key": api_key}


def chat_url(model, stream=False):
    provider = provider_key(model.get("provider"))
    base = _base(model)
    if provider == "anthropic":
        return base.rstrip("/") + "/messages"
    if provider == "gemini":
        model_id = str(model.get("model") or default_model("gemini")).removeprefix("models/")
        verb = "streamGenerateContent" if stream else "generateContent"
        suffix = "?alt=sse" if stream else ""
        return base.rstrip("/") + f"/models/{urllib.parse.quote(model_id, safe='.-_')}:{verb}{suffix}"
    if not base:
        return ""
    # Everything else — the OpenAI API itself, remote OpenAI-compatible APIs,
    # and every local runtime this stack deploys (vLLM, llama.cpp server,
    # Ollama's OpenAI endpoint) — speaks the /chat/completions dialect.
    return base.rstrip("/") + "/chat/completions"


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


def _anthropic_payload(model, messages, max_tokens, temperature, tools=None):
    system, kept = _system_and_messages(messages)
    
    # Anthropic uses alternating user/assistant messages. If we have tool outputs, we format them as user messages.
    formatted_messages = []
    for msg in kept:
        if msg["role"] == "tool":
            # Convert tool result to user message with tool_result content
            formatted_messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id"),
                    "content": str(msg.get("content"))
                }]
            })
        elif msg.get("tool_calls"):
            # Assistant message with tool calls
            content = []
            if msg.get("content"):
                content.append({"type": "text", "text": msg["content"]})
            for tc in msg["tool_calls"]:
                content.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": tc.get("args", {})
                })
            formatted_messages.append({
                "role": "assistant",
                "content": content
            })
        else:
            formatted_messages.append(msg)

    payload = {
        "model": model.get("model") or default_model("anthropic"),
        "max_tokens": max_tokens,
        "messages": _merge_same_role(formatted_messages),
        "temperature": temperature,
    }
    if system:
        payload["system"] = system
    
    if tools:
        anthropic_tools = []
        for t in tools:
            anthropic_tools.append({
                "name": t["id"], # Rasputin defines tool names in "id"
                "description": t.get("description", ""),
                "input_schema": t.get("input_schema", {"type": "object", "properties": {}})
            })
        payload["tools"] = anthropic_tools

    return payload


def _gemini_payload(model, messages, max_tokens, temperature, tools=None):
    system, kept = _system_and_messages(messages)
    contents = []
    for message in kept:
        if message["role"] == "tool":
            contents.append({
                "role": "user",
                "parts": [{
                    "functionResponse": {
                        "name": message.get("name") or "tool",
                        "response": {"result": message.get("content")}
                    }
                }]
            })
        elif message.get("tool_calls"):
            parts = []
            if message.get("content"):
                parts.append({"text": message["content"]})
            for tc in message["tool_calls"]:
                parts.append({
                    "functionCall": {
                        "name": tc["name"],
                        "args": tc.get("args", {})
                    }
                })
            contents.append({"role": "model", "parts": parts})
        else:
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
        
    if tools:
        gemini_tools = []
        for t in tools:
            gemini_tools.append({
                "name": t["id"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}})
            })
        payload["tools"] = [{"functionDeclarations": gemini_tools}]
        
    return payload


def _format_openai_messages(messages):
    # Rasputin's internal tool-call shape is {id, name, args} (see
    # _parse_openai_response / _finalize_tool_calls). That's what we parse
    # OUT of a model response, but OpenAI's wire format for an assistant
    # message going back IN requires each entry nested under
    # type:"function" / function:{name, arguments (a JSON string)}. Without
    # this, the second hop of any tool loop re-sends the internal shape
    # verbatim and a strict server (llama.cpp) rejects it outright.
    formatted = []
    for msg in messages or []:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            formatted.append({
                "role": "assistant",
                "content": msg.get("content") or None,
                "tool_calls": [
                    {
                        "id": tc.get("id"),
                        "type": "function",
                        "function": {
                            "name": tc.get("name"),
                            "arguments": json.dumps(tc.get("args", {}), ensure_ascii=False),
                        },
                    }
                    for tc in msg["tool_calls"]
                ],
            })
        else:
            formatted.append(msg)
    return formatted


def _openai_payload(model, messages, max_tokens, temperature, tools=None):
    payload = {
        "model": model.get("model") or default_model(model.get("provider")),
        "messages": _format_openai_messages(messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        openai_tools = []
        for t in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t["id"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}})
                }
            })
        payload["tools"] = openai_tools
    return payload


def _parse_anthropic_response(data):
    text_parts = []
    tool_calls = []
    for item in data.get("content", []) if isinstance(data, dict) else []:
        if isinstance(item, dict):
            if item.get("type") == "text":
                text_parts.append(str(item.get("text") or ""))
            elif item.get("type") == "tool_use":
                tool_calls.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "args": item.get("input", {})
                })
    return "\n".join(part for part in text_parts if part).strip(), tool_calls


def _parse_gemini_response(data):
    candidates = data.get("candidates", []) if isinstance(data, dict) else []
    if not candidates:
        return "", []
    content = candidates[0].get("content", {})
    parts = content.get("parts", [])
    
    text_parts = []
    tool_calls = []
    
    for part in parts:
        if isinstance(part, dict):
            if part.get("text"):
                text_parts.append(str(part["text"]))
            elif part.get("functionCall"):
                fc = part["functionCall"]
                tool_calls.append({
                    "id": f"call_{fc.get('name')}",
                    "name": fc.get("name"),
                    "args": fc.get("args", {})
                })
                
    return "\n".join(text_parts).strip(), tool_calls


def _parse_openai_response(data):
    message = data["choices"][0]["message"]
    text = message.get("content") or ""
    tool_calls = []
    
    for tc in message.get("tool_calls", []):
        if tc.get("type") == "function":
            fn = tc.get("function", {})
            args = {}
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except Exception:
                pass
            tool_calls.append({
                "id": tc.get("id"),
                "name": fn.get("name"),
                "args": args
            })
            
    return text.strip(), tool_calls


def _emit(on_delta, event):
    if not on_delta:
        return
    try:
        on_delta(event)
    except Exception:
        # A misbehaving delta consumer must never abort the model request —
        # the assembled (text, tool_calls) result is the source of truth.
        pass


def _open_sse(url, payload, headers, timeout=120):
    data = json.dumps(payload).encode("utf-8")
    req_headers = {"Accept": "text/event-stream", "Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=req_headers, method="POST")
    return urllib.request.urlopen(req, timeout=timeout)


def _iter_sse(response):
    """Yield the payload of each `data:` line. Stops on [DONE]."""
    for raw in response:
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data:"):
            continue
        data = line[len("data:"):].strip()
        if data == "[DONE]":
            return
        if data:
            yield data


def _finalize_tool_calls(slots):
    tool_calls = []
    for slot in slots:
        if not slot.get("name"):
            continue
        try:
            args = json.loads(slot.get("arguments") or "{}")
        except Exception:
            args = {}
        tool_calls.append({
            "id": slot.get("id") or f"call_{slot['name']}",
            "name": slot["name"],
            "args": args,
        })
    return tool_calls


def _stream_openai(url, payload, headers, on_delta):
    text_parts = []
    slots = {}
    with _open_sse(url, payload, headers) as response:
        for data in _iter_sse(response):
            try:
                chunk = json.loads(data)
            except Exception:
                continue
            for choice in chunk.get("choices") or []:
                delta = choice.get("delta") or {}
                piece = delta.get("content")
                if piece:
                    text_parts.append(piece)
                    _emit(on_delta, {"type": "text", "text": piece})
                for tc in delta.get("tool_calls") or []:
                    index = tc.get("index", 0)
                    slot = slots.setdefault(index, {"id": "", "name": "", "arguments": ""})
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name") and not slot["name"]:
                        slot["name"] = fn["name"]
                        _emit(on_delta, {"type": "tool_call", "id": slot["id"], "name": slot["name"]})
                    if fn.get("arguments"):
                        slot["arguments"] += fn["arguments"]
    ordered = [slots[key] for key in sorted(slots)]
    return "".join(text_parts).strip(), _finalize_tool_calls(ordered)


def _stream_anthropic(url, payload, headers, on_delta):
    blocks = {}
    with _open_sse(url, payload, headers) as response:
        for data in _iter_sse(response):
            try:
                event = json.loads(data)
            except Exception:
                continue
            kind = event.get("type")
            if kind == "content_block_start":
                index = event.get("index", 0)
                block = event.get("content_block") or {}
                blocks[index] = {
                    "type": block.get("type"),
                    "text": "",
                    "id": block.get("id", ""),
                    "name": block.get("name", ""),
                    "arguments": "",
                }
                if block.get("type") == "tool_use":
                    _emit(on_delta, {"type": "tool_call", "id": block.get("id", ""), "name": block.get("name", "")})
            elif kind == "content_block_delta":
                index = event.get("index", 0)
                block = blocks.setdefault(index, {"type": "text", "text": "", "id": "", "name": "", "arguments": ""})
                delta = event.get("delta") or {}
                if delta.get("type") == "text_delta" and delta.get("text"):
                    block["text"] += delta["text"]
                    _emit(on_delta, {"type": "text", "text": delta["text"]})
                elif delta.get("type") == "input_json_delta" and delta.get("partial_json"):
                    block["arguments"] += delta["partial_json"]
            elif kind == "message_stop":
                break
    ordered = [blocks[key] for key in sorted(blocks)]
    text = "\n".join(block["text"] for block in ordered if block["type"] == "text" and block["text"]).strip()
    tool_slots = [block for block in ordered if block["type"] == "tool_use"]
    return text, _finalize_tool_calls(tool_slots)


def _stream_gemini(url, payload, headers, on_delta):
    text_parts = []
    tool_calls = []
    with _open_sse(url, payload, headers) as response:
        for data in _iter_sse(response):
            try:
                chunk = json.loads(data)
            except Exception:
                continue
            candidates = chunk.get("candidates") or []
            if not candidates:
                continue
            for part in (candidates[0].get("content") or {}).get("parts") or []:
                if not isinstance(part, dict):
                    continue
                if part.get("text"):
                    text_parts.append(str(part["text"]))
                    _emit(on_delta, {"type": "text", "text": str(part["text"])})
                elif part.get("functionCall"):
                    fc = part["functionCall"]
                    call = {"id": f"call_{fc.get('name')}", "name": fc.get("name"), "args": fc.get("args", {})}
                    tool_calls.append(call)
                    _emit(on_delta, {"type": "tool_call", "id": call["id"], "name": call["name"]})
    return "".join(text_parts).strip(), tool_calls


REASONING_LEVELS = {"off", "low", "medium", "high"}
_ANTHROPIC_THINKING_BUDGETS = {"low": 2048, "medium": 8192, "high": 16384}
_GEMINI_THINKING_BUDGETS = {"off": 0, "low": 1024, "medium": 4096, "high": 8192}


def _apply_reasoning(payload, provider, model, reasoning):
    """Translate the UI reasoning level into provider-native request fields.

    "auto" leaves the payload untouched so existing behavior never changes.
    Servers that don't understand a field either ignore it (llama.cpp) or
    reject the request with a clear error the user can fix by switching back
    to Auto.
    """
    if reasoning not in REASONING_LEVELS:
        return payload
    if provider == "anthropic":
        budget = _ANTHROPIC_THINKING_BUDGETS.get(reasoning)
        if budget:
            payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
            # Anthropic requires temperature=1 and max_tokens > budget when
            # extended thinking is enabled.
            payload["temperature"] = 1
            payload["max_tokens"] = max(int(payload.get("max_tokens") or 0), budget + 1024)
    elif provider == "gemini":
        payload.setdefault("generationConfig", {})["thinkingConfig"] = {
            "thinkingBudget": _GEMINI_THINKING_BUDGETS[reasoning],
        }
    else:
        # OpenAI-compatible: reasoning models honor reasoning_effort; local
        # runtimes (llama.cpp/vLLM) additionally accept chat_template_kwargs
        # to toggle hybrid-thinking templates like Qwen3.
        if reasoning == "off":
            if model.get("runtime") != "remote-api":
                payload["chat_template_kwargs"] = {"enable_thinking": False}
        else:
            payload["reasoning_effort"] = reasoning
            if model.get("runtime") != "remote-api":
                payload["chat_template_kwargs"] = {"enable_thinking": True}
    return payload


# Model keys whose local runtime rejected a request carrying tool definitions.
# Populated at runtime the first time such a request 400s, so subsequent calls
# skip tools instead of paying the failed round-trip again. In-process only;
# re-detected after a restart, which is cheap.
_TOOLS_UNSUPPORTED = set()


def tools_unavailable(model_or_key):
    """Return whether this process has observed a local runtime reject tools.

    The flag is learned from an actual tools-bearing HTTP 400, not inferred from
    model names or runtime types. Conversational chat may still degrade to a
    plain reply, while agentic execution uses this signal to fail visibly
    instead of reporting tool-less prose as completed work.
    """
    if isinstance(model_or_key, dict):
        model_key = model_or_key.get("key")
    else:
        model_key = model_or_key
    return bool(model_key and model_key in _TOOLS_UNSUPPORTED)


def supports_agentic_tools(model):
    """Whether a model can safely enter a tool-executing task mode.

    WarSat records this at deployment time. A missing parser for a managed
    local runtime means plain chat is safe but tool definitions are not.
    """
    if not model:
        return False
    if model.get("key") == "dry-run" or model.get("provider") == "mock":
        return True
    if tools_unavailable(model):
        return False
    if is_api_provider(model):
        return True
    if model.get("managed"):
        return model.get("tool_support") == "agentic" or bool(model.get("tool_call_parser"))
    return True


def _http_error_body(exc):
    try:
        return exc.read().decode("utf-8", "replace")
    except Exception:
        return ""


def _parse_context_limit(body):
    """Pull the context length from a vLLM-style 400 ('max_tokens=N cannot be
    greater than max_model_len=...=M') so we can clamp max_tokens and retry.
    Returns the int limit, or None if the body isn't that error."""
    if not body or "max_model_len" not in body:
        return None
    match = re.search(r"max_model_len[^\d]*(\d+)", body)
    return int(match.group(1)) if match else None


def _build_chat_payload(provider, model, messages, max_tokens, temperature, tools, stream, reasoning):
    if provider == "anthropic":
        payload = _anthropic_payload(model, messages, max_tokens, temperature, tools)
        headers = _anthropic_headers(model)
        parser = _parse_anthropic_response
        streamer = _stream_anthropic
        if stream:
            payload["stream"] = True
    elif provider == "gemini":
        payload = _gemini_payload(model, messages, max_tokens, temperature, tools)
        headers = _gemini_headers(model)
        parser = _parse_gemini_response
        streamer = _stream_gemini
    else:
        # OpenAI API, remote OpenAI-compatible APIs, and all local runtimes.
        payload = _openai_payload(model, messages, max_tokens, temperature, tools)
        headers = _openai_headers(model)
        parser = _parse_openai_response
        streamer = _stream_openai
        payload["stream"] = stream
    _apply_reasoning(payload, provider, model, reasoning)
    return payload, headers, parser, streamer


def chat_sync(model, messages, max_tokens, temperature, tools=None, on_delta=None, reasoning="auto"):
    provider = provider_key(model.get("provider"))
    stream = on_delta is not None
    url = chat_url(model, stream=stream)
    if not url:
        raise AppError("model_base_url_missing", "Model has no base URL to send chat requests to.", 400)
    security.require_local_url(url)

    # Local runtimes are less forgiving than hosted APIs: a vLLM server started
    # without --enable-auto-tool-choice rejects any request carrying tools, and
    # llama.cpp/vLLM reject max_tokens > the model's context. Rather than fail
    # the whole chat, degrade for local runtimes only (remote APIs untouched):
    # drop tools / clamp max_tokens and retry once, remembering per model that
    # tools are unsupported so later calls skip them. Dropping tools turns an
    # agentic turn into a plain reply — fine for conversational chat, but note
    # the agentic tool loop cannot actually execute tools on such a runtime.
    local_like = not is_api_provider(model)
    model_key = model.get("key")
    cur_tools = None if (local_like and tools and model_key in _TOOLS_UNSUPPORTED) else tools
    cur_max = max_tokens

    first_error = None
    text, tool_calls = None, None
    for _ in range(3):
        payload, headers, parser, streamer = _build_chat_payload(
            provider, model, messages, cur_max, temperature, cur_tools, stream, reasoning
        )
        try:
            if stream:
                text, tool_calls = streamer(url, payload, headers, on_delta)
            else:
                data = _request_json(url, "POST", payload, headers, 60)
                text, tool_calls = parser(data)
            break
        except urllib.error.HTTPError as exc:
            if first_error is None:
                first_error = exc
            if not (local_like and exc.code == 400):
                raise
            body = _http_error_body(exc)
            if cur_tools:
                # Any 400 while tools are present: the runtime can't accept them.
                if model_key:
                    _TOOLS_UNSUPPORTED.add(model_key)
                cur_tools = None
                continue
            limit = _parse_context_limit(body)
            if limit and cur_max > limit:
                cur_max = limit
                continue
            raise first_error
    else:
        if first_error is not None:
            raise first_error

    if not text and not tool_calls:
        raise AppError("model_response_empty", "Provider returned no text or tool response.", 502)
    return text, tool_calls


async def chat(model, messages, max_tokens=1024, temperature=0.2, tools=None, on_delta=None, reasoning="auto"):
    """on_delta, when given, switches to a streaming request. It is invoked
    from a worker thread with {"type": "text", "text": ...} and
    {"type": "tool_call", "id": ..., "name": ...} events as they arrive;
    the returned (text, tool_calls) is identical either way."""
    return await asyncio.to_thread(chat_sync, model, messages, max_tokens, temperature, tools, on_delta, reasoning)


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
