from __future__ import annotations

import asyncio
import hashlib
import json
import math
import secrets
import threading
import time
import uuid
from collections import deque

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from backend.api.core import require_admin
from backend.core import preferences
from backend.core import runtime_store as store
from backend.core.response import ok
from backend.mcp import tools as tool_relay
from backend.mcp.layer import McpLayer
from backend.models import providers
from backend.models import registry as model_registry


router = APIRouter()
_CONFIG_KEY = "model_serving_config_v1"
_METRICS = deque(maxlen=200)
_METRICS_LOCK = threading.RLock()
_PROTOCOL_VERSION = "2025-11-25"


class ServingError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _defaults():
    return {
        "enabled": False,
        "api_key_hash": "",
        "mcp_tool_execution": False,
    }


def _load_config():
    saved = store.get_kv(_CONFIG_KEY, {})
    return {**_defaults(), **(saved if isinstance(saved, dict) else {})}


def _save_config(config):
    clean = {
        "enabled": bool(config.get("enabled")),
        "api_key_hash": str(config.get("api_key_hash") or ""),
        "mcp_tool_execution": bool(config.get("mcp_tool_execution")),
    }
    store.set_kv(_CONFIG_KEY, clean)
    return clean


def _hash_key(value: str):
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _request_key(request: Request):
    authorization = str(request.headers.get("authorization") or "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return str(
        request.headers.get("x-api-key")
        or request.headers.get("x-rasputin-key")
        or ""
    ).strip()


def _authorize(request: Request):
    config = _load_config()
    if not config["enabled"]:
        raise ServingError("serving_disabled", "Rasputin model serving is disabled.", 503)
    if not config["api_key_hash"]:
        raise ServingError("serving_key_missing", "Generate a serving API key in Models > Serving.", 503)
    supplied = _request_key(request)
    if not supplied or not secrets.compare_digest(_hash_key(supplied), config["api_key_hash"]):
        raise ServingError("authentication_error", "Invalid or missing model-serving API key.", 401)
    return config


def _base_url(request: Request):
    return str(request.base_url).rstrip("/")


def _public_status(request: Request):
    config = _load_config()
    base = _base_url(request)
    configured_models = _configured_models()
    models = _servable_models(configured_models)
    service_status = "ready" if config["enabled"] and config["api_key_hash"] else (
        "disabled" if not config["enabled"] else "needs_key"
    )
    readiness = service_status if service_status != "ready" else ("ready" if models else "no_models")
    next_actions = {
        "disabled": ["Enable model serving when you are ready to expose the gateway."],
        "needs_key": ["Generate a serving API key before sharing an endpoint."],
        "no_models": ["Configure and verify at least one reachable chat model."],
        "ready": [],
    }[readiness]
    with _METRICS_LOCK:
        recent = list(_METRICS)[-20:]
    return {
        "enabled": config["enabled"],
        "api_key_configured": bool(config["api_key_hash"]),
        "readiness": readiness,
        "servable_model_count": len(models),
        "configured_model_count": len(configured_models),
        "has_servable_model": bool(models),
        "next_actions": next_actions,
        "mcp_tool_execution": config["mcp_tool_execution"],
        "bind_policy": "loopback-default",
        "prompt_logging": False,
        "protocols": [
            {
                "id": "openai",
                "name": "OpenAI compatible",
                "status": readiness,
                "endpoints": [f"{base}/v1/models", f"{base}/v1/chat/completions"],
                "features": ["streaming", "tool calls", "usage"],
            },
            {
                "id": "anthropic",
                "name": "Anthropic Messages compatible",
                "status": readiness,
                "endpoints": [f"{base}/v1/messages"],
                "features": ["streaming", "tool_use blocks", "usage"],
            },
            {
                "id": "rasputin",
                "name": "Rasputin native",
                "status": readiness,
                "endpoints": [f"{base}/rasputin/v1/responses", f"{base}/rasputin/v1/metrics"],
                "features": ["request telemetry", "runtime identity", "streaming"],
            },
            {
                "id": "mcp",
                "name": "MCP authenticated JSON-RPC HTTP subset",
                "status": service_status,
                "endpoints": [f"{base}/mcp"],
                "features": ["initialize", "tools/list", "guarded tools/call", "no session resumption"],
            },
        ],
        "recent_requests": recent,
        "metrics_count": len(_METRICS),
    }


