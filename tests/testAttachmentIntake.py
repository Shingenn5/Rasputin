import base64
import json
import struct
import tempfile
import time
import unittest
import asyncio
import gc
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from backend.core import intake
from backend.core import runtime_store as store
from backend.engine.agent import AgentHub, AgentTask
from backend.mcp.layer import McpLayer


def encoded(payload):
    return base64.b64encode(payload).decode("ascii")


class AttachmentIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.intake_root = Path(self.temp.name) / "intake"
        self.root_patch = patch.object(intake, "INTAKE_DIR", self.intake_root)
        self.root_patch.start()
        self.store_patches = [patch.object(store, "DATA_DIR", Path(self.temp.name)), patch.object(store, "DB_FILE", Path(self.temp.name) / "test.db")]
        for item in self.store_patches:
            item.start()
        store.init_db()

    def tearDown(self):
        self.root_patch.stop()
        for item in reversed(self.store_patches):
            item.stop()
        gc.collect()
        self.temp.cleanup()

    def test_text_intake_persists_provenance_and_task_context(self):
        payload = b"Heading\nA durable attachment body.\n"
        record = intake.create("alice", "notes.txt", encoded(payload), "text/plain", len(payload), "use_once")

        self.assertEqual(record["mimeType"], "text/plain")
        self.assertEqual(record["parser"], "text")
        self.assertEqual(record["retention"], "use_once")
        self.assertGreaterEqual(len(record["provenance"]), 1)
        self.assertEqual(record["antivirus"]["status"], "not_configured")

        context, records = intake.prepare_task_context("alice", [record["id"]])
        self.assertIn('name="notes.txt"', context)
        self.assertIn("untrusted user-provided file content", context)
        self.assertIn("A durable attachment body", context)
        self.assertEqual(records[0]["contentHash"], __import__("hashlib").sha256(payload).hexdigest())

    def test_retention_can_change_before_binding_and_owner_is_enforced(self):
        payload = b"save this source"
        record = intake.create("alice", "source.md", encoded(payload), "text/markdown", len(payload))
        updated = intake.set_retention("alice", record["id"], "save_artifact")

        self.assertEqual(updated["retention"], "save_artifact")
        self.assertGreater(updated["expiresAt"], time.time())
        with self.assertRaisesRegex(ValueError, "not found"):
            intake.prepare_task_context("bob", [record["id"]])

    def test_size_mismatch_and_executables_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "size did not match"):
            intake.create("alice", "notes.txt", encoded(b"abc"), "text/plain", 99)
        with self.assertRaisesRegex(ValueError, "executable"):
            intake.create("alice", "malware.exe", encoded(b"MZ"), "application/octet-stream", 2)
        with self.assertRaisesRegex(ValueError, "does not match"):
            intake.create("alice", "renamed.txt", encoded(b"%PDF-1.7\n"), "text/plain", 9)

    def test_signature_detection_and_image_dimensions(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 640, 480) + b"\x08\x02\x00\x00\x00"
        record = intake.create("alice", "screen.png", encoded(png), "application/octet-stream", len(png))

        self.assertEqual(record["mimeType"], "image/png")
        self.assertEqual(record["parser"], "image_metadata")
        self.assertEqual(record["metadata"], {"width": 640, "height": 480})

    def test_expired_use_once_records_are_cleaned(self):
        payload = b"temporary"
        record = intake.create("alice", "temp.txt", encoded(payload), "text/plain", len(payload))
        record_dir = intake._record_dir("alice", record["id"])
        manifest_path = record_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["expiresAt"] = time.time() - 1
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        self.assertEqual(intake.cleanup_expired("alice"), 1)
        self.assertFalse(record_dir.exists())

    def test_task_attachment_count_is_bounded(self):
        with patch.object(intake, "MAX_TASK_ATTACHMENTS", 1):
            with self.assertRaisesRegex(ValueError, "at most 1"):
                intake.prepare_task_context("alice", ["intake_0000000000000001", "intake_0000000000000002"])

    def remember(self, owner, name, payload, task_id="task-original"):
        record = intake.create(owner, name, encoded(payload), declared_size=len(payload))
        _, records = intake.prepare_task_context(owner, [record["id"]])
        intake.bind_to_task(owner, records, task_id)
        return record

    def test_sent_document_survives_expiry_and_reopens_for_other_chat(self):
        record = self.remember("alice", "accounts.txt", b"Maya Chen owns the Blue Heron Labs account.")
        with patch("backend.core.intake.time.time", return_value=time.time() + 365 * 86400):
            self.assertEqual(intake.cleanup_expired("alice"), 0)
            loaded, _ = intake._load("alice", record["id"])
        self.assertEqual(loaded["state"], "remembered")
        self.assertIsNone(loaded["expiresAt"])
        # Each lookup uses a new SQLite connection, not in-memory chat history.
        hits = intake.search_documents("alice", "Who owns Blue Heron Labs?", task_id="task-different-chat")["hits"]
        self.assertIn("Maya Chen", hits[0]["text"])
        self.assertIn("accounts.txt", hits[0]["source"])
        self.assertEqual(intake.search_documents("bob", "Blue Heron Labs")["hits"], [])

    def test_pending_upload_is_not_recalled(self):
        record = intake.create("alice", "draft.txt", encoded(b"Maya Chen owns Blue Heron Labs."))
        self.assertEqual(record["retention"], "remember")
        self.assertEqual(intake.search_documents("alice", "Blue Heron")["hits"], [])
        intake.remove("alice", record["id"])
        self.assertEqual(intake.search_documents("alice", "Blue Heron")["hits"], [])

    def test_current_attachment_precedes_old_document(self):
        self.remember("alice", "briefing.txt", b"Blue Heron Labs account owner was formerly Owen Patel.", "task-old")
        self.remember("alice", "accounts.txt", b"Maya Chen owns the Blue Heron Labs account.", "task-current")
        hits = intake.search_documents("alice", "Who owns Blue Heron Labs?", task_id="task-current")["hits"]
        self.assertEqual(len(hits), 1)
        self.assertIn("Maya Chen", hits[0]["text"])

    def test_workbook_recall_has_sheet_and_row_provenance(self):
        from openpyxl import Workbook
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Knowledge"
        sheet.append(["Record ID", "Content"])
        for number in range(180):
            sheet.append([f"KB-{number:03}", "Unrelated calibration schedule and equipment specifications."])
        sheet.append(["KB-OWNER", "Maya Chen owns the Blue Heron Labs account."])
        buffer = BytesIO()
        workbook.save(buffer)
        self.remember("alice", "company.xlsx", buffer.getvalue())
        result = intake.search_documents("alice", "Who owns Blue Heron Labs?")
        hit = next(h for h in result["hits"] if "Maya Chen" in h["text"])
        self.assertEqual(hit["sheet_name"], "Knowledge")
        self.assertLessEqual(hit["row_start"], 182)
        self.assertGreaterEqual(hit["row_end"], 182)
        prompt = AgentHub().format_context(result)
        self.assertIn("Maya Chen", prompt)
        self.assertIn("sheet=Knowledge", prompt)
        self.assertIn("UNTRUSTED CONTENT", prompt)

    def test_light_chat_includes_document_evidence_without_workspace_tools(self):
        self.remember("alice", "accounts.txt", b"Maya Chen owns the Blue Heron Labs account.")
        hub = AgentHub()
        task = AgentTask("Who owns Blue Heron Labs?", "small-model", "general", mode="chat", workspace_path=".")
        task.owner_id = "alice"
        hub.phase_model = lambda *_: "small-model"
        captured = {}
        async def capture(_task, _phase, _role, sections, tools=None):
            captured.update({s["key"]: s for s in sections})
            return "ok"
        hub.governed_chat = capture
        async def no_tools(*_args):
            raise AssertionError("workspace tools are not required for lightweight document recall")
        hub.mcp.call_tool = no_tools
        with patch("backend.engine.agent.model_registry.get_model", return_value={"key": "small-model", "compatibility": {"promptProfile": "light"}}), patch("backend.engine.agent.security.load", return_value={"allow_file_read": True}), patch.object(hub, "_recall_memory", return_value=None):
            self.assertEqual(asyncio.run(hub.chat_reply(task)), "ok")
        self.assertIn("Maya Chen", captured["rag_sources"]["content"])
        self.assertTrue(captured["rag_sources"]["required"])
        self.assertEqual(captured["workspace_tree"]["content"], "")

    def test_rag_tool_derives_document_owner_from_task(self):
        self.remember("alice", "accounts.txt", b"Maya Chen owns the Blue Heron Labs account.")
        self.remember("bob", "private.txt", b"Bob Secret owns the Blue Heron Labs account.")
        layer = McpLayer()
        with patch.object(layer, "_task_memory_context", return_value=("alice", ".")), patch("backend.mcp.layer.security.load", return_value={"allow_file_read": True}), patch("backend.mcp.layer.rag.search", return_value={"query": "Blue Heron", "hits": []}):
            result = asyncio.run(layer.rag_search("Blue Heron", _task_id="task-alice"))
        self.assertIn("Maya Chen", result["hits"][0]["text"])
        self.assertNotIn("Bob Secret", str(result))

    def test_minimal_inference_keeps_recalled_document_in_provider_prompt(self):
        self.remember("alice", "accounts.txt", b"Maya Chen owns the Blue Heron Labs account.")
        hub = AgentHub()
        task = AgentTask("Who owns Blue Heron Labs?", "minimal-model", "general", mode="chat", workspace_path=".")
        task.owner_id = "alice"
        hub.phase_model = lambda *_: "minimal-model"
        requests = []
        async def capture(_key, messages, **kwargs):
            requests.append(messages)
            return "Maya Chen owns the Blue Heron Labs account.", []
        model = {"key": "minimal-model", "provider": "mock", "context_window": 4096, "max_tokens": 128, "compatibility": {"promptProfile": "minimal"}}
        with patch("backend.engine.agent.model_registry.get_model", return_value=model), patch("backend.engine.agent.security.load", return_value={"allow_file_read": True}), patch.object(hub, "_recall_memory", return_value=None), patch("backend.engine.agent._chat", capture):
            reply = asyncio.run(hub.chat_reply(task))
        self.assertIn("Maya Chen", reply)
        self.assertIn("Maya Chen", requests[0][0]["content"])
        self.assertIn("UNTRUSTED CONTENT", requests[0][0]["content"])
        self.assertFalse([item for item in task.trace if item["kind"] == "minimal_inference"][-1]["detail"]["retrievalSkipped"])


if __name__ == "__main__":
    unittest.main()
