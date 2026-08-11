import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class McpSafetyCertificationTests(unittest.TestCase):
    def test_certification_proves_fail_closed_discovery_routing_preview_and_audit(self):
        with tempfile.TemporaryDirectory(prefix="rasputin-mcp-safety-test-") as temp_dir:
            completed = subprocess.run(
                [sys.executable, "scripts/certify_mcp_safety.py", "--data-dir", temp_dir],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        report = json.loads(completed.stdout)
        self.assertTrue(report["passed"])
        self.assertEqual(report["schemaVersion"], "rasputin.mcp-safety-certification.v1")
        self.assertTrue(all(report["checks"].values()))
        self.assertFalse(report["policy"]["hostCommandsStarted"])
        self.assertFalse(report["policy"]["fixtureWorkspaceMutated"])

    def test_certification_refuses_non_empty_data_directory(self):
        with tempfile.TemporaryDirectory(prefix="rasputin-mcp-safety-test-") as temp_dir:
            marker = Path(temp_dir) / "do-not-touch.txt"
            marker.write_text("existing data", encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "scripts/certify_mcp_safety.py", "--data-dir", temp_dir],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 2)
        report = json.loads(completed.stdout)
        self.assertEqual(report["status"], "blocked")
        self.assertIn("non-empty data directory", report["error"])


if __name__ == "__main__":
    unittest.main()
