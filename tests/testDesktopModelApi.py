from __future__ import annotations

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("RASPUTIN_DATA_DIR", tempfile.mkdtemp(prefix="rasputin-desktop-api-tests-"))

from fastapi.testclient import TestClient

from backend import main
from backend.api import core
from backend.api.core import current_user, require_admin
from backend.models import acquisition as model_acquisition


class FakeDesktopService:
    def __init__(self):
        self.calls = []

    def start_variant_download(self, model_id, variant):
        self.calls.append(("start_variant_download", model_id, variant))
        return {"id": "job-1"}

    def list_jobs(self):
        self.calls.append(("list_jobs",))
        return [{"id": "job-1"}]

    def get_job(self, job_id):
        self.calls.append(("get_job", job_id))
        return {"id": job_id}

    def pause(self, job_id):
        self.calls.append(("pause", job_id))
        return {"id": job_id, "state": "paused"}

    def resume(self, job_id):
        self.calls.append(("resume", job_id))
        return {"id": job_id, "state": "downloading"}

    def cancel(self, job_id):
        self.calls.append(("cancel", job_id))
        return {"id": job_id, "state": "cancelled"}

    def retry(self, job_id):
        self.calls.append(("retry", job_id))
        return {"id": job_id, "state": "queued"}


class DesktopModelApiTests(unittest.TestCase):
    def setUp(self):
        main.app.dependency_overrides[current_user] = lambda: {"username": "admin", "role": "admin"}
        main.app.dependency_overrides[require_admin] = lambda: {"username": "admin", "role": "admin"}
        self.client = TestClient(main.app, base_url="http://127.0.0.1", raise_server_exceptions=False)

    def tearDown(self):
        main.app.dependency_overrides.clear()

    def test_model_id_compatibility_and_exact_variant_download(self):
        with patch.object(model_acquisition, "start_download", return_value={"id": "legacy"}) as legacy:
            response = self.client.post("/api/models/download", json={"modelId": "org/model"})
        self.assertEqual(response.status_code, 200, response.text)
        legacy.assert_called_once_with("org/model")

        variant = {
            "id": "org/model:q4",
            "repository": "org/model",
            "revision": "abc123",
            "files": ["model-Q4_K_M.gguf"],
            "modelFiles": ["model-Q4_K_M.gguf"],
            "mmprojFiles": [],
            "totalBytes": 123,
        }
        service = FakeDesktopService()
        with patch.object(core, "DesktopAcquisitionService", return_value=service):
            response = self.client.post("/api/models/download/variant", json={
                "modelId": "org/model", "variant": variant,
            })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(service.calls, [("start_variant_download", "org/model", variant)])
        self.assertEqual(response.json()["data"]["id"], "job-1")

    def test_download_job_reads_and_actions_delegate(self):
        service = FakeDesktopService()
        with patch.object(core, "DesktopAcquisitionService", return_value=service):
            response = self.client.get("/api/models/downloads")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["data"], [{"id": "job-1"}])
            response = self.client.get("/api/models/downloads/job-1")
            self.assertEqual(response.status_code, 200, response.text)
            for action in ("pause", "resume", "cancel", "retry"):
                response = self.client.post(f"/api/models/downloads/job-1/{action}")
                self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(service.calls, [
            ("list_jobs",), ("get_job", "job-1"),
            ("pause", "job-1"), ("resume", "job-1"),
            ("cancel", "job-1"), ("retry", "job-1"),
        ])

    def test_mutating_download_routes_require_admin(self):
        main.app.dependency_overrides.pop(require_admin, None)
        main.app.dependency_overrides[current_user] = lambda: {"username": "member", "role": "member"}
        response = self.client.post("/api/models/downloads/job-1/pause")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "permissionDenied")

    def test_catalog_detail_passes_variants_and_load_preview_is_planning_only(self):
        detail = {"modelId": "org/model", "variants": [{"id": "v1", "files": ["model.gguf"]}]}
        with patch.object(core.model_catalog, "hf_model_detail", return_value=detail) as catalog:
            response = self.client.get("/api/model-catalog/model/org/model")
        self.assertEqual(response.status_code, 200, response.text)
        catalog.assert_called_once_with("org/model")
        self.assertEqual(response.json()["data"]["variants"][0]["id"], "v1")

        plan = SimpleNamespace(to_dict=lambda: {"accepted": True, "command": ["llama-server"]})
        with patch.object(core.model_load_profiles, "resolve_load_plan", return_value=plan) as resolver:
            response = self.client.post("/api/model-catalog/load-plan-preview", json={
                "profile": {"contextLength": 4096},
                "hardware": {"devices": []},
                "modelMetadata": {"parameterCountB": 1},
                "runtimeCapabilities": {"supportedFlags": []},
            })
        self.assertEqual(response.status_code, 200, response.text)
        resolver.assert_called_once_with(
            {"contextLength": 4096},
            hardware={"devices": []},
            model={"parameterCountB": 1},
            capabilities={"supportedFlags": []},
            engine="llama-server",
            model_path=None,
        )
        self.assertTrue(response.json()["data"]["accepted"])


if __name__ == "__main__":
    unittest.main()
