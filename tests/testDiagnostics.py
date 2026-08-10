import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("RASPUTIN_DATA_DIR", tempfile.mkdtemp(prefix="rasputin-diagnostics-test-"))

from backend.core import diagnostics
from backend import main
from backend.api.core import current_user
from fastapi.testclient import TestClient


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        main.app.dependency_overrides[current_user] = lambda: {"username": "test", "role": "admin"}
        self.client = TestClient(main.app, base_url="http://127.0.0.1")

    def tearDown(self):
        main.app.dependency_overrides.clear()

    def test_report_is_read_only_and_contains_remediation_without_sensitive_payloads(self):
        with patch.object(diagnostics, "hardware_probe", return_value={
            "status": "warning",
            "detectedHardware": {"runtime": "native"},
            "checks": [{
                "id": "dockerDaemon",
                "label": "Docker Daemon",
                "status": "warn",
                "message": "Docker is unavailable.",
                "nextStep": "Start Docker Desktop.",
            }],
        }):
            report = diagnostics.run(username="admin", is_admin=True)

        self.assertIn(report["status"], {"attention", "blocked"})
        self.assertIn("app", report)
        self.assertIn("checks", report)
        self.assertTrue(any(item["id"] == "storage" for item in report["checks"]))
        docker = next(item for item in report["checks"] if item["id"] == "dockerDaemon")
        self.assertEqual(docker["nextAction"], "Start Docker Desktop.")
        serialized = str(report)
        self.assertNotIn("password", serialized.lower())
        self.assertNotIn("token", serialized.lower())

    def test_report_detects_recent_backup_artifact(self):
        backup_root = Path(diagnostics.store.DATA_DIR) / "backups"
        backup_root.mkdir(parents=True, exist_ok=True)
        backup = backup_root / "diagnostics-test.zip"
        backup.write_bytes(b"fixture")
        try:
            with patch.object(diagnostics, "hardware_probe", return_value={"checks": [], "detectedHardware": {}}):
                report = diagnostics.run()
            freshness = next(item for item in report["checks"] if item["id"] == "backupFreshness")
            self.assertEqual(freshness["status"], "pass")
            self.assertEqual(freshness["evidence"]["latest"], str(backup))
        finally:
            backup.unlink(missing_ok=True)

    def test_diagnostics_api_returns_live_contract_shape(self):
        with patch.object(diagnostics, "hardware_probe", return_value={"checks": [], "detectedHardware": {}}):
            response = self.client.get("/api/settings/diagnostics")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn(payload.get("status"), {"healthy", "attention", "blocked"})
        self.assertIn("checks", payload)
        self.assertIn("security", payload)


if __name__ == "__main__":
    unittest.main()
