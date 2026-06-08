import asyncio
import json
import os
import shlex
import time
import urllib.parse
from collections import deque
from pathlib import Path
from threading import Lock

from . import approvals
from . import audit
from . import security
from . import tool_relay
from . import runtime_store as store
from .response import AppError

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REGISTRY_FILE = DATA_DIR / "mcp_relays.json"
_lock = Lock()
_processes = {}
_request_ids = {}
_PROTOCOL_VERSION = "2025-06-18"
_SAFE_RISKS = {"guarded", "approval_required"}
_SAFE_PERMISSIONS = {
    "",
    None,
    "allow_file_read",
    "allow_file_write",
    "allow_file_reorganize",
    "allow_web_search",
    "allow_model_tests",
    "allow_model_registry_edit",
    "allow_docker_control",
}


class _ProcessState:
    def __init__(self, process):
        self.process = process
        self.lock = asyncio.Lock()
        self.logs = deque(maxlen=120)
        self.started_at = time.time()


def _blank():
    return {
        "servers": [
            {
                "id": "rasputin-tool-relay",
                "name": "Rasputin Tool Relay",
                "transport": "internal",
                "command": "",
                "args": [],
                "env": {},
                "cwd": str(ROOT),
                "enabled": True,
                "command_approved": True,
                "status": "available",
                "health": "available",
                "tools": [],
                "created_at": time.time(),
                "updated_at": time.time(),
            }
        ]
    }


def _load():
    DATA_DIR.mkdir(exist_ok=True)
    if not REGISTRY_FILE.exists():
        REGISTRY_FILE.write_text(json.dumps(_blank(), indent=2), encoding="utf-8")
    with _lock:
        try:
            data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = _blank()
    if "servers" not in data:
        data = _blank()
    if not any(item.get("id") == "rasputin-tool-relay" for item in data.get("servers", [])):
        data["servers"].insert(0, _blank()["servers"][0])
    data["servers"] = [_normalize_server(item) for item in data.get("servers", [])]
    return data


def _save(data):
    DATA_DIR.mkdir(exist_ok=True)
    data["servers"] = [_normalize_server(item) for item in data.get("servers", [])]
    with _lock:
        REGISTRY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _normalize_server(server):
    server = dict(server or {})
    transport = server.get("transport") or "stdio"
    server.setdefault("id", "")
    server.setdefault("name", server.get("id") or "MCP Server")
    server.setdefault("transport", transport)
    server.setdefault("command", "")
    server.setdefault("args", [])
    server.setdefault("env", {})
    server.setdefault("cwd", str(ROOT))
    server.setdefault("enabled", False)
    server.setdefault("command_approved", transport == "internal")
    server.setdefault("status", "available" if transport == "internal" else "registered")
    server.setdefault("health", "available" if transport == "internal" else "stopped")
    server.setdefault("last_error", "")
    server.setdefault("pending_approval_id", "")
    server.setdefault("pending_approval_code", "")
    server.setdefault("tools", [])
    server.setdefault("tool_policy", {})
    server.setdefault("created_at", time.time())
    server.setdefault("updated_at", time.time())
    return server


def _public(server):
    server = _normalize_server(server)
    server_id = server.get("id")
    enabled = bool(server.get("enabled"))
    running = _is_running(server_id)
    tool_count = len(tool_relay.catalog(include_external=False).get("tools", [])) if server_id == "rasputin-tool-relay" and enabled else len(server.get("tools") or [])
    return {
        "id": server_id,
        "name": server.get("name") or server_id,
        "transport": server.get("transport") or "stdio",
        "command": _command_text(server),
        "args": server.get("args") or [],
        "cwd": server.get("cwd") or str(ROOT),
        "enabled": enabled,
        "commandApproved": bool(server.get("command_approved")),
        "status": "running" if running else (server.get("status") or ("enabled" if enabled else "disabled")),
        "health": "running" if running else (server.get("health") or "unknown"),
        "lastError": server.get("last_error") or "",
        "toolCount": tool_count,
        "pendingApprovalId": server.get("pending_approval_id") or "",
        "pendingApprovalCode": server.get("pending_approval_code") or "",
        "logs": list(_processes.get(server_id).logs) if running else [],
        "updatedAt": server.get("updated_at"),
    }


