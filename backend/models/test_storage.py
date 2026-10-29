import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from backend.models import storage, registry, catalog
from backend.models.desktop_acquisition import DesktopAcquisitionService


class ModelStorageTests(unittest.TestCase):
    def test_new_jobs_follow_saved_folder_and_old_jobs_keep_destination(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            target = Path(tmp) / "other drive" / "models"
            variant = {"repository": "org/model", "revision": "rev1",
                       "files": [{"path": "model.gguf", "size": 4}]}
            service = DesktopAcquisitionService(data_root=root)
            old_job = service.manager.create_job(service._variant_to_download(variant))
            storage.set_download_folder(str(target), root)

            def transfer(file, destination, offset, control, progress):
                destination.write_bytes(b"GGUF")
                progress(4)

            restarted = DesktopAcquisitionService(data_root=root, transfer=transfer)
            self.assertEqual(restarted.model_library, target.resolve())
            self.assertTrue(restarted._variant_to_download(variant).destination.is_relative_to(target.resolve()))
            self.assertEqual(restarted.manager.get_job(old_job.id).destination, old_job.destination)
            new_job = restarted.manager.create_job(restarted._variant_to_download(variant))
            for job in (old_job, new_job):
                restarted.manager.run(job.id)
                self.assertEqual(restarted.manager.get_job(job.id).state, "completed")
                self.assertEqual((Path(job.destination) / "model.gguf").read_bytes(), b"GGUF")
            with self.assertRaises(ValueError):
                restarted._variant_to_download({**variant, "destination": str(Path(tmp) / "escape")})

    def test_previous_folders_remain_visible_after_change_and_reset(self):
        with TemporaryDirectory() as tmp, patch.dict(os.environ, {"RASPUTIN_DATA_DIR": tmp}):
            first = Path(tmp) / "first"
            second = Path(tmp) / "second"
            storage.set_download_folder(str(first))
            model = first / "saved.gguf"
            model.write_bytes(b"GGUF")
            storage.set_download_folder(str(second))
            storage.set_download_folder(str(Path(tmp) / "models"))
            self.assertEqual(storage.download_folder(), Path(tmp) / "models")
            self.assertIn(first.resolve(), catalog._local_model_roots())
            self.assertIn(second.resolve(), registry._model_library_roots())
            self.assertEqual(registry._safe_file(model), model.resolve())

    def test_invalid_and_unwritable_paths_leave_setting_unchanged(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for invalid in ("", "relative/models", str(Path(tmp).anchor), str(Path.home())):
                with self.subTest(path=invalid), self.assertRaises(ValueError):
                    storage.set_download_folder(invalid, root)
            file = root / "file"
            file.write_text("not a folder")
            with self.assertRaises(OSError):
                storage.set_download_folder(str(file), root)
            with patch.object(storage, "NamedTemporaryFile", side_effect=PermissionError):
                with self.assertRaises(PermissionError):
                    storage.set_download_folder(str(root / "locked"), root)
            self.assertEqual(storage.download_folder(root), root / "models")


if __name__ == "__main__":
    unittest.main()
