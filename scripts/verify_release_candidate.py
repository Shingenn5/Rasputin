"""Produce bounded release-candidate evidence for Rasputin.

This is a certification report, not a claim that every product boundary is
complete. Automated checks are run with isolated test data, while deployment
checks are read-only probes against explicitly supplied native/Docker URLs.
Known hardware and live-model gaps remain visible in the JSON result.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND_TEST_MODULES = (
    "tests.testBackendSmoke",
    "tests.testAssistantContracts",
    "tests.testAssistantUiContract",
    "tests.testMemoryUiContract",
    "tests.testWorkModeUiContract",
    "tests.test_coding_acceptance",
    "tests.test_coder_certification_cli",
    "tests.testDiagnostics",
    "tests.testBackup",
    "tests.testHardwareCapabilities",
    "tests.testResourceBroker",
    "tests.testWarsatAdvisor",
    "tests.testReleaseCandidate",
)
DEFAULT_ENDPOINTS = (
    "native=http://127.0.0.1:8788",
    "docker=http://127.0.0.1:8787",
)


def _redact(text: str) -> str:
    """Keep command evidence useful without echoing credentials or tokens."""

    value = str(text or "")
    value = re.sub(r"(?im)(password|token|secret|authorization)(\s*[:=]\s*)\S+", r"\1\2[redacted]", value)
    value = re.sub(r"(?i)bearer\s+\S+", "Bearer [redacted]", value)
    return value


def _run(label: str, command: list[str], *, env: dict[str, str] | None = None, timeout: int = 900) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "label": label,
            "passed": False,
            "exitCode": None,
            "command": command,
            "error": _redact(str(exc)),
        }
    output = _redact((completed.stdout or "") + (completed.stderr or ""))
    lines = [line for line in output.splitlines() if line.strip()]
    return {
        "label": label,
        "passed": completed.returncode == 0,
        "exitCode": completed.returncode,
        "command": command,
        "outputTail": lines[-16:],
    }


def _python() -> str:
    return str(VENV_PYTHON if VENV_PYTHON.is_file() else Path(sys.executable))


def _frontend_artifacts() -> dict[str, Any]:
    frontend = ROOT / "frontend"
    index = frontend / "index.html"
    assets = list((frontend / "assets").glob("*") if (frontend / "assets").is_dir() else [])
    return {
        "index": str(index),
        "indexExists": index.is_file(),
        "assetCount": len(assets),
        "assetsPresent": bool(assets),
        "passed": index.is_file() and bool(assets),
    }


def _deployment(endpoints: list[str], insecure: bool = False) -> dict[str, Any]:
    from scripts import verify_deployment_matrix as matrix

    results = []
    for item in endpoints:
        if "=" not in item:
            results.append({"label": item, "passed": False, "error": "expected LABEL=URL"})
            continue
        label, url = item.split("=", 1)
        try:
            results.append(matrix.verify_endpoint(label.strip(), url.strip(), insecure))
        except Exception as exc:  # deployment probes must report, not crash the report
            results.append({"label": label.strip(), "url": url.strip(), "passed": False, "error": _redact(str(exc))})
    artifacts = matrix.artifact_status()
    artifacts_ok = all(item["exists"] for item in artifacts.values())
    return {
        "passed": bool(results) and all(item.get("passed") for item in results),
        "deployments": results,
        "desktopArtifacts": artifacts,
        "desktopArtifactsPresent": artifacts_ok,
    }


def _known_boundaries() -> list[dict[str, str]]:
    return [
        {
            "id": "liveLocalCoderMission",
            "status": "blocked",
            "detail": "A reachable, certified local coder model is still required for the real edit-test-repair-review acceptance mission.",
        },
        {
            "id": "cleanInstanceRestore",
            "status": "open",
            "detail": "Separate-target restore and isolated SQLite migration rehearsal are verified; stopped active-data upgrade remains open.",
        },
        {
            "id": "voiceHardware",
            "status": "open",
            "detail": "Browser push-to-talk is wired and bounded; registered speech models, microphone permission, and speaker hardware need an operator run.",
        },
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", action="append", default=None, metavar="LABEL=URL")
    parser.add_argument("--insecure", action="store_true", help="accept a private CA for local deployment probes")
    parser.add_argument("--no-build", action="store_true", help="reuse the existing frontend build")
    args = parser.parse_args(argv)

    checks: dict[str, Any] = {}
    checks["documentation"] = _run("documentation", [_python(), "scripts/verify_docs.py", "--json"], timeout=120)

    with tempfile.TemporaryDirectory(prefix="rasputin-release-tests-") as isolated_data:
        test_env = os.environ.copy()
        test_env["RASPUTIN_DATA_DIR"] = isolated_data
        checks["backendTests"] = _run(
            "backend tests",
            [_python(), "-m", "unittest", *BACKEND_TEST_MODULES],
            env=test_env,
            timeout=900,
        )

    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if args.no_build:
        checks["frontendBuild"] = {"label": "frontend build", "passed": True, "skipped": True, "reason": "--no-build"}
    elif npm:
        checks["frontendBuild"] = _run("frontend build", [npm, "run", "build"], timeout=300)
    else:
        checks["frontendBuild"] = {"label": "frontend build", "passed": False, "error": "npm was not found"}
    checks["frontendArtifacts"] = _frontend_artifacts()
    checks["deploymentMatrix"] = _deployment(args.endpoint or list(DEFAULT_ENDPOINTS), args.insecure)

    automated_checks_passed = all(bool(item.get("passed")) for item in checks.values())
    boundaries = _known_boundaries()
    report = {
        "application": "Rasputin",
        "status": "candidate_with_boundaries" if automated_checks_passed else "verification_failed",
        "passed": automated_checks_passed,
        "releaseReady": False,
        "automatedChecksPassed": automated_checks_passed,
        "checks": checks,
        "knownBoundaries": boundaries,
        "releaseReadyReason": "The automated release gates pass, but the listed live-model, clean-restore, and voice-hardware evidence is still required before calling the product fully release-ready.",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if automated_checks_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
