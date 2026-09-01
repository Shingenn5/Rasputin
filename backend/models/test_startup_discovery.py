from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

from backend.core.response import AppError
from backend.models import registry


class StartupGgufDiscoveryTests(TestCase):
    def _store_patches(self, initial):
        store = deepcopy(initial)

        def load():
            return store

        def save(value):
            saved = deepcopy(value)
            store.clear()
            store.update(saved)

        return store, patch.object(registry, "_load", side_effect=load), patch.object(registry, "_save", side_effect=save)

    def test_native_startup_registers_safe_ggufs_idempotently(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "models"
            absent = Path(directory) / "missing-root"
            root.mkdir()
            coder = root / "Small-Coder-Q4_K_M.gguf"
            shard_one = root / "Large-Model-00001-of-00002.gguf"
            shard_two = root / "Large-Model-00002-of-00002.gguf"
            companion = root / "mmproj-Small-Coder-f16.gguf"
            invalid = root / "not-a-model.gguf"
            unsafe = root / "unsafe.gguf"
            for path in (coder, shard_one, shard_two, companion, unsafe):
                path.write_bytes(b"GGUF" + b"fixture")
            invalid.write_bytes(b"NOPE")
            stale = {
                "key": "stale-external",
                "runtime": "native-llamacpp",
                "host_model_path": str(Path(directory).parent / "outside-or-missing.gguf"),
            }
            store, load_patch, save_patch = self._store_patches({"models": [stale]})
            original_safe_file = registry._safe_file

            def safe_file(path):
                if Path(path).name == unsafe.name:
                    raise AppError("model_file_outside_visible_roots", "unsafe fixture", 403)
                return original_safe_file(path)

            with load_patch, save_patch, patch.object(registry.workspace, "is_native", return_value=True), patch.object(registry, "_model_library_roots", return_value=[absent, root]), patch.object(registry, "_safe_file", side_effect=safe_file), patch.object(registry.security, "require") as permission, patch.object(registry.audit, "log"):
                first = registry.discover_gguf_at_startup()
                second = registry.discover_gguf_at_startup()

            self.assertEqual(len(first["registered"]), 2)
            self.assertEqual(first["existing"], [])
            self.assertEqual(second["registered"], [])
            self.assertEqual(set(second["existing"]), set(first["registered"]))
            self.assertEqual(len(store["models"]), 3)
            self.assertEqual(store["models"][0], stale)
            imported_paths = {Path(item["host_model_path"]).name for item in store["models"][1:]}
            self.assertEqual(imported_paths, {coder.name, shard_one.name})
            self.assertNotIn(shard_two.name, imported_paths)
            self.assertTrue(all(item["runtime"] == "native-llamacpp" for item in store["models"][1:]))
            permission.assert_not_called()

    def test_discovery_is_native_only_and_bounded(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(3):
                (root / f"model-{index}.gguf").write_bytes(b"GGUF")
            store, load_patch, save_patch = self._store_patches({"models": []})
            with patch.object(registry.workspace, "is_native", return_value=False), patch.object(registry, "_model_library_roots") as roots:
                skipped = registry.discover_gguf_at_startup()
            roots.assert_not_called()
            self.assertEqual(skipped["registered"], [])
            with load_patch, save_patch, patch.object(registry.workspace, "is_native", return_value=True), patch.object(registry, "_model_library_roots", return_value=[root]), patch.object(registry.security, "require") as permission, patch.object(registry.audit, "log"):
                result = registry.discover_gguf_at_startup(limit=1)
            self.assertEqual(len(result["registered"]), 1)
            self.assertEqual(len(store["models"]), 1)
            self.assertTrue(result["truncated"])
            permission.assert_not_called()

    def test_public_native_model_reports_local_artifact_availability(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "available.gguf"
            path.write_bytes(b"GGUF")
            self.assertTrue(registry._public_model({"runtime": "native-llamacpp", "host_model_path": str(path)})["artifact_available"])
            path.unlink()
            stale = registry._public_model({"runtime": "native-llamacpp", "host_model_path": str(path)})
            self.assertFalse(stale["artifact_available"])
            external = registry._public_model({"runtime": "external-local", "base_url": "http://127.0.0.1:1/v1"})
            self.assertNotIn("artifact_available", external)

    def test_manual_import_still_requires_registry_permission(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "manual.gguf"
            path.write_bytes(b"GGUF")
            with patch.object(registry, "_safe_file", return_value=path), patch.object(registry.security, "require", side_effect=AppError("permission_denied", "disabled", 403)) as permission:
                with self.assertRaises(AppError):
                    registry.import_gguf({"path": str(path)})
            permission.assert_called_once_with("allow_model_registry_edit")


class StartupHookTests(IsolatedAsyncioTestCase):
    async def test_app_startup_runs_discovery_without_manual_scan_route(self):
        from backend import main

        with patch.object(main.auth, "bootstrap"), patch.object(main.auth, "localhost_bypass_enabled", return_value=False), patch.object(main.memory_store, "init_memory"), patch.object(main.skill_store, "init_skills"), patch.object(main.hub, "recover_pending", new=AsyncMock(return_value=[])), patch.object(main.telegram, "start_polling"), patch.object(main.model_registry, "discover_gguf_at_startup", return_value={"registered": ["auto-model"]}) as discover, patch.object(main.model_registry, "auto_repair_obvious"), patch.object(main.model_registry, "start_health_monitor"), patch.object(main.audit, "log"):
            await main.startup()
        discover.assert_called_once_with()
