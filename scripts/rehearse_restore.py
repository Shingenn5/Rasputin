"""Rehearse or safely apply a Rasputin backup into a separate data directory.

The default command is a non-mutating inspection.  ``--apply`` is required to
materialize an archive, and the destination must be absent or empty and must
not be the active ``RASPUTIN_DATA_DIR``.  ``--rehearse`` creates representative
isolated data, restores it, and initializes it in a fresh Python process.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _isolated_worker(target: Path, program: str, *arguments: str) -> dict:
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    env["RASPUTIN_DATA_DIR"] = str(target)
    env["RASPUTIN_ADMIN_USER"] = "admin"
    env["RASPUTIN_ADMIN_PASSWORD"] = "restore-rehearsal-only-password"
    completed = subprocess.run(
        [sys.executable, "-c", program, *arguments],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or "restore rehearsal worker failed")[-1000:])
    try:
        return json.loads((completed.stdout or "").strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise RuntimeError("restore rehearsal worker returned invalid output") from exc


def _create_and_restore_fixture(source: Path, target: Path) -> dict:
    # The worker owns all source connections opened by initialization/auth.
    # Process exit closes even legacy transaction-only contexts before the
    # parent's strict TemporaryDirectory cleanup runs on Windows.
    return _isolated_worker(source, """
import json
import sys
from contextlib import closing
from backend.core import auth, backup, runtime_store, workspace
runtime_store.init_db()
auth.bootstrap()
auth.create_user("rehearsal-member", "restore-member-only-password")
workspace.set_member("project-root", "rehearsal-member", "viewer")
with closing(runtime_store.connect()) as conn:
    now = runtime_store.now()
    for owner in ("admin", "rehearsal-member"):
        conn.execute(
            "INSERT INTO sessions(id,title,status,workspace,model,mode,skill,summary,created_at,updated_at,owner_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ("restore-" + owner, "Retained rehearsal session", "active", ".", "dry-run", "chat", "general", "", now, now, owner),
        )
    conn.commit()
(runtime_store.DATA_DIR / "operator-state.json").write_text(
    json.dumps({"restore": "verified"}), encoding="utf-8"
)
archive = backup.create_backup(destination=runtime_store.DATA_DIR / "backups" / "rehearsal.zip")
print(json.dumps({
    "archive": archive,
    "dryRun": backup.restore_to_directory(archive["path"], sys.argv[1], dry_run=True),
    "restore": backup.restore_to_directory(archive["path"], sys.argv[1], dry_run=False),
}))
""", str(target))


def _verify_restored_target(target: Path) -> dict:
    try:
        result = _isolated_worker(target, """
import json
from contextlib import closing
from backend.core import auth, runtime_store
runtime_store.init_db()
with closing(runtime_store.connect()) as conn:
    tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    sessions = {row["owner_id"] for row in conn.execute(
        "SELECT owner_id FROM sessions WHERE title='Retained rehearsal session'"
    ).fetchall()}
# Check preserved records before bootstrap could replace a missing account.
users = (runtime_store.get_kv("auth") or {}).get("users", [])
members = next((item.get("members", {}) for item in (runtime_store.get_kv("workspace_config") or {}).get("workspaces", []) if item.get("id") == "project-root"), {})
public = auth.bootstrap()
print(json.dumps({
    "databaseExists": runtime_store.DB_FILE.is_file(),
    "databaseIntegrity": integrity,
    "tableCount": len(tables),
    "authUsers": len(users),
    "adminPresent": any(user.get("username") == "admin" and user.get("role") == "admin" for user in users),
    "memberPresent": any(user.get("username") == "rehearsal-member" and user.get("role") == "member" for user in users),
    "sessionOwnersPreserved": sessions == {"admin", "rehearsal-member"},
    "workspaceMembershipPreserved": members.get("admin") == "owner" and members.get("rehearsal-member") == "viewer",
    "sidecarPreserved": json.loads((runtime_store.DATA_DIR / "operator-state.json").read_text(encoding="utf-8")) == {"restore": "verified"},
}))
""")
    except RuntimeError as exc:
        return {"passed": False, "error": str(exc)}
    result["passed"] = all(result.get(key) for key in (
        "databaseExists", "databaseIntegrity", "tableCount", "adminPresent",
        "memberPresent", "sessionOwnersPreserved", "workspaceMembershipPreserved", "sidecarPreserved",
    ))
    result["exitCode"] = 0
    return result


def _rehearse() -> dict:
    with tempfile.TemporaryDirectory(prefix="rasputin-restore-source-") as source_dir, tempfile.TemporaryDirectory(prefix="rasputin-restore-target-") as target_dir:
        source = Path(source_dir)
        target = Path(target_dir) / "restored-data"
        # No backend imports or data-directory environment mutations in this
        # parent: every runtime handle belongs to a completed isolated worker.
        fixture = _create_and_restore_fixture(source, target)
        archive = fixture["archive"]
        dry_run = fixture["dryRun"]
        applied = fixture["restore"]
        verification = _verify_restored_target(target)
        result = {
            "mode": "rehearse",
            "passed": bool(archive.get("integrityVerified") and dry_run.get("wouldRestore") and applied.get("restored") and verification.get("passed")),
            "archive": {"fileCount": archive.get("fileCount"), "path": archive.get("path"), "integrityVerified": archive.get("integrityVerified")},
            "dryRun": {"valid": dry_run.get("valid"), "destination": dry_run.get("destination")},
            "restore": {"restoredCount": applied.get("restoredCount"), "destination": applied.get("destination")},
            "verification": verification,
        }
    # Reaching this point proves both temporary trees were removed; no cleanup
    # errors are suppressed and no garbage-collection timing is required.
    result["cleanupPassed"] = not source.exists() and not target.exists()
    result["passed"] = result["passed"] and result["cleanupPassed"]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", nargs="?", help="backup ZIP to inspect or restore")
    parser.add_argument("destination", nargs="?", help="separate empty data directory")
    parser.add_argument("--apply", action="store_true", help="materialize the verified archive")
    parser.add_argument("--rehearse", action="store_true", help="run an isolated create/restore/migration rehearsal")
    args = parser.parse_args(argv)

    if args.rehearse:
        result = _rehearse()
    else:
        if not args.archive or not args.destination:
            parser.error("archive and destination are required unless --rehearse is used")
        from backend.core import backup

        result = backup.restore_to_directory(args.archive, args.destination, dry_run=not args.apply)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("passed", result.get("valid", False)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
