"""Opt-in real llama-server smoke test; never downloads or supplies model files."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.warsat.providers.native_llamacpp import _terminate


def check_prerequisites(model_path=None):
    executable = str(os.environ.get("RASPUTIN_LLAMA_SERVER") or "").strip()
    if not executable:
        return False, "RASPUTIN_LLAMA_SERVER is not set"
    resolved = executable if Path(executable).is_file() else shutil.which(executable)
    if not resolved:
        return False, f"llama-server executable not found: {executable}"
    if not model_path:
        return False, "a caller-provided tiny GGUF path is required (--model)"
    path = Path(model_path).expanduser()
    if not path.is_file():
        return False, f"GGUF model file not found: {path}"
    if path.suffix.lower() != ".gguf":
        return False, f"model path is not a .gguf file: {path}"
    return True, str(Path(resolved).resolve())


def _request(url, payload=None, timeout=5):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8", "replace")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", help="caller-provided tiny GGUF path")
    parser.add_argument("--port", type=int, default=18082)
    parser.add_argument("--check", action="store_true", help="only detect prerequisites; never start a process")
    args = parser.parse_args(argv)
    ready, detail = check_prerequisites(args.model)
    if not ready:
        print(f"SKIPPED: {detail}")
        return 0
    if args.check:
        print(f"PREREQUISITES OK: {detail}")
        return 0
    command = [detail, "--model", str(Path(args.model).expanduser().resolve()), "--host", "127.0.0.1", "--port", str(args.port)]
    creationflags = 0
    if os.name == "nt":
        # Isolate the opt-in harness from the console process group so an interrupted smoke run cannot signal the desktop app alongside it.
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=os.name != "nt", creationflags=creationflags)
    base = f"http://127.0.0.1:{args.port}"
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"llama-server exited with code {process.returncode}")
            try:
                status, _ = _request(base + "/health", timeout=1)
                if 200 <= status < 300:
                    break
            except (OSError, urllib.error.URLError):
                time.sleep(0.25)
        else:
            raise RuntimeError("llama-server health timeout")
        status, body = _request(base + "/v1/chat/completions", {"model": "smoke", "messages": [{"role": "user", "content": "Reply with exactly OK."}], "max_tokens": 8}, timeout=30)
        if not 200 <= status < 300:
            raise RuntimeError(f"chat completion returned HTTP {status}: {body[:300]}")
        print("VERIFIED: /health and /v1/chat/completions succeeded")
        return 0
    finally:
        if process.poll() is None:
            _terminate(process.pid)


if __name__ == "__main__":
    raise SystemExit(main())
