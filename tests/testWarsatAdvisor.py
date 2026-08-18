import unittest

from backend.warsat import advisor, benchmarks


class WarSatAdvisorTests(unittest.TestCase):
    def test_recommends_single_gpu_seed_with_explicit_sharding_assumption(self):
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
        self.assertFalse(result["planSeed"]["multiGpu"])
        self.assertFalse(result["approvalBypassed"])
        self.assertTrue(any("largest fitting single GPU" in item for item in result["assumptions"]))
        self.assertTrue(any("runtime certificate" in item for item in result["assumptions"]))

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


    def _hardware(self):
        return {"detectedHardware": {"gpus": [
            {"name": "RTX 3060", "memoryTotalMb": 12288},
            {"name": "RTX 5060 Ti", "memoryTotalMb": 16384},
        ]}}

    def _model(self, protocol="vllmCudaOpenai", estimate=14):
        return {
            "modelId": "profile-model",
            "modelRevision": "r1",
            "runtime": "vllm" if protocol == "vllmCudaOpenai" else "llama.cpp",
            "quantization": "q4",
            "deployable": True,
            "recommendedProtocol": protocol,
            "vramEstimateGb": estimate,
        }

    def _certificate(self, model, devices, protocol, placement, status=None, measured_at=None):
        cert = benchmarks.build_certificate({
            "modelId": model["modelId"],
            "modelRevision": model["modelRevision"],
            "runtime": model["runtime"],
            "protocolId": protocol,
            "deviceIds": devices,
            "contextWindow": 8192,
            "concurrency": 1,
            "quantization": model["quantization"],
            "placementMode": placement,
        }, [{"status": "ok", "totalLatencyMs": 100, "ttftMs": 20, "decodeMs": 80, "outputTokens": 40}], measured_at=measured_at or __import__("time").time())
        if status:
            cert["status"] = status
        return cert

    def test_fast_profile_uses_largest_single_gpu(self):
        result = advisor.recommend(self._model(), self._hardware(), profile="fast")
        self.assertEqual(result["placement"]["mode"], "single-gpu")
        self.assertEqual(result["placement"]["deviceIds"], ["1"])
        self.assertNotEqual(result["status"], "blocked")

    def test_balanced_blocks_when_only_aggregate_vram_fits(self):
        result = advisor.recommend(self._model(estimate=20), self._hardware(), profile="balanced")
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("largest single GPU" in item for item in result["blockers"]))

    def test_fresh_exact_evidence_wins_over_catalog_estimate(self):
        model = self._model()
        certificate = self._certificate(model, ["1"], "vllmCudaOpenai", "single-gpu")
        result = advisor.recommend(model, self._hardware(), profile="balanced", benchmark_certificate=certificate)
        self.assertEqual(result["benchmarkEvidence"]["status"], "exact")
        self.assertEqual(result["benchmarkEvidence"]["basis"], "measured-exact")
        self.assertEqual(result["benchmarkEvidence"]["certificateId"], certificate["certificateId"])
        self.assertEqual(result["benchmarkEvidence"]["metrics"]["ttftMs"]["p50"], 20.0)

    def test_stale_mismatched_and_partial_evidence_are_not_exact(self):
        model = self._model()
        stale = self._certificate(model, ["1"], "vllmCudaOpenai", "single-gpu", measured_at=1)
        mismatch = self._certificate(model, ["1"], "ollamaOpenaiServer", "single-gpu")
        partial = self._certificate(model, ["1"], "vllmCudaOpenai", "single-gpu", status="partial")
        self.assertEqual(benchmarks.match_certificate(stale, {
            "modelId": model["modelId"], "modelRevision": "r1", "runtime": "vllm",
            "protocolId": "vllmCudaOpenai", "deviceIds": ["1"], "contextWindow": 8192,
            "concurrency": 1, "quantization": "q4", "placementMode": "single-gpu",
        })["status"], "stale")
        self.assertEqual(benchmarks.match_certificate(mismatch, {
            "modelId": model["modelId"], "modelRevision": "r1", "runtime": "vllm",
            "protocolId": "vllmCudaOpenai", "deviceIds": ["1"], "contextWindow": 8192,
            "concurrency": 1, "quantization": "q4", "placementMode": "single-gpu",
        })["status"], "mismatch")
        self.assertEqual(benchmarks.match_certificate(partial, {
            "modelId": model["modelId"], "modelRevision": "r1", "runtime": "vllm",
            "protocolId": "vllmCudaOpenai", "deviceIds": ["1"], "contextWindow": 8192,
            "concurrency": 1, "quantization": "q4", "placementMode": "single-gpu",
        })["status"], "partial")

    def test_maximum_quality_combines_only_with_exact_llama_certificate(self):
        model = self._model("llamaCppGgufServer", estimate=22)
        certificate = self._certificate(model, ["0", "1"], "llamaCppGgufServer", "multi-gpu")
        result = advisor.recommend(model, self._hardware(), profile="maximum_quality", benchmark_certificate=certificate)
        self.assertEqual(result["placement"]["mode"], "multi-gpu")
        self.assertFalse(result["status"] == "blocked")
        vllm = self._model(estimate=22)
        vllm_certificate = self._certificate(vllm, ["0", "1"], "vllmCudaOpenai", "multi-gpu")
        blocked = advisor.recommend(vllm, self._hardware(), profile="maximum_quality", benchmark_certificate=vllm_certificate)
        self.assertEqual(blocked["placement"]["mode"], "single-gpu")
        self.assertEqual(blocked["status"], "blocked")

    def test_fast_ranking_prioritizes_measured_decode_tps(self):
        responsive = {
            "status": "ready",
            "profileScore": 90,
            "recommendation": {"modelRef": "responsive"},
            "benchmarkEvidence": {
                "exact": True,
                "metrics": {
                    "decodeTokensPerSecond": {"p50": 20.0},
                    "ttftMs": {"p50": 5.0},
                    "totalLatencyMs": {"p50": 100.0},
                },
            },
        }
        throughput = {
            "status": "ready",
            "profileScore": 80,
            "recommendation": {"modelRef": "throughput"},
            "benchmarkEvidence": {
                "exact": True,
                "metrics": {
                    "decodeTokensPerSecond": {"p50": 50.0},
                    "ttftMs": {"p50": 100.0},
                    "totalLatencyMs": {"p50": 200.0},
                },
            },
        }
        ranked = sorted([responsive, throughput], key=lambda item: advisor._ranking_key(item, "fast"))
        self.assertEqual(ranked[0]["recommendation"]["modelRef"], "throughput")

    def test_ranking_tie_break_is_lexicographic(self):
        first = dict(self._model(), modelId="b-model")
        second = dict(self._model(), modelId="a-model")
        ranked = advisor.rank_recommendations([first, second], self._hardware(), profile="balanced")
        self.assertEqual([item["recommendation"]["modelRef"] for item in ranked], ["a-model", "b-model"])


if __name__ == "__main__":
    unittest.main()
