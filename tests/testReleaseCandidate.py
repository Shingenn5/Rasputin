import contextlib
import io
import json
import subprocess
import unittest
from unittest.mock import MagicMock, patch

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
        self.assertIn("tests.testMcpSafety", verify_release_candidate.BACKEND_TEST_MODULES)
        self.assertIn("tests.testInstallationPreflight", verify_release_candidate.BACKEND_TEST_MODULES)
        self.assertIn("tests.testUiCertification", verify_release_candidate.BACKEND_TEST_MODULES)

    def test_release_gate_includes_frozen_v1_contract(self):
        self.assertIn("tests.testReleaseContract", verify_release_candidate.BACKEND_TEST_MODULES)


class ReleaseCandidateReportingTests(unittest.TestCase):
    def setUp(self):
        self.source = {"commit": "a" * 40, "dirty": False, "sha256": "b" * 64}
        self.patches = [
            patch("scripts.release_evidence.source_identity", return_value=self.source),
            patch.object(verify_release_candidate, "_run", return_value={"passed": True, "details": {"passed": True, "buildVerified": True}}),
            patch.object(verify_release_candidate, "_frontend_artifacts", return_value={"passed": True}),
            patch.object(verify_release_candidate, "_deployment", return_value={"passed": True}),
        ]
        self.mocks = [item.start() for item in self.patches]
        for item in self.patches:
            self.addCleanup(item.stop)

    def run_report(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = verify_release_candidate.main(list(args))
        return code, json.loads(output.getvalue())

    def test_default_endpoints_are_empty_and_target_must_be_selected(self):
        self.assertEqual((), verify_release_candidate.DEFAULT_ENDPOINTS)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            verify_release_candidate.main([])
        self.mocks[1].assert_not_called()
        self.mocks[3].assert_not_called()

    def test_explicit_native_alias_preserves_candidate_exit_code_without_certifying_release(self):
        code, report = self.run_report("--endpoint", "native=http://127.0.0.1:8899")
        self.assertEqual(0, code)
        self.assertTrue(report["passed"])
        self.assertFalse(report["releaseReady"])
        self.assertEqual("native-host", report["subject"]["target"])
        self.assertEqual(8, len(report["knownBoundaries"]))
        self.mocks[3].assert_called_once_with(["native=http://127.0.0.1:8899"], False)

    def test_require_ready_fails_when_required_evidence_is_missing(self):
        code, report = self.run_report("--target", "native-host", "--require-ready")
        self.assertEqual(1, code)
        self.assertFalse(report["releaseReady"])

    def test_identity_only_does_not_run_commands_or_probe(self):
        code, report = self.run_report("--target", "native-host", "--identity-only")
        self.assertEqual(0, code)
        self.assertEqual(self.source, report["subject"]["source"])
        self.mocks[1].assert_not_called()
        self.mocks[3].assert_not_called()

    def test_desktop_requires_actual_selected_package(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            verify_release_candidate.main(["--target", "desktop"])
        self.mocks[1].assert_not_called()

    def test_target_validation_rejects_retired_mixed_mismatched_and_remote_desktop(self):
        options = [
            ["--endpoint", "docker=http://127.0.0.1:8787"],
            ["--endpoint", "native=http://127.0.0.1:8899", "--endpoint", "desktop=http://127.0.0.1:8900"],
            ["--target", "desktop", "--endpoint", "native=http://127.0.0.1:8899"],
            ["--endpoint", "desktop=http://192.168.1.2:8788"],
            ["--endpoint", "native=http://user:secret@127.0.0.1:8899"],
        ]
        for args in options:
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                verify_release_candidate.main(args)
        self.mocks[1].assert_not_called()

    def test_valid_evidence_is_used_to_compute_ready_status(self):
        with patch("scripts.release_evidence.evaluate", return_value={"passed": True, "rows": [], "rejectedRecords": []}):
            code, report = self.run_report("--target", "native-host", "--require-ready")
        self.assertEqual(0, code)
        self.assertTrue(report["releaseReady"])
        self.assertEqual("release_ready", report["status"])
        self.assertEqual([], report["knownBoundaries"])

    def test_no_build_cannot_certify_automated_release_evidence(self):
        code, report = self.run_report("--target", "native-host", "--no-build")
        self.assertEqual(0, code)
        self.assertFalse(report["buildVerified"])
        self.assertFalse(report["releaseReady"])
        self.assertEqual("automatedRegression", report["knownBoundaries"][0]["id"])
        self.assertIn("--no-build", self.mocks[1].call_args.args[1])

    def test_source_change_during_verification_fails_gate(self):
        self.mocks[0].side_effect = [self.source, {**self.source, "sha256": "c" * 64}]
        code, report = self.run_report("--target", "native-host")
        self.assertEqual(1, code)
        self.assertFalse(report["checks"]["identityStable"]["passed"])

    def test_child_python_environment_does_not_inherit_python_home_or_path(self):
        with patch.dict("os.environ", {"PYTHONHOME": "unusable", "PYTHONPATH": "unusable"}):
            self.run_report("--target", "native-host")
        env = self.mocks[1].call_args.kwargs["env"]
        self.assertNotIn("PYTHONHOME", env)
        self.assertNotIn("PYTHONPATH", env)

    def test_redaction_removes_authorization_value_and_spaced_secrets(self):
        text = "Authorization: Bearer abcdef123456\npassword = private words\n"
        redacted = verify_release_candidate._redact(text)
        self.assertNotIn("abcdef123456", redacted)
        self.assertNotIn("private words", redacted)
        details = verify_release_candidate._redact_details({"token": "abc", "nested": ["Bearer 123"]})
        self.assertEqual("[redacted]", details["token"])
        self.assertNotIn("123", details["nested"][0])


class ReleaseSubprocessTests(unittest.TestCase):
    def test_timeout_stops_owned_harness_and_descendants(self):
        process = MagicMock()
        process.communicate.side_effect = subprocess.TimeoutExpired(["test"], 1)
        with patch.object(verify_release_candidate, "owned_popen", return_value=process), patch.object(verify_release_candidate, "stop_owned_process") as stop:
            result = verify_release_candidate._run("source", ["test"], timeout=1)
        self.assertFalse(result["passed"])
        stop.assert_called_once_with(process)

    def test_json_report_must_be_an_object_with_passing_result(self):
        for payload in ("invalid", "[]", '{"passed":false}', '{"passed":true}'):
            with self.subTest(payload=payload):
                process = MagicMock(returncode=0)
                process.communicate.return_value = (payload, "")
                with patch.object(verify_release_candidate, "owned_popen", return_value=process), patch.object(verify_release_candidate, "stop_owned_process"):
                    result = verify_release_candidate._run("source", ["test"], json_report=True)
                self.assertEqual(payload == '{"passed":true}', result["passed"])


if __name__ == "__main__":
    unittest.main()
