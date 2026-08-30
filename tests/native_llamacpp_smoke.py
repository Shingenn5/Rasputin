"""Opt-in real llama-server smoke test; never downloads or supplies model files."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.warsat.providers.native_llamacpp import _terminate


_DIAGNOSTIC_LINE_LIMIT = 80
_DIAGNOSTIC_CHAR_LIMIT = 12_000


class _DiagnosticTail:
    """Drain child output continuously while retaining only a bounded tail."""

    def __init__(self):
        self._lines = deque(maxlen=_DIAGNOSTIC_LINE_LIMIT)
        self._lock = threading.Lock()

    def append(self, line):
        with self._lock:
            self._lines.append(line.rstrip())

    def text(self):
        with self._lock:
            value = "\n".join(self._lines)
        return value[-_DIAGNOSTIC_CHAR_LIMIT:]


def _capture_output(stream, tail):
    try:
        for line in iter(stream.readline, ""):
            tail.append(line)
    finally:
        stream.close()


def _failure(message, tail):
    diagnostics = tail.text()
    if diagnostics:
        return RuntimeError(f"{message}\nllama-server diagnostics (tail):\n{diagnostics}")
    return RuntimeError(message)


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
    tail = _DiagnosticTail()
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=os.name != "nt",
        creationflags=creationflags,
    )
    capture_thread = threading.Thread(
        target=_capture_output,
        args=(process.stdout, tail),
        name="llama-smoke-diagnostics",
        daemon=True,
    )
    capture_thread.start()
    base = f"http://127.0.0.1:{args.port}"
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise _failure(f"llama-server exited with code {process.returncode}", tail)
            try:
                status, _ = _request(base + "/health", timeout=1)
                if 200 <= status < 300:
                    break
            except (OSError, urllib.error.URLError):
                time.sleep(0.25)
        else:
            raise _failure("llama-server health timeout", tail)
        try:
            status, body = _request(
                base + "/v1/chat/completions",
                {"model": "smoke", "messages": [{"role": "user", "content": "Reply with exactly OK."}], "max_tokens": 8},
                timeout=30,
            )
        except (OSError, urllib.error.URLError) as exc:
            raise _failure(f"chat completion request failed: {exc}", tail) from exc
        if not 200 <= status < 300:
            raise _failure(f"chat completion returned HTTP {status}: {body[:300]}", tail)
        print("VERIFIED: /health and /v1/chat/completions succeeded")
        return 0
    finally:
        if process.poll() is None:
            _terminate(process.pid, state={"pid": process.pid, "engine": command[0], "command": command})
        capture_thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