def servers():
    data = _load()
    return {
        "servers": [_public(item) for item in data.get("servers", [])],
        "registryFile": str(REGISTRY_FILE),
    }


def _find(data, server_id):
    for item in data.get("servers", []):
        if item.get("id") == server_id:
            return item
    raise AppError("mcp_server_missing", "MCP relay server was not found.", 404)


def _slug(value):
    text = str(value or "").strip().lower().replace(" ", "-")
    return "".join(char for char in text if char.isalnum() or char in {"-", "_"})[:80]


def _parse_command(payload):
    command = str(payload.get("command") or "").strip()
    args = payload.get("args")
    if isinstance(args, str):
        args = shlex.split(args)
    if not args:
        parts = shlex.split(command)
        if parts:
            command, args = parts[0], parts[1:]
    if not command:
        raise AppError("mcp_command_required", "A local stdio MCP server command is required.", 400)
    return command, [str(item) for item in (args or [])]


def _command_text(server):
    command = str(server.get("command") or "")
    args = server.get("args") or []
    return " ".join([command, *[shlex.quote(str(item)) for item in args]]).strip()


def _resolve_cwd(cwd):
    if not cwd:
        return str(ROOT)
    target = Path(str(cwd)).expanduser()
    if not target.is_absolute():
        target = ROOT / target
    target = target.resolve()
    if target != ROOT and ROOT not in target.parents:
        raise AppError("mcp_cwd_rejected", "MCP server cwd must stay inside the Rasputin project for this local-stdio pass.", 400)
    return str(target)


def _sanitize_env(env):
    clean = {}
    for key, value in dict(env or {}).items():
        name = str(key or "").strip()
        if not name or not name.replace("_", "").isalnum():
            raise AppError("mcp_env_rejected", "MCP env names must be simple local environment keys.", 400)
        clean[name] = str(value or "")
    return clean


def register(payload):
    payload = payload or {}
    server_id = _slug(payload.get("id") or payload.get("name"))
    if not server_id:
        raise AppError("mcp_server_id_required", "MCP relay server id is required.", 400)
    transport = str(payload.get("transport") or "stdio").strip()
    if transport not in {"stdio", "internal"}:
        raise AppError("mcp_transport_rejected", "Only local stdio or internal MCP relay transports are allowed.", 400)
    if transport == "internal":
        command, args, approval = "", [], None
        command_approved = True
        enabled = bool(payload.get("enabled", True))
        status = "available"
    else:
        command, args = _parse_command(payload)
        approval = approvals.create("mcp_register", {
            "server": server_id,
            "command": " ".join([command, *args]),
            "cwd": payload.get("cwd") or str(ROOT),
        }, risk_level="approval_required", workspace=".")
        command_approved = False
        enabled = False
        status = "pending_approval"
    stamp = time.time()
    server = {
        "id": server_id,
        "name": str(payload.get("name") or server_id),
        "transport": transport,
        "command": command,
        "args": args,
        "env": _sanitize_env(payload.get("env") or {}),
        "cwd": _resolve_cwd(payload.get("cwd")),
        "enabled": enabled,
        "command_approved": command_approved,
        "status": status,
        "health": "available" if transport == "internal" else "stopped",
        "last_error": "",
        "pending_approval_id": approval["id"] if approval else "",
        "pending_approval_code": approval["code"] if approval else "",
        "tools": [],
        "tool_policy": {},
        "created_at": stamp,
        "updated_at": stamp,
    }
    data = _load()
    data["servers"] = [item for item in data.get("servers", []) if item.get("id") != server_id] + [server]
    _save(data)
    audit.log("mcp_relay_registered", {"id": server_id, "transport": transport, "enabled": enabled, "approval": bool(approval)})
    public = _public(server)
    if approval:
        public["approval"] = approval
    return public


