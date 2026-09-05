"""Bounded local backup, verification, export, and deletion services."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
import tempfile
import time
import zipfile
from contextlib import closing
from pathlib import Path, PurePosixPath, PureWindowsPath

from backend.core import runtime_store as store


BACKUP_FORMAT_VERSION = 1
DATA_DIR = Path(store.DATA_DIR)
BACKUP_DIR = DATA_DIR / "backups"
EXPORT_DIR = DATA_DIR / "exports"
EXCLUDED_DIRS = {"backups", "exports", "models", "cache", "tls"}
EXCLUDED_SUFFIXES = {".pem", ".key"}
SQLITE_TRANSIENT_SUFFIXES = {"-wal", "-shm"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_link(path: Path) -> bool:
    # Windows junctions are reparse points, but are not always symlinks.
    info = path.lstat()
    return path.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _files():
    files = []
    excluded = []
    if not DATA_DIR.exists():
        return files, excluded
    def walk_error(error):
        raise error

    for root, directories, filenames in os.walk(DATA_DIR, followlinks=False, onerror=walk_error):
        for name in list(directories):
            path = Path(root) / name
            if _is_link(path) or name in EXCLUDED_DIRS:
                directories.remove(name)
                excluded.append({
                    "path": path.relative_to(DATA_DIR).as_posix(),
                    "reason": "symlink" if _is_link(path) else "cache_or_private_key",
                })
        for name in filenames:
            path = Path(root) / name
            relative = path.relative_to(DATA_DIR)
            if _is_link(path):
                excluded.append({"path": relative.as_posix(), "reason": "symlink"})
            elif path.suffix.lower() in EXCLUDED_SUFFIXES or any(name.endswith(suffix) for suffix in SQLITE_TRANSIENT_SUFFIXES):
                excluded.append({"path": relative.as_posix(), "reason": "cache_or_private_key"})
            elif path.is_file():
                files.append(path)
    return sorted(files), excluded


def _check_source_path(path: Path):
    relative = path.relative_to(DATA_DIR)
    if not path.resolve().is_relative_to(DATA_DIR.resolve()):
        raise ValueError("backup source leaves the application data directory")
    for item in (path, *[parent for parent in path.parents if parent != DATA_DIR and DATA_DIR in parent.parents]):
        if _is_link(item):
            raise ValueError("backup source changed to a link")


def _snapshot_database(source: Path, destination: Path):
    """Copy committed SQLite state without relying on a WAL checkpoint."""
    deadline = time.monotonic() + 30

    def progress(status, remaining, total):
        if time.monotonic() > deadline:
            raise TimeoutError("database backup exceeded its snapshot time limit")

    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as reader:
        with closing(sqlite3.connect(destination)) as writer:
            reader.backup(writer, pages=256, progress=progress, sleep=0.05)
            writer.commit()
            integrity = writer.execute("PRAGMA integrity_check").fetchall()
            if integrity != [("ok",)]:
                raise ValueError("database snapshot failed SQLite integrity verification")
            # The snapshot is standalone; do not leave required WAL bytes behind.
            writer.execute("PRAGMA journal_mode=DELETE")


def _copy_stable_file(source: Path, destination: Path):
    # Sidecars have no shared transaction with SQLite. Refuse detected writes
    # during copying; atomic replacement or a stable copy is accepted per file.
    for _ in range(3):
        _check_source_path(source)
        with source.open("rb") as reader:
            before = os.fstat(reader.fileno())
            with destination.open("wb") as writer:
                shutil.copyfileobj(reader, writer, length=1024 * 1024)
            after = os.fstat(reader.fileno())
        current = source.stat()
        # Windows fstat and path stat expose different ctime semantics. Compare
        # ctime only between calls on the same handle, not against path stat.
        signature = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns)
        if signature(before) == signature(after) == signature(current) and before.st_ctime_ns == after.st_ctime_ns:
            return
    raise RuntimeError("application state changed repeatedly while staging the backup; retry when idle")


def _stage_files(files, staging):
    staged = []
    for source in files:
        _check_source_path(source)
        destination = staging / source.relative_to(DATA_DIR)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as handle:
            sqlite_header = handle.read(16) == b"SQLite format 3" + bytes([0])
        known_database = source.resolve() == store.DB_FILE.resolve() or source.relative_to(DATA_DIR).as_posix() in {"trials.sqlite3", "archive.sqlite3"}
        if known_database or sqlite_header:
            _snapshot_database(source, destination)
        else:
            _copy_stable_file(source, destination)
        staged.append(destination)
    return staged


def _manifest(files, excluded, scope="application", root=None):
    entries = []
    for path in files:
        relative = path.relative_to(root or DATA_DIR).as_posix()
        entries.append({"path": relative, "bytes": path.stat().st_size, "sha256": _sha256(path)})
    return {
        "formatVersion": BACKUP_FORMAT_VERSION,
        "application": "Rasputin",
        "scope": scope,
        "createdAt": time.time(),
        "sourceDataDir": str(DATA_DIR),
        "entries": entries,
        "excluded": excluded,
        "consistency": {
            "database": "SQLite online backup of each database; committed state per database",
            "sidecars": "Individual staged copies; detected concurrent writes are retried",
            "crossFileAtomic": False,
        },
        "disclosure": "Application state may include local account hashes and encrypted/provider configuration; model caches, TLS keys, and workspace source files are excluded by default. Databases and sidecar files are not one cross-file transaction; use a stopped source when cross-file consistency is required.",
    }


def create_backup(destination=None, dry_run=False, include_workspace=False):
    if include_workspace:
        raise ValueError("workspace source backup is not enabled in the application backup scope")
    target = Path(destination) if destination else BACKUP_DIR / f"rasputin-{time.strftime('%Y%m%d-%H%M%S')}.zip"
    target = target.expanduser().resolve()
    active = DATA_DIR.resolve()
    if target.is_relative_to(active) and not target.is_relative_to(BACKUP_DIR.resolve()):
        raise ValueError("backup destination inside active data must be in the backups directory")
    files, excluded = _files()
    # Hashing and compression only consume this private staging tree. No
    # application lock is held during compression or archive verification.
    with tempfile.TemporaryDirectory(prefix="rasputin-backup-snapshot-") as temporary_dir:
        staging = Path(temporary_dir)
        staged = _stage_files(files, staging)
        manifest = _manifest(staged, excluded, root=staging)
        result = {
            "dryRun": bool(dry_run),
            "path": str(target),
            "manifest": manifest,
            "fileCount": len(staged),
            "excludedCount": len(excluded),
            "created": False,
            "verified": False,
            "integrityVerified": False,
            "restoreRehearsed": False,
        }
        if dry_run:
            return result
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=f".{target.name}-", suffix=".partial", dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=True))
                for path in staged:
                    archive.write(path, path.relative_to(staging).as_posix())
            verification = inspect_backup(temporary)
            if not verification["valid"] or verification["verifiedCount"] != len(staged):
                raise ValueError("created backup failed archive integrity verification")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    result.update({"created": True, "verified": True, "integrityVerified": True})
    return result


def _safe_archive_name(name):
    if not isinstance(name, str) or not name or "\\" in name or ":" in name or name == "manifest.json":
        return False
    path = PurePosixPath(name)
    return (
        not path.is_absolute()
        and not PureWindowsPath(name).anchor
        and ".." not in path.parts
        and path.as_posix() == name
        and name != "."
    )


def _inspect_archive(archive, target):
    try:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("backup manifest is missing or invalid") from exc
    if not isinstance(manifest, dict) or manifest.get("formatVersion") != BACKUP_FORMAT_VERSION:
        raise ValueError("backup format version is not supported")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
        raise ValueError("backup manifest entries are invalid")
    verified = []
    invalid = []
    names = archive.namelist()
    seen = set()
    if names.count("manifest.json") != 1:
        invalid.append({"path": "manifest.json", "reason": "duplicate_entry"})
    for entry in entries:
        name = entry.get("path")
        if not _safe_archive_name(name) or name not in names:
            invalid.append({"path": name, "reason": "unsafe_or_missing_entry"})
            continue
        if name.casefold() in seen or names.count(name) != 1:
            invalid.append({"path": name, "reason": "duplicate_entry"})
            continue
        seen.add(name.casefold())
        digest = hashlib.sha256()
        size = 0
        with archive.open(name) as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        item = {"path": name, "bytes": size, "sha256": digest.hexdigest()}
        if item["sha256"] != entry.get("sha256"):
            item["reason"] = "hash_mismatch"
            invalid.append(item)
        elif size != entry.get("bytes"):
            item["reason"] = "size_mismatch"
            invalid.append(item)
        else:
            verified.append(item)
    return {
        "path": str(target),
        "valid": not invalid,
        "formatVersion": manifest.get("formatVersion"),
        "scope": manifest.get("scope"),
        "createdAt": manifest.get("createdAt"),
        "fileCount": len(entries),
        "verifiedCount": len(verified),
        "invalid": invalid,
        "excluded": manifest.get("excluded") or [],
        "consistency": manifest.get("consistency"),
        "disclosure": manifest.get("disclosure") or "",
    }, manifest


def inspect_backup(path):
    target = Path(path).expanduser().resolve()
    if not target.is_file():
        raise ValueError("backup file does not exist")
    with zipfile.ZipFile(target, "r") as archive:
        report, _ = _inspect_archive(archive, target)
    return report


def restore_dry_run(path):
    report = inspect_backup(path)
    report.update({
        "dryRun": True,
        "wouldRestore": report["valid"],
        "nextAction": "Run restore from a stopped/clean instance after reviewing this report." if report["valid"] else "Create a new backup; this archive cannot be restored safely.",
    })
    return report


def restore_to_directory(path, destination, dry_run=True):
    """Restore verified files by renaming one staging directory into a clean target."""
    target = Path(destination).expanduser().resolve()
    active = DATA_DIR.resolve()
    if target.is_relative_to(active) or active.is_relative_to(target):
        raise ValueError("restore destination must be separate from the active data directory")

    def check_target():
        if target.exists() and not target.is_dir():
            raise ValueError("restore destination must be a directory")
        if target.exists() and any(target.iterdir()):
            raise ValueError("restore destination must be absent or empty")

    check_target()
    archive_path = Path(path).expanduser().resolve()
    # Hold the verified archive open through extraction instead of reopening a
    # potentially replaced path between inspection and extraction.
    with zipfile.ZipFile(archive_path, "r") as archive:
        report, manifest = _inspect_archive(archive, archive_path)
        if not report["valid"]:
            raise ValueError("backup archive failed manifest verification")
        report.update({
            "destination": str(target),
            "dryRun": bool(dry_run),
            "wouldRestore": True,
            "nextAction": "Use --apply against this clean target, then start Rasputin with RASPUTIN_DATA_DIR pointing to it." if dry_run else "Start Rasputin with RASPUTIN_DATA_DIR pointing to this restored target.",
        })
        if dry_run:
            return report
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".rasputin-restore-", dir=str(target.parent)))
        restored_count = 0
        try:
            for entry in manifest["entries"]:
                name = entry["path"]
                destination_file = (staging / name).resolve()
                if not destination_file.is_relative_to(staging):
                    raise ValueError("backup contains an unsafe manifest path")
                destination_file.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name, "r") as source, destination_file.open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                if destination_file.stat().st_size != entry["bytes"] or _sha256(destination_file) != entry["sha256"]:
                    raise ValueError("backup changed during extraction")
                restored_count += 1
            check_target()
            if target.exists():
                target.rmdir()  # Only remove the still-empty destination.
            staging.replace(target)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    report.update({"dryRun": False, "restoredCount": restored_count, "restored": True})
    return report


def _owner_counts(owner_id):
    owner = str(owner_id or "admin")
    counts = {}
    with store._lock, closing(store.connect()) as conn:
        for table in ("sessions", "tasks", "inbox_events", "connectors", "approvals", "memory_items", "memory_jobs", "assistant_plans", "assistant_context_capsules", "assistant_model_packs", "assistant_handoffs"):
            columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            if "owner_id" in columns:
                counts[table] = conn.execute(f"SELECT COUNT(*) AS n FROM {table} WHERE owner_id=?", (owner,)).fetchone()["n"]
    return counts


def export_owner_data(owner_id):
    owner = str(owner_id or "admin")
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    target = EXPORT_DIR / f"rasputin-owner-{owner.replace('/', '_')}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    counts = _owner_counts(owner)
    # Export counts and metadata only; full prompts/memory contents remain in
    # the local backup scope and are never returned by this API.
    payload = {
        "formatVersion": 1,
        "application": "Rasputin",
        "owner": owner,
        "createdAt": time.time(),
        "counts": counts,
        "disclosure": "This export contains owner-scoped record counts and no credentials, prompts, memory contents, or provider secrets.",
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"path": str(target), "counts": counts, "formatVersion": 1}


def delete_owner_data(owner_id, confirmation="", dry_run=True):
    owner = str(owner_id or "admin")
    counts = _owner_counts(owner)
    preview = {
        "owner": owner,
        "dryRun": bool(dry_run),
        "counts": counts,
        "confirmationRequired": "DELETE MY RASPUTIN DATA",
    }
    if dry_run or confirmation != "DELETE MY RASPUTIN DATA":
        return preview
    with store._lock, closing(store.connect()) as conn:
        task_rows = conn.execute("SELECT id FROM tasks WHERE owner_id=?", (owner,)).fetchall()
        task_ids = [row["id"] for row in task_rows]
        session_rows = conn.execute("SELECT id FROM sessions WHERE owner_id=?", (owner,)).fetchall()
        session_ids = [row["id"] for row in session_rows]
        if task_ids:
            marks = ",".join("?" for _ in task_ids)
            for table in ("outputs", "tool_calls", "task_events", "agent_traces"):
                conn.execute(f"DELETE FROM {table} WHERE task_id IN ({marks})", task_ids)
        if session_ids:
            marks = ",".join("?" for _ in session_ids)
            conn.execute(f"DELETE FROM messages WHERE session_id IN ({marks})", session_ids)
            conn.execute(f"DELETE FROM eviction_log WHERE session_id IN ({marks})", session_ids)
        for table in ("sessions", "tasks", "inbox_events", "connectors", "approvals", "memory_items", "memory_jobs", "assistant_plans", "assistant_context_capsules", "assistant_model_packs", "assistant_handoffs"):
            columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            if "owner_id" in columns:
                conn.execute(f"DELETE FROM {table} WHERE owner_id=?", (owner,))
        conn.commit()
    return {"owner": owner, "dryRun": False, "deleted": counts}
