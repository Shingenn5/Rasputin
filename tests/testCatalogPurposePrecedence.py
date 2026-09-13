import atexit
import os
import tempfile
import unittest

# Keep catalog import-time paths away from the user's live data directory when
# this focused module is run directly.
_TEST_DATA_DIR = tempfile.TemporaryDirectory(prefix="rasputin-catalog-purpose-")
os.environ.setdefault("RASPUTIN_DATA_DIR", _TEST_DATA_DIR.name)
atexit.register(_TEST_DATA_DIR.cleanup)

from backend.models.catalog import _normalize_hf_model


class CatalogPurposePrecedenceTests(unittest.TestCase):
    def test_embedding_pipeline_wins_over_incidental_code_name_and_tag(self):
        item = _normalize_hf_model({
            "id": "acme/code-search-embedding",
            "pipeline_tag": "feature-extraction",
            "tags": ["sentence-transformers", "code-search"],
        })

        self.assertEqual(item["purpose"], "embeddings")

    def test_text_classification_reranker_refinement_wins_over_incidental_code(self):
        item = _normalize_hf_model({
            "id": "BAAI/bge-reranker-v2-m3",
            "pipeline_tag": "text-classification",
            "tags": ["cross-encoder", "code"],
        })

        self.assertEqual(item["purpose"], "reranker")

    def test_sentence_similarity_embedding_wins_over_incidental_code(self):
        item = _normalize_hf_model({
            "id": "sentence-transformers/all-MiniLM-L6-v2",
            "pipeline_tag": "sentence-similarity",
            "tags": ["code-search"],
        })

        self.assertEqual(item["purpose"], "embeddings")

    def test_vision_and_speech_pipelines_win_over_incidental_code(self):
        fixtures = [
            ({
                "id": "acme/code-vision",
                "pipeline_tag": "image-to-text",
                "tags": ["code"],
            }, "vision"),
            ({
                "id": "acme/whisper-code",
                "pipeline_tag": "automatic-speech-recognition",
                "tags": ["code"],
            }, "speech"),
        ]

        for payload, expected in fixtures:
            with self.subTest(pipeline_tag=payload["pipeline_tag"]):
                self.assertEqual(_normalize_hf_model(payload)["purpose"], expected)

    def test_unknown_pipeline_metadata_still_uses_name_tag_heuristics(self):
        item = _normalize_hf_model({
            "id": "acme/code-model",
            "pipeline_tag": "future-task",
            "tags": [],
        })

        self.assertEqual(item["purpose"], "coding")

    def test_generation_metadata_still_refines_coder_and_reasoning_models(self):
        coder = _normalize_hf_model({
            "id": "acme/code-model",
            "pipeline_tag": "text-generation",
            "tags": [],
        })
        reasoning = _normalize_hf_model({
            "id": "acme/reasoning-model",
            "pipeline_tag": "text-generation",
            "tags": [],
        })

        self.assertEqual(coder["purpose"], "coding")
        self.assertEqual(reasoning["purpose"], "reasoning")


if __name__ == "__main__":
    unittest.main()
