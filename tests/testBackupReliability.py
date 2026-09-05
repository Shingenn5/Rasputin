"""Regression coverage for immutable snapshots and bounded restore publication."""

import errno
import hashlib
import json
import os
import sqlite3
import tempfile
import threading
import unittest
import zipfile
from contextlib import ExitStack, closing
from pathlib import Path
from unittest.mock import patch

if "RASPUTIN_DATA_DIR" not in os.environ:
    os.environ["RASPUTIN_DATA_DIR"] = tempfile.mkdtemp(prefix="rasputin-backup-import-")

from backend.core import backup
from scripts import rehearse_restore


class BackupReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.resources = ExitStack()
        self.addCleanup(self.resources.close)
        self.root = Path(self.resources.enter_context(tempfile.TemporaryDirectory(prefix="rasputin-backup-regression-")))
        self.source = self.root / "source"
        self.source.mkdir()
        self.backups = self.source / "backups"
        self.database = self.source / "rasputin.db"
        for attribute, value in (("DATA_DIR", self.source), ("BACKUP_DIR", self.backups), ("EXPORT_DIR", self.source / "exports")):
            self.resources.enter_context(patch.object(backup, attribute, value))
        self.resources.enter_context(patch.object(backup.store, "DB_FILE", self.database))
        self.note = self.source / "state.json"
        self.note.write_text('{"version": 1}', encoding="utf-8")
        self.archive = self.backups / "snapshot.zip"

    def assert_no_staging(self):
        if self.backups.exists():
            self.assertEqual(list(self.backups.glob("*.partial")), [])
        self.assertEqual(list(self.root.glob(".rasputin-restore-*")), [])

    def test_live_source_change_after_manifest_does_not_change_archive(self):
        manifest = backup._manifest

        def mutate_source(*args, **kwargs):
            result = manifest(*args, **kwargs)
            self.note.write_text('{"version": 2}', encoding="utf-8")
            return result

        with patch.object(backup, "_manifest", side_effect=mutate_source):
            result = backup.create_backup(self.archive)
        self.assertTrue(result["created"])
        self.assertTrue(result["integrityVerified"])
        self.assertFalse(result["restoreRehearsed"])
        self.assertFalse(result["manifest"]["consistency"]["crossFileAtomic"])
        self.assertTrue(backup.inspect_backup(self.archive)["valid"])
        with zipfile.ZipFile(self.archive) as archive:
            self.assertEqual(json.loads(archive.read("state.json")), {"version": 1})
        self.assertEqual(json.loads(self.note.read_text(encoding="utf-8")), {"version": 2})

    def test_active_sqlite_writer_yields_committed_standalone_database(self):
        with closing(sqlite3.connect(self.database)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("CREATE TABLE snapshot_values(id INTEGER PRIMARY KEY, value INTEGER, payload TEXT)")
            conn.executemany("INSERT INTO snapshot_values VALUES(?, 1, ?)", [(index, "x" * 4096) for index in range(300)])
            conn.commit()
        writing = threading.Event()
        release = threading.Event()
        errors = []

        def writer():
            try:
                with closing(sqlite3.connect(self.database)) as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    conn.execute("UPDATE snapshot_values SET value=2")
                    writing.set()
                    if not release.wait(20):
                        raise TimeoutError("test did not release writer")
                    conn.commit()
            except BaseException as exc:
                errors.append(exc)
                writing.set()

        thread = threading.Thread(target=writer)
        thread.start()
        try:
            self.assertTrue(writing.wait(10))
            self.assertFalse(errors)
            result = backup.create_backup(self.archive)
            self.assertTrue(result["verified"])
            target = self.root / "restored"
            backup.restore_to_directory(self.archive, target, dry_run=False)
            with closing(sqlite3.connect(target / "rasputin.db")) as conn:
                self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(conn.execute("SELECT DISTINCT value FROM snapshot_values").fetchall(), [(1,)])
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM snapshot_values").fetchone()[0], 300)
            self.assertFalse((target / "rasputin.db-wal").exists())
        finally:
            release.set()
            thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertFalse(errors, str(errors))

    def test_secondary_sqlite_wal_commits_survive_restore(self):
        # The primary store is not the only database. Keep connections open so
        # committed rows remain in WAL instead of being checkpointed on close.
        with ExitStack() as databases:
            for name in ("trials.sqlite3", "archive.sqlite3", "nested/extension.data"):
                path = self.source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                conn = databases.enter_context(closing(sqlite3.connect(path)))
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA wal_autocheckpoint=0")
                conn.execute("CREATE TABLE evidence(value TEXT)")
                conn.execute("INSERT INTO evidence VALUES('committed only in WAL')")
                conn.commit()
                self.assertTrue(Path(str(path) + "-wal").exists())
            backup.create_backup(self.archive)
            target = self.root / "restored"
            backup.restore_to_directory(self.archive, target, dry_run=False)
            for name in ("trials.sqlite3", "archive.sqlite3", "nested/extension.data"):
                with closing(sqlite3.connect(target / name)) as conn:
                    self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                    self.assertEqual(conn.execute("SELECT value FROM evidence").fetchone()[0], "committed only in WAL")

    def test_detected_sidecar_writes_are_bounded_and_not_published(self):
        copy = backup.shutil.copyfileobj
        calls = []

        def change_during_copy(reader, writer, **kwargs):
            copy(reader, writer, **kwargs)
            calls.append(True)
            self.note.write_text("x" * (10 + len(calls)), encoding="utf-8")

        with patch.object(backup.shutil, "copyfileobj", side_effect=change_during_copy):
            with self.assertRaisesRegex(RuntimeError, "changed repeatedly"):
                backup.create_backup(self.archive)
        self.assertEqual(len(calls), 3)
        self.assertFalse(self.archive.exists())
        self.assert_no_staging()

    def test_bad_manifest_never_replaces_existing_backup(self):
        self.backups.mkdir()
        self.archive.write_bytes(b"previous backup")
        manifest = backup._manifest

        def corrupt_manifest(*args, **kwargs):
            result = manifest(*args, **kwargs)
            result["entries"][0]["sha256"] = "0" * 64
            return result

        with patch.object(backup, "_manifest", side_effect=corrupt_manifest):
            with self.assertRaisesRegex(ValueError, "integrity verification"):
                backup.create_backup(self.archive)
        self.assertEqual(self.archive.read_bytes(), b"previous backup")
        self.assert_no_staging()

    def test_disk_full_and_interrupted_packaging_preserve_existing_backup(self):
        self.backups.mkdir()
        self.archive.write_bytes(b"previous backup")
        for failure in (OSError(errno.ENOSPC, "test disk full"), KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__):
                with patch.object(backup.zipfile.ZipFile, "write", side_effect=failure):
                    with self.assertRaises(type(failure)):
                        backup.create_backup(self.archive)
                self.assertEqual(self.archive.read_bytes(), b"previous backup")
                self.assert_no_staging()

    def test_failed_publication_is_reported_and_cleans_partial_archive(self):
        self.backups.mkdir()
        self.archive.write_bytes(b"previous backup")
        with patch.object(Path, "replace", side_effect=PermissionError("test publication denied")):
            with self.assertRaisesRegex(PermissionError, "publication denied"):
                backup.create_backup(self.archive)
        self.assertEqual(self.archive.read_bytes(), b"previous backup")
        self.assert_no_staging()

    def test_dry_run_has_no_published_or_verified_claim(self):
        result = backup.create_backup(self.archive, dry_run=True)
        self.assertTrue(result["dryRun"])
        self.assertFalse(result["created"])
        self.assertFalse(result["verified"])
        self.assertFalse(result["integrityVerified"])
        self.assertFalse(self.backups.exists())
        self.assertEqual(self.note.read_text(encoding="utf-8"), '{"version": 1}')

    def test_backup_destination_cannot_overwrite_active_state(self):
        with self.assertRaisesRegex(ValueError, "active data"):
            backup.create_backup(self.note)
        self.assertEqual(self.note.read_text(encoding="utf-8"), '{"version": 1}')

    def test_restore_refuses_active_parent_child_and_nonempty_targets(self):
        backup.create_backup(self.archive)
        nonempty = self.root / "nonempty"
        nonempty.mkdir()
        protected = nonempty / "keep.txt"
        protected.write_text("keep", encoding="utf-8")
        for target in (self.source, self.source / "nested", self.root, nonempty):
            with self.subTest(target=target.name):
                with self.assertRaises(ValueError):
                    backup.restore_to_directory(self.archive, target, dry_run=False)
        self.assertEqual(protected.read_text(encoding="utf-8"), "keep")
        self.assertFalse((self.source / "nested").exists())

    def test_restore_extraction_failure_never_publishes_target(self):
        backup.create_backup(self.archive)
        target = self.root / "restored"
        with patch.object(backup.shutil, "copyfileobj", side_effect=OSError(errno.ENOSPC, "test disk full")):
            with self.assertRaises(OSError):
                backup.restore_to_directory(self.archive, target, dry_run=False)
        self.assertFalse(target.exists())
        self.assert_no_staging()

    def test_restore_publication_failure_never_leaves_partial_target(self):
        backup.create_backup(self.archive)
        target = self.root / "restored"
        with patch.object(Path, "replace", side_effect=PermissionError("test publication denied")):
            with self.assertRaises(PermissionError):
                backup.restore_to_directory(self.archive, target, dry_run=False)
        self.assertFalse(target.exists())
        self.assert_no_staging()

    def test_restore_checks_extracted_bytes_before_publication(self):
        backup.create_backup(self.archive)
        target = self.root / "restored"
        copy = backup.shutil.copyfileobj

        def corrupt_extraction(reader, writer, **kwargs):
            copy(reader, writer, **kwargs)
            writer.write(b"corruption")

        with patch.object(backup.shutil, "copyfileobj", side_effect=corrupt_extraction):
            with self.assertRaisesRegex(ValueError, "changed during extraction"):
                backup.restore_to_directory(self.archive, target, dry_run=False)
        self.assertFalse(target.exists())
        self.assert_no_staging()

    def test_manifest_paths_and_size_are_checked(self):
        data = b"state"
        cases = [
            ("../escape.txt", len(data)), ("C:/escape.txt", len(data)),
            ("C:escape.txt", len(data)), ("/escape.txt", len(data)),
            ("nested\\escape.txt", len(data)), ("state.txt", len(data) + 1),
        ]
        for name, size in cases:
            with self.subTest(name=name):
                archive_path = self.root / "unsafe.zip"
                manifest = {"formatVersion": 1, "entries": [{"path": name, "bytes": size, "sha256": hashlib.sha256(data).hexdigest()}]}
                with zipfile.ZipFile(archive_path, "w") as archive:
                    archive.writestr("manifest.json", json.dumps(manifest))
                    archive.writestr(name, data)
                self.assertFalse(backup.inspect_backup(archive_path)["valid"])
                with self.assertRaises(ValueError):
                    backup.restore_to_directory(archive_path, self.root / "restored", dry_run=False)

    def test_private_keys_models_and_linked_files_are_excluded(self):
        (self.source / "secret.key").write_text("private", encoding="utf-8")
        models = self.source / "models"
        models.mkdir()
        (models / "weights.gguf").write_bytes(b"not application state")
        outside = self.root / "outside.txt"
        outside.write_text("private outside", encoding="utf-8")
        link = self.source / "linked.txt"
        try:
            link.symlink_to(outside)
        except OSError:
            link = None
        result = backup.create_backup(self.archive)
        entries = {entry["path"] for entry in result["manifest"]["entries"]}
        self.assertEqual(entries, {"state.json"})
        if link is not None:
            self.assertTrue(any(entry["reason"] == "symlink" for entry in result["manifest"]["excluded"]))

    def test_failed_rehearsal_worker_still_cleans_its_temporary_trees(self):
        captured = []

        def fail(source, target):
            captured.extend([source, target.parent])
            raise RuntimeError("test fixture failure")

        with patch.object(rehearse_restore, "_create_and_restore_fixture", side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, "fixture failure"):
                rehearse_restore._rehearse()
        self.assertEqual(len(captured), 2)
        self.assertTrue(all(not path.exists() for path in captured))


if __name__ == "__main__":
    unittest.main()