def _configured_models(source=None):
    source = model_registry.all_models() if source is None else source
    return [
        model for model in source
        if model.get("key") != "dry-run"
        and model.get("provider") not in {"mock", "hash-vector"}
        and model.get("role") != "embeddings"
    ]


def _servable_models(source=None):
    out = []
    for model in _configured_models(source):
        if model.get("enabled") is False:
            continue
        if not model.get("base_url"):
            continue
        if str(model.get("runtime_status") or "").lower() in {
            "stopped", "unreachable", "error", "failed", "missing", "unhealthy",
        }:
            continue
        out.append(model)
    return out


def _resolve_model(requested):
    models = _servable_models()
    model_id = str(requested or "").strip()
    if not model_id:
        selected = preferences.load("admin").get("selectedModel")
        model_id = str(selected or "").strip()
    model = next(
        (
            item
            for item in models
            if item.get("key") == model_id or item.get("model") == model_id
        ),
        None,
    )
    if not model:
        raise ServingError("model_not_found", f"Model '{model_id or 'unspecified'}' is not available for serving.", 404)
    status = str(model.get("runtime_status") or "").lower()
    if status in {"stopped", "unreachable", "error", "failed", "missing"}:
        raise ServingError("model_unavailable", f"Model '{model.get('key')}' is {status}.", 503)
    return model


def _plain_content(value):
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        return "" if value is None else str(value)
    parts = []
    for block in value:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            parts.append(str(block.get("text") or ""))
    return "\n".join(part for part in parts if part)


def _require_list(value, field):
    if not isinstance(value, list):
        raise ServingError("invalid_request_error", f"{field} must be an array.", 400)
    return value


def _number(value, field, default, minimum=None, maximum=None):
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ServingError("invalid_request_error", f"{field} must be numeric.", 400) from None
    if not math.isfinite(result) or (minimum is not None and result < minimum) or (maximum is not None and result > maximum):
        raise ServingError("invalid_request_error", f"{field} is out of range.", 400)
    return result


def _integer(value, field, default, minimum=1):
    if value is None:
        return default
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ServingError("invalid_request_error", f"{field} must be an integer.", 400) from None
    if result < minimum:
        raise ServingError("invalid_request_error", f"{field} must be at least {minimum}.", 400)
    return result


def _openai_messages(payload):
    messages = []
    raw_messages = _require_list(payload.get("messages"), "messages")
    allowed_roles = {"system", "developer", "user", "assistant", "tool"}
    for raw in raw_messages:
        if not isinstance(raw, dict) or str(raw.get("role") or "").lower() not in allowed_roles:
            raise ServingError("invalid_request_error", "Each message must have a supported role.", 400)
        content = raw.get("content")
        if content is not None and not isinstance(content, (str, list)):
            raise ServingError("invalid_request_error", "message content must be a string or array.", 400)
        message = {
            "role": str(raw.get("role")).lower(),
            "content": _plain_content(raw.get("content")),
        }
        if raw.get("name"):
            message["name"] = raw["name"]
        if raw.get("tool_call_id"):
            message["tool_call_id"] = raw["tool_call_id"]
        tool_calls = []
        if raw.get("tool_calls") is not None and not isinstance(raw.get("tool_calls"), list):
            raise ServingError("invalid_request_error", "tool_calls must be an array.", 400)
        for call in raw.get("tool_calls") or []:
            if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
                raise ServingError("invalid_request_error", "Each tool call must contain a function.", 400)
            fn = call.get("function") or {}
            if not fn.get("name"):
                raise ServingError("invalid_request_error", "Each tool call function needs a name.", 400)
            raw_arguments = fn.get("arguments") or "{}"
            try:
                arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
            except (TypeError, ValueError, json.JSONDecodeError):
                raise ServingError("invalid_request_error", "Tool call arguments must be valid JSON.", 400) from None
            if not isinstance(arguments, dict):
                raise ServingError("invalid_request_error", "Tool call arguments must be a JSON object.", 400)
            tool_calls.append({
                "id": call.get("id") or f"call_{fn.get('name') or 'tool'}",
                "name": fn.get("name") or "tool",
                "args": arguments,
            })
        if tool_calls:
            message["tool_calls"] = tool_calls
        messages.append(message)
    return messages


