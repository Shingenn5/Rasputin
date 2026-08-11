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


def _verify_restored_target(target: Path) -> dict:
    verifier = """
import json
from backend.core import auth, runtime_store
runtime_store.init_db()
public = auth.bootstrap()
with runtime_store._lock, runtime_store.connect() as conn:
    tables = {row['name'] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
print(json.dumps({
    "databaseExists": runtime_store.DB_FILE.is_file(),
    "tableCount": len(tables),
    "authUsers": int(public.get("user_count") or 0),
    "adminPresent": public.get("role") == "admin",
}))
"""
    env = os.environ.copy()
    env["RASPUTIN_DATA_DIR"] = str(target)
    env["RASPUTIN_ADMIN_PASSWORD"] = "restore-rehearsal-only-password"
    completed = subprocess.run(
        [sys.executable, "-c", verifier],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        return {
            "passed": False,
            "exitCode": completed.returncode,
            "error": (completed.stderr or completed.stdout or "restore verification failed")[-1000:],
        }
    try:
        result = json.loads((completed.stdout or "{}").strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        return {"passed": False, "exitCode": completed.returncode, "error": f"invalid verifier output: {exc}"}
    result["passed"] = bool(result.get("databaseExists") and result.get("tableCount") and result.get("adminPresent"))
    result["exitCode"] = completed.returncode
    return result


def _rehearse() -> dict:
    from contextlib import redirect_stdout
    from io import StringIO

    with tempfile.TemporaryDirectory(prefix="rasputin-restore-source-") as source_dir, tempfile.TemporaryDirectory(prefix="rasputin-restore-target-") as target_dir:
        source = Path(source_dir)
        target = Path(target_dir) / "restored-data"
        original_data_dir = os.environ.get("RASPUTIN_DATA_DIR")
        original_password = os.environ.get("RASPUTIN_ADMIN_PASSWORD")
        os.environ["RASPUTIN_DATA_DIR"] = str(source)
        os.environ["RASPUTIN_ADMIN_PASSWORD"] = "restore-rehearsal-only-password"
        try:
            from backend.core import auth, backup, runtime_store

            runtime_store.init_db()
            with redirect_stdout(StringIO()):
                auth.bootstrap()
            fixture = source / "operator-state.json"
            fixture.write_text('{"restore": "verified"}\n', encoding="utf-8")
            archive = backup.create_backup(destination=source / "backups" / "rehearsal.zip")
            dry_run = backup.restore_to_directory(archive["path"], target, dry_run=True)
            applied = backup.restore_to_directory(archive["path"], target, dry_run=False)
            verification = _verify_restored_target(target)
            return {
                "mode": "rehearse",
                "passed": bool(dry_run.get("wouldRestore") and applied.get("restored") and verification.get("passed")),
                "archive": {"fileCount": archive.get("fileCount"), "path": archive.get("path")},
                "dryRun": {"valid": dry_run.get("valid"), "destination": dry_run.get("destination")},
                "restore": {"restoredCount": applied.get("restoredCount"), "destination": applied.get("destination")},
                "verification": verification,
            }
        finally:
            if original_data_dir is None:
                os.environ.pop("RASPUTIN_DATA_DIR", None)
            else:
                os.environ["RASPUTIN_DATA_DIR"] = original_data_dir
            if original_password is None:
                os.environ.pop("RASPUTIN_ADMIN_PASSWORD", None)
            else:
                os.environ["RASPUTIN_ADMIN_PASSWORD"] = original_password


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
