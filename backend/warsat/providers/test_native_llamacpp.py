import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from backend.core.response import AppError
from backend.warsat.providers.native_llamacpp import NativeLlamaCppProvider, NATIVE_RUNTIME
from tests.native_llamacpp_smoke import _DIAGNOSTIC_CHAR_LIMIT, _DiagnosticTail, _failure, check_prerequisites


class NativeLlamaCppProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_data_dir = os.environ.get("RASPUTIN_DATA_DIR")
        os.environ["RASPUTIN_DATA_DIR"] = self.temp_dir.name
        self.model_path = Path(self.temp_dir.name) / "demo.gguf"
        self.model_path.write_bytes(b"not-a-real-gguf")
        self.model = {
            "key": "demo",
            "runtime": NATIVE_RUNTIME,
            "host_model_path": str(self.model_path),
            "base_url": "http://127.0.0.1:18081/v1",
            "port": 18081,
            "context": 4096,
            "context_auto": True,
            "n_gpu_layers": 99,
            "split_mode": "tensor",
            "tensor_split": "1,0.75",
            "size_mb": 2000,
            "hardware_snapshot": {
                "devices": [
                    {"id": "0", "free_mb": 9000, "compute_capability": "8.6"},
                    {"id": "1", "free_mb": 9000, "compute_capability": "8.6"},
                ],
                "safety_margin_mb": 0,
            },
            "runtime_capabilities": {
                "flags": {"--split-mode": True, "--tensor-split": True},
            },
        }
        self.provider = NativeLlamaCppProvider()

    def tearDown(self):
        if self.previous_data_dir is None:
            os.environ.pop("RASPUTIN_DATA_DIR", None)
        else:
            os.environ["RASPUTIN_DATA_DIR"] = self.previous_data_dir
        self.temp_dir.cleanup()

    def test_command_is_native_and_preserves_llama_controls(self):
        command = self.provider._command(self.model, "llama-server.exe")
        self.assertEqual(command[0], "llama-server.exe")
        self.assertIn("--host", command)
        self.assertIn("127.0.0.1", command)
        self.assertIn("--fit", command)
        self.assertIn("--split-mode", command)
        self.assertIn("--tensor-split", command)
        self.assertNotIn("docker", " ".join(command).lower())

    def test_automatic_plan_prefers_fitting_single_gpu_and_accepts_injected_snapshots(self):
        model = {
            **self.model,
            "load_profile": {"context_length": 4096},
            "model_memory": {"gpu_memory_mb": 6000},
        }
        model.pop("hardware_snapshot")
        model.pop("runtime_capabilities")
        model.pop("split_mode")
        model.pop("tensor_split")
        model.pop("n_gpu_layers")
        provider = NativeLlamaCppProvider(
            hardware_snapshot_provider=lambda _model: {
                "devices": [
                    {"id": "0", "free_mb": 5000},
                    {"id": "1", "free_mb": 9000},
                ],
                "safety_margin_mb": 0,
            },
            runtime_capabilities_provider=lambda _model: {},
        )
        command = provider._command(model, "llama-server.exe")
        plan = provider._load_plan(model, engine="llama-server.exe")
        assert plan.resolved_settings["split_mode"] == "none"
        assert [item["device_id"] for item in plan.device_allocation] == ["1"]
        assert "--host" in command and "--port" in command

    def test_explicit_advanced_profile_maps_kv_cache_and_runtime_controls(self):
        model = {
            **self.model,
            "load_profile": {
                "context_length": 2048,
                "gpu_layers": 24,
                "fit": "off",
                "split_mode": "layer",
                "kv_offload": False,
                "cache_type_k": "q8_0",
                "cache_type_v": "q4_0",
                "flash_attention": True,
                "batch_size": 512,
                "ubatch_size": 128,
                "parallel_slots": 2,
                "threads": 8,
                "threads_batch": 4,
            },
        }
        command = self.provider._command(model, "llama-server.exe")
        for flag, value in (
            ("--ctx-size", "2048"),
            ("--gpu-layers", "24"),
            ("--no-kv-offload", "true"),
            ("--cache-type-k", "q8_0"),
            ("--cache-type-v", "q4_0"),
            ("--flash-attn", "on"),
            ("--batch-size", "512"),
            ("--ubatch-size", "128"),
            ("--parallel", "2"),
            ("--threads", "8"),
            ("--threads-batch", "4"),
        ):
            assert command[command.index(flag) + 1] == value

    def test_unequal_gpu_tensor_split_is_blocked_before_spawn(self):
        blocked = {
            **self.model,
            "load_profile": {"split_mode": "tensor", "tensor_split": "1,1"},
            "hardware_snapshot": {
                "devices": [
                    {"id": "0", "free_mb": 9000, "compute_capability": "8.6"},
                    {"id": "1", "free_mb": 12000, "compute_capability": "8.9"},
                ],
                "safety_margin_mb": 0,
            },
        }
        with patch("backend.warsat.providers.native_llamacpp._find_engine") as find_engine,              patch("backend.warsat.providers.native_llamacpp.subprocess.Popen") as popen:
            result = self.provider.start(blocked)
        assert result["status"] == "blocked"
        assert result["blockReasons"]
        assert any("unequal GPUs" in reason for reason in result["blockReasons"])
        find_engine.assert_not_called()
        popen.assert_not_called()

    def test_unconfirmed_runtime_capability_blocks_experimental_split(self):
        blocked = {
            **self.model,
            "load_profile": {"split_mode": "tensor", "tensor_split": "1,1"},
            "runtime_capabilities": {},
        }
        result = self.provider.start(blocked)
        assert result["status"] == "blocked"
        assert any("capability" in reason for reason in result["blockReasons"])

    def test_success_persists_resolved_plan_and_complete_command(self):
        process = Mock()
        process.pid = 4242
        process.poll.return_value = None
        with patch("backend.warsat.providers.native_llamacpp._find_engine", return_value="llama-server.exe"),              patch("backend.warsat.providers.native_llamacpp.subprocess.Popen", return_value=process),              patch("backend.warsat.providers.native_llamacpp._health", return_value=True), patch("backend.warsat.providers.native_llamacpp._warm_up", return_value={"status": "complete", "seconds": 1}):
            result = self.provider.start(self.model)
        state = json.loads((Path(os.environ["RASPUTIN_DATA_DIR"]) / "llama.cpp" / "demo.json").read_text(encoding="utf-8"))
        assert result["ok"]
        assert result["resolvedPlan"]["command"] == result["command"]
        assert state["resolvedPlan"] == result["resolvedPlan"]
        assert "--host" in state["command"] and "127.0.0.1" in state["command"]
        self.provider.stop(self.model)

    def test_warmup_is_bounded_synthetic_and_uses_owned_loopback_port(self):
        from backend.warsat.providers import native_llamacpp as native
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{"tokens_predicted": 2}'
        with patch.object(native.urllib.request, "urlopen", return_value=response) as request:
            result = native._warm_up({**self.model, "base_url": "https://untrusted.invalid/v1"})
        self.assertEqual(result["status"], "complete")
        req = request.call_args.args[0]
        self.assertEqual(req.full_url, "http://127.0.0.1:18081/completion")
        payload = json.loads(req.data)
        self.assertEqual(payload["n_predict"], 2)
        self.assertTrue(payload["ignore_eos"])
        self.assertFalse(payload["cache_prompt"])
        self.assertLessEqual(len(payload["prompt"].split()), 256)
        self.assertEqual(request.call_args.kwargs["timeout"], 120)

    def test_healthy_process_is_not_ready_until_warmup_completes(self):
        from backend.warsat.providers import native_llamacpp as native
        for stage, expected in (("loading", "starting"), ("warming", "starting"), ("ready", "running")):
            with self.subTest(stage=stage), patch.object(native, "_read_state", return_value={"startupStage": stage}), patch.object(native, "_owned_process", return_value=Mock()), patch.object(native, "_health", return_value=True):
                self.assertEqual(self.provider.status(self.model), expected)

    def test_failed_warmup_does_not_report_ready_and_stops_new_process(self):
        from backend.warsat.providers import native_llamacpp as native
        process = Mock(pid=4242)
        process.poll.return_value = None
        with patch.object(native, "_find_engine", return_value="llama-server.exe"), patch.object(native.subprocess, "Popen", return_value=process), patch.object(native, "_health", return_value=True), patch.object(native, "_warm_up", side_effect=TimeoutError("warm-up timeout")), patch.object(self.provider, "stop", return_value={"ok": True}) as stop:
            result = self.provider.start(self.model)
        self.assertFalse(result["ok"])
        self.assertEqual(result["failureCode"], "warmup_failed")
        self.assertEqual(stop.call_count, 2)

    def test_managed_runtime_path_is_used_before_path_fallback(self):
        managed = Path(self.temp_dir.name) / "managed-llama-server.exe"
        managed.write_bytes(b"runtime")
        with patch("backend.warsat.providers.native_llamacpp.LlamaCppRuntimeService") as runtime_service,                 patch("backend.warsat.providers.native_llamacpp.shutil.which", return_value=None):
            runtime_service.return_value.active_engine_path.return_value = str(managed)
            from backend.warsat.providers.native_llamacpp import _find_engine
            self.assertEqual(_find_engine({}), str(managed.resolve()))

    def test_missing_engine_is_reported_without_docker(self):
        previous = os.environ.pop("RASPUTIN_LLAMA_SERVER", None)
        try:
            with patch("backend.warsat.providers.native_llamacpp._find_engine", return_value=""):
                result = self.provider.start({**self.model, "engine_path": "definitely-not-a-real-llama-server"})
        finally:
            if previous is not None:
                os.environ["RASPUTIN_LLAMA_SERVER"] = previous
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("llama-server", result["error"])

    def test_runtime_download_failure_is_actionable(self):
        with patch(
            "backend.warsat.providers.native_llamacpp._find_engine",
            side_effect=AppError("runtime_download_failed", "Could not acquire selected runtime."),
        ):
            result = self.provider.start(self.model)

        self.assertFalse(result["ok"])
        self.assertEqual(result["failureCode"], "runtime_download_failed")
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("internet connection", result["recoveryGuidance"])

    def test_mmproj_from_registered_artifact_is_an_exact_command_argument(self):
        mmproj = Path(self.temp_dir.name) / "mmproj-demo-f16.gguf"
        mmproj.write_bytes(b"projection")
        model = {**self.model, "artifact": {"mmprojFiles": [{"localPath": str(mmproj)}]}}
        command = self.provider._command(model, "llama-server.exe")
        self.assertEqual(command[command.index("--mmproj") + 1], str(mmproj.resolve()))
        self.assertNotIn("docker", " ".join(command).lower())

    def test_health_timeout_forces_recovery_and_removes_state(self):
        process = Mock(pid=4243)
        process.poll.return_value = None
        with patch("backend.warsat.providers.native_llamacpp._find_engine", return_value="llama-server.exe"), \
             patch("backend.warsat.providers.native_llamacpp.subprocess.Popen", return_value=process), \
             patch("backend.warsat.providers.native_llamacpp._health", return_value=False), \
             patch("backend.warsat.providers.native_llamacpp._START_TIMEOUT", 0.01), \
             patch("backend.warsat.providers.native_llamacpp._terminate") as terminate:
            result = self.provider.start(self.model)
        self.assertFalse(result["ok"])
        self.assertEqual(result["failureCode"], "health_timeout")
        self.assertEqual(terminate.call_args.args, (4243,))
        self.assertEqual(terminate.call_args.kwargs["state"]["pid"], 4243)
        self.assertFalse((Path(os.environ["RASPUTIN_DATA_DIR"]) / "llama.cpp" / "demo.json").exists())

    def test_crash_and_log_text_have_stable_failure_codes(self):
        process = Mock(pid=4244)
        process.poll.return_value = 7
        with patch("backend.warsat.providers.native_llamacpp._find_engine", return_value="llama-server.exe"), \
             patch("backend.warsat.providers.native_llamacpp.subprocess.Popen", return_value=process), \
             patch("backend.warsat.providers.native_llamacpp._health", return_value=False), \
             patch("backend.warsat.providers.native_llamacpp._terminate"):
            result = self.provider.start(self.model)
        self.assertFalse(result["ok"])
        self.assertEqual(result["failureCode"], "process_crash")
        self.assertTrue(result["recoveryGuidance"])

    def test_failure_mapping_covers_runtime_errors(self):
        from backend.warsat.providers.native_llamacpp import _failure_from_text
        self.assertEqual(_failure_from_text("unknown argument --mmproj")["failureCode"], "unsupported_flag")
        self.assertEqual(_failure_from_text("CUDA out of memory")["failureCode"], "load_oom")
        self.assertEqual(_failure_from_text("invalid GGUF magic")["failureCode"], "model_corrupt")

    def test_smoke_failure_includes_bounded_child_diagnostics(self):
        tail = _DiagnosticTail()
        for index in range(200):
            tail.append(f"diagnostic-{index} " + ("x" * 200))
        error = _failure("llama-server health timeout", tail)
        message = str(error)
        self.assertIn("llama-server health timeout", message)
        self.assertIn("llama-server diagnostics (tail):", message)
        self.assertIn("diagnostic-199", message)
        self.assertNotIn("diagnostic-0", message)
        self.assertLessEqual(len(message.split("llama-server diagnostics (tail):\n", 1)[1]), _DIAGNOSTIC_CHAR_LIMIT)

    def test_live_smoke_prerequisite_detection_skips_without_runtime_or_model(self):
        with patch.dict(os.environ, {}, clear=True):
            ready, reason = check_prerequisites(None)
        self.assertFalse(ready)
        self.assertIn("RASPUTIN_LLAMA_SERVER", reason)

    def test_reused_pid_is_never_adopted_or_stopped(self):
        from backend.warsat.providers import native_llamacpp as native
        state = {"pid": 4242, "processCreatedAt": 10.0, "engine": "llama-server.exe", "command": ["llama-server.exe", "--model", "demo.gguf"]}
        native._write_state(self.model, state)
        process = Mock()
        process.create_time.return_value = 20.0
        with patch.object(native.psutil, "Process", return_value=process), patch.object(native, "_health") as health:
            self.assertEqual(self.provider.status(self.model), "stopped")
            native._write_state(self.model, state)
            self.assertTrue(self.provider.stop(self.model)["ok"])
        process.terminate.assert_not_called()
        process.kill.assert_not_called()
        health.assert_not_called()

    def test_matching_pid_with_different_command_is_not_owned(self):
        from backend.warsat.providers import native_llamacpp as native
        process = Mock()
        process.cmdline.return_value = ["unrelated.exe"]
        with patch.object(native.psutil, "Process", return_value=process):
            self.assertIsNone(native._owned_process({"pid": 4242, "command": ["llama-server.exe"]}))

    def test_stop_terminates_only_matching_owned_process(self):
        from backend.warsat.providers import native_llamacpp as native
        process = Mock()
        process.create_time.return_value = 10.0
        process.cmdline.return_value = ["llama-server.exe", "--model", "demo.gguf"]
        process.exe.return_value = "llama-server.exe"
        process.children.return_value = []
        state = {"pid": 4242, "processCreatedAt": 10.0, "engine": "llama-server.exe", "command": process.cmdline.return_value}
        native._write_state(self.model, state)
        with patch.object(native.psutil, "Process", return_value=process), patch.object(native.psutil, "wait_procs", return_value=([], [])):
            self.assertTrue(self.provider.stop(self.model)["ok"])
        process.terminate.assert_called_once_with()
        process.kill.assert_not_called()

    def test_failed_stop_retains_state_for_retry(self):
        from backend.warsat.providers import native_llamacpp as native
        native._write_state(self.model, {"pid": 4242})
        with patch.object(native, "_terminate", side_effect=OSError("still running")):
            result = self.provider.stop(self.model)
        self.assertFalse(result["ok"])
        self.assertEqual(result["failureCode"], "stop_failed")
        self.assertEqual(native._read_state(self.model)["pid"], 4242)

    def test_occupied_port_is_blocked_before_spawn(self):
        from backend.warsat.providers import native_llamacpp as native
        with patch.object(native, "_find_engine", return_value="llama-server.exe"), patch.object(native, "_port_available", return_value=False), patch.object(native.subprocess, "Popen") as spawn:
            result = self.provider.start(self.model)
        self.assertEqual(result["failureCode"], "port_in_use")
        spawn.assert_not_called()

    def test_exited_child_cannot_borrow_another_healthy_endpoint(self):
        from backend.warsat.providers import native_llamacpp as native
        process = Mock(pid=4244)
        process.poll.return_value = 7
        with patch.object(native, "_find_engine", return_value="llama-server.exe"), patch.object(native.subprocess, "Popen", return_value=process), patch.object(native, "_health", return_value=True) as health:
            result = self.provider.start(self.model)
        self.assertFalse(result["ok"])
        self.assertEqual(result["failureCode"], "process_crash")
        health.assert_not_called()

    def test_native_capability_probe_is_cached_and_exact(self):
        from backend.warsat.providers import native_llamacpp as native
        native._engine_capabilities.cache_clear()
        output = Mock(returncode=0, stdout="--split-mode {none,layer,row} --tensor-split N --fit-target N", stderr="")
        with patch.object(native.subprocess, "run", return_value=output) as run:
            first = native._engine_capabilities("test-engine", 123)
            second = native._engine_capabilities("test-engine", 123)
        self.assertEqual(first, second)
        self.assertTrue(first["flags"]["--split-mode"])
        self.assertFalse(first["flags"]["--fit"])
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], ["test-engine", "--help"])
        native._engine_capabilities.cache_clear()

    def test_initial_status_is_stopped(self):
        self.assertEqual(self.provider.status(self.model), "stopped")


if __name__ == "__main__":
    unittest.main()
