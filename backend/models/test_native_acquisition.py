import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from backend.models import acquisition, registry

class NativeAcquisitionTests(unittest.TestCase):

    def test_snapshot_registration_uses_host_runtime_without_desktop_flag(self):
        for native in (True, False):
            with self.subTest(native=native), tempfile.TemporaryDirectory() as directory:
                model = Path(directory) / 'model.gguf'
                model.write_bytes(b'test fixture')
                state = {'status': 'starting'}
                info = SimpleNamespace(siblings=[SimpleNamespace(rfilename=model.name, size=model.stat().st_size)])
                with patch.dict(os.environ, {'RASPUTIN_DESKTOP_ONLY': '0'}), patch.dict(acquisition._ACTIVE_DOWNLOADS, {'test': state}, clear=True), patch.object(acquisition, 'MODELS_DIR', Path(directory)), patch.object(acquisition.workspace, 'is_native', return_value=native), patch.object(acquisition, 'model_info', return_value=info), patch.object(acquisition, 'snapshot_download', return_value=directory), patch.object(registry, 'upsert') as upsert:
                    acquisition._download_thread('test', 'org/model')
                self.assertEqual(state['status'], 'completed')
                registered = upsert.call_args.args[0]
                if native:
                    self.assertEqual(registered['runtime'], 'native-llamacpp')
                    self.assertEqual(registered['host_model_path'], str(model))
                    self.assertNotIn('warsatProtocol', registered)
                else:
                    self.assertEqual(registered['warsatProtocol'], 'llamaCppGgufServer')

    def test_native_hardware_probe_does_not_require_or_invoke_docker(self):
        from backend import warsat
        with patch.dict(os.environ, {'RASPUTIN_DESKTOP_ONLY': '0'}), patch.object(warsat.security, 'load', return_value={'allow_docker_control': False}), patch.object(warsat, '_docker_cli_path') as docker, patch.object(warsat, '_gpu_probe_via_docker') as docker_gpu, patch.object(warsat.shutil, 'which', return_value=None), patch.object(warsat, '_model_mount_state', return_value={'id': 'models', 'status': 'pass', 'nextStep': ''}):
            result = warsat.hardware_probe(native_models=True)
        docker.assert_not_called()
        docker_gpu.assert_not_called()
        self.assertTrue(result['ok'])

    def test_catalog_detail_wire_payload_retains_exact_sizes_and_filenames(self):
        from backend.models import catalog
        from backend.core.response import ok
        from backend.models.desktop_acquisition import DesktopAcquisitionService
        from unittest.mock import MagicMock
        filename = 'sub_dir/model_Q4_K_M.gguf'
        raw = {'id': 'org/model', 'sha': 'a' * 40, 'siblings': [{'rfilename': filename, 'size': 1234}]}
        client = MagicMock()
        client.__enter__.return_value = client
        client.get.return_value.json.return_value = raw
        with patch.object(catalog.httpx, 'Client', return_value=client):
            detail = catalog.hf_model_detail('org/model')
        client.get.assert_called_once_with(catalog.HF_API_URL + '/org/model', params={'blobs': 'true'})
        wire = ok(detail)['data']
        variant = wire['variants'][0]
        self.assertEqual(variant['fileSizes'], {filename: 1234})
        with tempfile.TemporaryDirectory() as directory:
            service = DesktopAcquisitionService(data_root=directory)
            download = service._variant_to_download(variant)
        self.assertEqual(download.files[0].path, filename)
        self.assertEqual(download.files[0].expected_size, 1234)

    def test_existing_native_registration_gets_live_file_size_for_load_planning(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / 'model-00001-of-00002.gguf'
            second = Path(directory) / 'model-00002-of-00002.gguf'
            first.write_bytes(b'a' * 1024)
            model = {'runtime': 'native-llamacpp', 'host_model_path': str(first)}
            self.assertEqual(registry._native_file_size_metadata(model), {})
            second.write_bytes(b'b' * 2048)
            public = registry._public_model(model)
        self.assertEqual(public['size_bytes'], 3072)
        self.assertEqual(public['size_mb'], 3072 / (1024 * 1024))
        self.assertNotIn('size_bytes', model)

    def test_browser_load_profile_overrides_legacy_fields_and_auto_context(self):
        from backend.warsat.providers.native_llamacpp import NativeLlamaCppProvider
        profile = NativeLlamaCppProvider._profile({'context': 0, 'context_auto': True, 'n_gpu_layers': 0, 'split_mode': 'layer', 'load_profile': {'gpuLayers': 'auto', 'splitMode': 'auto', 'contextLength': 2048}})
        self.assertEqual(profile['gpuLayers'], 'auto')
        self.assertNotIn('gpu_layers', profile)
        self.assertNotIn('context_length', profile)
        self.assertNotIn('split_mode', profile)
        auto = NativeLlamaCppProvider._profile({'context': 0, 'context_auto': True, 'load_profile': {'gpuLayers': 'auto'}})
        self.assertNotIn('context_length', auto)

    def test_native_provider_discovers_same_manifest_as_runtime_settings(self):
        from backend.warsat.providers import native_llamacpp
        with tempfile.TemporaryDirectory() as directory:
            engine = Path(directory) / 'llama-server.exe'
            engine.write_bytes(b'test runtime')
            manifest = Path(directory) / 'manifest.json'
            with patch.dict(os.environ, {'RASPUTIN_DESKTOP_ONLY': '0', 'RASPUTIN_LLAMA_SERVER': ''}), patch.object(native_llamacpp, 'discover_manifest_path', return_value=manifest), patch.object(native_llamacpp, 'LlamaCppRuntimeService') as factory:
                factory.return_value.active_engine_path.return_value = str(engine)
                result = native_llamacpp._find_engine({})
            factory.assert_called_once_with(manifest_path=manifest)
            self.assertEqual(result, str(engine))

    def test_native_import_defaults_to_auto_placement_and_preserves_explicit_cpu(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.gguf"
            path.write_bytes(b"gguf")
            for supplied, expected in (({}, "auto"), ({"n_gpu_layers": 0}, 0)):
                with self.subTest(supplied=supplied), patch.object(registry, "_safe_file", return_value=path), patch.object(registry, "_gguf_already_imported", return_value=None), patch.object(registry, "next_port", return_value=18081), patch.object(registry.security, "require"), patch.object(registry.audit, "log"), patch.object(registry, "upsert", side_effect=lambda model: model):
                    model = registry.import_gguf({"path": str(path), **supplied})
                self.assertEqual(model["n_gpu_layers"], expected)
                self.assertEqual(model["split_mode"], "auto")

    def test_partial_load_profile_retains_saved_cpu_preference(self):
        from unittest.mock import Mock
        provider = Mock()
        provider.start.return_value = {"ok": True}
        model = {"key": "native", "runtime": "native-llamacpp", "managed": True}
        saved = {"models": {"memoryMode": "cpu_only"}, "resources": {"hostMemoryHeadroomMb": 3072}}
        with patch.object(registry, "get_model", return_value=model), patch.object(registry.runtime_store, "get_kv", return_value=saved), patch.object(registry, "get_provider", return_value=provider), patch.object(registry.security, "require") as require, patch.object(registry.audit, "log"):
            self.assertTrue(registry.start_model("native", {"contextLength": 2048})["ok"])
        passed = provider.start.call_args.args[0]
        self.assertEqual(passed["load_profile"], {"contextLength": 2048, "memory_mode": "cpu_only"})
        self.assertEqual(passed["host_memory_headroom_mb"], 3072)
        require.assert_called_once_with("allow_model_registry_edit")

    def test_native_logs_use_native_model_permission(self):
        from unittest.mock import Mock
        provider = Mock()
        provider.logs.return_value = {"ok": True, "logs": "load diagnostics"}
        with patch.object(registry, "get_model", return_value={"runtime": "native-llamacpp", "managed": True}), patch.object(registry, "get_provider", return_value=provider), patch.object(registry.security, "require") as require:
            result = registry.logs_model("native", 20)
        self.assertEqual(result["logs"], "load diagnostics")
        require.assert_called_once_with("allow_model_registry_edit")

    def test_artifact_registration_and_existing_models_have_readable_identity(self):
        artifact = {"artifact_id": "a1", "repository": "publisher/Small-Coder-GGUF", "variant_id": "gguf:1234", "quantization": "Q4_K_M", "main_model_path": "model.gguf"}
        with patch.object(registry, "import_gguf", side_effect=lambda value: value):
            registered = registry.register_artifact(artifact)
        self.assertEqual(registered["name"], "Small-Coder-GGUF (Q4_K_M)")
        public = registry._public_model({**artifact, "runtime": "native-llamacpp", "name": artifact["variant_id"]})
        self.assertEqual(public["name"], registered["name"])
        self.assertEqual(public["publisher"], "publisher")
        custom = registry._public_model({**artifact, "runtime": "native-llamacpp", "name": "My custom label"})
        self.assertEqual(custom["name"], "My custom label")
