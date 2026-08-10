import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CoderCertificationCliTests(unittest.TestCase):
    def test_unregistered_model_is_explicitly_blocked(self):
        with tempfile.TemporaryDirectory(prefix="rasputin-certification-") as data_dir:
            env = dict(os.environ)
            env.pop("RASPUTIN_DATA_DIR", None)
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "certify_local_coder.py"),
                    "missing-coder",
                    "--json",
                    "--data-dir",
                    data_dir,
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            evidence = json.loads(result.stdout)
            self.assertEqual(evidence["status"], "blocked")
            self.assertEqual(evidence["reason"], "model_not_registered")
            self.assertIn("Register", evidence["nextAction"])


if __name__ == "__main__":
    unittest.main()
