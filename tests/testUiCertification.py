import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UiCertificationTests(unittest.TestCase):
    def test_source_contract_certifies_without_starting_runtime(self):
        completed = subprocess.run(
            [sys.executable, "scripts/certify_ui_contract.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        report = json.loads(completed.stdout)
        self.assertTrue(report["passed"])
        self.assertEqual(report["schemaVersion"], "rasputin.ui-contract-certification.v1")
        self.assertTrue(all(report["checks"].values()))
        self.assertFalse(report["evidence"]["browserInteraction"])
        self.assertFalse(report["evidence"]["runtimeStarted"])

    def test_certification_reports_missing_source_without_touching_generated_output(self):
        with tempfile.TemporaryDirectory(prefix="rasputin-ui-contract-test-") as temp_dir:
            root = Path(temp_dir)
            source = root / "frontend-src" / "src" / "features" / "dashboard"
            source.mkdir(parents=True)
            (source / "DashboardView.jsx").write_text("// intentionally incomplete", encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "scripts/certify_ui_contract.py", "--root", str(root)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 1, completed.stderr or completed.stdout)
        report = json.loads(completed.stdout)
        self.assertEqual(report["status"], "failed")
        self.assertIn("workstationAssistantEntryPoints", report["missing"])
        self.assertFalse(report["evidence"]["generatedFrontendTouched"])


if __name__ == "__main__":
    unittest.main()
