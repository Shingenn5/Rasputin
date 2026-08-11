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


if __name__ == "__main__":
    unittest.main()
