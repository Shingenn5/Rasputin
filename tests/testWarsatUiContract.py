import unittest
from pathlib import Path


class WarsatUiContractTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