def set_enabled(server_id, enabled):
    data = _load()
    server = _find(data, server_id)
    if server.get("id") == "rasputin-tool-relay" and not enabled:
        raise AppError("mcp_internal_relay_required", "The internal Rasputin Tool Relay cannot be disabled.", 400)
    if enabled and server.get("transport") == "stdio" and not server.get("command_approved"):
        raise AppError("mcp_approval_required", "Approve the MCP server registration before enabling it.", 403)
    server["enabled"] = bool(enabled)
    server["status"] = "enabled" if enabled else "disabled"
    server["updated_at"] = time.time()
    _save(data)
    audit.log("mcp_relay_enabled" if enabled else "mcp_relay_disabled", {"id": server_id})
    return _public(server)


async def start(server_id, approval_id=None):
    data = _load()
    server = _find(data, server_id)
    if server.get("transport") == "internal":
        return _public(server)
    if not server.get("command_approved"):
        target_approval = approval_id or server.get("pending_approval_id")
        approvals.require_approved(target_approval, "mcp_register")
        server["command_approved"] = True
        server["pending_approval_id"] = ""
        server["pending_approval_code"] = ""
    server["enabled"] = True
    try:
        await _ensure_started(server)
        server["status"] = "running"
        server["health"] = "running"
        server["last_error"] = ""
    except Exception as exc:
        server["status"] = "error"
        server["health"] = "error"
        server["last_error"] = str(exc)
        _save(data)
        raise
    server["updated_at"] = time.time()
    _save(data)
    audit.log("mcp_relay_started", {"id": server_id})
    return _public(server)


async def stop(server_id):
    state = _processes.pop(server_id, None)
    if state:
        state.process.terminate()
        try:
            await asyncio.wait_for(state.process.wait(), timeout=5)
        except asyncio.TimeoutError:
            state.process.kill()
            await state.process.wait()
    data = _load()
    server = _find(data, server_id)
    if server.get("transport") != "internal":
        server["status"] = "stopped"
        server["health"] = "stopped"
        server["updated_at"] = time.time()
        _save(data)
    audit.log("mcp_relay_stopped", {"id": server_id})
    return _public(server)


async def restart(server_id, approval_id=None):
    await stop(server_id)
    return await start(server_id, approval_id)


async def discover(server_id):
    data = _load()
    server = _find(data, server_id)
    if not server.get("enabled") and server.get("transport") != "stdio":
        return {"server": _public(server), "tools": [], "message": "Relay server is disabled."}
    if server.get("transport") == "internal":
        tools = tool_relay.catalog(include_external=False).get("tools", [])
        return {
            "server": _public(server),
            "tools": tools,
            "message": "Internal Tool Relay tools are available through Rasputin policy.",
        }
    if not server.get("enabled"):
        return {"server": _public(server), "tools": [], "message": "Relay server is disabled until registration is approved and started."}
    await _ensure_started(server)
    response = await _request(server_id, "tools/list", {})
    raw_tools = response.get("tools") or []
    server["tools"] = [_normalize_tool(server, item) for item in raw_tools]
    server["status"] = "running"
    server["health"] = "running"
    server["updated_at"] = time.time()
    _replace_server(server)
    audit.log("mcp_tools_discovered", {"id": server_id, "count": len(server["tools"])})
    return {
        "server": _public(server),
        "tools": [public_tool(tool, server) for tool in server["tools"]],
        "message": f"Discovered {len(server['tools'])} MCP tool(s). Classify a tool before execution.",
    }


def server_tools(server_id):
    data = _load()
    server = _find(data, server_id)
    return {"server": _public(server), "tools": [public_tool(tool, server) for tool in server.get("tools", [])]}


def classify_tool(tool_id, payload):
    server_id, tool_name = decode_tool_id(tool_id)
    data = _load()
    server = _find(data, server_id)
    policy = dict(server.get("tool_policy") or {})
    risk = str((payload or {}).get("risk") or "approval_required")
    if risk not in _SAFE_RISKS:
        raise AppError("mcp_tool_risk_rejected", "External MCP tools may be guarded or approval-required in this pass.", 400)
    permission = (payload or {}).get("permission_flag") or (payload or {}).get("permissionFlag") or ""
    if permission not in _SAFE_PERMISSIONS:
        raise AppError("mcp_permission_rejected", "Unsupported MCP tool permission flag.", 400)
    policy[tool_name] = {
        "risk": risk,
        "permission_flag": permission,
        "enabled": bool((payload or {}).get("enabled", True)),
        "approval_behavior": "one_time_approval" if risk == "approval_required" else "not_required",
        "updated_at": time.time(),
    }
    server["tool_policy"] = policy
    server["updated_at"] = time.time()
    _save(data)
    audit.log("mcp_tool_classified", {"server": server_id, "tool": tool_name, "risk": risk, "permission": permission})
    return get_tool_definition(tool_id)


