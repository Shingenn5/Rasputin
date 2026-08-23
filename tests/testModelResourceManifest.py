import unittest

from backend.models import catalog
from backend.models import resource_manifest


class ModelResourceManifestTests(unittest.TestCase):
    def test_manifest_is_versioned_and_valid_for_quantized_model(self):
        manifest = resource_manifest.build_manifest({
            "modelId": "example/Qwen-32B-GGUF",
            "parameterCountB": 32,
            "quantization": "Q4_K_M",
            "vramEstimateGb": 22,
            "contextWindow": 8192,
            "purpose": "coding",
            "capabilities": ["coding", "tools"],
            "recommendedProfile": "large",
            "recommendedProtocol": "llamaCppGgufServer",
            "runtimeOptions": [{"protocolId": "llamaCppGgufServer", "label": "llama.cpp"}],
            "source": "test",
            "checksum": "abc123",
            "license": "apache-2.0",
        })

        self.assertEqual(manifest["schemaVersion"], resource_manifest.SCHEMA_VERSION)
        self.assertEqual(manifest["identity"]["checksum"], "abc123")
        self.assertEqual(manifest["identity"]["license"], "apache-2.0")
        self.assertEqual(manifest["weights"]["quantization"]["name"], "Q4")
        self.assertGreater(manifest["weights"]["estimatedVramGb"], 0)
        self.assertEqual(manifest["kvCache"]["status"], "unmeasured")
        self.assertTrue(manifest["placement"]["combinedVramAllowed"])
        self.assertEqual(manifest["roleFit"]["purpose"], "coding")
        self.assertTrue(resource_manifest.validate_manifest(manifest)["valid"])

    def test_fit_enrichment_reports_headroom_without_claiming_measurement(self):
        item = catalog._normalize_hf_model({
            "id": "bartowski/Qwen2.5-Coder-32B-Q4_K_M-GGUF",
            "pipeline_tag": "text-generation",
            "tags": ["gguf", "Q4_K_M", "license:apache-2.0"],
            "sha": "deadbeef",
        })
        fitted = catalog._fit_item(item, {"detectedHardware": {"gpus": [
            {"memoryTotalMb": 12288},
            {"memoryTotalMb": 16311},
        ]}})
        manifest = fitted["resourceManifest"]

        self.assertEqual(manifest["identity"]["checksum"], "deadbeef")
        self.assertEqual(manifest["identity"]["license"], "apache-2.0")
        self.assertEqual(manifest["fit"]["basis"], "catalog-estimate")
        self.assertAlmostEqual(manifest["fit"]["availableVramGb"], 28599 / 1024, places=2)
        self.assertAlmostEqual(
            manifest["fit"]["headroomGb"],
            28599 / 1024 - fitted["vramEstimateGb"],
            places=2,
        )
        self.assertEqual(manifest["kvCache"]["status"], "unmeasured")

    def test_estimate_distinguishes_precision_and_includes_deployment_overhead(self):
        fp16 = resource_manifest.estimate_vram_demand({
            "modelId": "Example-7B",
            "parameterCountB": 7,
            "quantization": "BF16",
            "recommendedProtocol": "vllmCudaOpenai",
        })
        int8 = resource_manifest.estimate_vram_demand({
            "modelId": "Example-7B",
            "parameterCountB": 7,
            "quantization": "INT8",
            "recommendedProtocol": "vllmCudaOpenai",
        })
        q4 = resource_manifest.estimate_vram_demand({
            "modelId": "Example-7B-GGUF",
            "parameterCountB": 7,
            "quantization": "Q4_K_M",
            "recommendedProtocol": "llamaCppGgufServer",
        })

        self.assertGreater(fp16["totalGb"], int8["totalGb"])
        self.assertGreater(int8["totalGb"], q4["totalGb"])
        self.assertGreater(fp16["totalGb"], fp16["weightsGb"])
        self.assertIn("rangeGb", fp16)
        self.assertEqual(fp16["confidence"], "low")

    def test_context_and_concurrency_increase_known_kv_demand(self):
        base = {
            "modelId": "Example-14B",
            "parameterCountB": 14,
            "quantization": "FP16",
            "recommendedProtocol": "vllmCudaOpenai",
            "kvCache": {"perTokenMb": 0.25},
        }
        one = resource_manifest.estimate_vram_demand({**base, "contextWindow": 4096, "concurrency": 1})
        four = resource_manifest.estimate_vram_demand({**base, "contextWindow": 16384, "concurrency": 4})

        self.assertGreater(four["kvCacheGb"], one["kvCacheGb"])
        self.assertGreater(four["totalGb"], one["totalGb"])
        self.assertEqual(four["confidence"], "medium")
        self.assertEqual(four["concurrency"], 4)

    def test_measured_runtime_vram_is_authoritative(self):
        manifest = resource_manifest.build_manifest({
            "modelId": "Example-7B",
            "parameterCountB": 7,
            "quantization": "FP16",
            "recommendedProtocol": "vllmCudaOpenai",
            "kvCache": {
                "status": "measured",
                "residentVramGb": 11.25,
                "measuredAt": "2026-08-18T00:00:00Z",
            },
        })

        # The measured KV value is a component, so weights and runtime
        # overhead remain part of total deployment demand.
        self.assertAlmostEqual(manifest["runtimeEnvelope"]["estimatedVramGb"], 27.87, places=2)
        self.assertEqual(manifest["runtimeEnvelope"]["breakdown"]["kvCacheGb"], 11.25)
        self.assertEqual(manifest["runtimeEnvelope"]["confidence"], "medium")
        self.assertEqual(
            manifest["runtimeEnvelope"]["estimateSource"],
            "measured-kv-cache-plus-estimated-runtime",
        )

        measured_total = resource_manifest.build_manifest({
            "modelId": "Example-7B",
            "parameterCountB": 7,
            "quantization": "FP16",
            "measuredRuntimeVramGb": 18.5,
        })
        self.assertEqual(measured_total["runtimeEnvelope"]["estimatedVramGb"], 18.5)
        self.assertEqual(measured_total["runtimeEnvelope"]["confidence"], "measured")
        self.assertEqual(measured_total["runtimeEnvelope"]["estimateSource"], "measured-runtime-total")

    def test_matching_catalog_total_preserves_estimator_range(self):
        model = {
            "modelId": "Example-7B-AWQ",
            "parameterCountB": 7,
            "quantization": "AWQ",
            "recommendedProtocol": "vllmCudaOpenai",
        }
        estimate = resource_manifest.estimate_vram_demand(model)
        manifest = resource_manifest.build_manifest({**model, "vramEstimateGb": estimate["totalGb"]})
        self.assertEqual(manifest["runtimeEnvelope"]["rangeGb"], estimate["rangeGb"])
        self.assertEqual(manifest["runtimeEnvelope"]["confidence"], estimate["confidence"])

    def test_catalog_fit_uses_largest_gpu_for_vllm_and_aggregate_for_gguf(self):
        hardware = {"detectedHardware": {"gpus": [
            {"memoryTotalMb": 12288},
            {"memoryTotalMb": 16384},
        ]}}
        vllm = {
            "id": "example/14B",
            "modelId": "example/14B",
            "name": "Example 14B",
            "deployable": True,
            "recommendedProtocol": "vllmCudaOpenai",
            "vramEstimateGb": 18,
        }
        gguf = {**vllm, "id": "example-14B.gguf", "modelId": "example-14B.gguf",
                "recommendedProtocol": "llamaCppGgufServer"}
        vllm_fit = catalog._fit_item(vllm, hardware)
        gguf_fit = catalog._fit_item(gguf, hardware)

        self.assertEqual(vllm_fit["fitLabel"], "Blocked")
        self.assertTrue(any("largest detected GPU" in reason for reason in vllm_fit["blockedReasons"]))
        self.assertNotEqual(gguf_fit["fitLabel"], "Blocked")
        self.assertTrue(any("aggregate detected VRAM" in reason for reason in gguf_fit["fitReasons"]))

        matching_hardware = {"detectedHardware": {"gpus": [
            {"name": "RTX 4090", "memoryTotalMb": 24576},
            {"name": "RTX 4090", "memoryTotalMb": 24576},
        ]}}
        matching_vllm = catalog._fit_item({**vllm, "vramEstimateGb": 30}, matching_hardware)
        self.assertNotEqual(matching_vllm["fitLabel"], "Blocked")
        self.assertTrue(any("matching vLLM tensor-parallel GPUs" in reason for reason in matching_vllm["fitReasons"]))

    def test_legacy_catalog_item_is_enriched_on_fit(self):
        fitted = catalog._fit_item({
            "id": "legacy-model",
            "modelId": "legacy-model",
            "name": "Legacy model",
            "deployable": True,
            "purpose": "chat",
            "parameterCountB": 7,
            "vramEstimateGb": 12,
            "recommendedProtocol": "vllmCudaOpenai",
        }, {"detectedHardware": {"gpus": [{"memoryTotalMb": 16384}]}})

        self.assertEqual(fitted["resourceManifest"]["schemaVersion"], resource_manifest.SCHEMA_VERSION)
        self.assertEqual(fitted["resourceManifest"]["fit"]["label"], fitted["fitLabel"])
        self.assertFalse(fitted["resourceManifest"]["placement"]["combinedVramAllowed"])


if __name__ == "__main__":
    unittest.main()
