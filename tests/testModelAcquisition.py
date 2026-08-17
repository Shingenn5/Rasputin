import unittest
from types import SimpleNamespace

from backend.models import acquisition


class ModelAcquisitionTests(unittest.TestCase):
    def test_trusted_progress_requires_known_total_and_bounded_bytes(self):
        self.assertEqual(acquisition._trusted_progress(400, 1000), 40.0)
        self.assertIsNone(acquisition._trusted_progress(None, 1000))
        self.assertIsNone(acquisition._trusted_progress(float("nan"), 1000))
        self.assertIsNone(acquisition._trusted_progress(400, float("inf")))
        self.assertIsNone(acquisition._trusted_progress(0, 0))
        self.assertIsNone(acquisition._trusted_progress(1200, 1000))

    def test_total_is_unknown_when_any_hub_file_size_is_missing_or_invalid(self):
        self.assertEqual(
            acquisition._known_total_bytes(SimpleNamespace(siblings=[
                SimpleNamespace(size=700),
                SimpleNamespace(size=300),
            ])),
            1000,
        )
        self.assertIsNone(acquisition._known_total_bytes(SimpleNamespace(siblings=[])))
        self.assertIsNone(acquisition._known_total_bytes(SimpleNamespace(siblings=[SimpleNamespace(size=None)])))
        self.assertIsNone(acquisition._known_total_bytes(SimpleNamespace(siblings=[SimpleNamespace(size="unknown")])))
        self.assertIsNone(acquisition._known_total_bytes(SimpleNamespace(siblings=[SimpleNamespace(size=0)])))

    def test_confirmed_completion_only_reports_trusted_100_for_known_total(self):
        self.assertEqual(acquisition._completed_progress(1000, 400), (1000, 100.0, True))
        self.assertEqual(acquisition._completed_progress(None, 400), (400, None, False))
        self.assertEqual(acquisition._completed_progress(0, 400), (400, None, False))

    def test_cache_size_counts_blobs_without_snapshot_duplicates(self):
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            blobs = root_path / "blobs"
            snapshots = root_path / "snapshots" / "commit"
            blobs.mkdir(parents=True)
            snapshots.mkdir(parents=True)
            (blobs / "weight.bin").write_bytes(b"1234")
            (snapshots / "weight.bin").write_bytes(b"duplicate")
            self.assertEqual(acquisition._get_directory_size(root_path), 4)


if __name__ == "__main__":
    unittest.main()
