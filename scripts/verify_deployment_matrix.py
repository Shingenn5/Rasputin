"""Read-only health and security verification across Rasputin deployments."""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _request(url: str, insecure: bool = False) -> tuple[int, dict, bytes]:
    context = ssl._create_unverified_context() if insecure and url.startswith("https://") else None
    with urllib.request.urlopen(url, timeout=8, context=context) as response:
        return response.status, dict(response.headers.items()), response.read()


def verify_endpoint(label: str, base_url: str, insecure: bool = False) -> dict:
    base_url = base_url.rstrip("/")
    status, headers, body = _request(f"{base_url}/api/health", insecure)
    payload = json.loads(body.decode("utf-8"))
    health_ok = status == 200 and payload.get("ok") is True

    root_status, root_headers, _ = _request(f"{base_url}/", insecure)
    normalized = {key.lower(): value for key, value in root_headers.items()}
    security_ok = (
        normalized.get("x-content-type-options", "").lower() == "nosniff"
        and normalized.get("x-frame-options", "").upper() == "DENY"
        and normalized.get("referrer-policy", "").lower() == "no-referrer"
    )
    return {
        "label": label,
        "url": base_url,
        "healthy": health_ok,
        "frontend": root_status == 200,
        "securityHeaders": security_ok,
        "passed": health_ok and root_status == 200 and security_ok,
    }


def artifact_status() -> dict:
    paths = {
        "backendRuntime": ROOT / "dist" / "desktop-backend" / "rasputin-backend" / "rasputin-backend.exe",
        "unpackedDesktop": ROOT / "dist" / "electron" / "win-unpacked" / "Rasputin.exe",
    }
    return {name: {"path": str(path), "exists": path.is_file()} for name, path in paths.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="verify_deployment_matrix.py")
    parser.add_argument(
        "--endpoint",
        action="append",
        default=[],
        metavar="LABEL=URL",
        help="deployment endpoint to verify; repeat for desktop, native-host, docker, or remote",
    )
    parser.add_argument("--insecure", action="store_true", help="accept a private CA for this local verification only")
    parser.add_argument("--require-desktop-artifacts", action="store_true")
    args = parser.parse_args(argv)

    results = []
    for item in args.endpoint:
        if "=" not in item:
            parser.error(f"invalid endpoint {item!r}; expected LABEL=URL")
        label, url = item.split("=", 1)
        try:
            results.append(verify_endpoint(label.strip(), url.strip(), args.insecure))
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
            results.append({"label": label.strip(), "url": url.strip(), "passed": False, "error": str(exc)})

    artifacts = artifact_status()
    artifacts_ok = all(item["exists"] for item in artifacts.values())
    passed = all(item.get("passed") for item in results) and (artifacts_ok or not args.require_desktop_artifacts)
    report = {"passed": passed, "deployments": results, "desktopArtifacts": artifacts}
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
