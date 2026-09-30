"""Live MCP protocol and durable document-index correctness regressions."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

_DATA = tempfile.TemporaryDirectory(prefix="rasputin-mcp-rag-", ignore_cleanup_errors=True)
os.environ.setdefault("RASPUTIN_DATA_DIR", _DATA.name)

from backend.core import runtime_store, workspace
from backend.mcp import relay
from backend.rag import vector as rag
from backend.engine.agent import AgentHub


class HttpFixture(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def reply(self, status, body=b"", content_type="application/json", session=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        held_stream = content_type == "text/event-stream" and self.server.state.get("hold_open")
        if not held_stream:
            self.send_header("Content-Length", str(len(body)))
        if session:
            self.send_header("Mcp-Session-Id", session)
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()
        if held_stream:
            self.server.release_stream.wait(2)
            self.close_connection = True

    def do_POST(self):
        message = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        method = message["method"]
        state = self.server.state
        state["calls"].append(method)
        if method == "initialize":
            state["generation"] += 1
            state["session"] = "test-session-" + str(state["generation"])
            state["initialized"] = False
            result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}}
            session = state["session"] if state["stateful"] else None
        else:
            session = None
            if state["stateful"]:
                if self.headers.get("Mcp-Session-Id") != state["session"]:
                    self.reply(404)
                    return
                if self.headers.get("MCP-Protocol-Version") != "2025-06-18":
                    self.reply(400)
                    return
            if method == "notifications/initialized":
                state["initialized"] = True
                self.reply(202)
                return
            if state["stateful"] and not state["initialized"]:
                self.reply(400)
                return
            if state.get("expire") and method == "tools/call":
                state["expire"] = False
                state["session"] = "expired"
                self.reply(404)
                return
            if method == "tools/list":
                result = {"tools": [{"name": "echo", "inputSchema": {"type": "object", "properties": {"message": {"type": "string"}}}}]}
            elif method == "tools/call":
                result = {"content": [{"type": "text", "text": message["params"]["arguments"]["message"]}]}
            else:
                result = {}
        response = {"jsonrpc": "2.0", "id": message["id"], "result": result}
        if state["sse"]:
            body = ('data: {"jsonrpc":"2.0","method":"notifications/message","params":{}}\n\n'
                    + 'event: message\ndata: ' + json.dumps(response) + '\n\n').encode()
            self.reply(200, body, "text/event-stream", session)
        else:
            self.reply(200, json.dumps(response).encode(), session=session)

    def do_DELETE(self):
        self.server.state["deleted"] = self.headers.get("Mcp-Session-Id")
        self.reply(200)

    def log_message(self, *_args):
        pass


class McpHttpRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), HttpFixture)
        self.server.daemon_threads = True
        self.server.release_stream = threading.Event()
        self.server.state = {"stateful": False, "sse": False, "generation": 0, "calls": []}
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        relay.register({"id": "http-regression", "transport": "streamable_http",
                        "network_target": f"http://127.0.0.1:{self.server.server_port}/mcp", "enabled": True})

    async def asyncTearDown(self):
        self.server.release_stream.set()
        await relay.stop("http-regression")
        await asyncio.to_thread(self.server.shutdown)
        self.server.server_close()

    async def check_workflow(self):
        tested = await relay.test_server("http-regression")
        self.assertEqual(tested["server"]["health"], "running")
        for _ in range(2):
            found = await relay.discover("http-regression")
            self.assertEqual(found["tools"][0]["mcpToolName"], "echo")
        relay.classify_tool("mcp:http-regression:echo", {"risk": "guarded", "enabled": True})
        response = await relay.call_tool("mcp:http-regression:echo", {"message": "rehearsal-ok"})
        self.assertEqual(response["content"][0]["text"], "rehearsal-ok")

    async def test_http_test_and_repeat_discovery(self):
        await self.check_workflow()

    async def test_stateful_json_session_and_initialized_notification(self):
        self.server.state["stateful"] = True
        await self.check_workflow()
        self.assertEqual(self.server.state["calls"].count("initialize"), 1)
        await relay.stop("http-regression")
        self.assertEqual(self.server.state["deleted"], "test-session-1")

    async def test_streamable_http_accepts_sse_responses(self):
        self.server.state.update(stateful=True, sse=True)
        await self.check_workflow()

    async def test_expired_session_reinitializes_before_retry(self):
        self.server.state.update(stateful=True, expire=True)
        await self.check_workflow()
        self.assertEqual(self.server.state["generation"], 2)

    async def test_sse_returns_response_before_stream_closes(self):
        self.server.state.update(sse=True, hold_open=True)
        await relay.test_server("http-regression")
        response = await relay._request("http-regression", "tools/list", {}, timeout=0.5)
        self.assertEqual(response["tools"][0]["name"], "echo")

    async def test_http_restart_creates_a_new_session(self):
        self.server.state["stateful"] = True
        await self.check_workflow()
        restarted = await relay.restart("http-regression")
        self.assertEqual(restarted["health"], "running")
        self.assertEqual(self.server.state["generation"], 2)
        self.assertEqual((await relay.discover("http-regression"))["tools"][0]["mcpToolName"], "echo")


class RagIndexRegressionTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="rag-documents-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        workspace.approve(str(self.root), "RAG regression")
        workspace.select(str(self.root))
        runtime_store.set_kv("rag_vector", rag._blank())
        runtime_store.set_kv("rag_vector_stats", None)

    def test_changed_unreadable_document_removes_stale_evidence(self):
        path = self.root / "notes.md"
        path.write_text("Old launch code is SILVERFOX")
        rag.ingest(str(self.root))
        path.write_text("Changed document cannot currently be parsed.")
        with patch.object(rag, "_read_document", return_value=([], {"parser": "text", "reason": "read_failed"})):
            result = rag.ingest(str(self.root))
        self.assertEqual(result["docs_skipped"], 1)
        self.assertEqual(rag.search("SILVERFOX", path=str(self.root))["hits"], [])
        self.assertEqual(rag.stats()["docs"], 0)

    def test_simultaneous_ingests_preserve_both_document_updates(self):
        paths = [self.root / name for name in ("alpha.md", "beta.md")]
        for path in paths:
            path.write_text("launch evidence " + path.stem)
        entered, release, second_started, second_finished = (threading.Event() for _ in range(4))
        original_load = rag._load
        first_thread = []

        def held_snapshot():
            snapshot = original_load()
            if threading.get_ident() == first_thread[0]:
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("snapshot not released")
            return snapshot

        def first():
            first_thread.append(threading.get_ident())
            return rag.ingest(str(paths[0]))

        def second():
            second_started.set()
            result = rag.ingest(str(paths[1]))
            second_finished.set()
            return result

        with patch.object(rag, "_load", held_snapshot), ThreadPoolExecutor(max_workers=2) as pool:
            initial = pool.submit(first)
            try:
                self.assertTrue(entered.wait(3))
                overlapping = pool.submit(second)
                self.assertTrue(second_started.wait(3))
                # Before the fix this lets the second ingest commit first;
                # the first then overwrites it with its earlier snapshot.
                second_finished.wait(1)
            finally:
                release.set()
            initial.result(timeout=5)
            overlapping.result(timeout=5)
        self.assertEqual({doc["path"] for doc in rag.raw_index()["docs"]}, {"alpha.md", "beta.md"})
        self.assertEqual(rag.stats()["docs"], 2)

    def test_long_paragraph_tail_is_indexed_with_its_line_citation(self):
        path = self.root / "report.md"
        path.write_text("filler " * 1000 + "Launch password is BRONZEBADGER.", encoding="utf-8")
        rag.ingest(str(self.root))
        hits = rag.search("BRONZEBADGER", path=str(path))["hits"]
        self.assertTrue(any("BRONZEBADGER" in hit["text"] for hit in hits))
        self.assertTrue(all(hit["line_start"] == 1 and hit["line_end"] == 1 for hit in hits))

    def test_model_context_includes_matching_passage_beyond_chunk_prefix(self):
        path = self.root / "brief.md"
        path.write_text("filler " * 300 + "Launch password is COPPEROTTER.")
        rag.ingest(str(self.root))
        results = rag.search("What is the launch password in brief.md?", path=str(path))
        context = AgentHub().format_context(results)
        self.assertIn("COPPEROTTER", context)
        self.assertIn("brief.md", context)
        self.assertIn("UNTRUSTED CONTENT", context)

    def test_reindex_upgrades_unchanged_legacy_chunks(self):
        path = self.root / "legacy.md"
        path.write_text("filler " * 1000 + "Launch password is AMBERMARTEN.")
        rag.ingest(str(self.root))
        index = rag.raw_index()
        index["docs"][0].pop("chunking_version")
        index["chunks"] = index["chunks"][:1]
        rag._save(index)
        result = rag.ingest(str(self.root))
        self.assertEqual(result["docs_indexed"], 1)
        self.assertTrue(any("AMBERMARTEN" in hit["text"] for hit in rag.search("AMBERMARTEN", path=str(path))["hits"]))


if __name__ == "__main__":
    unittest.main()
