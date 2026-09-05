"""Run source regressions with fresh state, real local auth, and owned processes.

This gate never connects to an operator instance or starts a real model. Browser
checks run against an owned temporary Native Host and may use explicit fixtures.
A passing source report is not installed-package or live-model certification.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.owned_process import owned_popen, stop_owned_process
GROUPS = ("documentation", "backend", "javascript", "desktop", "build", "browser")
BACKEND_TEST_MODULES = (
    "tests.testBackendSmoke", "tests.testAssistantContracts",
    "tests.testAssistantUiContract", "tests.testMemoryUiContract",
    "tests.testWorkModeUiContract", "tests.test_coding_acceptance",
    "tests.test_coder_certification_cli", "tests.testDiagnostics",
    "tests.testBackup", "tests.testBackupReliability", "tests.testHardwareCapabilities",
    "tests.testResourceBroker", "tests.testWarsatAdmission",
    "tests.testWarsatUiContract", "tests.test_model_fleet_certification",
    "tests.testVoiceProfiles", "tests.testMemoryRestart",
    "tests.testMcpSafety", "tests.testInstallationPreflight",
    "tests.testUiCertification", "tests.testWarsatAdvisor",
    "tests.testModelResourceManifest", "tests.testWarsatBenchmarks",
    "tests.testAdaptiveBudgets", "tests.testReleaseContract",
    "tests.testReleaseCandidate", "tests.testTaskRecoveryContract",
    "tests.testTrialsScorecards", "tests.testReleaseEvidence",
    "tests.testSourceRegressionRunner",
)


def isolated_environment(data_dir: Path, password: str) -> dict[str, str]:
    """Exclude inherited application settings and Python hooks from test children."""
    env = {
        key: value for key, value in os.environ.items()
        if not key.upper().startswith("RASPUTIN_")
        and key.upper() not in {"PYTHONHOME", "PYTHONPATH", "WRAPPER_RUNTIME"}
    }
    env.update({
        "RASPUTIN_DATA_DIR": str(data_dir),
        "RASPUTIN_ADMIN_PASSWORD": password,
        "RASPUTIN_DESKTOP_ONLY": "0",
        "RASPUTIN_LOCALHOST_BYPASS": "0",
        "RASPUTIN_TEST_AUTH_BYPASS": "0",
        "RASPUTIN_NATIVE_DOCKER_CACHE": "0",
        "WRAPPER_RUNTIME": "native",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "HOST": "127.0.0.1",
    })
    return env


def redact(output: str, password: str = "") -> str:
    """Bound diagnostic output and remove generated credentials and auth values."""
    if password:
        output = output.replace(password, "[redacted]")
    output = re.sub(r"(?i)bearer\s+\S+", "Bearer [redacted]", output)
    return re.sub(r"(?im)(password|secret|token|authorization)(\s*[:=]\s*)[^\r\n]+", r"\1\2[redacted]", output)


def run_check(name: str, command: list[str], env: dict[str, str], *, timeout: int = 900) -> dict:
    """Run one bounded gate and report failures without disclosing bootstrap secrets."""
    started = time.monotonic()
    process = None
    try:
        process = owned_popen(
            command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        stdout, stderr = process.communicate(timeout=timeout)
        output = redact(stdout + stderr, env.get("RASPUTIN_ADMIN_PASSWORD", ""))
        result = {
            "name": name, "passed": process.returncode == 0,
            "exitCode": process.returncode,
            "durationSeconds": round(time.monotonic() - started, 2),
            "outputTail": [line[:600] for line in output.splitlines() if line.strip()][-18:],
        }
        count = re.search(r"Ran (\d+) tests?", output)
        if not count:
            count = re.search(r"(?m)^# tests (\d+)", output)
        if count:
            result["testCount"] = int(count.group(1))
        skipped = re.search(r"(?m)^# skipped (\d+)", output) or re.search(r"OK \(skipped=(\d+)\)", output)
        if skipped:
            result["skipped"] = int(skipped.group(1))
        if name.startswith("browser") and (result.get("testCount", 0) <= 0 or result.get("skipped", 0)):
            result.update(passed=False, error="Browser fixture must run rather than skip.")
        return result
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"name": name, "passed": False, "exitCode": None, "error": redact(str(exc), env.get("RASPUTIN_ADMIN_PASSWORD", ""))}
    finally:
        if process is not None:
            stop_owned_process(process)


def javascript_tests(*, browser: bool = False) -> list[str]:
    """Discover all matching source tests; empty discovery is an error."""
    tests = sorted(
        str(path.relative_to(ROOT))
        for path in (ROOT / "tests").glob("*.test.mjs")
        if path.name.endswith(".browser.test.mjs") == browser
    )
    if not tests:
        raise RuntimeError("No browser tests found" if browser else "No JavaScript tests found")
    return tests


def browser_checks(env: dict[str, str], scratch: Path, artifacts: Path | None) -> list[dict]:
    """Start an isolated authenticated server, check fixtures, and release its state."""
    with socket.socket() as port_socket:
        port_socket.bind(("127.0.0.1", 0))
        port = port_socket.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"
    server_env = dict(env, PORT=str(port))
    log_path = scratch / "browser-server.log"
    results = []
    process = None
    try:
        with log_path.open("w", encoding="utf-8") as log:
            process = owned_popen(
                [sys.executable, "server.py"], cwd=ROOT, env=server_env,
                stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            # Verify the unique generated credential before any browser mutation.
            # A port collision must never cause fixtures to use another instance.
            deadline = time.monotonic() + 60
            authenticated = False
            while time.monotonic() < deadline and process.poll() is None:
                try:
                    request = urllib.request.Request(
                        base_url + "/api/auth/login",
                        data=json.dumps({"username": "admin", "password": env["RASPUTIN_ADMIN_PASSWORD"]}).encode(),
                        headers={"Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(request, timeout=2) as response:
                        authenticated = response.status == 200 and json.load(response).get("ok") is True
                    if authenticated:
                        break
                except (OSError, ValueError, urllib.error.URLError):
                    time.sleep(0.25)
            if not authenticated or process.poll() is not None:
                raise RuntimeError("Owned isolated browser server did not become ready.")
            browser_env = dict(
                server_env, RASPUTIN_TEST_BASE_URL=base_url,
                RASPUTIN_TEST_ADMIN_PASSWORD=env["RASPUTIN_ADMIN_PASSWORD"],
            )
            if artifacts:
                artifacts.mkdir(parents=True, exist_ok=True)
                browser_env["RASPUTIN_TEST_ARTIFACT_DIR"] = str(artifacts)
            for test_file in javascript_tests(browser=True):
                results.append(run_check("browser:" + Path(test_file).name, ["node", "--test", "--test-reporter=tap", test_file], browser_env, timeout=180))
    except (OSError, RuntimeError) as exc:
        details = redact(log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else "", env["RASPUTIN_ADMIN_PASSWORD"])
        results.append({"name": "browser:startup", "passed": False, "error": str(exc), "outputTail": details.splitlines()[-10:]})
    finally:
        if process is not None:
            stop_owned_process(process)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-build", action="store_true", help="Reuse frontend artifacts; report buildVerified=false.")
    parser.add_argument("--groups", nargs="+", choices=GROUPS, default=list(GROUPS))
    parser.add_argument("--browser-artifacts", type=Path, help="Optional directory for fixture screenshots, outside application data.")
    args = parser.parse_args(argv)
    groups = set(args.groups)
    checks = []
    def record(result):
        checks.append(result)
        if not args.json:
            count = f" ({result['testCount']} tests, {result.get('skipped', 0)} skipped)" if "testCount" in result else ""
            print(f"{'PASS' if result['passed'] else 'FAIL'} {result['name']}{count}", flush=True)
            if not result["passed"]:
                print("\n".join(result.get("outputTail", [])), flush=True)
    build_verified = False
    with tempfile.TemporaryDirectory(prefix="rasputin-source-regressions-") as temporary:
        scratch = Path(temporary)
        env = isolated_environment(scratch / "data", secrets.token_urlsafe(32))
        if groups.intersection({"build", "backend", "browser"}):
            if args.no_build:
                record({"name": "build", "passed": True, "skipped": True, "reason": "--no-build; existing assets are not fresh build evidence"})
            else:
                npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
                result = run_check("build", [npm, "run", "build"], env, timeout=300) if npm else {"name": "build", "passed": False, "error": "npm is not installed"}
                build_verified = result["passed"]
                record(result)
        if "documentation" in groups:
            record(run_check("documentation", [sys.executable, "scripts/verify_docs.py"], env, timeout=120))
        if "backend" in groups:
            # FastAPI mounts generated frontend assets during import, so a fresh
            # checkout must build before the first backend process imports main.
            if not (ROOT / "frontend/index.html").is_file() or (not args.no_build and not build_verified):
                record({"name": "backend:prerequisite", "passed": False, "error": "A successful frontend build is required before backend imports."})
            else:
                # Each module owns a separate process and data directory.
                for module in BACKEND_TEST_MODULES:
                    suite_env = dict(env, RASPUTIN_DATA_DIR=str(scratch / module))
                    record(run_check(module, [sys.executable, "-m", "unittest", module], suite_env))
        if "javascript" in groups:
            record(run_check("javascript", ["node", "--test", "--test-reporter=tap", "--test-concurrency=1", *javascript_tests()], env, timeout=180))
        if "desktop" in groups:
            for source in ("desktop/main.cjs", "desktop/backend-supervisor.cjs", "desktop/settings.cjs"):
                record(run_check("syntax:" + source, ["node", "--check", source], env, timeout=30))
            record(run_check("desktop:lifecycle", ["node", "--test", "--test-reporter=tap", "tests/desktopLifecycle.test.cjs"], env, timeout=120))
        if "browser" in groups:
            if not (ROOT / "frontend/index.html").is_file() or (not args.no_build and not build_verified):
                record({"name": "browser:prerequisite", "passed": False, "error": "A successful frontend build is required."})
            else:
                for result in browser_checks(env, scratch, args.browser_artifacts.resolve() if args.browser_artifacts else None):
                    record(result)
    report = {
        "schemaVersion": 1, "evidenceType": "source-regression",
        "passed": bool(checks) and all(check["passed"] for check in checks),
        "buildVerified": build_verified, "groups": sorted(groups), "checks": checks,
        "boundaries": ["Browser fixtures are source-app evidence, not installed-app, live-model, or hardware certification."],
    }
    print(json.dumps(report, indent=2) if args.json else f"Source regression result: {'PASS' if report['passed'] else 'FAIL'} ({len(checks)} checks)")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
