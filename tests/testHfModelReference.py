import unittest
from unittest.mock import patch

from backend.models import catalog


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.links = {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class RecordingClient:
    responses = []
    calls = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, params=None):
        type(self).calls.append((url, params))
        if type(self).responses:
            return type(self).responses.pop(0)
        return FakeResponse([])


class HfModelReferenceTests(unittest.TestCase):
    def setUp(self):
        RecordingClient.calls = []
        RecordingClient.responses = []

    def test_normalize_accepts_ids_urls_and_revision_suffixes(self):
        cases = {
            "org/model": "org/model",
            " org/model/ ": "org/model",
            "https://huggingface.co/org/model": "org/model",
            "https://huggingface.co/org/model/": "org/model",
            "https://www.huggingface.co/org/model/tree/main": "org/model",
            "https://huggingface.co/org/model/blob/main/subdir/config.json": "org/model",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(catalog.normalize_hf_reference(value), expected)

    def test_normalize_rejects_untrusted_or_malformed_references(self):
        for value in (
            "https://example.com/org/model",
            "http://huggingface.co/",
            "https://huggingface.co/org",
            "https://huggingface.co/org/model/tree",
            "org/model/extra",
            "not a model id",
        ):
            with self.subTest(value=value):
                self.assertIsNone(catalog.normalize_hf_reference(value))

    def test_unrelated_url_is_safe_empty_result_without_api_request(self):
        with patch.object(catalog.httpx, "Client", RecordingClient) as client:
            result = catalog.search_hf("https://example.com/org/model")
        self.assertEqual(RecordingClient.calls, [])
        self.assertEqual(result["items"], [])
        self.assertFalse(result["exactMatch"])
        self.assertEqual(result["normalizedModelId"], "")
        self.assertIn("huggingface.co", result["error"])

    def test_fuzzy_search_preserves_original_query_and_metadata(self):
        RecordingClient.responses = [FakeResponse([{"id": "org/qwen-coder", "tags": []}])]
        with patch.object(catalog.httpx, "Client", RecordingClient):
            result = catalog.search_hf("qwen coder", limit=10)
        self.assertEqual(result["query"], "qwen coder")
        self.assertFalse(result["exactMatch"])
        self.assertEqual(result["normalizedModelId"], "")
        self.assertEqual(RecordingClient.calls[0][1]["search"], "qwen coder")
        self.assertEqual(result["items"][0]["id"], "org/qwen-coder")

    def test_exact_url_uses_normalized_lookup_and_promotes_without_duplicate(self):
        exact_id = "org/special-model"
        RecordingClient.responses = [
            FakeResponse([{"id": "org/other-model", "tags": []}]),
            FakeResponse({"id": exact_id, "tags": [], "downloads": 10}),
        ]
        query = "https://www.huggingface.co/org/special-model/tree/main"
        with patch.object(catalog.httpx, "Client", RecordingClient):
            result = catalog.search_hf(query, limit=10)
        self.assertTrue(result["exactMatch"])
        self.assertEqual(result["normalizedModelId"], exact_id)
        self.assertEqual(result["query"], query)
        self.assertEqual(result["items"][0]["id"], exact_id)
        self.assertEqual([item["id"] for item in result["items"]].count(exact_id), 1)
        self.assertEqual(RecordingClient.calls[0][1]["search"], exact_id)
        self.assertTrue(RecordingClient.calls[1][0].endswith("/org/special-model"))

    def test_nonexistent_exact_reference_never_returns_fuzzy_substitutes(self):
        RecordingClient.responses = [
            FakeResponse([{"id": "org/similar-but-wrong", "tags": []}]),
            FakeResponse({}, status_code=404),
        ]
        with patch.object(catalog.httpx, "Client", RecordingClient):
            result = catalog.search_hf("org/does-not-exist", limit=10)
        self.assertFalse(result["exactMatch"])
        self.assertEqual(result["normalizedModelId"], "org/does-not-exist")
        self.assertEqual(result["items"], [])
        self.assertIn("was not found", result["error"])

    def test_exact_result_already_in_fuzzy_page_is_not_requested_again(self):
        exact_id = "org/already-there"
        RecordingClient.responses = [FakeResponse([{"id": exact_id, "tags": []}])]
        with patch.object(catalog.httpx, "Client", RecordingClient):
            result = catalog.search_hf(exact_id, limit=10)
        self.assertTrue(result["exactMatch"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(len(RecordingClient.calls), 1)
        self.assertEqual(result["items"][0]["id"], exact_id)


if __name__ == "__main__":
    unittest.main()
