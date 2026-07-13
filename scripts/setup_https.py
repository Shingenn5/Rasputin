"""Generate Rasputin's local HTTPS leaf certificate with mkcert.

This script deliberately delegates CA creation and trust installation to the
official mkcert executable. It never reads or copies mkcert's root CA key.
"""

from __future__ import annotations

import argparse
import ipaddress
import shutil
import socket
import subprocess
import sys
from pathlib import Path


def _valid_name(value: str) -> str:
    value = value.strip()
    if not value or any(ch.isspace() for ch in value):
        raise argparse.ArgumentTypeError("names must be hostnames or IP addresses without whitespace")
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        pass
    labels = value.rstrip(".").split(".")
    if any(
        not label
        or len(label) > 63
        or label.startswith("-")
        or label.endswith("-")
        or not label.replace("-", "a").isalnum()
        for label in labels
    ):
        raise argparse.ArgumentTypeError(f"invalid hostname: {value}")
    return value.rstrip(".")


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure trusted local HTTPS for Rasputin")
    parser.add_argument("--output-dir", default="data/tls")
    parser.add_argument("--name", action="append", type=_valid_name, dest="names")
    parser.add_argument("--skip-install", action="store_true", help="do not run mkcert -install")
    args = parser.parse_args()

    executable = shutil.which("mkcert")
    if not executable:
        print("mkcert was not found on PATH.", file=sys.stderr)
        print("Install it from https://github.com/FiloSottile/mkcert, then rerun this command.", file=sys.stderr)
        return 2

    names = args.names or ["localhost", "127.0.0.1", "::1", socket.gethostname()]
    names = list(dict.fromkeys(names))
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    cert = output / "rasputin.pem"
    key = output / "rasputin-key.pem"

    if not args.skip_install:
        subprocess.run([executable, "-install"], check=True)
    subprocess.run(
        [executable, "-cert-file", str(cert), "-key-file", str(key), *names],
        check=True,
    )
    (output / "hosts.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
    print(f"Certificate: {cert}")
    print(f"Private key: {key}")
    print(f"Names: {', '.join(names)}")
    print("Keep the leaf private key local. Never copy mkcert's rootCA-key.pem.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
