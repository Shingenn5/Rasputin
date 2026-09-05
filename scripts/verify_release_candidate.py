"""Produce bounded release-candidate evidence for Rasputin.

This is a certification report, not a claim that every product boundary is
complete. Automated checks are run with isolated test data, while deployment
checks are read-only probes against explicitly selected native owners. Imported
evidence can close release rows only for the selected source/package/model identities.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.verify_source_regressions import BACKEND_TEST_MODULES, owned_popen, stop_owned_process

DEFAULT_ENDPOINTS: tuple[str, ...] = ()


def _redact(text: str) -> str:
    """Keep command evidence useful without echoing credentials or tokens."""

    value = str(text or "")
    value = re.sub(r"(?i)bearer\s+\S+", "Bearer [redacted]", value)
    value = re.sub(r"(?im)(password|token|secret|authorization)(\s*[:=]\s*)[^\r\n]+", r"\1\2[redacted]", value)
    return value


def _redact_details(value: Any) -> Any:
    if isinstance(value, str):
        return _redact(value)
    if isinstance(value, list):
        return [_redact_details(item) for item in value]
    if isinstance(value, dict):
        return {
            key: "[redacted]" if key.lower() in {"password", "token", "secret", "authorization"} else _redact_details(item)
            for key, item in value.items()
        }
    return value


def _run(label: str, command: list[str], *, env: dict[str, str] | None = None, timeout: int = 900, json_report: bool = False) -> dict[str, Any]:
    process = None
    try:
        process = owned_popen(
            command,
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        stdout, stderr = process.communicate(timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "label": label,
            "passed": False,
            "exitCode": None,
            "command": command,
            "error": _redact(str(exc)),
        }
    finally:
        if process is not None:
            stop_owned_process(process)
    output = _redact((stdout or "") + (stderr or ""))
    lines = [line for line in output.splitlines() if line.strip()]
    details = None
    if json_report:
        try:
            details = _redact_details(json.loads(stdout))
        except (ValueError, TypeError):
            return {"label": label, "passed": False, "error": "source regression command did not return valid JSON"}
        if not isinstance(details, dict):
            return {"label": label, "passed": False, "error": "source regression report must be an object"}
    return {
        **({"details": details} if json_report else {}),
        "label": label,
        "passed": process.returncode == 0 and (details is None or details.get("passed") is True),
        "exitCode": process.returncode,
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


def _target(parser: argparse.ArgumentParser, target: str | None, endpoints: list[str]) -> str:
    from urllib.parse import urlsplit

    aliases = {"native": "native-host", "native-host": "native-host", "desktop": "desktop"}
    owners = set()
    for endpoint in endpoints:
        label, separator, url = endpoint.partition("=")
        if not separator or label.strip() not in aliases:
            parser.error("--endpoint expects native-host=URL or desktop=URL (native=URL remains supported)")
        owner = aliases[label.strip()]
        owners.add(owner)
        parsed = urlsplit(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            parser.error("endpoints must be explicit HTTP(S) base URLs without credentials, queries, or fragments")
        if owner == "desktop" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            parser.error("Desktop probes must target loopback")
    if len(owners) > 1 or (target and owners and owners != {target}):
        parser.error("all endpoints must belong to the selected native target")
    selected = target or next(iter(owners), None)
    if selected is None:
        parser.error("select --target native-host|desktop or an explicit supported --endpoint")
    return selected


def main(argv: list[str] | None = None) -> int:
    from scripts import release_evidence as evidence

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("native-host", "desktop"))
    parser.add_argument("--endpoint", action="append", default=None, metavar="LABEL=URL")
    parser.add_argument("--package", type=Path, help="actual tested Desktop installer or package file")
    parser.add_argument("--model", action="append", default=[], metavar="ROLE=ARTIFACT_SHA256:RUNTIME_SHA256:CONFIG_SHA256")
    parser.add_argument("--evidence", type=Path, help="version 1 evidence bundle; keep it outside the source checkout")
    parser.add_argument("--identity-only", action="store_true", help="print selected identities without running checks or probing endpoints")
    parser.add_argument("--require-ready", action="store_true", help="return failure unless every release evidence row passes")
    parser.add_argument("--insecure", action="store_true", help="accept a private CA for local deployment probes")
    parser.add_argument("--no-build", action="store_true", help="reuse frontend artifacts; this run cannot certify release readiness")
    args = parser.parse_args(argv)
    target = _target(parser, args.target, args.endpoint or [])
    try:
        source = evidence.source_identity(ROOT)
        subject = {
            "source": source, "target": target,
            "package": evidence.package_identity(target, source, args.package),
            "models": evidence.parse_models(args.model),
        }
    except (evidence.EvidenceError, OSError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    if args.identity_only:
        print(json.dumps({"schemaVersion": 1, "subject": subject}, indent=2, sort_keys=True))
        return 0

    test_env = os.environ.copy()
    test_env.pop("PYTHONHOME", None)
    test_env.pop("PYTHONPATH", None)
    command = [_python(), "scripts/verify_source_regressions.py", "--json"]
    if args.no_build:
        command.append("--no-build")
    checks = {
        "sourceRegressions": _run("source regressions", command, env=test_env, timeout=3600, json_report=True),
        "frontendArtifacts": _frontend_artifacts(),
        "deploymentMatrix": _deployment(args.endpoint or [], args.insecure),
    }
    try:
        checks["identityStable"] = {
            "passed": evidence.source_identity(ROOT) == source
            and evidence.package_identity(target, source, args.package) == subject["package"],
            "detail": "Selected source and package must remain unchanged throughout verification.",
        }
    except (evidence.EvidenceError, OSError, subprocess.SubprocessError):
        checks["identityStable"] = {"passed": False, "detail": "Selected identity could not be rechecked."}
    automated_checks_passed = all(bool(item.get("passed")) for item in checks.values())
    build_verified = not args.no_build and checks["sourceRegressions"].get("details", {}).get("buildVerified") is True
    matrix = evidence.evaluate(
        args.evidence, subject,
        automated_passed=automated_checks_passed and build_verified,
    )
    boundaries = [
        {"id": row["id"], "status": "open", "detail": "; ".join(row["missing"])}
        for row in matrix["rows"] if row["status"] != "passed"
    ]
    if matrix["rejectedRecords"]:
        boundaries.append({"id": "invalidEvidence", "status": "open", "detail": "Imported records were rejected; inspect evidence.rejectedRecords."})
    ready = matrix["passed"]
    report = {
        "schemaVersion": 2,
        "application": "Rasputin",
        "subject": subject,
        "status": "release_ready" if ready else ("candidate_with_boundaries" if automated_checks_passed else "verification_failed"),
        "passed": automated_checks_passed,
        "releaseReady": ready,
        "automatedChecksPassed": automated_checks_passed,
        "buildVerified": build_verified,
        "checks": checks,
        "evidence": matrix,
        "knownBoundaries": boundaries,
        "releaseReadyReason": (
            "Current automated gates and all required evidence rows pass for the selected target and identities."
            if ready else "Release readiness requires a current frontend build, passing automated gates, and matching fresh artifact-backed evidence for every open row."
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if (ready if args.require_ready else automated_checks_passed) else 1


if __name__ == "__main__":
    raise SystemExit(main())
