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
