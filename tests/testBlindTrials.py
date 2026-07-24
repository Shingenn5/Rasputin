import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from backend.trials import blind


class BlindTrialsTests(unittest.TestCase):
    def test_repeatable_comparison_hides_identity_until_reveal_and_promotes_evidence(self):
        models = {
            "model-a": {"key": "model-a", "name": "Model A"},
            "model-b": {"key": "model-b", "name": "Model B"},
        }

        async def answer(model_key, messages, temperature=0.2, tools=None):
            self.assertEqual(0.2, temperature)
            self.assertIsNone(tools)
            return f"answer from {model_key}"

        with patch.object(blind.model_registry, "get_model", side_effect=lambda key: models.get(key)), \
             patch.object(blind, "_chat", new=AsyncMock(side_effect=answer)):
            hidden = asyncio.run(blind.run(
                "Repeatable coding fit",
                ["Write a function.", "Explain its complexity."],
                ["model-a", "model-b"],
                repetitions=2,
                seed="fixed-seed",
                mission="coding",
                owner="alice",
            ))

        self.assertEqual("completed", hidden["status"])
        self.assertEqual(2, hidden["metrics"]["repetitions"])
        self.assertEqual(8, hidden["metrics"]["sampleCount"])
        self.assertNotIn("model-a", str(hidden))
        self.assertNotIn("model-b", str(hidden))
        self.assertFalse(hidden["config"]["revealed"])
        self.assertEqual(2, len(hidden["runs"]))
        with self.assertRaisesRegex(ValueError, "Reveal"):
            blind.promote_certificate(hidden["id"], "model-a", "alice")

        revealed = blind.reveal(hidden["id"], "alice")
        self.assertTrue(revealed["config"]["revealed"])
        self.assertIn("model-a", str(revealed))
        self.assertIn("model-b", str(revealed))

        certificate = blind.promote_certificate(hidden["id"], "model-a", "alice", "coding")
        scores = certificate["scores"]
        self.assertEqual("fitnessCertificate", scores["kind"])
        self.assertEqual(4, scores["measured"]["sampleCount"])
        self.assertTrue(scores["evidence"]["identityHiddenDuringRun"])
        self.assertIn("No semantic quality claim", scores["limitations"][0])

    def test_certificate_rejects_missing_comparison(self):
        with self.assertRaisesRegex(ValueError, "not found"):
            blind.promote_certificate("missing", "model-a", "alice")


if __name__ == "__main__":
    unittest.main()