def _openai_tools(payload):
    out = []
    raw_tools = payload.get("tools")
    if raw_tools is None:
        return out
    for item in _require_list(raw_tools, "tools"):
        if not isinstance(item, dict) or item.get("type") != "function":
            raise ServingError("invalid_request_error", "Only function tools are supported.", 400)
        fn = item.get("function") or {}
        if not fn.get("name") or not isinstance(fn.get("parameters") or {}, dict):
            raise ServingError("invalid_request_error", "Function tools need a name and object parameters.", 400)
        out.append({
            "id": fn["name"],
            "description": fn.get("description") or "",
            "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
        })
    return out


def _openai_tool_choice(payload, tools):
    choice = payload.get("tool_choice")
    if choice is None or choice == "auto":
        return tools
    if choice == "none":
        return []
    if choice == "required" or isinstance(choice, dict):
        raise ServingError(
            "unsupported_tool_choice",
            "This serving adapter supports tool_choice auto and none; required and named choices are not enforceable.",
            400,
        )
    raise ServingError("invalid_request_error", "tool_choice must be auto, none, or a supported choice.", 400)


def _anthropic_messages(payload):
    messages = []
    system = _plain_content(payload.get("system"))
    if system:
        messages.append({"role": "system", "content": system})
    for raw in _require_list(payload.get("messages"), "messages"):
        if not isinstance(raw, dict) or raw.get("role") not in {"user", "assistant"}:
            raise ServingError("invalid_request_error", "Each message must have user or assistant role.", 400)
        role = str(raw.get("role"))
        content = raw.get("content")
        if isinstance(content, str):
            messages.append({"role": role, "content": content})
            continue
        if not isinstance(content, list):
            raise ServingError("invalid_request_error", "message content must be a string or array.", 400)
        text_parts = []
        tool_calls = []
        tool_results = []
        for block in content:
            if not isinstance(block, dict):
                raise ServingError("invalid_request_error", "Each content block must be an object.", 400)
            kind = block.get("type")
            if kind == "text":
                text_parts.append(str(block.get("text") or ""))
            elif kind == "tool_use":
                if not block.get("name") or not isinstance(block.get("input") or {}, dict):
                    raise ServingError("invalid_request_error", "tool_use blocks need name and object input.", 400)
                tool_calls.append({
                    "id": block.get("id") or f"call_{block.get('name') or 'tool'}",
                    "name": block.get("name") or "tool",
                    "args": block.get("input") or {},
                })
            elif kind == "tool_result":
                if not block.get("tool_use_id"):
                    raise ServingError("invalid_request_error", "tool_result blocks need tool_use_id.", 400)
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": block.get("tool_use_id"),
                    "content": _plain_content(block.get("content")),
                })
            else:
                raise ServingError("invalid_request_error", f"Unsupported content block type: {kind}.", 400)
        if text_parts or tool_calls:
            message = {"role": role, "content": "\n".join(text_parts)}
            if tool_calls:
                message["tool_calls"] = tool_calls
            messages.append(message)
        messages.extend(tool_results)
    return messages


def _anthropic_tools(payload):
    out = []
    raw_tools = payload.get("tools")
    if raw_tools is None:
        return out
    for item in _require_list(raw_tools, "tools"):
        if not isinstance(item, dict) or not item.get("name") or not isinstance(item.get("input_schema") or {}, dict):
            raise ServingError("invalid_request_error", "Anthropic tools need a name and object input_schema.", 400)
        out.append({
            "id": item["name"],
            "description": item.get("description") or "",
            "input_schema": item.get("input_schema") or {"type": "object", "properties": {}},
        })
    return out


