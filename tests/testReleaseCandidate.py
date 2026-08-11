import unittest

from scripts import verify_release_candidate


class ReleaseCandidateContractTests(unittest.TestCase):
    def test_release_gate_includes_current_ui_contract_modules(self):
        self.assertIn("tests.testAssistantUiContract", verify_release_candidate.BACKEND_TEST_MODULES)
        self.assertIn("tests.testMemoryUiContract", verify_release_candidate.BACKEND_TEST_MODULES)
        self.assertIn("tests.testWorkModeUiContract", verify_release_candidate.BACKEND_TEST_MODULES)
        self.assertIn("tests.testWarsatAdmission", verify_release_candidate.BACKEND_TEST_MODULES)
        self.assertIn("tests.testWarsatUiContract", verify_release_candidate.BACKEND_TEST_MODULES)
        self.assertIn("tests.test_model_fleet_certification", verify_release_candidate.BACKEND_TEST_MODULES)
        self.assertIn("tests.testVoiceProfiles", verify_release_candidate.BACKEND_TEST_MODULES)
        self.assertIn("tests.testMemoryRestart", verify_release_candidate.BACKEND_TEST_MODULES)

    def test_release_gate_includes_frozen_v1_contract(self):
        self.assertIn("tests.testReleaseContract", verify_release_candidate.BACKEND_TEST_MODULES)


if __name__ == "__main__":
    unittest.main()
