import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("RASPUTIN_DATA_DIR", tempfile.mkdtemp(prefix="rasputin-backup-test-"))

from backend import main
from backend.api.core import current_user
from backend.core import backup
from backend.core import runtime_store


class BackupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime_store.init_db()

    def test_backup_manifest_hashes_and_restore_dry_run(self):
        source = Path(runtime_store.DATA_DIR) / "operator-note.json"
        source.write_text('{"safe": true}\n', encoding="utf-8")
        private = Path(runtime_store.DATA_DIR) / "tls.key"
        private.write_text("private", encoding="utf-8")
        try:
            created = backup.create_backup()
            self.assertTrue(Path(created["path"]).is_file())
            self.assertGreaterEqual(created["fileCount"], 1)
            self.assertTrue(any(item["path"] == "tls.key" for item in created["manifest"]["excluded"]))

            inspected = backup.inspect_backup(created["path"])
            self.assertTrue(inspected["valid"])
            self.assertEqual(inspected["verifiedCount"], inspected["fileCount"])
            dry_run = backup.restore_dry_run(created["path"])
            self.assertTrue(dry_run["dryRun"])
            self.assertTrue(dry_run["wouldRestore"])

            with zipfile.ZipFile(created["path"], "a") as archive:
                archive.writestr("unexpected.txt", "not in manifest")
            self.assertTrue(backup.inspect_backup(created["path"])["valid"])
        finally:
            source.unlink(missing_ok=True)
            private.unlink(missing_ok=True)

    def test_owner_export_and_confirmed_delete_are_scoped(self):
        owner = "backup-owner"
        other = "other-owner"
        with runtime_store._lock, runtime_store.connect() as conn:
            now = runtime_store.now()
            conn.execute("INSERT OR REPLACE INTO sessions(id,title,status,workspace,model,mode,skill,summary,created_at,updated_at,owner_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)", ("backup-session", "Owner session", "active", ".", "dry-run", "chat", "general", "", now, now, owner))
            conn.execute("INSERT OR REPLACE INTO sessions(id,title,status,workspace,model,mode,skill,summary,created_at,updated_at,owner_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)", ("other-session", "Other session", "active", ".", "dry-run", "chat", "general", "", now, now, other))
            conn.execute("INSERT OR REPLACE INTO tasks(id,session_id,objective,model,skill,mode,status,progress,result,workspace,created_at,updated_at,owner_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", ("backup-task", "backup-session", "owner work", "dry-run", "general", "chat", "done", 100, "done", ".", now, now, owner))
            conn.commit()
        exported = backup.export_owner_data(owner)
        self.assertTrue(Path(exported["path"]).is_file())
        preview = backup.delete_owner_data(owner, dry_run=True)
        self.assertEqual(preview["counts"]["sessions"], 1)
        self.assertTrue(preview["dryRun"])
        deleted = backup.delete_owner_data(owner, confirmation="DELETE MY RASPUTIN DATA", dry_run=False)
        self.assertFalse(deleted["dryRun"])
        with runtime_store._lock, runtime_store.connect() as conn:
            self.assertIsNone(conn.execute("SELECT id FROM sessions WHERE id='backup-session'").fetchone())
            self.assertIsNotNone(conn.execute("SELECT id FROM sessions WHERE id='other-session'").fetchone())

    def test_recovery_api_keeps_preview_and_restore_paths_bounded(self):
        main.app.dependency_overrides[current_user] = lambda: {"username": "api-owner", "role": "admin"}
        client = TestClient(main.app, base_url="http://127.0.0.1", raise_server_exceptions=False)
        try:
            preview = client.post("/api/recovery/backup", json={"dryRun": True})
            self.assertEqual(preview.status_code, 200)
            self.assertTrue(preview.json()["data"]["dryRun"])

            status = client.get("/api/recovery/status")
            self.assertEqual(status.status_code, 200)
            self.assertEqual(status.json()["data"]["restoreMode"], "dry-run only while the service is running")

            outside = Path(tempfile.gettempdir()) / "rasputin-outside-backup.zip"
            rejected = client.post("/api/recovery/restore/verify", json={"path": str(outside)})
            self.assertEqual(rejected.status_code, 403)

            unsupported = client.post("/api/recovery/backup", json={"dryRun": True, "includeWorkspace": True})
            self.assertEqual(unsupported.status_code, 400)
        finally:
            main.app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main()
