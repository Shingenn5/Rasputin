import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("RASPUTIN_DATA_DIR", tempfile.mkdtemp(prefix="rasputin-assistant-model-requests-"))

from fastapi.testclient import TestClient

from backend import main
from backend.models import compatibility


class AssistantModelRequestTests(unittest.TestCase):
    def setUp(self):
        self.user = {"username": "model-request-owner", "role": "admin"}
        main.app.dependency_overrides.clear()
        from backend.api.core import current_user
        main.app.dependency_overrides[current_user] = lambda: dict(self.user)
        self.client = TestClient(main.app, base_url="http://127.0.0.1", raise_server_exceptions=False)

    def tearDown(self):
        main.app.dependency_overrides.clear()

    def _hardware(self):
        return {"detectedHardware": {"gpus": [{"index": 0, "name": "Test GPU", "memoryTotalMb": 16384}]}}

    def _catalog(self):
        return {
            "items": [
                {
                    "id": "local-code",
                    "modelId": "local-code",
                    "name": "Local Code",
                    "capabilities": ["chat", "code", "tools"],
                    "deployable": True,
                    "apiOnly": False,
                    "recommendedProtocol": "vllmCudaOpenai",
                    "vramEstimateGb": 8,
                    "resourceManifest": {"status": "estimated"},
                },
                {
                    "id": "api-code",
                    "modelId": "api-code",
                    "name": "API Code",
                    "capabilities": ["chat", "code", "tools"],
                    "deployable": False,
                    "apiOnly": True,
                    "recommendedProtocol": "apiOnly",
                },
                {
                    "id": "local-chat",
                    "modelId": "local-chat",
                    "name": "Local Chat",
                    "capabilities": ["chat"],
                    "deployable": True,
                    "apiOnly": False,
                    "recommendedProtocol": "vllmCudaOpenai",
                },
            ],
            "source": {"status": "test"},
        }

    def _advice(self, items, hardware=None, **kwargs):
        return [
            {
                "status": "ready",
                "profileScore": 90,
                "recommendation": {"modelRef": item["modelId"], "protocolId": item["recommendedProtocol"]},
                "planSeed": {"modelRef": item["modelId"], "protocolId": item["recommendedProtocol"]},
                "placement": {"mode": "single-gpu"},
                "benchmarkEvidence": {"status": "unavailable", "exact": False},
                "evidence": {"confidence": "medium", "estimated": {}},
                "blockers": [],
                "warnings": [],
            }
            for item in items
        ]

    def _create(self, capabilities=None):
        payload = {"mission": "code", "requiredCapabilities": capabilities or ["chat", "code", "tools"]}
        with patch("backend.assistant.model_requests.hardware_probe", return_value=self._hardware()),              patch("backend.assistant.model_requests.catalog.catalog", return_value=self._catalog()),              patch("backend.assistant.model_requests.advisor.rank_recommendations", side_effect=self._advice),              patch("backend.assistant.model_requests.benchmarks.list_certificates", return_value=[]):
            return self.client.post("/api/assistant/model-requests", json=payload)

    def test_unknown_and_audio_capabilities_are_rejected(self):
        unknown = self._create(capabilities=["telepathy"])
        self.assertEqual(unknown.status_code, 400)
        self.assertIn("unsupported capability", unknown.json()["error"]["message"])
        audio = self._create(capabilities=["audio.transcribe"])
        self.assertEqual(audio.status_code, 400)
        self.assertIn("voice uses dedicated local STT/TTS", audio.json()["error"]["message"])

    def test_local_deployable_all_of_filter_rejects_api_only(self):
        response = self._create(capabilities=["chat", "code"])
        self.assertEqual(response.status_code, 200)
        items = response.json()["data"]["recommendations"]
        self.assertEqual([item["catalogItem"]["modelId"] for item in items], ["local-code"])

    def test_profile_defaults_fast_and_exact_profile_is_passed_to_advisor(self):
        with patch("backend.assistant.model_requests.hardware_probe", return_value=self._hardware()),              patch("backend.assistant.model_requests.catalog.catalog", return_value=self._catalog()),              patch("backend.assistant.model_requests.benchmarks.list_certificates", return_value=[]),              patch("backend.assistant.model_requests.advisor.rank_recommendations", side_effect=self._advice) as ranked:
            self.client.post("/api/assistant/model-requests", json={"mission": "code", "requiredCapabilities": ["chat", "code"]})
            self.assertEqual(ranked.call_args.kwargs["profile"], "fast")
            self.client.post("/api/assistant/model-requests", json={"mission": "code", "requiredCapabilities": ["chat", "code"], "profile": "maximum_quality"})
            self.assertEqual(ranked.call_args.kwargs["profile"], "maximum_quality")

    def test_measured_throughput_evidence_is_exposed(self):
        def measured(items, hardware=None, **kwargs):
            results = self._advice(items, hardware, **kwargs)
            results[0]["profileScore"] = 99
            results[0]["benchmarkEvidence"] = {
                "status": "exact",
                "exact": True,
                "metrics": {
                    "decodeTokensPerSecond": {"p50": 42.5},
                    "ttftMs": {"p50": 120.0},
                },
            }
            return results

        with patch("backend.assistant.model_requests.hardware_probe", return_value=self._hardware()),              patch("backend.assistant.model_requests.catalog.catalog", return_value=self._catalog()),              patch("backend.assistant.model_requests.benchmarks.list_certificates", return_value=[]),              patch("backend.assistant.model_requests.advisor.rank_recommendations", side_effect=measured) as ranked:
            response = self.client.post(
                "/api/assistant/model-requests",
                json={"mission": "code", "requiredCapabilities": ["chat", "code"], "profile": "balanced"},
            )
        self.assertEqual(response.status_code, 200)
        recommendation = response.json()["data"]["recommendations"][0]
        self.assertEqual(ranked.call_args.kwargs["profile"], "balanced")
        self.assertEqual(recommendation["throughputEvidence"]["status"], "measured")
        self.assertEqual(recommendation["throughputEvidence"]["decodeTokensPerSecond"]["p50"], 42.5)
        self.assertEqual(recommendation["throughputEvidence"]["ttftMs"]["p50"], 120.0)

    def test_owner_isolation_and_immutable_selection(self):
        created = self._create()
        request = created.json()["data"]
        candidate = request["recommendations"][0]
        selected = self.client.post(
            f"/api/assistant/model-requests/{request['requestId']}/select",
            json={"candidateId": candidate["candidateId"]},
        )
        self.assertEqual(selected.status_code, 200)
        selected.json()["data"]["recommendations"][0]["catalogItem"]["name"] = "mutated client copy"
        fetched = self.client.get(f"/api/assistant/model-requests/{request['requestId']}").json()["data"]
        self.assertEqual(fetched["recommendations"][0]["catalogItem"]["name"], "Local Code")

        from backend.api.core import current_user
        main.app.dependency_overrides[current_user] = lambda: {"username": "other-owner", "role": "member"}
        self.assertEqual(self.client.get(f"/api/assistant/model-requests/{request['requestId']}").status_code, 404)
        self.assertEqual(self.client.get("/api/assistant/model-requests").json()["data"]["requests"], [])

    def test_create_and_select_do_not_touch_docker_or_registry(self):
        with patch("backend.assistant.model_requests.hardware_probe", return_value=self._hardware()),              patch("backend.assistant.model_requests.catalog.catalog", return_value=self._catalog()),              patch("backend.assistant.model_requests.advisor.rank_recommendations", side_effect=self._advice),              patch("backend.assistant.model_requests.benchmarks.list_certificates", return_value=[]),              patch("backend.assistant.model_requests.registry.get_model") as get_model:
            created = self.client.post(
                "/api/assistant/model-requests",
                json={"mission": "code", "requiredCapabilities": ["chat", "code"]},
            )
            self.assertEqual(created.status_code, 200)
            request = created.json()["data"]
            selected = self.client.post(
                f"/api/assistant/model-requests/{request['requestId']}/select",
                json={"candidateId": request["recommendations"][0]["candidateId"]},
            )
            self.assertEqual(selected.status_code, 200)
            get_model.assert_not_called()

    def test_blocked_candidate_cannot_be_selected(self):
        def blocked(items, hardware=None, **kwargs):
            results = self._advice(items, hardware, **kwargs)
            results[0]["blockers"] = ["insufficient_vram"]
            return results

        with patch("backend.assistant.model_requests.hardware_probe", return_value=self._hardware()), \
             patch("backend.assistant.model_requests.catalog.catalog", return_value=self._catalog()), \
             patch("backend.assistant.model_requests.advisor.rank_recommendations", side_effect=blocked), \
             patch("backend.assistant.model_requests.benchmarks.list_certificates", return_value=[]):
            created = self.client.post(
                "/api/assistant/model-requests",
                json={"mission": "code", "requiredCapabilities": ["chat", "code", "tools"]},
            )
        request = created.json()["data"]
        self.assertEqual(request["status"], "blocked")
        selected = self.client.post(
            f"/api/assistant/model-requests/{request['requestId']}/select",
            json={"candidateId": request["recommendations"][0]["candidateId"]},
        )
        self.assertEqual(selected.status_code, 409)
        self.assertIn("does not satisfy", selected.json()["error"]["message"])

    def test_assistant_warsat_plan_uses_immutable_selected_snapshot(self):
        request = self._create().json()["data"]
        candidate = request["recommendations"][0]
        selected = self.client.post(
            f"/api/assistant/model-requests/{request['requestId']}/select",
            json={"candidateId": candidate["candidateId"]},
        )
        self.assertEqual(selected.status_code, 200)

        captured = {}
        def make_plan(payload):
            captured.update(payload)
            return {"status": "planned"}

        with patch("backend.api.warsat_api.warsat.make_plan", side_effect=make_plan):
            response = self.client.post(
                "/api/warsat/plan",
                json={
                    "assistantRequestId": request["requestId"],
                    "modelRef": "attacker/model",
                    "protocolId": "llamaCppGgufServer",
                    "gpuDevice": "99",
                    "role": "attacker",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["modelRef"], "local-code")
        self.assertEqual(captured["protocolId"], "vllmCudaOpenai")
        self.assertEqual(captured["role"], "coder")
        self.assertNotIn("gpuDevice", captured)
        self.assertEqual(captured["ownerId"], self.user["username"])
        self.assertEqual(response.json()["data"]["assistantRequestId"], request["requestId"])

    def test_verify_selected_exact_certified_model_and_unqualified_variants(self):
        created = self._create(capabilities=["chat", "code", "tools"])
        request = created.json()["data"]
        candidate_id = request["recommendations"][0]["candidateId"]
        self.client.post(
            f"/api/assistant/model-requests/{request['requestId']}/select",
            json={"candidateId": candidate_id},
        )
        model = {
            "key": "registered-code",
            "model": "local-code",
            "runtime": "warsat-vllm",
            "runtime_status": "reachable",
            "compatibility": {"status": "certified", "toolSupport": "agentic", "supportedModes": ["chat", "code"]},
        }
        model["compatibility"]["fingerprint"] = compatibility.runtime_fingerprint(model)
        with patch("backend.assistant.model_requests.registry.get_model", return_value=model):
            selected = self.client.post(
                f"/api/assistant/model-requests/{request['requestId']}/verify",
                json={"modelKey": "registered-code"},
            )
        self.assertEqual(selected.status_code, 200)
        self.assertEqual(selected.json()["data"]["status"], "selected")

        for profile, key in [
            ({"status": "limited", "toolSupport": "chat-only", "supportedModes": ["chat"]}, "tool-incapable"),
            ({"status": "certified", "toolSupport": "agentic", "supportedModes": ["chat", "code"]}, "stale"),
        ]:
            mismatched = {**model, "key": key, "compatibility": dict(profile)}
            if key == "stale":
                mismatched["compatibility"]["fingerprint"] = "old-fingerprint"
            with patch("backend.assistant.model_requests.registry.get_model", return_value=mismatched):
                result = self.client.post(
                    f"/api/assistant/model-requests/{request['requestId']}/verify",
                    json={"modelKey": key},
                )
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()["data"]["status"], "unqualified")


if __name__ == "__main__":
    unittest.main()
