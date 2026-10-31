"""Managed runtime acquisition; real official download is explicitly opt-in."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid

os.environ.setdefault("RASPUTIN_DATA_DIR", tempfile.mkdtemp(prefix="rasputin-runtime-tests-"))

from backend.core import auth, runtime_store as store, security, sandbox_execution as execution
from backend.core import sandbox_runtime as runtime
from backend.core.datadir import data_dir


@unittest.skipUnless(os.name == "nt", "Windows runtime acquisition")
class SandboxRuntimeTests(unittest.TestCase):
    def setUp(self):
        with contextlib.redirect_stdout(io.StringIO()):
            auth.bootstrap()
        self.owner = auth.list_users()[0]["username"]
        self.member = "rt" + uuid.uuid4().hex[:12]
        auth.create_user(self.member, uuid.uuid4().hex, role="member")
        security.save({"offline_lock": False})
        store.set_kv(execution._RUNTIME_KEY, None)
        self.payloads = {"node.exe": b"MZ-test-fixture-not-executed", "LICENSE": b"fixture license"}
        self.fixture = {"id": "node-fixture-" + uuid.uuid4().hex, "version": "v26.13.0", "architecture": "x64",
                        "assets": [{"name": name, "url": "https://nodejs.org/fixture/" + name,
                                    "sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content)}
                                   for name, content in self.payloads.items()]}
        with runtime._lock:
            runtime._state.clear()
            runtime._state.update(state="idle", downloaded_bytes=0)

    def transport(self, asset, destination, cancel, progress):
        destination.write_bytes(self.payloads[asset["name"]])
        progress(asset["size_bytes"])

    def test_install_verifies_both_assets_pins_identity_and_reuses_verified_cache_offline(self):
        with patch.object(runtime, "selected_runtime", return_value=self.fixture):
            runtime.install(self.owner, downloader=self.transport)
            config = store.get_kv(execution._RUNTIME_KEY)
            self.assertTrue(config["managed"])
            self.assertEqual(self.fixture["id"], config["runtime_id"])
            self.assertEqual(self.fixture["assets"][0]["sha256"], config["sha256"])
            self.assertTrue(runtime.status()["installed"])
            executable = Path(config["path"])
            original = executable.read_bytes()
            executable.write_bytes(b"x" * len(original))
            self.assertFalse(runtime.status()["installed"], "Size alone must not establish runtime integrity")
            executable.write_bytes(original)
            security.save({"offline_lock": True})
            with patch.object(runtime, "_download", side_effect=AssertionError("cache reuse attempted network")):
                runtime.install(self.owner)

    def test_cancelled_failed_and_corrupt_downloads_do_not_publish_or_pin(self):
        for kind in ("cancel", "failure", "corrupt"):
            with self.subTest(kind=kind), patch.object(runtime, "selected_runtime", return_value=self.fixture):
                cancel = threading.Event()
                def transport(asset, destination, signal, progress):
                    if kind == "failure":
                        destination.write_bytes(b"partial")
                        raise OSError("fixture private details must not escape")
                    self.transport(asset, destination, signal, progress)
                    if kind == "cancel":
                        signal.set()
                    if kind == "corrupt":
                        destination.write_bytes(b"wrong hash")
                with self.assertRaises((runtime.InstallCancelled, OSError, ValueError)):
                    runtime.install(self.owner, cancel=cancel, downloader=transport)
                self.assertFalse(store.get_kv(execution._RUNTIME_KEY))
                self.assertFalse(runtime._folder(self.fixture).exists())
                self.assertEqual([], list(runtime._folder(self.fixture).parent.glob(".acquire-*")))

    def test_offline_and_member_requests_are_refused_before_downloading(self):
        with patch.object(runtime, "selected_runtime", return_value=self.fixture), \
             patch.object(runtime, "_download") as download:
            with self.assertRaises(PermissionError):
                runtime.install(self.member)
            security.save({"offline_lock": True})
            with self.assertRaises(PermissionError):
                runtime.install(self.owner)
            download.assert_not_called()

    def test_existing_corrupt_files_are_repaired_without_removing_unknown_files(self):
        target = runtime._folder(self.fixture)
        target.mkdir(parents=True)
        (target / "node.exe").write_bytes(b"damaged")
        (target / "keep.txt").write_text("keep", encoding="utf-8")
        with patch.object(runtime, "selected_runtime", return_value=self.fixture):
            runtime.install(self.owner, downloader=self.transport)
            self.assertTrue(runtime._verified(target, self.fixture))
        self.assertEqual("keep", (target / "keep.txt").read_text(encoding="utf-8"))

    def test_redirected_runtime_folder_is_never_modified(self):
        target = runtime._folder(self.fixture)
        target.parent.mkdir(parents=True, exist_ok=True)
        unrelated = data_dir() / ("unrelated-" + uuid.uuid4().hex)
        unrelated.mkdir()
        sentinel = unrelated / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        subprocess.run([str(Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe"), "/d", "/c", "mklink", "/J", str(target), str(unrelated)],
                       check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            with patch.object(runtime, "selected_runtime", return_value=self.fixture), self.assertRaises(ValueError):
                runtime.install(self.owner, downloader=self.transport)
            self.assertEqual("keep", sentinel.read_text(encoding="utf-8"))
        finally:
            target.rmdir()

    def test_background_job_is_reused_and_cancellation_is_observable(self):
        started = threading.Event()
        def install(username, cancel):
            started.set()
            if cancel.wait(5):
                raise runtime.InstallCancelled()
            raise AssertionError("cancellation was not delivered")
        with patch.object(runtime, "selected_runtime", return_value=self.fixture), patch.object(runtime, "install", side_effect=install):
            first = runtime.start(self.owner)
            self.assertTrue(started.wait(2))
            self.assertEqual(first["job_id"], runtime.start(self.owner)["job_id"])
            with self.assertRaises(PermissionError):
                runtime.cancel(self.member)
            runtime.cancel(self.owner)
            runtime._thread.join(timeout=5)
            self.assertFalse(runtime._thread.is_alive())
            self.assertEqual("cancelled", runtime.status()["state"])
            # The worker can set its terminal state just before its thread exits.
            # A last-moment cancel must not turn that state into perpetual stopping.
            with patch.object(runtime._thread, "is_alive", return_value=True):
                for terminal in ("ready", "error", "cancelled"):
                    runtime._state["state"] = terminal
                    self.assertEqual(terminal, runtime.cancel(self.owner)["state"])

    def test_manifest_selection_and_source_hash_size_validation(self):
        manifest = json.loads(runtime._MANIFEST.read_text(encoding="utf-8"))
        with patch.dict(os.environ, {"PROCESSOR_ARCHITEW6432": ""}), patch.object(runtime.platform, "machine", return_value="AMD64"):
            self.assertEqual("x64", runtime.selected_runtime()["architecture"])
            with patch.dict(os.environ, {"PROCESSOR_ARCHITEW6432": "ARM64"}):
                self.assertEqual("arm64", runtime.selected_runtime()["architecture"])
            for key, value in (("url", "https://untrusted.invalid/node.exe"), ("sha256", "bad"), ("size_bytes", 0)):
                bad = json.loads(json.dumps(manifest))
                bad["runtimes"][0]["assets"][0][key] = value
                with patch.object(runtime.json, "loads", return_value=bad), self.assertRaises(ValueError):
                    runtime.selected_runtime()

    def test_downloader_is_bounded_and_never_attaches_model_tokens(self):
        asset = self.fixture["assets"][0]
        class Response(io.BytesIO):
            headers = {"Content-Length": str(asset["size_bytes"])}
            def geturl(self):
                return asset["url"]
        with tempfile.TemporaryDirectory(dir=data_dir()) as directory:
            target = Path(directory) / "download.exe"
            opener = unittest.mock.Mock()
            opener.open.return_value = Response(self.payloads["node.exe"])
            with patch.dict(os.environ, {"HF_TOKEN": "fixture-secret"}), patch.object(runtime.urllib.request, "build_opener", return_value=opener):
                runtime._download(asset, target, threading.Event(), lambda count: None)
            request = opener.open.call_args.args[0]
            self.assertNotIn("authorization", {name.lower() for name, value in request.header_items()})
            self.assertEqual(self.payloads["node.exe"], target.read_bytes())
            with self.assertRaises(ValueError):
                runtime._PinnedRedirects().redirect_request(request, None, 302, "redirect", {}, "https://untrusted.invalid")

    def test_api_runtime_setup_and_cancellation_require_an_administrator(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend.api.core import current_user
        app.dependency_overrides[current_user] = lambda: {"username": self.member, "role": "member"}
        try:
            client = TestClient(app, base_url="http://127.0.0.1:8899")
            with patch.object(runtime, "start") as start, patch.object(runtime, "cancel") as cancel:
                self.assertEqual(403, client.post("/api/execution/runtime/install").status_code)
                self.assertEqual(403, client.post("/api/execution/runtime/cancel").status_code)
                start.assert_not_called()
                cancel.assert_not_called()
        finally:
            app.dependency_overrides.pop(current_user, None)


@unittest.skipUnless(os.name == "nt" and os.environ.get("RASPUTIN_VERIFY_MANAGED_RUNTIME"), "Opt-in official runtime download and execution")
class ManagedRuntimeLiveTests(unittest.TestCase):
    def test_official_runtime_is_verified_then_executes_inside_appcontainer(self):
        from backend.core import windows_sandbox
        with contextlib.redirect_stdout(io.StringIO()):
            auth.bootstrap()
        owner = auth.list_users()[0]["username"]
        selected = runtime.install(owner)
        config = store.get_kv(execution._RUNTIME_KEY)
        scratch = data_dir() / "runtime-proof"
        scratch.mkdir(exist_ok=True)
        result = windows_sandbox.probe(config["path"], {}, ["-e", "console.log(process.version)"],
                                     scratch_parent=scratch, expected_executable_sha256=config["sha256"])
        self.assertTrue(result["ran"], result)
        self.assertEqual(0, result["exit_code"], result)
        self.assertEqual(selected["version"], result["output"].strip())
        self.assertTrue(runtime._verified(runtime._folder(selected), selected))


if __name__ == "__main__":
    unittest.main()
