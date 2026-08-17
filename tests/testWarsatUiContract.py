import unittest
from pathlib import Path


class WarsatUiContractTests(unittest.TestCase):
    def test_model_actions_send_the_card_registry_key(self):
        app_source = (Path(__file__).resolve().parents[1] / "frontend-src" / "src" / "app" / "App.jsx").read_text(encoding="utf-8")
        models_source = (Path(__file__).resolve().parents[1] / "frontend-src" / "src" / "features" / "models" / "ModelsView.jsx").read_text(encoding="utf-8")
        self.assertIn("async function runModelAction(action, key)", app_source)
        self.assertIn("const resolvedKey = typeof key === \"string\" ? key.trim() : \"\";", app_source)
        self.assertIn("key: resolvedKey", app_source)
        self.assertIn("runModelAction?.(op, model.key)", models_source)
        self.assertIn('runModelAction?.("test", model?.key)', models_source)

    def test_launch_brief_surfaces_resource_admission_and_locks_unsafe_states(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "frontend-src"
            / "src"
            / "features"
            / "warsat"
            / "WarsatView.jsx"
        ).read_text(encoding="utf-8")
        self.assertIn("resourceAdmission", source)
        self.assertIn("resourceAdmissionBlocked", source)
        self.assertIn("data-testid=\"warsat-resource-admission\"", source)
        self.assertIn("const admittedResource = resourceAdmission || plan?.resourceAdmission || null;", source)
        self.assertIn("const admittedResourceStatus = resourceAdmissionStatus || admittedResource?.status || \"unmeasured\";", source)
        self.assertIn("Resource admission blocked", source)
        self.assertIn("Waiting for capacity", source)

    def test_plan_paths_submit_fresh_hardware_capacity_evidence(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "frontend-src"
            / "src"
            / "app"
            / "App.jsx"
        ).read_text(encoding="utf-8")
        self.assertIn("const [nextWarsat, runtimes, hardware]", source)
        self.assertIn("loaded?.hardware?.capabilityProfile", source)
        self.assertIn("const hardware = await loadWarsatHardware();", source)
        self.assertIn("hardware?.capabilityProfile || warsatHardware?.capabilityProfile", source)

    def test_model_download_progress_is_visible_and_reload_safe(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "frontend-src"
            / "src"
            / "features"
            / "warsat"
            / "WarsatView.jsx"
        ).read_text(encoding="utf-8")
        self.assertIn("/api/warsat/download-progress?containerName=", source)
        self.assertIn('data-testid={compact ? "warsat-container-download-progress" : "warsat-download-progress"}', source)
        self.assertIn("Downloading model weights", source)
        self.assertIn("percentage unavailable", source)
        self.assertIn("{hasTrustedPercent && (", source)
        self.assertIn("progress.progressTrusted === true", source)
        self.assertIn("Number.isFinite(downloaded)", source)
        self.assertIn("const runningNamesKey", source)


if __name__ == "__main__":
    unittest.main()
