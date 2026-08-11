"""Run a read-only cross-platform installation preflight.

The command checks repository assets, locally available CLI tools, Docker
Compose client availability, and default loopback port occupancy. It does not
write configuration, touch Rasputin data, stop processes, or contact a remote
service. Port occupancy is informational: an existing healthy instance is not
an error, but a new instance may need a different host port.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "rasputin.installation-preflight.v1"


def _command(name: str, args: list[str] | None = None) -> dict:
    executable = shutil.which(name)
    result = {"name": name, "present": bool(executable)}
    if not executable:
        return result
    result["version"] = ""
    if args is None:
        return result
    try:
        completed = subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            env={**os.environ, "DOCKER_CLI_HINTS": "false"},
        )
        output = (completed.stdout or completed.stderr or "").strip().splitlines()
        result["version"] = output[0][:160] if output else ""
        result["exit_code"] = completed.returncode
    except (OSError, subprocess.TimeoutExpired) as exc:
        result["error"] = type(exc).__name__
    return result


def _compose_command() -> dict:
    docker = shutil.which("docker")
    result = {"present": False, "version": ""}
    if not docker:
        return result
    # Keep Docker CLI configuration isolated so a read-only version probe does
    # not read or modify the operator's Docker credentials/configuration.
    with tempfile.TemporaryDirectory(prefix="rasputin-docker-config-") as config_dir:
        env = {**os.environ, "DOCKER_CONFIG": config_dir, "DOCKER_CLI_HINTS": "false"}
        try:
            completed = subprocess.run(
                [docker, "compose", "version"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"present": False, "error": type(exc).__name__}
    output = (completed.stdout or completed.stderr or "").strip().splitlines()
    result["present"] = completed.returncode == 0
    result["version"] = output[0][:160] if output else ""
    result["exit_code"] = completed.returncode
    return result


def _port(port: int) -> dict:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        state = "in_use" if probe.connect_ex(("127.0.0.1", port)) == 0 else "available"
    return {
        "port": port,
        "state": state,
        "next_action": (
            "Use the existing instance or choose another host port with WRAPPER_PORT."
            if state == "in_use"
            else "No listener detected on the default port."
        ),
    }


def _run(root: Path) -> dict:
    required_files = [
        "README.md",
        "docker-compose.yml",
        "Dockerfile",
        "requirements.txt",
        "package.json",
        "frontend-src",
        "backend",
        "rasputin.ps1",
        "rasputin.sh",
    ]
    files = {item: (root / item).exists() for item in required_files}
    commands = {
        "git": _command("git", ["--version"]),
        "docker": _command("docker", ["--version"]),
        "python": _command("python", ["--version"]),
        "node": _command("node", ["--version"]),
        "npm": _command("npm.cmd" if os.name == "nt" else "npm", ["--version"]),
    }
    commands["docker_compose"] = _compose_command()
    ports = [_port(8787), _port(8788)]
    docker_ready = bool(commands["docker"]["present"] and commands["docker_compose"]["present"])
    native_ready = bool(os.name == "nt" and (root / "rasputin.ps1").is_file())
    missing_assets = sorted(item for item, present in files.items() if not present)
    required_path_ready = not missing_assets
    if required_path_ready and (docker_ready or native_ready):
        status = "ready"
    elif missing_assets:
        status = "blocked"
    else:
        status = "needs_prerequisite"
    next_actions = []
    if missing_assets:
        next_actions.append("Run the preflight from the repository root so all deployment assets are available.")
    if not docker_ready:
        next_actions.append("Install and start Docker Desktop (Windows/macOS) or Docker Engine plus Compose v2 (Linux) for Docker deployment.")
    if os.name == "nt" and not native_ready:
        next_actions.append("Keep rasputin.ps1 available for the supported Windows Native Server path.")
    next_actions.extend(item["next_action"] for item in ports if item["state"] == "in_use")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": status,
        "passed": status == "ready",
        "platform": {"os": os.name, "platform": sys.platform, "dockerDeploymentSupported": docker_ready, "nativeDeploymentSupported": native_ready},
        "repository": {"root": str(root), "requiredAssets": files, "missingAssets": missing_assets},
        "commands": commands,
        "ports": ports,
        "policy": {"readOnly": True, "runtimeDataTouched": False, "processesStopped": False, "remoteEndpointsContacted": False, "credentialsRead": False},
        "nextActions": list(dict.fromkeys(next_actions)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT), help="repository root to inspect")
    args = parser.parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(json.dumps({"schemaVersion": SCHEMA_VERSION, "status": "blocked", "passed": False, "error": "repository root does not exist"}, indent=2, sort_keys=True))
        return 2
    report = _run(root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