def _token_estimate(value):
    try:
        text = json.dumps(value, ensure_ascii=False)
    except Exception:
        text = str(value or "")
    return max(0, (len(text) + 3) // 4)


def _wire_tool_calls(tool_calls):
    return [
        {
            "id": call.get("id") or f"call_{call.get('name')}",
            "type": "function",
            "function": {
                "name": call.get("name"),
                "arguments": json.dumps(call.get("args") or {}, ensure_ascii=False),
            },
        }
        for call in tool_calls or []
    ]


def _usage(messages, text, tool_calls, native_metrics=None):
    native = native_metrics or {}
    raw = native.get("usage") or {}
    input_tokens = raw.get("prompt_tokens", raw.get("input_tokens"))
    output_tokens = raw.get("completion_tokens", raw.get("output_tokens"))
    estimated = input_tokens is None or output_tokens is None
    input_tokens = int(input_tokens if input_tokens is not None else _token_estimate(messages))
    output_tokens = int(output_tokens if output_tokens is not None else _token_estimate([text, tool_calls]))
    return {
        "prompt_tokens": input_tokens,
        "completion_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "estimated": estimated,
    }


def _record_metric(protocol, request_id, model, started, first_token_at, messages, text, tool_calls, native_metrics, error=None):
    finished = time.perf_counter()
    usage = _usage(messages, text, tool_calls, native_metrics)
    timing = (native_metrics or {}).get("timing") or {}
    record = {
        "request_id": request_id,
        "protocol": protocol,
        "model": model.get("key"),
        "runtime": model.get("runtime") or model.get("provider"),
        "queue_ms": 0.0,
        "ttft_ms": round(((first_token_at or finished) - started) * 1000, 2),
        "total_ms": round((finished - started) * 1000, 2),
        "decode_tokens_per_second": timing.get("predicted_per_second"),
        "input_tokens": usage["prompt_tokens"],
        "output_tokens": usage["completion_tokens"],
        "usage_estimated": usage["estimated"],
        "tool_call_count": len(tool_calls or []),
        "status": "error" if error else "completed",
        "error": (error.code if isinstance(error, ServingError) else "upstream_error") if error else "",
        "created_at": time.time(),
    }
    with _METRICS_LOCK:
        _METRICS.append(record)
    return record, usage


async def _infer(protocol, model, messages, max_tokens, temperature, tools, reasoning="auto", stream=False, request_id=None, on_event=None):
    request_id = request_id or f"req_{uuid.uuid4().hex[:20]}"
    started = time.perf_counter()
    first_token_at = None
    native_metrics = {}

    def on_delta(event):
        nonlocal first_token_at
        if event.get("type") == "text" and first_token_at is None:
            first_token_at = time.perf_counter()
        if event.get("type") == "metrics":
            native_metrics.update({key: value for key, value in event.items() if key != "type"})
        if on_event:
            on_event(event)

    try:
        text, tool_calls = await providers.chat(
            model,
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools or None,
            on_delta=on_delta if stream else None,
            reasoning=reasoning,
        )
    except Exception as exc:
        _record_metric(protocol, request_id, model, started, first_token_at, messages, "", [], native_metrics, error=exc)
        raise
    record, usage = _record_metric(
        protocol, request_id, model, started, first_token_at, messages, text, tool_calls, native_metrics
    )
    return request_id, text, tool_calls, record, usage


def _openai_error(exc):
    if isinstance(exc, ServingError):
        status, code, message = exc.status, exc.code, exc.message
    else:
        status, code, message = 502, "upstream_error", "Model request failed."
    return JSONResponse(status_code=status, content={
        "error": {"message": message, "type": code, "param": None, "code": code}
    })


def _anthropic_error(exc):
    if isinstance(exc, ServingError):
        status, code, message = exc.status, exc.code, exc.message
    else:
        status, code, message = 502, "api_error", "Model request failed."
    return JSONResponse(status_code=status, content={
        "type": "error", "error": {"type": code, "message": message}
    })


def _native_error(exc):
    if isinstance(exc, ServingError):
        status, code, message = exc.status, exc.code, exc.message
    else:
        status, code, message = 502, "upstream_error", "Model request failed."
    return JSONResponse(status_code=status, content={
        "error": {"code": code, "message": message}
    })


def _start_stream_inference(protocol, model, messages, max_tokens, temperature, tools, reasoning):
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue()
    request_id = f"req_{uuid.uuid4().hex[:20]}"

    def push(event):
        loop.call_soon_threadsafe(queue.put_nowait, ("event", event))

    async def run():
        try:
            result = await _infer(
                protocol, model, messages, max_tokens, temperature, tools,
                reasoning, stream=True, request_id=request_id, on_event=push,
            )
            await asyncio.sleep(0)
            await queue.put(("done", result))
        except Exception as exc:
            await queue.put(("error", exc))

    task = asyncio.create_task(run())
    return request_id, queue, task


def _stream_error(protocol, exc):
    if isinstance(exc, ServingError):
        code, message = exc.code, exc.message
    else:
        code, message = "upstream_error", "Model request failed."
    if protocol == "anthropic":
        return f"event: error\ndata: {json.dumps({'type': 'error', 'error': {'type': code, 'message': message}})}\n\n"
    return f"data: {json.dumps({'error': {'message': message, 'type': code, 'code': code}})}\n\n"


@router.get("/api/model-serving")
async def serving_status(request: Request, _user=Depends(require_admin)):
    return ok(_public_status(request))


@router.post("/api/model-serving/config")
async def serving_config(req: dict, request: Request, _user=Depends(require_admin)):
    config = _load_config()
    if "enabled" in req:
        config["enabled"] = bool(req["enabled"])
    if "mcpToolExecution" in req or "mcp_tool_execution" in req:
        config["mcp_tool_execution"] = bool(req.get("mcpToolExecution", req.get("mcp_tool_execution")))
    _save_config(config)
    return ok(_public_status(request))


@router.post("/api/model-serving/key/rotate")
async def serving_key_rotate(request: Request, _user=Depends(require_admin)):
    api_key = f"ras_{secrets.token_urlsafe(32)}"
    config = _load_config()
    config["api_key_hash"] = _hash_key(api_key)
    config["enabled"] = True
    _save_config(config)
    return ok({**_public_status(request), "api_key": api_key})


@router.get("/v1/models")
async def openai_models(request: Request):
    try:
        _authorize(request)
        data = [
            {
                "id": model.get("key"),
                "object": "model",
                "created": 0,
                "owned_by": "rasputin",
                "rasputin_runtime": model.get("runtime") or model.get("provider"),
                "rasputin_model_id": model.get("model"),
            }
            for model in _servable_models()
        ]
        return {"object": "list", "data": data}
    except Exception as exc:
        return _openai_error(exc)


@router.post("/v1/chat/completions")
async def openai_chat_completions(req: dict, request: Request):
    try:
        _authorize(request)
        model = _resolve_model(req.get("model"))
        messages = _openai_messages(req)
        if not messages:
            raise ServingError("invalid_request_error", "messages must contain at least one message.", 400)
        tools = _openai_tool_choice(req, _openai_tools(req))
        max_tokens = _integer(req.get("max_completion_tokens") or req.get("max_tokens"), "max_tokens", 1024)
        temperature = _number(req.get("temperature"), "temperature", 0.2, 0, 2)
        stream_requested = req.get("stream", False)
        if not isinstance(stream_requested, bool):
            raise ServingError("invalid_request_error", "stream must be boolean.", 400)
        if stream_requested:
            request_id, events, task = _start_stream_inference(
                "openai", model, messages, max_tokens, temperature, tools, req.get("reasoning_effort", "auto")
            )
        else:
            request_id, text, tool_calls, metric, usage = await _infer(
                "openai", model, messages, max_tokens, temperature, tools,
                req.get("reasoning_effort", "auto"), stream=False,
            )
        if not stream_requested:
            message = {"role": "assistant", "content": text or None}
            if tool_calls:
                message["tool_calls"] = _wire_tool_calls(tool_calls)
            return {
                "id": f"chatcmpl_{request_id[4:]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model.get("key"),
                "choices": [{
                    "index": 0,
                    "message": message,
                    "finish_reason": "tool_calls" if tool_calls else "stop",
                    "logprobs": None,
                }],
                "usage": {key: value for key, value in usage.items() if key != "estimated"},
                "rasputin": {"request_id": request_id, "metrics": metric},
            }

        async def stream():
            body_id = f"chatcmpl_{request_id[4:]}"
            created = int(time.time())
            initial = {"id": body_id, "object": "chat.completion.chunk", "created": created,
                       "model": model.get("key"), "choices": [{"index": 0,
                       "delta": {"role": "assistant"}, "finish_reason": None}]}
            yield f"data: {json.dumps(initial)}\n\n"
            result = None
            while True:
                kind, value = await events.get()
                if kind == "event":
                    if value.get("type") == "text" and value.get("text"):
                        chunk = {**initial, "choices": [{"index": 0, "delta": {"content": value["text"]}, "finish_reason": None}]}
                        yield f"data: {json.dumps(chunk)}\n\n"
                elif kind == "error":
                    yield _stream_error("openai", value)
                    yield "data: [DONE]\n\n"
                    return
                else:
                    result = value
                    break
            _, text, tool_calls, metric, usage = result
            if tool_calls:
                chunk = {**initial, "choices": [{"index": 0, "delta": {"tool_calls": [
                    {**call, "index": index} for index, call in enumerate(_wire_tool_calls(tool_calls))
                ]}, "finish_reason": None}]}
                yield f"data: {json.dumps(chunk)}\n\n"
            final = {**initial, "choices": [{"index": 0, "delta": {},
                     "finish_reason": "tool_calls" if tool_calls else "stop"}]}
            yield f"data: {json.dumps(final)}\n\n"
            if (req.get("stream_options") or {}).get("include_usage"):
                terminal = {**initial, "choices": [], "usage": {key: value for key, value in usage.items() if key != "estimated"}}
                yield f"data: {json.dumps(terminal)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")
    except Exception as exc:
        return _openai_error(exc)


