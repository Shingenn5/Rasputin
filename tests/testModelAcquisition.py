import unittest

from backend.models import acquisition


class ModelAcquisitionTests(unittest.TestCase):
    def test_trusted_progress_requires_known_total_and_bounded_bytes(self):
        self.assertEqual(acquisition._trusted_progress(400, 1000), 40.0)
        self.assertIsNone(acquisition._trusted_progress(0, 0))
        self.assertIsNone(acquisition._trusted_progress(1200, 1000))

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
