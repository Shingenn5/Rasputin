import asyncio
import json
import os
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_DATA = tempfile.TemporaryDirectory(prefix="rasputin-mcp-product-test-")
os.environ["RASPUTIN_DATA_DIR"] = _DATA.name

from backend.mcp import relay
from backend.core import approvals
from backend.core.response import AppError


class _McpHttpHandler(BaseHTTPRequestHandler):
    calls = []
    token = "test-secret"

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        self.__class__.calls.append((body.get("method"), self.headers.get("Authorization")))
        if self.headers.get("Authorization") != f"Bearer {self.token}":
            self.send_response(401)
            self.end_headers()
            return
        method = body.get("method")
        if method == "initialize":
            result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}}
        elif method == "tools/list":
            result = {"tools": [{"name": "http_echo", "description": "Echo", "inputSchema": {"type": "object", "required": ["message"], "properties": {"message": {"type": "string"}}}}]}
        elif method == "tools/call":
            result = {"content": [{"type": "text", "text": body["params"]["arguments"]["message"]}]}
        else:
            result = {}
        payload = json.dumps({"jsonrpc": "2.0", "id": body.get("id"), "result": result}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args):
        return


class McpProductizationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        relay._processes.clear()
        relay._request_ids.clear()

    async def asyncTearDown(self):
        for item in list(relay._load().get("servers", [])):
            if item.get("id") != "rasputin-tool-relay":
                try:
                    await relay.stop(item["id"])
                except Exception:
                    pass

    async def test_stdio_register_approve_discover_catalog_and_policy(self):
        registered = relay.register_operator_fixture()
        self.assertFalse(registered["enabled"])
        approval = registered["approval"]
        self.assertNotIn(_McpHttpHandler.token, json.dumps(registered))
        approvals.approve(approval["id"])
        await relay.start(registered["id"], approval["id"])
        discovered = await relay.discover(registered["id"])
        tool = discovered["tools"][0]
        self.assertFalse(tool["callable"])
        relay.classify_tool(tool["id"], {"risk": "guarded", "enabled": True})
        catalog = relay.external_tool_definitions()
        self.assertTrue(any(item["id"] == tool["id"] for item in catalog))
        with self.assertRaises(AppError) as ctx:
            await relay.call_tool(tool["id"], {})
        self.assertEqual(ctx.exception.code, "mcp_tool_arguments_invalid")
        result = await relay.call_tool(tool["id"], {"message": "ok"})
        self.assertIn("fixture-ok", json.dumps(result))

    async def test_streamable_http_secret_ref_and_catalog(self):
        _McpHttpHandler.calls = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), _McpHttpHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        os.environ["MCP_TEST_TOKEN"] = "Bearer " + _McpHttpHandler.token
        try:
            registered = relay.register({
                "id": "http-fixture",
                "name": "HTTP Fixture",
                "transport": "streamable_http",
                "network_target": f"http://127.0.0.1:{server.server_port}/mcp",
                "secret_refs": {"Authorization": "$ENV:MCP_TEST_TOKEN"},
                "enabled": True,
            })
            self.assertEqual(registered["transport"], "streamable_http")
            self.assertEqual(registered["secretRefs"], ["Authorization"])
            self.assertNotIn(_McpHttpHandler.token, json.dumps(registered))
            discovered = await relay.discover("http-fixture")
            self.assertEqual(discovered["tools"][0]["mcpToolName"], "http_echo")
            relay.classify_tool("mcp:http-fixture:http_echo", {"risk": "guarded", "enabled": True})
            result = await relay.call_tool("mcp:http-fixture:http_echo", {"message": "hello"})
            self.assertIn("hello", json.dumps(result))
            self.assertEqual(_McpHttpHandler.calls[0][0], "initialize")
            self.assertEqual(_McpHttpHandler.calls[0][1], "Bearer test-secret")
        finally:
            server.shutdown()
            server.server_close()

    async def test_mcp_cwd_is_limited_to_packaged_or_approved_roots(self):
        with self.assertRaises(AppError) as ctx:
            relay.register({
                "id": "outside-root",
                "name": "Outside Root",
                "transport": "stdio",
                "command": "python",
                "cwd": tempfile.gettempdir(),
            })
        self.assertEqual(ctx.exception.code, "mcp_cwd_rejected")

    async def test_frozen_fixture_uses_packaged_backend_entrypoint(self):
        with patch.object(relay.sys, "frozen", True, create=True), patch.object(relay.sys, "executable", "rasputin-backend.exe"):
            registered = relay.register_operator_fixture()
        self.assertEqual(registered["command"], "rasputin-backend.exe --mcp-fixture")
        self.assertEqual(registered["args"], ["--mcp-fixture"])

    async def test_legacy_sse_is_explicitly_rejected(self):
        with self.assertRaises(AppError) as ctx:
            relay.register({"id": "sse", "transport": "sse", "url": "http://127.0.0.1"})
        self.assertEqual(ctx.exception.code, "mcp_transport_rejected")


if __name__ == "__main__":
    unittest.main()