async def call_tool(tool_id, args=None, task_id=None, tool_call_id=None):
    definition = get_tool_definition(tool_id)
    if not definition:
        raise AppError("mcp_tool_missing", "External MCP tool was not found.", 404)
    if not definition.get("enabled"):
        raise AppError("mcp_tool_disabled", "External MCP tool is disabled until classified.", 403)
    if not tool_relay.permission_allowed(definition):
        raise PermissionError(f"{definition.get('permission_flag') or 'tool'} is disabled")
    args = dict(args or {})
    approval_id = args.pop("approval_id", None)
    if definition.get("risk") == "approval_required" and not approval_id:
        approval = approvals.create("mcp_tool_call", {
            "tool": definition["id"],
            "server": definition.get("serverId"),
            "args": tool_relay.redact_args(definition["id"], args),
        }, risk_level="approval_required", task_id=task_id, tool_call_id=tool_call_id, workspace=".")
        return {
            "preview": True,
            "approval_id": approval["id"],
            "approval_code": approval["code"],
            "kind": "mcp_tool_call",
            "message": "Approval required before external MCP tool execution.",
        }
    if definition.get("risk") == "approval_required":
        approvals.require_approved(approval_id, "mcp_tool_call")
    server_id, tool_name = decode_tool_id(tool_id)
    data = _load()
    server = _find(data, server_id)
    await _ensure_started(server)
    return await _request(server_id, "tools/call", {"name": tool_name, "arguments": args})


def external_tool_definitions():
    data = _load()
    out = []
    for server in data.get("servers", []):
        if server.get("transport") != "stdio":
            continue
        out.extend(public_tool(tool, server) for tool in server.get("tools", []))
    return out


def is_external_tool(tool_id):
    return str(tool_id or "").startswith("mcp:")


def get_tool_definition(tool_id):
    if not is_external_tool(tool_id):
        return None
    server_id, tool_name = decode_tool_id(tool_id)
    data = _load()
    server = _find(data, server_id)
    for tool in server.get("tools", []):
        if tool.get("name") == tool_name:
            return public_tool(tool, server)
    return None


def public_tool(tool, server):
    server = _normalize_server(server)
    tool_name = tool.get("name") or ""
    policy = (server.get("tool_policy") or {}).get(tool_name, {})
    classified = bool(policy)
    enabled = bool(policy.get("enabled", False)) and bool(server.get("enabled")) and bool(server.get("command_approved"))
    risk = policy.get("risk") or "approval_required"
    permission = policy.get("permission_flag") or ""
    disabled_reason = ""
    if not classified:
        disabled_reason = "Tool classification required."
    elif not server.get("enabled"):
        disabled_reason = "MCP server is disabled."
    elif not server.get("command_approved"):
        disabled_reason = "MCP server registration approval is required."
    elif not enabled:
        disabled_reason = "MCP tool is disabled by policy."
    definition = {
        "id": encode_tool_id(server["id"], tool_name),
        "display_name": f"{server.get('name')}: {tool.get('title') or tool_name}",
        "description": tool.get("description") or "External local MCP tool.",
        "category": "MCP",
        "risk": risk,
        "permission_flag": permission or None,
        "enabled": enabled,
        "implemented": True,
        "external": True,
        "available": not bool(disabled_reason),
        "disabled_reason": disabled_reason,
        "approval_behavior": policy.get("approval_behavior") or "one_time_approval",
        "timeout_seconds": int(policy.get("timeout_seconds") or 45),
        "output_summary_policy": "external_mcp_redacted_summary",
        "input_schema": tool.get("inputSchema") or {"type": "object", "properties": {}},
        "serverId": server["id"],
        "serverName": server.get("name"),
        "mcpToolName": tool_name,
        "classified": classified,
    }
    return tool_relay.public_definition(definition) if classified else definition


