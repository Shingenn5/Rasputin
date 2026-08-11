import time
import unittest
from unittest.mock import patch

from backend.engine import context
from backend.engine import agent


class AdaptiveBudgetTests(unittest.TestCase):
    def _certificate(self, *, age=0, concurrency=2, success_rate=1.0, p95=900):
        return {
            "status": "measured",
            "createdAt": time.time() - age,
            "spec": {"contextWindow": 16384, "concurrency": concurrency},
            "summary": {"successRate": success_rate, "ttftMs": {"p95": p95}},
        }

    def test_measured_kv_cache_caps_context_without_changing_unmeasured_defaults(self):
        profile = context.adaptive_profile({
            "contextWindow": 32768,
            "maxTokens": 2048,
            "availableVramGb": 16,
            "resourceManifest": {
                "weights": {"estimatedVramGb": 8},
                "kvCache": {"status": "measured", "perTokenMb": 0.5},
            },
        })
        self.assertEqual(profile["limits"]["contextWindow"], 14336)
        self.assertIn("resourceManifest.kvCache", profile["evidence"])
        self.assertEqual(profile["maxSubagents"], 4)

        unmeasured = context.adaptive_profile({
            "contextWindow": 32768,
            "resourceManifest": {"kvCache": {"status": "unmeasured"}},
        })
        self.assertEqual(unmeasured["limits"]["contextWindow"], 32768)
        self.assertIn("unmeasured", " ".join(unmeasured["reasons"]))

    def test_fresh_certificate_caps_children_and_slow_partial_evidence(self):
        profile = context.adaptive_profile({
            "contextWindow": 32768,
            "maxTokens": 4096,
            "benchmarkCertificate": self._certificate(concurrency=2, success_rate=0.75, p95=6200),
        }, role="code")
        self.assertEqual(profile["limits"]["contextWindow"], 16384)
        self.assertEqual(profile["limits"]["maxTokens"], 2048)
        self.assertEqual(profile["maxSubagents"], 1)
        self.assertTrue(profile["certificateFresh"])
        self.assertIn("benchmarkCertificate.spec.concurrency", profile["evidence"])
        self.assertIn("partial/slow", " ".join(profile["reasons"]))

    def test_stale_certificate_is_not_used_for_adaptation(self):
        profile = context.adaptive_profile({
            "contextWindow": 32768,
            "benchmarkCertificate": self._certificate(age=31 * 24 * 60 * 60, concurrency=1),
        })
        self.assertEqual(profile["limits"]["contextWindow"], 32768)
        self.assertEqual(profile["maxSubagents"], 4)
        self.assertFalse(profile["certificateFresh"])
        self.assertIn("stale", " ".join(profile["reasons"]))

    def test_agent_start_records_and_applies_child_budget(self):
        hub = agent.AgentHub()
        model = {
            "key": "certified-local",
            "provider": "mock",
            "role": "coder",
            "benchmarkCertificate": self._certificate(concurrency=2),
        }
        with patch("backend.engine.agent.model_registry.get_model", return_value=model), \
             patch("backend.engine.agent.model_providers.supports_agentic_tools", return_value=True), \
             patch.object(hub, "_schedule_queued_task"):
            task = hub.start("bounded task", model="certified-local", mode="code", subagents=3)

        self.assertEqual(task.subagents, 1)
        trace = next(item for item in task.trace if item["kind"] == "adaptive_budget")
        self.assertEqual(trace["detail"]["requestedSubagents"], 3)
        self.assertEqual(trace["detail"]["resolvedSubagents"], 1)


if __name__ == "__main__":
    unittest.main()