@router.post("/v1/messages")
async def anthropic_messages(req: dict, request: Request):
    try:
        _authorize(request)
        version = request.headers.get("anthropic-version")
        if not version:
            raise ServingError("invalid_request_error", "anthropic-version header is required.", 400)
        if version != "2023-06-01":
            raise ServingError("invalid_request_error", "Unsupported anthropic-version.", 400)
        model = _resolve_model(req.get("model"))
        messages = _anthropic_messages(req)
        if not messages:
            raise ServingError("invalid_request_error", "messages must contain at least one message.", 400)
        tools = _anthropic_tools(req)
        if req.get("tool_choice") not in (None, "auto"):
            raise ServingError("unsupported_tool_choice", "Anthropic tool_choice enforcement is not supported by this adapter.", 400)
        max_tokens = _integer(req.get("max_tokens"), "max_tokens", 1024)
        temperature = _number(req.get("temperature"), "temperature", 0.2, 0, 1)
        stream_requested = req.get("stream", False)
        if not isinstance(stream_requested, bool):
            raise ServingError("invalid_request_error", "stream must be boolean.", 400)
        if not stream_requested:
            request_id, text, tool_calls, metric, usage = await _infer(
                "anthropic", model, messages, max_tokens, temperature, tools, stream=False,
            )
            content_blocks = ([{"type": "text", "text": text}] if text else []) + [
                {"type": "tool_use", "id": call.get("id"), "name": call.get("name"), "input": call.get("args") or {}}
                for call in tool_calls
            ]
            return {
                "id": f"msg_{request_id[4:]}", "type": "message", "role": "assistant",
                "model": model.get("key"), "content": content_blocks,
                "stop_reason": "tool_use" if tool_calls else "end_turn", "stop_sequence": None,
                "usage": {"input_tokens": usage["prompt_tokens"], "output_tokens": usage["completion_tokens"]},
                "rasputin": {"request_id": request_id, "metrics": metric},
            }

        request_id, events, task = _start_stream_inference(
            "anthropic", model, messages, max_tokens, temperature, tools, "auto"
        )

        async def stream():
            message_id = f"msg_{request_id[4:]}"
            start = {"id": message_id, "type": "message", "role": "assistant", "model": model.get("key"),
                     "content": [], "stop_reason": None, "stop_sequence": None,
                     "usage": {"input_tokens": 0, "output_tokens": 0}}
            yield f"event: message_start\ndata: {json.dumps({'type': 'message_start', 'message': start})}\n\n"
            index = 0
            text_index = None
            tool_indexes = []
            result = None
            while True:
                kind, value = await events.get()
                if kind == "event":
                    if value.get("type") == "text" and value.get("text"):
                        if text_index is None:
                            text_index = index
                            index += 1
                            yield f"event: content_block_start\ndata: {json.dumps({'type': 'content_block_start', 'index': text_index, 'content_block': {'type': 'text', 'text': ''}})}\n\n"
                        yield f"event: content_block_delta\ndata: {json.dumps({'type': 'content_block_delta', 'index': text_index, 'delta': {'type': 'text_delta', 'text': value['text']}})}\n\n"
                    elif value.get("type") == "tool_call":
                        tool_index = index
                        index += 1
                        tool_indexes.append((tool_index, value.get("id"), value.get("name")))
                        block = {"type": "tool_use", "id": value.get("id"), "name": value.get("name"), "input": {}}
                        yield f"event: content_block_start\ndata: {json.dumps({'type': 'content_block_start', 'index': tool_index, 'content_block': block})}\n\n"
                elif kind == "error":
                    yield _stream_error("anthropic", value)
                    return
                else:
                    result = value
                    break
            _, text, tool_calls, metric, usage = result
            if text_index is not None:
                yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': text_index})}\n\n"
            for position, (tool_index, _tool_id, _tool_name) in enumerate(tool_indexes):
                call = tool_calls[position] if position < len(tool_calls) else None
                if call:
                    delta = {"type": "input_json_delta", "partial_json": json.dumps(call.get("args") or {})}
                    yield f"event: content_block_delta\ndata: {json.dumps({'type': 'content_block_delta', 'index': tool_index, 'delta': delta})}\n\n"
                yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': tool_index})}\n\n"
            message_delta = {
                "type": "message_delta", "delta": {"stop_reason": "tool_use" if tool_calls else "end_turn", "stop_sequence": None},
                "usage": {"output_tokens": usage["completion_tokens"]},
            }
            yield f"event: message_delta\ndata: {json.dumps(message_delta)}\n\n"
            yield f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")
    except Exception as exc:
        return _anthropic_error(exc)


