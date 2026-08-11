import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MemoryRestartRehearsalTests(unittest.TestCase):
    def test_isolated_rehearsal_proves_persistence_correction_and_owner_boundary(self):
        with tempfile.TemporaryDirectory(prefix="rasputin-memory-restart-test-") as temp_dir:
            completed = subprocess.run(
                [sys.executable, "scripts/rehearse_memory_restart.py", "--data-dir", temp_dir],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        report = json.loads(completed.stdout)
        self.assertTrue(report["passed"])
        self.assertEqual(report["schemaVersion"], "rasputin.memory-restart-rehearsal.v1")
        self.assertTrue(report["policy"]["isolatedDataDirectory"])
        self.assertFalse(report["policy"]["activeDataTouched"])
        self.assertEqual(report["evidence"]["verifyAfterFreshProcess"]["original_status"], "superseded")
        self.assertEqual(report["evidence"]["verifyAfterFreshProcess"]["correction_status"], "saved")
        self.assertEqual(report["evidence"]["verifyAfterFreshProcess"]["other_owner_result_count"], 0)

    def test_refuses_non_empty_data_directory(self):
        with tempfile.TemporaryDirectory(prefix="rasputin-memory-restart-test-") as temp_dir:
            marker = Path(temp_dir) / "do-not-touch.txt"
            marker.write_text("existing data", encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "scripts/rehearse_memory_restart.py", "--data-dir", temp_dir],
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