def encode_tool_id(server_id, tool_name):
    return f"mcp:{server_id}:{urllib.parse.quote(str(tool_name or ''), safe='')}"


def decode_tool_id(tool_id):
    parts = str(tool_id or "").split(":", 2)
    if len(parts) != 3 or parts[0] != "mcp":
        raise AppError("mcp_tool_id_invalid", "Invalid MCP tool id.", 400)
    return parts[1], urllib.parse.unquote(parts[2])


def _normalize_tool(server, item):
    schema = item.get("inputSchema") or item.get("input_schema") or {"type": "object", "properties": {}}
    return {
        "name": str(item.get("name") or "")[:160],
        "title": str(item.get("title") or item.get("name") or "")[:160],
        "description": str(item.get("description") or "")[:1000],
        "inputSchema": schema if isinstance(schema, dict) else {"type": "object", "properties": {}},
        "discoveredAt": time.time(),
    }


def _replace_server(server):
    data = _load()
    data["servers"] = [server if item.get("id") == server.get("id") else item for item in data.get("servers", [])]
    _save(data)


def _is_running(server_id):
    state = _processes.get(server_id)
    return bool(state and state.process.returncode is None)


async def _ensure_started(server):
    server_id = server.get("id")
    if _is_running(server_id):
        return _processes[server_id]
    command = server.get("command")
    args = server.get("args") or []
    env = os.environ.copy()
    for key, value in (server.get("env") or {}).items():
        text = str(value or "")
        env[key] = os.environ.get(text[5:], "") if text.startswith("$ENV:") else text
    try:
        process = await asyncio.create_subprocess_exec(
            command,
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=server.get("cwd") or str(ROOT),
            env=env,
        )
    except FileNotFoundError as exc:
        raise AppError("mcp_command_missing", f"MCP command was not found: {command}", 400) from exc
    except Exception as exc:
        raise AppError("mcp_start_failed", f"MCP server failed to start: {exc}", 400) from exc
    state = _ProcessState(process)
    _processes[server_id] = state
    asyncio.create_task(_read_stderr(server_id, state))
    await _initialize(server_id)
    return state


async def _read_stderr(server_id, state):
    while state.process.stderr and state.process.returncode is None:
        line = await state.process.stderr.readline()
        if not line:
            break
        state.logs.append(line.decode("utf-8", errors="replace").strip()[:500])


async def _initialize(server_id):
    response = await _request(server_id, "initialize", {
        "protocolVersion": _PROTOCOL_VERSION,
        "capabilities": {"tools": {}},
        "clientInfo": {"name": "Rasputin", "version": "0.2.0"},
    }, timeout=12)
    state = _processes[server_id]
    notification = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
    state.process.stdin.write((json.dumps(notification) + "\n").encode("utf-8"))
    await state.process.stdin.drain()
    return response


async def _request(server_id, method, params=None, timeout=20):
    state = _processes.get(server_id)
    if not state or state.process.returncode is not None:
        raise AppError("mcp_server_not_running", "MCP server is not running.", 400)
    async with state.lock:
        request_id = _request_ids.get(server_id, 0) + 1
        _request_ids[server_id] = request_id
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
        state.process.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        await state.process.stdin.drain()
        while True:
            try:
                raw = await asyncio.wait_for(state.process.stdout.readline(), timeout=timeout)
            except asyncio.TimeoutError as exc:
                raise AppError("mcp_request_timeout", f"MCP request timed out: {method}", 504) from exc
            if not raw:
                raise AppError("mcp_server_exited", "MCP server exited before responding.", 502)
            try:
                message = json.loads(raw.decode("utf-8"))
            except Exception:
                state.logs.append(raw.decode("utf-8", errors="replace").strip()[:500])
                continue
            if message.get("id") != request_id:
                continue
            if "error" in message:
                error = message.get("error") or {}
                raise AppError("mcp_protocol_error", error.get("message") or str(error), 502)
            return message.get("result") or {}