@router.post("/rasputin/v1/responses")
async def rasputin_responses(req: dict, request: Request):
    try:
        _authorize(request)
        model = _resolve_model(req.get("model"))
        messages = req.get("messages") or []
        if not messages and req.get("input") is not None:
            messages = [{"role": "user", "content": _plain_content(req.get("input"))}]
        messages = _openai_messages({"messages": messages})
        if not messages:
            raise ServingError("invalid_request", "input or messages is required.", 400)
        tools = _openai_tools(req)
        max_tokens = _integer(req.get("max_output_tokens") or req.get("max_tokens"), "max_output_tokens", 1024)
        temperature = _number(req.get("temperature"), "temperature", 0.2, 0, 2)
        stream_requested = req.get("stream", False)
        if not isinstance(stream_requested, bool):
            raise ServingError("invalid_request", "stream must be boolean.", 400)
        if not stream_requested:
            request_id, text, tool_calls, metric, usage = await _infer(
                "rasputin", model, messages, max_tokens, temperature, tools,
                req.get("reasoning", "auto"), stream=False,
            )
            return {
                "id": request_id, "object": "rasputin.response", "model": model.get("key"),
                "output": ([{"type": "message", "role": "assistant", "content": text}] if text else []) + [
                    {"type": "tool_call", "id": call.get("id"), "name": call.get("name"), "arguments": call.get("args") or {}}
                    for call in tool_calls
                ],
                "usage": usage, "metrics": metric,
            }

        request_id, events, task = _start_stream_inference(
            "rasputin", model, messages, max_tokens, temperature, tools, req.get("reasoning", "auto")
        )

        async def stream():
            yield f"event: response.started\ndata: {json.dumps({'type': 'response.started', 'response': {'id': request_id, 'model': model.get('key')}})}\n\n"
            result = None
            while True:
                kind, value = await events.get()
                if kind == "event" and value.get("type") == "text" and value.get("text"):
                    yield f"event: response.output_text.delta\ndata: {json.dumps({'type': 'response.output_text.delta', 'delta': value['text']})}\n\n"
                elif kind == "error":
                    yield _stream_error("rasputin", value)
                    return
                elif kind == "done":
                    result = value
                    break
            _, text, tool_calls, metric, usage = result
            body = {
                "id": request_id, "object": "rasputin.response", "model": model.get("key"),
                "output": ([{"type": "message", "role": "assistant", "content": text}] if text else []) + [
                    {"type": "tool_call", "id": call.get("id"), "name": call.get("name"), "arguments": call.get("args") or {}}
                    for call in tool_calls
                ],
                "usage": usage, "metrics": metric,
            }
            yield f"event: response.completed\ndata: {json.dumps({'type': 'response.completed', 'response': body})}\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")
    except Exception as exc:
        return _native_error(exc)


