import unittest

from backend.warsat import advisor


class WarSatAdvisorTests(unittest.TestCase):
    def test_recommends_multi_gpu_plan_seed_with_evidence_classes(self):
        result = advisor.recommend(
            {
                "modelId": "Qwen/Qwen2.5-Coder-7B-Instruct",
                "purpose": "coding",
                "capabilities": ["coding", "tools"],
                "deployable": True,
                "recommendedProtocol": "vllmCudaOpenai",
                "toolCallParserHint": "hermes",
                "vramEstimateGb": 22,
                "contextWindow": 16384,
            },
            {"detectedHardware": {"gpus": [
                {"name": "GPU A", "memoryTotalMb": 12288},
                {"name": "GPU B", "memoryTotalMb": 16384},
            ]}},
            mission="coding",
        )
        self.assertEqual("ready_with_assumptions", result["status"])
        self.assertEqual(28, result["evidence"]["observed"]["aggregateVramGb"])
        self.assertEqual(6, result["evidence"]["estimated"]["vramMarginGb"])
        self.assertTrue(result["planSeed"]["multiGpu"])
        self.assertFalse(result["approvalBypassed"])
        self.assertTrue(any("shard" in item for item in result["assumptions"]))

    def test_blocks_memory_overcommit(self):
        result = advisor.recommend(
            {"modelId": "large", "deployable": True, "recommendedProtocol": "vllmCudaOpenai", "vramEstimateGb": 24},
            {"detectedHardware": {"gpus": [{"memoryTotalMb": 16384}]}},
        )
        self.assertEqual("blocked", result["status"])
        self.assertTrue(any("exceeds aggregate VRAM" in item for item in result["blockers"]))

    def test_blocks_parser_runtime_mismatch(self):
        result = advisor.recommend(
            {"modelId": "model.gguf", "deployable": True, "recommendedProtocol": "llamaCppGgufServer", "vramEstimateGb": 8},
            {"detectedHardware": {"gpus": [{"memoryTotalMb": 12288}]}},
            tool_call_parser="hermes",
        )
        self.assertEqual("blocked", result["status"])
        self.assertTrue(any("not supported" in item for item in result["blockers"]))


if __name__ == "__main__":
    unittest.main()
