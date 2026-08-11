"""Rehearse owner-scoped lasting memory across fresh Python processes.

The rehearsal uses an isolated, empty data directory and two independent
Python processes.  It proves that a saved memory item, duplicate detection,
reviewed correction/supersession, provenance, and owner boundaries survive a
process restart.  It never opens the active data directory, starts a model,
opens audio devices, contacts a remote endpoint, or changes deployment state.
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
SCHEMA_VERSION = "rasputin.memory-restart-rehearsal.v1"
OWNER = "restart-rehearsal-owner"
OTHER_OWNER = "restart-rehearsal-other-owner"
WORKSPACE = "C:/rasputin/restart-rehearsal"


def _phase(data_dir: Path, phase: str, ids: dict | None = None) -> dict:
    payload = json.dumps(ids or {}, separators=(",", ":"))
    source = r'''
import json
import sys

from backend.rag import memory

owner = "restart-rehearsal-owner"
other_owner = "restart-rehearsal-other-owner"
workspace = "C:/rasputin/restart-rehearsal"
phase = sys.argv[1]
ids = json.loads(sys.argv[2])

if phase == "seed":
    memory.init_memory()
    original = memory.add_item(
        "preference",
        {"key": "assistant.tone", "value": "sarcastic but respectful"},
        scope="workspace",
        workspace_id=workspace,
        owner_id=owner,
        canonical_key="preference:assistant.tone",
        source_task_id="restart-task-original",
        source_session_id="restart-session-original",
        source_message_ids=["restart-message-original"],
        export=False,
    )
    duplicate = memory.add_item(
        "preference",
        {"key": "assistant.tone", "value": "sarcastic but respectful"},
        scope="workspace",
        workspace_id=workspace,
        owner_id=owner,
        canonical_key="preference:assistant.tone",
        export=False,
    )
    correction = memory.add_item(
        "preference",
        {"key": "assistant.tone", "value": "dry sarcasm with respectful wording"},
        scope="workspace",
        workspace_id=workspace,
        owner_id=owner,
        canonical_key="preference:assistant.tone",
        source_task_id="restart-task-correction",
        source_session_id="restart-session-correction",
        source_message_ids=["restart-message-correction"],
        export=False,
    )
    approved = memory.approve_item(correction["id"], owner)
    print(json.dumps({
        "original_id": original["id"],
        "correction_id": approved["id"],
        "duplicate_of_id": duplicate.get("duplicate_of_id"),
        "deduplicated": bool(duplicate.get("deduplicated")),
        "correction_status": approved.get("status"),
        "correction_source_task_id": approved.get("source_task_id"),
    }))
elif phase == "verify":
    memory.init_memory()
    original = memory.get_item(ids["original_id"], owner)
    correction = memory.get_item(ids["correction_id"], owner)
    recalled = memory.search("respectful wording", limit=10, owner_id=owner, workspace_id=workspace)
    other_owner = memory.search("respectful wording", limit=10, owner_id=other_owner, workspace_id=workspace)
    print(json.dumps({
        "original_status": original.get("status") if original else None,
        "correction_status": correction.get("status") if correction else None,
        "correction_source_task_id": correction.get("source_task_id") if correction else None,
        "recalled_ids": [item.get("id") for item in recalled.get("items", [])],
        "other_owner_result_count": len(other_owner.get("items", [])),
        "saved_count": len(memory.list_items("saved", owner_id=owner, workspace_id=workspace)),
        "superseded_count": len(memory.list_items("superseded", owner_id=owner, workspace_id=workspace)),
    }))
else:
    raise SystemExit("unknown rehearsal phase")
'''
    env = os.environ.copy()
    env["RASPUTIN_DATA_DIR"] = str(data_dir)
    completed = subprocess.run(
        [sys.executable, "-c", source, phase, payload],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "phase failed").strip()[-1000:]
        raise RuntimeError(f"{phase} phase failed: {detail}")
    try:
        return json.loads(completed.stdout.strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{phase} phase returned invalid evidence") from exc


def _run(data_dir: Path) -> dict:
    seed = _phase(data_dir, "seed")
    verify = _phase(data_dir, "verify", seed)
    passed = (
        seed.get("deduplicated")
        and seed.get("duplicate_of_id") == seed.get("original_id")
        and seed.get("correction_status") == "saved"
        and seed.get("correction_source_task_id") == "restart-task-correction"
        and verify.get("original_status") == "superseded"
        and verify.get("correction_status") == "saved"
        and verify.get("correction_source_task_id") == "restart-task-correction"
        and seed.get("correction_id") in verify.get("recalled_ids", [])
        and verify.get("other_owner_result_count") == 0
        and verify.get("saved_count") == 1
        and verify.get("superseded_count") == 1
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "passed" if passed else "failed",
        "passed": bool(passed),
        "evidence": {
            "seed": seed,
            "verifyAfterFreshProcess": verify,
            "processes": 2,
            "workspaceScope": WORKSPACE,
        },
        "policy": {
            "isolatedDataDirectory": True,
            "activeDataTouched": False,
            "modelsStarted": False,
            "audioIoStarted": False,
            "remoteEndpointsContacted": False,
            "deploymentChanged": False,
        },
        "nextActions": [] if passed else ["Inspect the isolated rehearsal phase output and rerun after correcting the memory lifecycle."],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        help="empty isolated directory to use; omitted means a temporary directory is removed after the run",
    )
    args = parser.parse_args(argv)

    try:
        if args.data_dir:
            data_dir = Path(args.data_dir).expanduser().resolve()
            if data_dir.exists() and any(data_dir.iterdir()):
                report = {
                    "schemaVersion": SCHEMA_VERSION,
                    "status": "blocked",
                    "passed": False,
                    "error": "refusing to write a non-empty data directory; use an isolated empty target",
                }
                print(json.dumps(report, indent=2, sort_keys=True))
                return 2
            data_dir.mkdir(parents=True, exist_ok=True)
            report = _run(data_dir)
        else:
            with tempfile.TemporaryDirectory(prefix="rasputin-memory-restart-") as temp_dir:
                report = _run(Path(temp_dir))
    except (OSError, RuntimeError, ValueError) as exc:
        report = {
            "schemaVersion": SCHEMA_VERSION,
            "status": "failed",
            "passed": False,
            "error": str(exc)[:1000],
        }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
