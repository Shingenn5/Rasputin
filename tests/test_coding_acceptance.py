import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CodingAcceptanceFixtureTests(unittest.TestCase):
    def test_deterministic_coding_acceptance_fixture(self):
        env = dict(os.environ)
        env.pop("RASPUTIN_DATA_DIR", None)
        env["RASPUTIN_PYTHON"] = str(ROOT / ".venv" / "Scripts" / "python.exe")
        result = subprocess.run(
            [str(ROOT / ".venv" / "Scripts" / "python.exe"), str(ROOT / "scripts" / "run_coding_acceptance.py"), "--json"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        evidence = json.loads(result.stdout)
        self.assertTrue(evidence["passed"])
        self.assertEqual(evidence["evidence_mode"], "mocked")
        self.assertEqual(evidence["live_model"]["status"], "skipped")
        self.assertGreaterEqual(evidence["model_calls"], 3)
        self.assertEqual(evidence["test_runs"][0]["exit_code"], 1)
        self.assertEqual(evidence["test_runs"][-1]["exit_code"], 0)
        self.assertIn("test_run", evidence["task_trace_kinds"])
        self.assertEqual(len(evidence["patch_results"]), 2)
        self.assertIn("return left + right", evidence["final_file"])


if __name__ == "__main__":
    unittest.main()
