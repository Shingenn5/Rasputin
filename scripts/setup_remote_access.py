"""Generate or apply private remote-access configuration for Rasputin.

Nothing is exposed by default. Tailscale changes require --apply; Caddy output
is generated as a file for operator review before Caddy is started or reloaded.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit


def _tailscale_binary() -> str:
    found = shutil.which("tailscale")
    if found:
        return found
    windows = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Tailscale" / "tailscale.exe"
    if windows.is_file():
        return str(windows)
    raise RuntimeError("Tailscale was not found. Install and sign in to Tailscale first.")


def _tailscale_identity(binary: str) -> dict:
    result = subprocess.run([binary, "status", "--json"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Tailscale is not connected.")
    status = json.loads(result.stdout)
    node = status.get("Self") or {}
    dns_name = str(node.get("DNSName") or "").rstrip(".")
    if not dns_name:
        raise RuntimeError("Tailscale did not report a MagicDNS name for this machine.")
    return {"dns_name": dns_name, "backend_state": status.get("BackendState")}


def tailscale(args: argparse.Namespace) -> int:
    binary = _tailscale_binary()
    identity = _tailscale_identity(binary)
    print(f"Tailscale node: {identity['dns_name']} ({identity['backend_state']})")
    print(f"Private URL: https://{identity['dns_name']}")
    print(f"Native Host allowlist: --allowed-host {identity['dns_name']}")
    if not args.apply:
        print(f"Plan only. To apply: tailscale serve --bg --yes {args.target}")
        return 0
    result = subprocess.run([binary, "serve", "--bg", "--yes", args.target], check=False)
    if result.returncode == 0:
        subprocess.run([binary, "serve", "status"], check=False)
    return result.returncode


_HOSTNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$")


def caddy_config(hostname: str, target: str, internal_tls: bool = False) -> str:
    hostname = hostname.strip().lower()
    if not _HOSTNAME_RE.fullmatch(hostname) or ".." in hostname:
        raise ValueError("hostname must be a plain DNS name without a scheme, port, or path")
    parsed = urlsplit(target)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.path not in {"", "/"}:
        raise ValueError("target must be an http(s) origin such as http://127.0.0.1:8788")
    lines = [
        f"{hostname} {{",
        f"    reverse_proxy {target.rstrip('/')} {{",
        "        health_uri /api/health",
        "        health_interval 30s",
        "    }",
    ]
    if internal_tls:
        lines.append("    tls internal")
    lines.extend(["}", ""])
    return "\n".join(lines)


def caddy(args: argparse.Namespace) -> int:
    config = caddy_config(args.hostname, args.target, args.internal_tls)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(config, encoding="utf-8")
    print(f"Wrote {output}")
    print(f"Native Host allowlist: --allowed-host {args.hostname.lower()}")
    print("Review the file, then start or reload Caddy explicitly.")
    return 0


def probe(args: argparse.Namespace) -> int:
    url = args.url.rstrip("/")
    context = ssl._create_unverified_context() if args.insecure else None
    try:
        with urllib.request.urlopen(f"{url}/api/health", timeout=args.timeout, context=context) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if response.status != 200:
                raise RuntimeError(f"unexpected HTTP status {response.status}")
    except (OSError, urllib.error.URLError, ValueError) as exc:
        print(f"Remote access probe failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"url": url, "status": response.status, "health": payload}, indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="setup_remote_access.py")
    commands = root.add_subparsers(dest="command", required=True)

    tailscale_parser = commands.add_parser("tailscale", help="plan or apply private Tailscale Serve access")
    tailscale_parser.add_argument("--target", default="http://127.0.0.1:8788")
    tailscale_parser.add_argument("--apply", action="store_true")
    tailscale_parser.set_defaults(handler=tailscale)

    caddy_parser = commands.add_parser("caddy", help="generate a reviewed Caddy reverse-proxy configuration")
    caddy_parser.add_argument("--hostname", required=True)
    caddy_parser.add_argument("--target", default="http://127.0.0.1:8788")
    caddy_parser.add_argument("--output", required=True)
    caddy_parser.add_argument("--internal-tls", action="store_true")
    caddy_parser.set_defaults(handler=caddy)

    probe_parser = commands.add_parser("probe", help="verify a Rasputin URL through its final access path")
    probe_parser.add_argument("--url", required=True)
    probe_parser.add_argument("--timeout", type=float, default=5)
    probe_parser.add_argument("--insecure", action="store_true")
    probe_parser.set_defaults(handler=probe)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.handler(args)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Remote access setup failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
