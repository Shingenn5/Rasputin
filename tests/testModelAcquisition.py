import unittest
from unittest.mock import patch

from backend.models import acquisition


class ModelAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.previous = acquisition._ACTIVE_DOWNLOADS
        acquisition._ACTIVE_DOWNLOADS = {}

    def tearDown(self):
        acquisition._ACTIVE_DOWNLOADS = self.previous

    def test_different_models_get_independent_parallel_download_jobs(self):
        with patch("backend.models.acquisition.threading.Thread") as thread:
            first = acquisition.start_download("org/coder")
            second = acquisition.start_download("org/assistant")

        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(thread.call_count, 2)
        self.assertEqual({item["modelId"] for item in acquisition.get_active_downloads()}, {"org/coder", "org/assistant"})

    def test_same_model_reuses_its_existing_download(self):
        with patch("backend.models.acquisition.threading.Thread") as thread:
            first = acquisition.start_download("org/coder")
            second = acquisition.start_download("org/coder")

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(thread.call_count, 1)


if __name__ == "__main__":
    unittest.main()
