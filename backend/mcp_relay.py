import json
import time
from pathlib import Path
from threading import Lock

from . import audit
from . import tool_relay
from .response import AppError

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REGISTRY_FILE = DATA_DIR / "mcp_relays.json"
_lock = Lock()


def _blank():
    return {
        "servers": [
            {
                "id": "rasputin-tool-relay",
                "name": "Rasputin Tool Relay",
                "transport": "internal",
                "command": "",
                "enabled": True,
                "status": "available",
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
    return data


def _save(data):
    DATA_DIR.mkdir(exist_ok=True)
    with _lock:
        REGISTRY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _public(server):
    server_id = server.get("id")
    enabled = bool(server.get("enabled"))
    tool_count = len(tool_relay.catalog().get("tools", [])) if server_id == "rasputin-tool-relay" and enabled else 0
    return {
        "id": server_id,
        "name": server.get("name") or server_id,
        "transport": server.get("transport") or "stdio",
        "command": server.get("command") or "",
        "enabled": enabled,
        "status": server.get("status") or ("enabled" if enabled else "disabled"),
        "toolCount": tool_count,
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


def register(payload):
    payload = payload or {}
    server_id = str(payload.get("id") or payload.get("name") or "").strip().lower().replace(" ", "-")
    if not server_id:
        raise AppError("mcp_server_id_required", "MCP relay server id is required.", 400)
    transport = str(payload.get("transport") or "stdio").strip()
    if transport not in {"stdio", "internal"}:
        raise AppError("mcp_transport_rejected", "Only local stdio or internal MCP relay transports are allowed.", 400)
    stamp = time.time()
    server = {
        "id": server_id,
        "name": str(payload.get("name") or server_id),
        "transport": transport,
        "command": str(payload.get("command") or ""),
        "enabled": bool(payload.get("enabled", False)),
        "status": "registered",
        "created_at": stamp,
        "updated_at": stamp,
    }
    data = _load()
    data["servers"] = [item for item in data.get("servers", []) if item.get("id") != server_id] + [server]
    _save(data)
    audit.log("mcp_relay_registered", {"id": server_id, "transport": transport, "enabled": server["enabled"]})
    return _public(server)


def set_enabled(server_id, enabled):
    data = _load()
    server = _find(data, server_id)
    if server.get("id") == "rasputin-tool-relay" and not enabled:
        raise AppError("mcp_internal_relay_required", "The internal Rasputin Tool Relay cannot be disabled.", 400)
    server["enabled"] = bool(enabled)
    server["status"] = "enabled" if enabled else "disabled"
    server["updated_at"] = time.time()
    _save(data)
    audit.log("mcp_relay_enabled" if enabled else "mcp_relay_disabled", {"id": server_id})
    return _public(server)


def discover(server_id):
    data = _load()
    server = _find(data, server_id)
    if not server.get("enabled"):
        return {"server": _public(server), "tools": [], "message": "Relay server is disabled."}
    if server.get("transport") != "internal":
        return {
            "server": _public(server),
            "tools": [],
            "message": "Local stdio MCP discovery is registered but execution is not enabled in this V1 pass.",
        }
    tools = tool_relay.catalog().get("tools", [])
    return {
        "server": _public(server),
        "tools": tools,
        "message": "Internal Tool Relay tools are available through Rasputin policy.",
    }
