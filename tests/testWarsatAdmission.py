import unittest
from unittest.mock import patch

from backend.assistant import runtime as assistant_runtime
from backend.core.response import AppError
from backend.models import resource_manifest
from backend import warsat
from backend.warsat import admission


def _profile(*sizes):
    return {
        "schemaVersion": 1,
        "devices": [
            {
                "deviceId": f"gpu:{index}",
                "static": {"index": index, "name": f"GPU {index}", "vendor": "nvidia", "memoryTotalMb": size},
                "volatile": {"memoryFreeMb": size},
            }
            for index, size in enumerate(sizes)
        ],
    }


class WarsatAdmissionIntegrationTests(unittest.TestCase):
    def test_model_download_progress_reports_partial_huggingface_bytes(self):
        container = "rasputin-qwen-8085"
        partial = "/root/.cache/huggingface/hub/models--demo--Qwen/blobs/weights.downloadInProgress"

        def fake_run(args, timeout=120, check=True):
            if args[:3] == ["docker", "inspect", "--format"]:
                return {"returnCode": 0, "stdout": '["--hf-repo", "demo/Qwen", "--hf-file", "weights.gguf"]', "stderr": ""}
            if args[:3] == ["docker", "exec", container]:
                return {"returnCode": 0, "stdout": f"400\t{partial}\n", "stderr": ""}
            raise AssertionError(f"unexpected docker command: {args}")

        with patch("backend.warsat._docker_runtime_enabled", return_value={"enabled": True, "dockerControlEnabled": True}), \
             patch("backend.warsat._managed_container", return_value=(container, {"rasputin.managed": "true"})), \
             patch("backend.warsat._run_command", side_effect=fake_run), \
             patch("backend.warsat._hf_file_size", return_value=1000):
            progress = warsat.download_progress(container)

        self.assertEqual(progress["status"], "downloading")
        self.assertEqual(progress["bytesDownloaded"], 400)
        self.assertEqual(progress["totalBytes"], 1000)
        self.assertEqual(progress["percent"], 40.0)
        self.assertEqual(progress["source"]["repo"], "demo/Qwen")

    def test_model_download_progress_distinguishes_no_active_partial_file(self):
        container = "rasputin-qwen-8085"

        def fake_run(args, timeout=120, check=True):
            if args[:3] == ["docker", "inspect", "--format"]:
                return {"returnCode": 0, "stdout": '["--hf-repo", "demo/Qwen", "--hf-file", "weights.gguf"]', "stderr": ""}
            if args[:3] == ["docker", "exec", container]:
                return {"returnCode": 0, "stdout": "", "stderr": ""}
            raise AssertionError(f"unexpected docker command: {args}")

        with patch("backend.warsat._docker_runtime_enabled", return_value={"enabled": True, "dockerControlEnabled": True}), \
             patch("backend.warsat._managed_container", return_value=(container, {"rasputin.managed": "true"})), \
             patch("backend.warsat._run_command", side_effect=fake_run):
            progress = warsat.download_progress(container)

        self.assertEqual(progress["status"], "not_downloading")
        self.assertIn("cached weights", progress["message"])

    def test_model_download_progress_withholds_inconsistent_percent(self):
        container = "rasputin-qwen-8085"
        partial = "/root/.cache/huggingface/hub/models--demo--Qwen/blobs/weights.downloadInProgress"

        def fake_run(args, timeout=120, check=True):
            if args[:3] == ["docker", "inspect", "--format"]:
                return {"returnCode": 0, "stdout": '["--hf-repo", "demo/Qwen", "--hf-file", "weights.gguf"]', "stderr": ""}
            if args[:3] == ["docker", "exec", container]:
                return {"returnCode": 0, "stdout": f"1200\t{partial}\n", "stderr": ""}
            raise AssertionError(f"unexpected docker command: {args}")

        with patch("backend.warsat._docker_runtime_enabled", return_value={"enabled": True, "dockerControlEnabled": True}), \
             patch("backend.warsat._managed_container", return_value=(container, {"rasputin.managed": "true"})), \
             patch("backend.warsat._run_command", side_effect=fake_run), \
             patch("backend.warsat._hf_file_size", return_value=1000):
            progress = warsat.download_progress(container)

        self.assertEqual(progress["status"], "downloading")
        self.assertIsNone(progress["percent"])

    def test_vllm_preview_blocks_model_that_exceeds_each_single_gpu(self):
        _manifest, decision, request = admission.plan_admission(
            model={
                "modelId": "demo/12b",
                "vramEstimateGb": 12,
                "recommendedProtocol": "vllmCudaOpenai",
                "runtimeOptions": [{"protocolId": "vllmCudaOpenai"}],
            },
            capability_profile=_profile(8192, 10240),
            runtime="vllm",
            protocol_id="vllmCudaOpenai",
        )
        self.assertEqual(request["requestedVramMb"], 12288)
        self.assertEqual(decision["status"], "blocked")
        self.assertIn("requested_vram_exceeds_observed_device_capacity", decision["reasons"])

    def test_combined_vram_requires_a_runtime_manifest_and_explicit_opt_in(self):
        vllm_manifest = resource_manifest.build_manifest({
            "modelId": "demo/20b",
            "vramEstimateGb": 20,
            "recommendedProtocol": "vllmCudaOpenai",
            "runtimeOptions": [{"protocolId": "vllmCudaOpenai"}],
        })
        _manifest, blocked, _request = admission.plan_admission(
            supplied_manifest=vllm_manifest,
            capability_profile=_profile(12288, 16384),
            runtime="vllm",
            protocol_id="vllmCudaOpenai",
            payload={"gpuDevice": "all"},
            explicit_combined=True,
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("combined_vram_requires_explicit_opt_in", blocked["reasons"])

        gguf_manifest = resource_manifest.build_manifest({
            "modelId": "demo-20b-q4.gguf",
            "vramEstimateGb": 20,
            "recommendedProtocol": "llamaCppGgufServer",
            "runtimeOptions": [{"protocolId": "llamaCppGgufServer"}],
        })
        _manifest, ready, _request = admission.plan_admission(
            supplied_manifest=gguf_manifest,
            capability_profile=_profile(12288, 16384),
            runtime="llama.cpp",
            protocol_id="llamaCppGgufServer",
            payload={"gpuDevice": "all"},
            explicit_combined=True,
        )
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(sum(item["vramMb"] for item in ready["placements"]), 20480)

    def test_qwen_gguf_combined_admission_needs_measured_free_vram(self):
        """Installed totals alone must not unlock an unsafe combined launch."""
        manifest = resource_manifest.build_manifest({
            "modelId": "Qwen3.8-27B-Q4_K_M.gguf",
            "vramEstimateGb": 19,
            "recommendedProtocol": "llamaCppGgufServer",
            "runtimeOptions": [{"protocolId": "llamaCppGgufServer"}],
        })
        totals_only = {
            "schemaVersion": 1,
            "devices": [
                {"deviceId": "gpu:0", "static": {"memoryTotalMb": 12288}},
                {"deviceId": "gpu:1", "static": {"memoryTotalMb": 16384}},
            ],
        }
        _manifest, blocked, _request = admission.plan_admission(
            supplied_manifest=manifest,
            capability_profile=totals_only,
            runtime="llama.cpp",
            protocol_id="llamaCppGgufServer",
            payload={"gpuDevice": "all"},
            explicit_combined=True,
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertIsNone(blocked["capacity"]["devices"][0]["freeMb"])

        _manifest, ready, request = admission.plan_admission(
            supplied_manifest=manifest,
            capability_profile=_profile(12288, 16384),
            runtime="llama.cpp",
            protocol_id="llamaCppGgufServer",
            payload={"gpuDevice": "all"},
            explicit_combined=True,
        )
        self.assertEqual(request["requestedVramMb"], 19456)
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(sum(item["vramMb"] for item in ready["placements"]), 19456)

    def test_make_plan_exposes_ready_admission_without_starting_runtime(self):
        with patch("backend.warsat._hf_repo_inventory", return_value=None), \
             patch("backend.warsat._visible_gpus_for_plan", return_value=[]), \
             patch("backend.warsat._fleet_state", return_value={"gpus": [], "runningModels": []}), \
             patch("backend.warsat._docker_runtime_enabled", return_value={
                 "enabled": False,
                 "dockerControlEnabled": False,
                 "dockerCliAvailable": False,
                 "message": "Docker control disabled for test",
             }), \
             patch("backend.core.security.load", return_value={"allow_docker_control": False}):
            plan = warsat.make_plan({
                "protocolId": "vllmCudaOpenai",
                "modelRef": "demo/7b",
                "hostPort": 8099,
                "vramEstimateGb": 6,
                "capabilityProfile": _profile(12288),
            })
        self.assertEqual(plan["resourceAdmission"]["status"], "ready")
        self.assertEqual(plan["resourceAdmission"]["placements"][0]["deviceId"], "gpu:0")
        self.assertEqual(plan["resourceManifest"]["schemaVersion"], resource_manifest.SCHEMA_VERSION)
        self.assertTrue(any("Docker control is disabled" in warning for warning in plan["warnings"]))

    def test_model_pack_preview_exposes_unmeasured_admission_without_hardware_probe(self):
        models = [{
            "key": "main-local",
            "model": "demo-7b",
            "provider": "llama.cpp",
            "role": "main",
            "runtime_status": "reachable",
            "enabled": True,
            "managed": False,
            "vram_estimate_gb": 6,
        }]
        with patch.object(assistant_runtime.model_registry, "all_models", return_value=models), \
             patch.object(assistant_runtime.security, "load", return_value={"allow_docker_control": False}):
            preview = assistant_runtime.build_model_pack_preview({
                "packId": "local",
                "entries": [{"id": "conversation", "role": "main", "modelKey": "main-local"}],
            })
        entry = preview["entries"][0]
        self.assertEqual(preview["placement_policy"]["capacity_status"], "unmeasured")
        self.assertEqual(entry["resource_admission"]["status"], "unmeasured")
        self.assertIn("runtime_inventory_not_supplied", entry["resource_admission"]["reasons"])
        self.assertEqual(entry["status"], "ready")

    def test_deploy_rejects_a_plan_marked_blocked_before_docker_checks(self):
        with self.assertRaises(AppError) as raised:
            warsat._validate_deploy_plan({
                "resourceAdmission": {"status": "blocked", "reasons": ["requested_vram_exceeds_observed_device_capacity"]},
            })
        self.assertEqual(raised.exception.code, "warsat_resource_admission_blocked")
        self.assertEqual(raised.exception.status, 409)


if __name__ == "__main__":
    unittest.main()