@router.get("/rasputin/v1/metrics")
async def rasputin_metrics(request: Request):
    try:
        _authorize(request)
        with _METRICS_LOCK:
            recent = list(_METRICS)
        return {
            "object": "rasputin.metrics",
            "prompt_logging": False,
            "count": len(recent),
            "requests": recent,
        }
    except Exception as exc:
        return _native_error(exc)


def _mcp_response(message_id, result=None, error=None):
    body = {"jsonrpc": "2.0", "id": message_id}
    if error is not None:
        body["error"] = error
    else:
        body["result"] = result if result is not None else {}
    return body


@router.get("/mcp")
async def mcp_listen(request: Request):
    try:
        _authorize(request)
    except Exception as exc:
        error = {"code": -32001, "message": getattr(exc, "message", "Authentication failed.")}
        return JSONResponse(status_code=getattr(exc, "status", 401), content=_mcp_response(None, error=error))

    async def stream():
        payload = {"jsonrpc": "2.0", "method": "notifications/message", "params": {
            "level": "info", "data": "Rasputin authenticated MCP JSON-RPC HTTP subset is ready."
        }}
        yield f"event: message\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/mcp")
async def mcp_post(req: dict, request: Request):
    message_id = req.get("id") if isinstance(req, dict) else None
    try:
        config = _authorize(request)
        if not isinstance(req, dict) or req.get("jsonrpc") != "2.0" or not isinstance(req.get("method"), str):
            return JSONResponse(status_code=400, content=_mcp_response(message_id, error={"code": -32600, "message": "Invalid JSON-RPC request."}))
        header_version = request.headers.get("MCP-Protocol-Version")
        supported_versions = {_PROTOCOL_VERSION, "2025-06-18"}
        if header_version and header_version not in supported_versions:
            return JSONResponse(status_code=400, content=_mcp_response(message_id, error={"code": -32602, "message": "Unsupported MCP protocol version."}))
        method = req.get("method")
        params = req.get("params")
        if params is not None and not isinstance(params, dict):
            return JSONResponse(status_code=400, content=_mcp_response(message_id, error={"code": -32602, "message": "params must be an object."}))
        if method == "notifications/initialized":
            return Response(status_code=202, headers={"MCP-Protocol-Version": header_version or _PROTOCOL_VERSION})
        if method == "initialize":
            requested = str((params or {}).get("protocolVersion") or header_version or _PROTOCOL_VERSION)
            if requested not in supported_versions:
                return JSONResponse(status_code=400, content=_mcp_response(message_id, error={"code": -32602, "message": "Unsupported MCP protocol version."}))
            result = {
                "protocolVersion": requested,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "Rasputin", "version": "0.2.0"},
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            catalog = tool_relay.catalog()
            result = {"tools": [
                {
                    "name": item.get("id"),
                    "title": item.get("display_name"),
                    "description": item.get("description") or "",
                    "inputSchema": item.get("input_schema") or {"type": "object", "properties": {}},
                    "annotations": {"readOnlyHint": item.get("risk") == "safe"},
                }
                for item in catalog.get("callable_tools") or []
            ]}
        elif method == "tools/call":
            if not config["mcp_tool_execution"]:
                raise ServingError(
                    "mcp_execution_disabled",
                    "MCP tool execution is disabled in Models > Serving.",
                    403,
                )
            name = str(params.get("name") or "")
            if not name:
                raise ServingError("invalid_params", "tools/call requires a tool name.", 400)
            if params.get("arguments") is not None and not isinstance(params.get("arguments"), dict):
                raise ServingError("invalid_params", "tools/call arguments must be an object.", 400)
            arguments = dict(params.get("arguments") or {})
            result_data = await McpLayer().call_tool(name, arguments)
            result = {
                "content": [{"type": "text", "text": json.dumps(result_data, ensure_ascii=False)}],
                "structuredContent": result_data if isinstance(result_data, dict) else {"result": result_data},
                "isError": False,
            }
        else:
            return JSONResponse(
                status_code=404,
                content=_mcp_response(message_id, error={"code": -32601, "message": f"Method not found: {method}"}),
            )
        return JSONResponse(
            content=_mcp_response(message_id, result=result),
            headers={"MCP-Protocol-Version": requested if method == "initialize" else (header_version or _PROTOCOL_VERSION)},
        )
    except ServingError as exc:
        return JSONResponse(
            status_code=exc.status,
            content=_mcp_response(message_id, error={"code": -32001, "message": exc.message, "data": {"code": exc.code}}),
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content=_mcp_response(message_id, error={"code": -32603, "message": "Internal error."}),
        )
