"""Acquire the pinned execution runtime into app-owned storage, without a host install."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import tempfile
import threading
import time
import urllib.request
import uuid

from backend.core import audit, security
from backend.core.datadir import data_dir

_lock = threading.RLock()
_thread = None
_cancel = threading.Event()
_state = {"state": "idle", "downloaded_bytes": 0}
_MAX_ASSET_BYTES = 150 * 1024 * 1024
_MANIFEST = Path(__file__).resolve().parents[2] / "runtime" / "execution" / "manifest.json"


class InstallCancelled(RuntimeError):
    pass


def selected_runtime():
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    version = manifest.get("version", "")
    if not re.fullmatch(r"v\d+\.\d+\.\d+", version) or manifest.get("engine") != "node":
        raise ValueError("Invalid pinned execution runtime manifest.")
    machine = (os.environ.get("PROCESSOR_ARCHITEW6432") or platform.machine()).lower()
    architecture = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(machine)
    runtime = next((item for item in manifest["runtimes"] if item["architecture"] == architecture), None)
    if os.name != "nt" or not runtime:
        raise ValueError("The execution runtime requires 64-bit Windows on x64 or ARM64 hardware.")
    if runtime.get("id") != f"node-{version}-windows-{architecture}":
        raise ValueError("Execution runtime identity does not match its architecture.")
    assets = runtime.get("assets", [])
    if len(assets) != 2 or {item.get("name") for item in assets} != {"node.exe", "LICENSE"}:
        raise ValueError("The execution runtime must include its executable and license.")
    for asset in assets:
        expected_url = (f"https://nodejs.org/dist/{version}/win-{architecture}/node.exe" if asset["name"] == "node.exe"
                        else f"https://raw.githubusercontent.com/nodejs/node/{version}/LICENSE")
        if (asset.get("url") != expected_url or not re.fullmatch(r"[0-9a-f]{64}", asset.get("sha256", ""))
                or type(asset.get("size_bytes")) is not int or not 0 < asset["size_bytes"] <= _MAX_ASSET_BYTES):
            raise ValueError("Execution runtime asset is not pinned to an approved source, size, and hash.")
    return {**runtime, "version": version}


def _folder(runtime):
    return data_dir() / "runtimes" / "execution" / runtime["id"]


def _ordinary(path):
    return path.is_file() and not (path.lstat().st_file_attributes & 0x400)


def _verified(folder, runtime):
    for asset in runtime["assets"]:
        path = folder / asset["name"]
        if not _ordinary(path) or path.stat().st_size != asset["size_bytes"]:
            return False
        with path.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != asset["sha256"]:
                return False
    return True


def status():
    with _lock:
        current = dict(_state)
    try:
        runtime = selected_runtime()
        folder = _folder(runtime)
        # Status checks current bytes, and each execution independently verifies
        # its copied executable. Neither result is an execution authorization.
        present = _verified(folder, runtime)
        policy = security.load()
        current.update(supported=True, version=runtime["version"], architecture=runtime["architecture"],
                       runtime_id=runtime["id"], total_bytes=sum(asset["size_bytes"] for asset in runtime["assets"]),
                       installed=present, offline=bool(policy.get("offline_lock")), execution_enabled=bool(policy.get("allow_shell_execution")),
                       source="nodejs.org", license="MIT and bundled third-party licenses")
    except (OSError, ValueError, KeyError, TypeError):
        current.update(supported=False, installed=False, message="The pinned runtime is unavailable for this system.")
    return current


class _PinnedRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        # Assets are pinned to direct official URLs. Do not forward credentials or
        # silently acquire executable bytes from a different redirect destination.
        raise ValueError("Runtime asset redirects are not permitted.")


def _download(asset, destination, cancel, progress):
    opener = urllib.request.build_opener(_PinnedRedirects())
    request = urllib.request.Request(asset["url"], headers={"User-Agent": "Rasputin-Runtime/1"})
    digest, received = hashlib.sha256(), 0
    deadline = time.monotonic() + 180
    with opener.open(request, timeout=20) as response, destination.open("xb") as output:
        if response.geturl() != asset["url"]:
            raise ValueError("Runtime asset source changed.")
        declared = response.headers.get("Content-Length")
        if declared is not None and int(declared) != asset["size_bytes"]:
            raise ValueError("Runtime asset size does not match its pin.")
        while True:
            if cancel.is_set():
                raise InstallCancelled()
            if time.monotonic() > deadline:
                raise TimeoutError("Runtime download exceeded its time limit.")
            chunk = response.read(min(1024 * 1024, asset["size_bytes"] - received + 1))
            if not chunk:
                break
            received += len(chunk)
            if received > asset["size_bytes"]:
                raise ValueError("Runtime asset exceeded its pinned size.")
            digest.update(chunk)
            output.write(chunk)
            progress(len(chunk))
        output.flush()
        os.fsync(output.fileno())
    if received != asset["size_bytes"] or digest.hexdigest() != asset["sha256"]:
        raise ValueError("Runtime asset failed integrity verification.")


def _safe_folder(path):
    storage = data_dir().resolve()
    if not path.resolve().is_relative_to(storage):
        raise ValueError("Managed runtime storage escaped application data.")
    for ancestor in [path, *path.parents]:
        if ancestor.exists() and ancestor.lstat().st_file_attributes & 0x400:
            raise ValueError("Managed runtime storage cannot traverse reparse points.")
        if ancestor == storage:
            break


def install(username, *, cancel=None, downloader=None):
    """Worker entry point; downloaded runtime code is never executed on the host."""
    from backend.core import sandbox_execution as execution

    if execution._actor(username)["role"] != "admin":
        raise PermissionError("Administrator access is required to acquire the runtime.")
    cancel = cancel if cancel is not None else threading.Event()
    runtime = selected_runtime()
    target = _folder(runtime)
    _safe_folder(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not _verified(target, runtime):
        if security.load().get("offline_lock"):
            raise PermissionError("Offline mode blocks runtime downloads. Connect and disable offline mode, then retry.")
        with tempfile.TemporaryDirectory(prefix=".acquire-", dir=target.parent) as temporary:
            staging = Path(temporary)
            assert staging.resolve().is_relative_to(target.parent.resolve())
            def progress(count):
                with _lock:
                    _state["downloaded_bytes"] = _state.get("downloaded_bytes", 0) + count
            for asset in runtime["assets"]:
                if cancel.is_set():
                    raise InstallCancelled()
                (downloader or _download)(asset, staging / asset["name"], cancel, progress)
            # Verify staged files even when a test/alternate transport supplied them.
            if not _verified(staging, runtime):
                raise ValueError("Downloaded runtime failed verification.")
            if cancel.is_set():
                raise InstallCancelled()
            _safe_folder(target)
            target.mkdir(exist_ok=True)
            for asset in runtime["assets"]:
                path = target / asset["name"]
                if path.exists() and not _ordinary(path):
                    raise ValueError("Runtime publication cannot replace a redirected file.")
                os.replace(staging / asset["name"], path)
    if cancel.is_set():
        raise InstallCancelled()
    expected = next(asset["sha256"] for asset in runtime["assets"] if asset["name"] == "node.exe")
    pinned = execution.configure_toolchain(str(target / "node.exe"), username,
                managed_identity={"runtime_id": runtime["id"], "version": runtime["version"], "sha256": expected})
    audit.log("sandbox_runtime_acquired", {"runtime_id": runtime["id"], "sha256": pinned["sha256"]})
    return runtime


def _worker(username):
    try:
        install(username, cancel=_cancel)
        result = {"state": "ready", "message": "Execution runtime is installed and verified."}
    except InstallCancelled:
        result = {"state": "cancelled", "message": "Runtime setup was cancelled. Retry when ready."}
    except Exception as exc:
        # Never retain upstream exception text, environment, or private paths.
        result = {"state": "error", "message": f"Runtime setup failed ({type(exc).__name__}). Check connectivity and retry."}
    with _lock:
        _state.update(result)


def start(username):
    from backend.core.sandbox_execution import _actor
    if _actor(username)["role"] != "admin":
        raise PermissionError("Administrator access is required to acquire the runtime.")
    global _thread
    with _lock:
        if _thread and _thread.is_alive():
            return status()
        selected_runtime()  # unsupported systems fail before starting a job
        _cancel.clear()
        _state.clear()
        _state.update(state="installing", downloaded_bytes=0, job_id=uuid.uuid4().hex)
        _thread = threading.Thread(target=_worker, args=(username,), name="sandbox-runtime-install", daemon=True)
        _thread.start()
        return status()


def cancel(username):
    from backend.core.sandbox_execution import _actor
    if _actor(username)["role"] != "admin":
        raise PermissionError("Administrator access is required to cancel runtime setup.")
    with _lock:
        if _thread and _thread.is_alive() and _state.get("state") == "installing":
            _cancel.set()
            _state.update(state="stopping", message="Stopping runtime setup…")
    return status()


def shutdown():
    _cancel.set()
