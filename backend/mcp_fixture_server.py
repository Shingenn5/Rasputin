import json
import sys


PROTOCOL_VERSION = "2025-06-18"


def send(payload):
    print(json.dumps(payload), flush=True)


def result(msg, data):
    send({"jsonrpc": "2.0", "id": msg.get("id"), "result": data})


def error(msg, code, message):
    send({"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": code, "message": message}})


def handle(msg):
    method = msg.get("method")
    if method == "initialize":
        result(msg, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
            "serverInfo": {"name": "rasputin-operator-fixture", "version": "1.0.0"},
        })
    elif method == "tools/list":
        result(msg, {"tools": [{
            "name": "fixture_status",
            "title": "Fixture Status",
            "description": "Returns a harmless status echo for MCP operator testing.",
            "inputSchema": {
                "type": "object",
                "properties": {"message": {"type": "string", "description": "Short test message."}},
                "required": ["message"],
            },
        }]})
    elif method == "tools/call":
        params = msg.get("params") or {}
        args = params.get("arguments") or {}
        if params.get("name") != "fixture_status":
            error(msg, -32602, "unknown fixture tool")
            return
        message = str(args.get("message") or "operator fixture ok")[:160]
        result(msg, {
            "content": [{"type": "text", "text": f"Fixture ready: {message}"}],
            "structuredContent": {"status": "fixture-ok", "echo": message},
        })
    elif method == "resources/list":
        result(msg, {"resources": [{
            "uri": "rasputin://fixture/operator-readme",
            "name": "Operator fixture readme",
            "description": "Read-only capability used to verify MCP resource discovery.",
            "mimeType": "text/plain",
        }]})
    elif method == "prompts/list":
        result(msg, {"prompts": [{
            "name": "fixture-operator-check",
            "description": "Read-only prompt metadata used to verify MCP prompt discovery.",
            "arguments": [{"name": "topic", "description": "Short test topic.", "required": False}],
        }]})
    elif method == "notifications/initialized":
        return
    else:
        error(msg, -32601, "unsupported fixture method")


def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
            if isinstance(msg, dict):
                handle(msg)
        except Exception as exc:
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}})


if __name__ == "__main__":
    main()
