"""Deterministic native llama.cpp HTTP/process contract coverage.

The child is a test-only Python fixture, not llama.cpp and not inference
proof. No GGUF is created, opened, downloaded, or loaded by this test.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from backend.warsat.providers.native_llamacpp import _terminate


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "fake_llama_server.py"


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _request(url: str, payload=None, timeout: float = 1.0):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


class NativeLlamaCppHttpContractTests(unittest.TestCase):
    def test_fixture_health_chat_and_process_cleanup(self):
        port = _free_loopback_port()
        process = None
        with tempfile.TemporaryDirectory() as temp_dir:
            command = [
                sys.executable,
                "-u",
                str(FIXTURE),
                "--model",
                str(Path(temp_dir) / "not-loaded.gguf"),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ]
            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
                    subprocess, "CREATE_NEW_PROCESS_GROUP", 0
                )
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=os.name != "nt",
                creationflags=creationflags,
            )
            base = f"http://127.0.0.1:{port}"
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        self.fail(f"fixture exited with code {process.returncode}")
                    try:
                        status, body = _request(base + "/health")
                        if 200 <= status < 300:
                            self.assertEqual(body["status"], "ok")
                            break
                    except (OSError, urllib.error.URLError):
                        time.sleep(0.05)
                else:
                    self.fail("fixture health timeout")

                status, body = _request(
                    base + "/v1/chat/completions",
                    {"model": "test-only", "messages": [{"role": "user", "content": "hello"}]},
                )
                self.assertEqual(status, 200)
                self.assertEqual(body["choices"][0]["message"]["content"], "OK")
            finally:
                if process.poll() is None:
                    _terminate(process.pid)
                process.wait(timeout=5)

            self.assertIsNotNone(process.poll())
            with self.assertRaises((OSError, urllib.error.URLError, TimeoutError)):
                _request(base + "/health", timeout=0.5)


if __name__ == "__main__":
    unittest.main()
