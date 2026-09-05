"""Behavioral checks for isolated regression orchestration."""
from contextlib import redirect_stdout
import io
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from scripts import verify_source_regressions as runner
from scripts import owned_process


class SourceRegressionRunnerTests(unittest.TestCase):
    def test_isolation_overrides_operator_data_and_auth_bypass(self):
        with patch.dict(os.environ, {"RASPUTIN_DATA_DIR": "operator-data", "RASPUTIN_DESKTOP_ONLY": "1", "PYTHONPATH": "inherited", "WRAPPER_RUNTIME": "docker"}):
            env = runner.isolated_environment(Path("isolated-data"), "fixture-password")
        self.assertEqual(env["RASPUTIN_DATA_DIR"], "isolated-data")
        self.assertEqual(env["RASPUTIN_DESKTOP_ONLY"], "0")
        self.assertEqual(env["RASPUTIN_TEST_AUTH_BYPASS"], "0")
        self.assertEqual(env["WRAPPER_RUNTIME"], "native")
        self.assertNotIn("PYTHONPATH", env)

    def test_browser_discovery_cannot_silently_pass_without_fixtures(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner, "ROOT", Path(temporary)):
            with self.assertRaisesRegex(RuntimeError, "No browser tests"):
                runner.javascript_tests(browser=True)
        with patch.object(runner, "owned_popen") as launch, patch.object(runner, "stop_owned_process"):
            process = launch.return_value
            process.communicate.return_value = ("# tests 0\n# skipped 0\n", "")
            process.returncode = 0
            result = runner.run_check("browser:zero-tests", ["node", "--test"], {})
        self.assertEqual(0, result["testCount"])
        self.assertFalse(result["passed"], "Zero executed browser tests must fail")

    def test_discovery_keeps_browser_gates_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "tests").mkdir()
            for name in ("contract.test.mjs", "actual.browser.test.mjs", "desktop.test.cjs"):
                (root / "tests" / name).touch()
            with patch.object(runner, "ROOT", root):
                self.assertEqual([Path(x).name for x in runner.javascript_tests()], ["contract.test.mjs"])
                self.assertEqual([Path(x).name for x in runner.javascript_tests(browser=True)], ["actual.browser.test.mjs"])

    def test_browser_report_requires_executed_unskipped_tests(self):
        for output, expected in (
            ("", False),
            ("# tests 0\n# skipped 0", False),
            ("# tests 1\n# skipped 1", False),
            ("# tests 1\n# skipped 0", True),
        ):
            with self.subTest(output=output):
                process = MagicMock(returncode=0)
                process.communicate.return_value = (output, "")
                with patch.object(runner, "owned_popen", return_value=process), patch.object(runner, "stop_owned_process"):
                    result = runner.run_check("browser:fixture", ["node", "--test"], {})
                self.assertEqual(expected, result["passed"])

    def test_fresh_checkout_builds_before_backend_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calls = []
            def execute(name, command, env, **kwargs):
                calls.append(name)
                if name == "build":
                    (root / "frontend").mkdir()
                    (root / "frontend/index.html").write_text("fixture")
                else:
                    self.assertTrue((root / "frontend/index.html").is_file())
                return {"name": name, "passed": True}
            with patch.object(runner, "ROOT", root), patch.object(runner, "BACKEND_TEST_MODULES", ("fixture",)), patch.object(runner.shutil, "which", return_value="npm"), patch.object(runner, "run_check", side_effect=execute), redirect_stdout(io.StringIO()):
                self.assertEqual(0, runner.main(["--groups", "backend"]))
            self.assertEqual(["build", "fixture"], calls)

    def test_failed_build_blocks_backend_even_with_old_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "frontend").mkdir()
            (root / "frontend/index.html").write_text("stale")
            with patch.object(runner, "ROOT", root), patch.object(runner.shutil, "which", return_value="npm"), patch.object(runner, "run_check", return_value={"name": "build", "passed": False}) as run, redirect_stdout(io.StringIO()):
                self.assertEqual(1, runner.main(["--groups", "backend"]))
            self.assertEqual(1, run.call_count)
            self.assertEqual("build", run.call_args.args[0])

    def test_no_build_requires_existing_assets_before_backend(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner, "ROOT", Path(temporary)), patch.object(runner, "run_check") as run, redirect_stdout(io.StringIO()):
            self.assertEqual(1, runner.main(["--groups", "backend", "--no-build"]))
            run.assert_not_called()

    def test_diagnostics_redact_generated_and_header_credentials(self):
        output = runner.redact("password: fixture-password\nAuthorization: Bearer abc123", "fixture-password")
        self.assertNotIn("fixture-password", output)
        self.assertNotIn("abc123", output)

