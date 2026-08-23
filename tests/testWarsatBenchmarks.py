import os
import tempfile
import unittest

os.environ.setdefault("RASPUTIN_DATA_DIR", tempfile.mkdtemp(prefix="rasputin-benchmark-tests-"))

from fastapi.testclient import TestClient

from backend import main
from backend.api.core import current_user, require_admin
from backend.warsat import benchmarks


def _samples():
    return [
        {"status": "ok", "totalLatencyMs": 100, "ttftMs": 20, "decodeMs": 80, "outputTokens": 40, "promptTokens": 80},
        {"status": "ok", "totalLatencyMs": 200, "ttftMs": 40, "decodeMs": 160, "outputTokens": 80, "promptTokens": 80},
        {"status": "ok", "totalLatencyMs": 300, "ttftMs": 60, "decodeMs": 240, "outputTokens": 120, "promptTokens": 80},
    ]


class WarsatBenchmarkTests(unittest.TestCase):
    def setUp(self):
        main.app.dependency_overrides[current_user] = lambda: {"username": "alice", "role": "admin"}
        main.app.dependency_overrides[require_admin] = lambda: {"username": "alice", "role": "admin"}
        self.client = TestClient(main.app, base_url="http://127.0.0.1", raise_server_exceptions=False)

    def tearDown(self):
        main.app.dependency_overrides.clear()

    def test_certificate_aggregates_latency_and_throughput_without_quality_claim(self):
        certificate = benchmarks.build_certificate({
            "modelId": "local-coder",
            "runtime": "vllm",
            "protocolId": "vllmCudaOpenai",
            "deviceIds": ["1"],
            "contextWindow": 4096,
            "concurrency": 1,
            "quantization": "awq",
        }, _samples(), owner="alice", measured_at=1_700_000_000)

        self.assertEqual(certificate["schemaVersion"], benchmarks.SCHEMA_VERSION)
        self.assertEqual(certificate["status"], "measured")
        self.assertEqual(certificate["summary"]["successRate"], 1.0)
        self.assertEqual(certificate["summary"]["totalLatencyMs"]["p50"], 200.0)
        self.assertEqual(certificate["summary"]["ttftMs"]["p95"], 58.0)
        self.assertEqual(certificate["summary"]["decodeTokensPerSecond"]["p50"], 500.0)
        self.assertEqual(certificate["quality"]["status"], "unmeasured")
        self.assertTrue(benchmarks.validate_certificate(certificate)["valid"])
        self.assertTrue(benchmarks.is_fresh(certificate, now=1_700_000_010))

    def test_certificate_rejects_invalid_sample_and_scopes_store_by_owner(self):
        with self.assertRaisesRegex(ValueError, "requires totalLatencyMs"):
            benchmarks.build_certificate({
                "modelId": "model",
                "runtime": "llama.cpp",
                "protocolId": "llamaCppGgufServer",
            }, [{"status": "ok"}], owner="alice")

        saved = benchmarks.save_certificate(benchmarks.build_certificate({
            "modelId": "stored-model",
            "runtime": "llama.cpp",
            "protocolId": "llamaCppGgufServer",
        }, _samples(), owner="alice"))
        self.assertEqual(benchmarks.get_certificate(saved["certificateId"], owner="alice")["owner"], "alice")
        self.assertIsNone(benchmarks.get_certificate(saved["certificateId"], owner="bob"))
        self.assertEqual(len(benchmarks.list_certificates(owner="alice", model_id="stored-model")), 1)

    def test_benchmark_api_records_and_lists_certificate(self):
        response = self.client.post("/api/warsat/benchmarks", json={
            "modelId": "api-model",
            "runtime": "vllm",
            "protocolId": "vllmCudaOpenai",
            "deviceIds": ["1"],
            "contextWindow": 4096,
            "samples": _samples(),
        })
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()["data"]
        self.assertEqual(data["schemaVersion"], benchmarks.SCHEMA_VERSION)
        self.assertTrue(data["fresh"])

        listed = self.client.get("/api/warsat/benchmarks?model_id=api-model")
        self.assertEqual(listed.status_code, 200)
        list_data = listed.json()["data"]
        self.assertEqual(list_data["count"], 1)
        certificate_id = list_data["items"][0]["certificateId"]
        detail = self.client.get(f"/api/warsat/benchmarks/{certificate_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["data"]["spec"]["modelId"], "api-model")


    def test_exact_tuple_match_reports_field_mismatches(self):
        certificate = benchmarks.build_certificate({
            "modelId": "tuple-model",
            "modelRevision": "rev-a",
            "runtime": "vllm",
            "protocolId": "vllmCudaOpenai",
            "deviceIds": ["1"],
            "contextWindow": 4096,
            "concurrency": 1,
            "quantization": "awq",
            "placementMode": "single-gpu",
        }, _samples(), owner="alice", measured_at=1_700_000_000)
        target = dict(certificate["spec"])
        self.assertTrue(benchmarks.match_certificate(certificate, target, now=1_700_000_010)["exact"])
        target["placementMode"] = "multi-gpu"
        mismatch = benchmarks.match_certificate(certificate, target, now=1_700_000_010)
        self.assertEqual(mismatch["status"], "mismatch")
        self.assertIn("placementMode", mismatch["mismatches"])
        self.assertFalse(mismatch["exact"])


    def test_advisor_api_accepts_camel_profile_and_owner_scoped_certificate(self):
        certificate = benchmarks.build_certificate({
            "modelId": "api-advisor-model",
            "modelRevision": "rev-a",
            "runtime": "vllm",
            "protocolId": "vllmCudaOpenai",
            "deviceIds": ["1"],
            "contextWindow": 4096,
            "concurrency": 1,
            "quantization": "awq",
            "placementMode": "single-gpu",
        }, _samples(), owner="alice")
        benchmarks.save_certificate(certificate)
        response = self.client.post("/api/warsat/advisor", json={
            "model": {
                "modelId": "api-advisor-model", "modelRevision": "rev-a",
                "runtime": "vllm", "quantization": "awq", "vramEstimateGb": 14,
                "recommendedProtocol": "vllmCudaOpenai",
            },
            "hardware": {"detectedHardware": {"gpus": [
                {"memoryTotalMb": 12288}, {"memoryTotalMb": 16384},
            ]}},
            "profile": "fast",
            "contextWindow": 4096,
            "benchmarkCertificateId": certificate["certificateId"],
        })
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()["data"]
        self.assertEqual(data["profile"], "fast")
        self.assertEqual(data["placement"]["deviceIds"], ["1"])
        self.assertEqual(data["benchmarkEvidence"]["status"], "exact")


    def test_all_profiles_selects_fresh_owner_scoped_certificates_per_tuple(self):
        model = {
            "modelId": "all-profiles-model", "modelRevision": "rev-a",
            "runtime": "vllm", "quantization": "awq",
            "recommendedProtocol": "vllmCudaOpenai", "vramEstimateGb": 14,
        }
        stale = benchmarks.build_certificate({
            "modelId": model["modelId"], "modelRevision": "rev-a", "runtime": "vllm",
            "protocolId": "vllmCudaOpenai", "deviceIds": ["1"], "contextWindow": 8192,
            "concurrency": 1, "quantization": "awq", "placementMode": "single-gpu",
        }, _samples(), owner="alice", measured_at=1)
        fresh = benchmarks.build_certificate({
            **stale["spec"],
        }, _samples(), owner="alice")
        foreign = benchmarks.build_certificate({
            **stale["spec"],
        }, _samples(), owner="bob")
        benchmarks.save_certificate(stale)
        benchmarks.save_certificate(fresh)
        benchmarks.save_certificate(foreign)

        response = self.client.post("/api/warsat/advisor", json={
            "model": model,
            "hardware": {"detectedHardware": {
                "gpus": [{"memoryTotalMb": 12288}, {"memoryTotalMb": 16384}],
            }},
            "allProfiles": True,
        })
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()["data"]
        self.assertEqual(set(data["profiles"]), {"fast", "balanced", "maximumQuality"})
        self.assertEqual(data["profiles"]["fast"]["benchmarkEvidence"]["certificateId"], fresh["certificateId"])
        self.assertEqual(data["profiles"]["balanced"]["benchmarkEvidence"]["status"], "exact")
        self.assertEqual(data["profiles"]["maximumQuality"]["benchmarkEvidence"]["certificateId"], fresh["certificateId"])

    def test_all_profiles_match_each_profile_placement_tuple(self):
        model = {
            "modelId": "all-profiles-large", "modelRevision": "rev-a",
            "runtime": "llama.cpp", "quantization": "q4",
            "recommendedProtocol": "llamaCppGgufServer", "vramEstimateGb": 22,
        }
        combined = benchmarks.build_certificate({
            "modelId": model["modelId"], "modelRevision": "rev-a", "runtime": "llama.cpp",
            "protocolId": "llamaCppGgufServer", "deviceIds": ["0", "1"], "contextWindow": 8192,
            "concurrency": 1, "quantization": "q4", "placementMode": "multi-gpu",
        }, _samples(), owner="alice")
        benchmarks.save_certificate(combined)
        response = self.client.post("/api/warsat/advisor/profiles", json={
            "model": model,
            "hardware": {"detectedHardware": {
                "gpus": [{"memoryTotalMb": 12288}, {"memoryTotalMb": 16384}],
            }},
        })
        self.assertEqual(response.status_code, 200, response.text)
        profiles = response.json()["data"]["profiles"]
        for profile in profiles.values():
            self.assertEqual(profile["benchmarkEvidence"]["status"], "exact")
            self.assertEqual(profile["placement"]["mode"], "multi-gpu")


if __name__ == "__main__":
    unittest.main()
