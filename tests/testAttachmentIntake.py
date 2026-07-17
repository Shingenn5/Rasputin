import base64
import json
import struct
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.core import intake


def encoded(payload):
    return base64.b64encode(payload).decode("ascii")


class AttachmentIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.intake_root = Path(self.temp.name) / "intake"
        self.root_patch = patch.object(intake, "INTAKE_DIR", self.intake_root)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
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


if __name__ == "__main__":
    unittest.main()