@unittest.skipUnless(os.name == "nt", "Windows Job ownership contract")
class OwnedProcessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rasputin-owned-process-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.env = runner.isolated_environment(self.root / "data", "fixture-password")

    def assertOwnedChildGone(self, record):
        import psutil
        try:
            child = psutil.Process(record["pid"])
        except psutil.NoSuchProcess:
            return
        if abs(child.create_time() - record["createdAt"]) > 0.01:
            return  # The original process exited and the PID was reused.
        still_running = child.is_running()
        if still_running:
            # A failing regression must not leave its own synthetic child behind.
            child.kill()
            child.wait(timeout=5)
        self.assertFalse(still_running, "Owned descendant survived gate cleanup")

    def wrapper(self, *, linger=False):
        record = self.root / "child.json"
        code = (
            "import json, pathlib, subprocess, sys, time, psutil;"
            "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],"
            "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);"
            "identity={'pid':child.pid,'createdAt':psutil.Process(child.pid).create_time()};"
            f"pathlib.Path({str(record)!r}).write_text(json.dumps(identity));"
            "print('owned wrapper ready',flush=True);"
            + ("time.sleep(60)" if linger else "")
        )
        return [sys.executable, "-c", code], record

    def test_exited_wrapper_retains_descendant_ownership(self):
        command, record = self.wrapper()
        sentinel = owned_process.owned_popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            env=self.env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            result = runner.run_check("owned-exit", command, self.env, timeout=15)
            self.assertTrue(result["passed"], result)
            self.assertEqual(0, result["exitCode"])
            self.assertIn("owned wrapper ready", result["outputTail"])
            self.assertOwnedChildGone(json.loads(record.read_text()))
            self.assertIsNone(sentinel.poll(), "A separately launched process must remain untouched")
        finally:
            owned_process.stop_owned_process(sentinel)

    def test_timeout_stops_wrapper_and_redirected_descendant(self):
        command, record = self.wrapper(linger=True)
        result = runner.run_check("owned-timeout", command, self.env, timeout=5)
        self.assertFalse(result["passed"])
        self.assertIn("timed out", result["error"])
        self.assertTrue(record.exists(), "Wrapper reached descendant startup before timeout")
        self.assertOwnedChildGone(json.loads(record.read_text()))

    def test_startup_failure_never_executes_unowned_child(self):
        original_popen = subprocess.Popen
        marker = self.root / "must-not-run"
        for phase in ("assign", "resume"):
            with self.subTest(phase=phase):
                children = []
                def capture(*args, **kwargs):
                    process = original_popen(*args, **kwargs)
                    children.append(process)
                    return process
                with patch.object(owned_process.subprocess, "Popen", side_effect=capture), patch.object(
                    owned_process._WindowsJob, phase, side_effect=OSError("injected ownership failure"),
                ):
                    result = runner.run_check("owned-startup", [
                        sys.executable, "-c",
                        f"from pathlib import Path; Path({str(marker)!r}).write_text('unexpected')",
                    ], self.env, timeout=10)
                self.assertFalse(result["passed"])
                self.assertIn("injected ownership failure", result["error"])
                self.assertFalse(marker.exists(), "Code ran before ownership and safe resume")
                self.assertEqual(1, len(children))
                self.assertIsNotNone(children[0].poll(), "Failed suspended startup was retained")

    def test_job_creation_failure_does_not_launch_any_process(self):
        with patch.object(owned_process, "_WindowsJob", side_effect=OSError("job unavailable")), patch.object(
            owned_process.subprocess, "Popen",
        ) as launch:
            result = runner.run_check("owned-no-job", [sys.executable, "-c", "raise SystemExit(0)"], self.env)
        self.assertFalse(result["passed"])
        launch.assert_not_called()

    def test_missing_executable_fails_without_retaining_job_handle(self):
        original_job = owned_process._WindowsJob
        jobs = []
        def create():
            job = original_job()
            jobs.append(job)
            return job
        with patch.object(owned_process, "_WindowsJob", side_effect=create):
            result = runner.run_check("owned-missing", [str(self.root / "missing.exe")], self.env)
        self.assertFalse(result["passed"])
        self.assertEqual(1, len(jobs))
        self.assertIsNone(jobs[0].handle)


if __name__ == "__main__":
    unittest.main()
