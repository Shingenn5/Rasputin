from __future__ import annotations

import os
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

os.environ.setdefault("RASPUTIN_DATA_DIR", os.path.join(os.getcwd(), ".test-runtime-api-data"))

from backend.api import core
from backend.core.response import AppError


class FakeManifest:
    def to_dict(self):
        return {"version": "b-test"}


class FakeRuntimeService:
    def __init__(self):
        self.calls = []

    def status(self):
        self.calls.append(("status",))
        return {"engine": "llama.cpp"}

    def select(self, hardware, runtime):
        self.calls.append(("select", hardware, runtime))
        return FakeManifest()

    def install(self, selection):
        self.calls.append(("install", selection))
        return {"version": "b-test"}

    def activate(self, version):
        self.calls.append(("activate", version))
        return {"version": version}

    def rollback(self):
        self.calls.append(("rollback",))
        return {"version": "b-previous"}

    def verify_active(self):
        self.calls.append(("verify_active",))
        return {"ok": True}


class LlamaCppRuntimeRoutesTests(IsolatedAsyncioTestCase):
    async def test_routes_delegate_to_service_without_process_launch(self):
        service = FakeRuntimeService()
        with patch.object(core, "_desktop_runtime_service", return_value=service):
            self.assertTrue((await core.llamacpp_runtime_status())["ok"])
            selected = await core.llamacpp_runtime_select(
                core.RuntimeSelectIn(hardware={"platform": "windows", "architecture": "x64", "accelerators": ["cpu"]})
            )
            installed = await core.llamacpp_runtime_install(
                core.RuntimeInstallIn(manifest={"engine": "llama.cpp", "version": "b-test"})
            )
            activated = await core.llamacpp_runtime_activate(core.RuntimeActivateIn(version="b-test"))
            rolled_back = await core.llamacpp_runtime_rollback()
            verified = await core.llamacpp_runtime_verify()

        self.assertEqual(service.calls, [
            ("status",),
            ("select", {"platform": "windows", "architecture": "x64", "accelerators": ["cpu"]}, None),
            ("install", {"engine": "llama.cpp", "version": "b-test"}),
            ("activate", "b-test"),
            ("rollback",),
            ("verify_active",),
        ])
        self.assertEqual(selected["data"], {"version": "b-test"})
        self.assertEqual(installed["data"], {"version": "b-test"})
        self.assertEqual(activated["data"], {"version": "b-test"})
        self.assertEqual(rolled_back["data"], {"version": "b-previous"})
        self.assertEqual(verified["data"], {"ok": True})

    async def test_install_requires_explicit_selection(self):
        with self.assertRaises(AppError) as raised:
            await core.llamacpp_runtime_install(core.RuntimeInstallIn())
        self.assertEqual(raised.exception.code, "runtime_selection_required")
        self.assertEqual(raised.exception.status, 409)

    async def test_factory_rejects_docker_mode(self):
        with patch.dict(os.environ, {"WRAPPER_RUNTIME": "docker"}):
            with self.assertRaises(AppError) as raised:
                core._desktop_runtime_service()
        self.assertEqual(raised.exception.code, "runtime_desktop_only")
        self.assertEqual(raised.exception.status, 409)


if __name__ == "__main__":
    unittest.main()
