import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class InstallationPreflightTests(unittest.TestCase):
    def test_repository_preflight_is_read_only_and_reports_deployment_paths(self):
        completed = subprocess.run(
            [sys.executable, "scripts/check_installation.py", "--root", str(ROOT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        report = json.loads(completed.stdout)
        self.assertIn(completed.returncode, (0, 2))
        self.assertEqual(report["schemaVersion"], "rasputin.installation-preflight.v1")
        self.assertTrue(all(report["repository"]["requiredAssets"].values()))
        self.assertTrue(report["policy"]["readOnly"])
        self.assertFalse(report["policy"]["runtimeDataTouched"])
        self.assertEqual({item["port"] for item in report["ports"]}, {8787, 8788})

    def test_missing_repository_root_is_blocked_without_writes(self):
        with tempfile.TemporaryDirectory(prefix="rasputin-preflight-missing-") as temp_dir:
            missing = Path(temp_dir) / "does-not-exist"
            completed = subprocess.run(
                [sys.executable, "scripts/check_installation.py", "--root", str(missing)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 2)
        report = json.loads(completed.stdout)
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["passed"])


if __name__ == "__main__":
    unittest.main()
