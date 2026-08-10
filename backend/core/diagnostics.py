"""Owner-facing, read-only operational diagnostics.

The report intentionally contains paths, statuses, counts, and remediation
steps only. It never includes model prompts, memory contents, credentials, or
container logs.
"""

from __future__ import annotations

import json
import os
import platform
import time
from pathlib import Path

from backend.core import runtime_store as store
from backend.core import security
from backend.core import workspace
from backend.models import registry as model_registry
from backend.warsat import hardware_probe


ROOT = Path(__file__).resolve().parents[2]


def _check(check_id, label, status, detail, evidence=None, next_action=""):
    return {
        "id": check_id,
        "label": label,
        "status": status,
        "detail": detail,
        "evidence": evidence or {},
        "nextAction": next_action,
    }


def _app_version():
    try:
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        return str(package.get("version") or "unknown")
    except Exception:
        return "unknown"


def _storage_check():
    data_dir = Path(store.DATA_DIR)
    db_file = Path(store.DB_FILE)
    writable = False
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe = data_dir / ".diagnostics-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        writable = True
    except OSError:
        writable = False
    status = "pass" if data_dir.is_dir() and writable else "block"
    return _check(
        "storage",
        "Application storage",
        status,
        "Storage exists and is writable." if status == "pass" else "Rasputin cannot write its isolated application data directory.",
        {
            "dataDir": str(data_dir),
            "database": str(db_file),
            "databasePresent": db_file.is_file(),
            "databaseBytes": db_file.stat().st_size if db_file.is_file() else 0,
        },
        "Choose a writable RASPUTIN_DATA_DIR or repair its permissions." if status != "pass" else "",
    )


def _backup_check():
    candidates = [Path(store.DATA_DIR) / "backups", Path(store.DATA_DIR) / "backup"]
    files = [path for root in candidates if root.is_dir() for path in root.iterdir() if path.is_file()]
    latest = max(files, key=lambda path: path.stat().st_mtime, default=None)
    if not latest:
        return _check(
            "backupFreshness",
            "Backup freshness",
            "warn",
            "No local backup artifact has been recorded yet.",
            {"latest": None},
            "Create and verify a backup before relying on this instance for important work.",
        )
    age_hours = max(0.0, (time.time() - latest.stat().st_mtime) / 3600)
    status = "pass" if age_hours <= 24 * 7 else "warn"
    return _check(
        "backupFreshness",
        "Backup freshness",
        status,
        f"Latest backup is {age_hours:.1f} hour(s) old.",
        {"latest": str(latest), "ageHours": round(age_hours, 2)},
        "Create a fresh backup and rehearse restore." if status != "pass" else "",
    )


def _model_check():
    models = model_registry.all_models()
    reachable = [item for item in models if item.get("runtime_status") in {"reachable", "healthy", "ready", "running"}]
    certified = [item for item in reachable if (item.get("compatibility") or {}).get("status") == "certified"]
    coder_ready = [
        item for item in certified
        if "code" in ((item.get("compatibility") or {}).get("supportedModes") or [])
        and (item.get("compatibility") or {}).get("toolSupport") == "agentic"
    ]
    if coder_ready:
        status = "pass"
        detail = f"{len(coder_ready)} reachable model(s) are certified for Code."
        next_action = ""
    elif reachable:
        status = "warn"
        detail = f"{len(reachable)} reachable model(s) found, but none are certified for Code."
        next_action = "Run local coder certification and use Chat until tool calling and context retention pass."
    else:
        status = "block"
        detail = "No reachable model endpoint is registered."
        next_action = "Start or register a local model, then run its health test."
    return _check(
        "models",
        "Model readiness",
        status,
        detail,
        {"registered": len(models), "reachable": len(reachable), "certified": len(certified), "coderReady": len(coder_ready)},
        next_action,
    )


def _workspace_check(username, is_admin):
    try:
        active = workspace.get_active(username, is_admin)
        active_path = active.get("active_path")
        readable = bool(active_path and Path(active_path).exists() and os.access(active_path, os.R_OK))
        status = "pass" if readable else "warn"
        detail = f"Active workspace: {active.get('active_name') or active_path or 'none'}." if readable else "No readable active workspace is selected."
        next_action = "Approve a readable workspace and select it before starting file tasks." if not readable else ""
        return _check("workspace", "Workspace access", status, detail, {
            "activePath": active_path,
            "approvedCount": len(active.get("workspaces") or []),
            "readable": readable,
        }, next_action)
    except Exception as exc:
        return _check("workspace", "Workspace access", "block", "Workspace registry could not be read.", {"errorType": type(exc).__name__}, "Repair the workspace registry or choose a new approved workspace.")


def run(category="all", username="admin", is_admin=True):
    checks = [_storage_check(), _backup_check(), _model_check(), _workspace_check(username, is_admin)]
    try:
        hardware = hardware_probe()
        hardware_checks = hardware.get("checks") if isinstance(hardware, dict) else []
        for item in hardware_checks or []:
            checks.append({
                "id": item.get("id"),
                "label": item.get("label"),
                "status": item.get("status"),
                "detail": item.get("message") or item.get("detail") or "",
                "evidence": item.get("evidence") or {},
                "nextAction": item.get("nextAction") or item.get("nextStep") or "",
            })
        detected = hardware.get("detected") or hardware.get("detectedHardware") or {}
    except Exception as exc:
        detected = {}
        checks.append(_check("runtimeProbe", "Runtime probe", "block", "Docker/GPU diagnostics could not be completed.", {"errorType": type(exc).__name__}, "Inspect Docker/WSL availability and restart the runtime if needed."))
    statuses = {item.get("status") for item in checks}
    overall = "blocked" if "block" in statuses else "attention" if "warn" in statuses else "healthy"
    return {
        "status": overall,
        "generatedAt": time.time(),
        "category": category,
        "app": {
            "name": "Rasputin",
            "version": _app_version(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "runtime": os.environ.get("WRAPPER_RUNTIME") or "native",
        },
        "security": security.offline_status(),
        "detected": detected,
        "checks": checks,
    }
