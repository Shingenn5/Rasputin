"""Bounded local backup, verification, export, and deletion services."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

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


def _files():
    files = []
    excluded = []
    if not DATA_DIR.exists():
        return files, excluded
    for path in DATA_DIR.rglob("*"):
        # Do not follow links out of the application data boundary. A backup
        # must never read arbitrary host files through a symlink in data/.
        if path.is_symlink():
            excluded.append({"path": str(path.relative_to(DATA_DIR)), "reason": "symlink"})
            continue
        if not path.is_file():
            continue
        relative = path.relative_to(DATA_DIR)
        parts = set(relative.parts)
        if parts & EXCLUDED_DIRS or path.suffix.lower() in EXCLUDED_SUFFIXES or any(path.name.endswith(suffix) for suffix in SQLITE_TRANSIENT_SUFFIXES):
            excluded.append({"path": str(relative), "reason": "cache_or_private_key"})
            continue
        files.append(path)
    return files, excluded


def _checkpoint_database():
    """Move SQLite WAL contents into the main database before archiving it."""

    if not store.DB_FILE.exists():
        return
    with store._lock, store.connect() as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def _manifest(files, excluded, scope="application"):
    entries = []
    for path in files:
        relative = str(path.relative_to(DATA_DIR)).replace("\\", "/")
        entries.append({"path": relative, "bytes": path.stat().st_size, "sha256": _sha256(path)})
    return {
        "formatVersion": BACKUP_FORMAT_VERSION,
        "application": "Rasputin",
        "scope": scope,
        "createdAt": time.time(),
        "sourceDataDir": str(DATA_DIR),
        "entries": entries,
        "excluded": excluded,
        "disclosure": "Application state may include local account hashes and encrypted/provider configuration; model caches, TLS keys, and workspace source files are excluded by default.",
    }


def create_backup(destination=None, dry_run=False, include_workspace=False):
    if include_workspace:
        raise ValueError("workspace source backup is not enabled in the application backup scope")
    _checkpoint_database()
    files, excluded = _files()
    manifest = _manifest(files, excluded)
    target = Path(destination) if destination else BACKUP_DIR / f"rasputin-{time.strftime('%Y%m%d-%H%M%S')}.zip"
    target = target.expanduser().resolve()
    if dry_run:
        return {
            "dryRun": True,
            "path": str(target),
            "manifest": manifest,
            "fileCount": len(files),
            "excludedCount": len(excluded),
        }
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".partial")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=True))
            for path in files:
                archive.write(path, str(path.relative_to(DATA_DIR)).replace("\\", "/"))
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "dryRun": False,
        "path": str(target),
        "manifest": manifest,
        "fileCount": len(files),
        "excludedCount": len(excluded),
        "verified": True,
    }


def inspect_backup(path):
    target = Path(path).expanduser().resolve()
    if not target.is_file():
        raise ValueError("backup file does not exist")
    with zipfile.ZipFile(target, "r") as archive:
        try:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        except (KeyError, json.JSONDecodeError) as exc:
            raise ValueError("backup manifest is missing or invalid") from exc
        if manifest.get("formatVersion") != BACKUP_FORMAT_VERSION:
            raise ValueError("backup format version is not supported")
        verified = []
        invalid = []
        names = set(archive.namelist())
        for entry in manifest.get("entries") or []:
            name = str(entry.get("path") or "")
            if not name or name.startswith("/") or ".." in Path(name).parts or name not in names:
                invalid.append({"path": name, "reason": "unsafe_or_missing_entry"})
                continue
            data = archive.read(name)
            digest = hashlib.sha256(data).hexdigest()
            item = {"path": name, "bytes": len(data), "sha256": digest}
            if digest != entry.get("sha256"):
                item["reason"] = "hash_mismatch"
                invalid.append(item)
            else:
                verified.append(item)
    return {
        "path": str(target),
        "valid": not invalid,
        "formatVersion": manifest.get("formatVersion"),
        "scope": manifest.get("scope"),
        "createdAt": manifest.get("createdAt"),
        "fileCount": len(manifest.get("entries") or []),
        "verifiedCount": len(verified),
        "invalid": invalid,
        "excluded": manifest.get("excluded") or [],
        "disclosure": manifest.get("disclosure") or "",
    }


def restore_dry_run(path):
    report = inspect_backup(path)
    report.update({
        "dryRun": True,
        "wouldRestore": report["valid"],
        "nextAction": "Run restore from a stopped/clean instance after reviewing this report." if report["valid"] else "Create a new backup; this archive cannot be restored safely.",
    })
    return report


def restore_to_directory(path, destination, dry_run=True):
    """Restore application files into a separate empty data directory.

    The running service must never restore over ``DATA_DIR``.  Callers must
    provide an absent or empty destination; extraction happens in a sibling
    staging directory before files are moved into place.  This keeps a failed
    archive or interrupted extraction from leaving a partially restored target.
    """

    target = Path(destination).expanduser().resolve()
    active = DATA_DIR.resolve()
    if target == active:
        raise ValueError("restore destination must be separate from the active data directory")
    if target.exists() and not target.is_dir():
        raise ValueError("restore destination must be a directory")
    if target.exists() and any(target.iterdir()):
        raise ValueError("restore destination must be absent or empty")

    report = inspect_backup(path)
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
        with zipfile.ZipFile(Path(path).expanduser().resolve(), "r") as archive:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            for entry in manifest.get("entries") or []:
                name = str(entry.get("path") or "")
                if not name or name.startswith("/") or ".." in Path(name).parts:
                    raise ValueError("backup contains an unsafe manifest path")
                destination_file = (staging / name).resolve()
                if not destination_file.is_relative_to(staging):
                    raise ValueError("backup contains an unsafe manifest path")
                destination_file.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name, "r") as source, destination_file.open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                restored_count += 1
        target.mkdir(parents=True, exist_ok=True)
        for child in staging.iterdir():
            child.replace(target / child.name)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    report.update({
        "dryRun": False,
        "restoredCount": restored_count,
        "restored": True,
    })
    return report


def _owner_counts(owner_id):
    owner = str(owner_id or "admin")
    counts = {}
    with store._lock, store.connect() as conn:
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
    with store._lock, store.connect() as conn:
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
