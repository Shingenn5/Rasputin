import json
from urllib.error import HTTPError
from io import BytesIO
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ["RASPUTIN_DATA_DIR"] = tempfile.mkdtemp(prefix="rasputin-benchmark-runner-tests-")

from fastapi.testclient import TestClient

from backend import main
from backend.api import warsat_api
from backend.api.core import current_user, require_admin
from backend.core import runtime_store
from backend.models import providers as model_providers
from backend.models import registry as model_registry
from backend.warsat import benchmarks


class WarsatBenchmarkRunnerTests(unittest.TestCase):
    def setUp(self):
        runtime_store.set_kv(benchmarks.STORE_KEY, [])
        main.app.dependency_overrides[current_user] = lambda: {"username": "alice", "role": "admin"}
        main.app.dependency_overrides[require_admin] = lambda: {"username": "alice", "role": "admin"}
        self.client = TestClient(
            main.app,
            base_url="http://127.0.0.1",
            raise_server_exceptions=False,
        )

    def tearDown(self):
        main.app.dependency_overrides.clear()

    @staticmethod
    def registered_model():
        return {
            "key": "registered-qwen",
            "name": "Registered Qwen",
            "provider": "openai-compatible",
            "runtime": "warsat-llama.cpp",
            "model": "Qwen/Test-Q4",
            "protocol_id": "llamaCppGgufServer",
            "model_revision": "sha-test",
            "model_format": "gguf",
            "quantization": "Q4_K_M",
            "device_ids": ["gpu:0", "gpu:1"],
            "placement_mode": "multi-gpu",
            "context_window": 8192,
            "concurrency": 1,
            "base_url": "http://127.0.0.1:8123/v1",
            "enabled": True,
            "managed": True,
        }

    def test_run_measures_stream_and_persists_exact_registered_identity(self):
        calls = []

        def fake_chat(model, messages, max_tokens, temperature, **kwargs):
            calls.append((model, messages, max_tokens, temperature, kwargs))
            kwargs["on_delta"]({"type": "text", "text": "confirmed"})
            kwargs["on_delta"]({
                "type": "metrics",
                "usage": {"completion_tokens": 8, "prompt_tokens": 15},
                "timings": {
                    "prompt_n": 15,
                    "prompt_ms": 10,
                    "predicted_n": 8,
                    "predicted_ms": 40,
                    "predicted_per_second": 200,
                },
            })
            return "confirmed", []

        model = self.registered_model()
        with patch.object(model_registry, "get_model", return_value=model),              patch.object(model_providers, "chat_sync", side_effect=fake_chat),              patch.object(warsat_api.warsat, "deploy") as deploy,              patch.object(warsat_api.warsat, "stop") as stop,              patch.object(warsat_api.warsat, "restart") as restart:
            response = self.client.post(
                "/api/warsat/benchmarks/run",
                json={
                    "modelId": "registered-qwen",
                    "samples": 2,
                    "maxTokens": 32,
                    "timeoutSeconds": 2,
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()["data"]
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1][0]["content"], warsat_api.warsat_benchmark_runner.FIXED_PROMPT)
        self.assertEqual(calls[0][2], 32)
        self.assertEqual(data["owner"], "alice")
        self.assertEqual(data["summary"]["sampleCount"], 2)
        self.assertEqual(data["summary"]["decodeTokensPerSecond"]["p50"], 200.0)
        spec = data["spec"]
        self.assertEqual(spec["modelId"], "Qwen/Test-Q4")
        self.assertEqual(spec["modelRevision"], "sha-test")
        self.assertEqual(spec["runtime"], "warsat-llama.cpp")
        self.assertEqual(spec["protocolId"], "llamaCppGgufServer")
        self.assertEqual(spec["deviceIds"], ["gpu:0", "gpu:1"])
        self.assertEqual(spec["contextWindow"], 8192)
        self.assertEqual(spec["concurrency"], 1)
        self.assertEqual(spec["quantization"], "Q4_K_M")
        self.assertEqual(spec["placementMode"], "multi-gpu")
        deploy.assert_not_called()
        stop.assert_not_called()
        restart.assert_not_called()
        saved = benchmarks.list_certificates(owner="alice", model_id="Qwen/Test-Q4")
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["certificateId"], data["certificateId"])

    def test_real_openai_stream_shape_emits_usage_and_llama_timings_metrics(self):
        class FakeSseResponse:
            def __init__(self, payloads):
                self._lines = [
                    f"data: {payload}\n".encode("utf-8")
                    for payload in payloads
                ]

            def __iter__(self):
                return iter(self._lines)

            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

        payloads = [
            json.dumps({
                "choices": [{"delta": {"content": "confirmed"}}],
            }),
            json.dumps({
                "choices": [],
                "usage": {"prompt_tokens": 15, "completion_tokens": 8},
                "timings": {
                    "prompt_n": 15,
                    "prompt_ms": 10,
                    "predicted_n": 8,
                    "predicted_ms": 40,
                    "predicted_per_second": 200,
                    "predicted_per_token_ms": 5,
                },
            }),
            "[DONE]",
        ]
        events = []
        with patch.object(
            model_providers,
            "_open_sse",
            return_value=FakeSseResponse(payloads),
        ):
            text, tool_calls = model_providers._stream_openai(
                "http://127.0.0.1/v1/chat/completions",
                {"stream": True, "stream_options": {"include_usage": True}},
                {},
                events.append,
            )

        self.assertEqual(text, "confirmed")
        self.assertEqual(tool_calls, [])
        metrics = next(event for event in events if event["type"] == "metrics")
        self.assertEqual(metrics["usage"]["completion_tokens"], 8)
        self.assertEqual(metrics["timing"]["predicted_n"], 8)
        self.assertEqual(metrics["timing"]["predicted_per_second"], 200)

    def test_stream_options_rejection_retries_without_optional_field(self):
        model = self.registered_model()
        error = HTTPError(
            "http://127.0.0.1/v1/chat/completions",
            400,
            "stream_options unsupported",
            {},
            BytesIO(b"stream_options unsupported"),
        )
        with patch.object(
            model_providers,
            "_stream_openai",
            side_effect=[error, ("confirmed", [])],
        ) as stream:
            result = model_providers.chat_sync(
                model,
                [{"role": "user", "content": "Say ok."}],
                8,
                0,
                on_delta=lambda _event: None,
                reasoning="off",
            )

        self.assertEqual(result, ("confirmed", []))
        self.assertEqual(len(stream.call_args_list), 2)
        self.assertEqual(
            stream.call_args_list[0].args[1]["stream_options"],
            {"include_usage": True},
        )
        self.assertNotIn("stream_options", stream.call_args_list[1].args[1])

    def test_unreachable_registered_model_fails_without_persisting(self):
        model = self.registered_model()
        with patch.object(model_registry, "get_model", return_value=model),              patch.object(model_providers, "chat_sync", side_effect=ConnectionError("connection refused")):
            response = self.client.post(
                "/api/warsat/benchmarks/run",
                json={"modelId": "registered-qwen", "timeoutSeconds": 1},
            )

        self.assertEqual(response.status_code, 502, response.text)
        self.assertIn("connection refused", response.text)
        self.assertEqual(benchmarks.list_certificates(owner="alice"), [])

    def test_samples_and_tokens_are_bounded(self):
        model = self.registered_model()
        with patch.object(model_registry, "get_model", return_value=model):
            for payload in (
                {"modelId": "registered-qwen", "samples": 0},
                {"modelId": "registered-qwen", "samples": 4},
                {"modelId": "registered-qwen", "maxTokens": 129},
            ):
                response = self.client.post("/api/warsat/benchmarks/run", json=payload)
                self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(benchmarks.list_certificates(owner="alice"), [])

    def test_missing_usage_or_token_timing_fails_visibly(self):
        model = self.registered_model()

        def no_metrics(*_args, **kwargs):
            kwargs["on_delta"]({"type": "text", "text": "confirmed"})
            return "confirmed", []

        with patch.object(model_registry, "get_model", return_value=model),              patch.object(model_providers, "chat_sync", side_effect=no_metrics):
            response = self.client.post(
                "/api/warsat/benchmarks/run",
                json={"modelId": "registered-qwen"},
            )

        self.assertEqual(response.status_code, 502, response.text)
        self.assertIn("usable generated-token", response.text)
        self.assertEqual(benchmarks.list_certificates(owner="alice"), [])


if __name__ == "__main__":
    unittest.main()
