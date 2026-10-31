"""Live native UI verification with real authentication and disposable execution state.

Build the frontend first. Run with .venv Python and --scratch-dir pointing to an
existing external directory. Evidence stays there; the owned server/data are removed.
"""
import argparse
import gc
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8899)
    parser.add_argument("--runtime-setup", action="store_true", help="Verify managed runtime download and execution from an unconfigured application")
    parser.add_argument("--backend-executable", type=Path, help="Verify a specific packaged backend instead of the source server")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    scratch = args.scratch_dir.resolve(strict=True)
    if not args.scratch_dir.is_absolute() or root.is_relative_to(scratch) or scratch.is_relative_to(root):
        parser.error("Select an absolute scratch directory outside the source checkout.")
    if os.name != "nt" or not 1024 <= args.port <= 65535:
        parser.error("This verification requires Windows and an unprivileged test port.")
    if args.backend_executable and (not args.backend_executable.is_absolute() or not args.backend_executable.is_file()):
        parser.error("Select an existing absolute packaged backend executable.")
    with socket.socket() as check:
        check.bind(("127.0.0.1", args.port))
    artifacts = scratch / ("sandbox-review-evidence-" + uuid.uuid4().hex[:12])
    artifacts.mkdir()
    sys.path.insert(0, str(root))
    base_url = f"http://127.0.0.1:{args.port}"
    with tempfile.TemporaryDirectory(prefix="sandbox-review-live-", dir=scratch) as temporary:
        base = Path(temporary).resolve()
        assert base.is_relative_to(scratch)
        data, source = base / "data", base / "review-workspace"
        source.mkdir()
        admin_password, member_password = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        os.environ.update(RASPUTIN_DATA_DIR=str(data), RASPUTIN_ADMIN_USER="admin", RASPUTIN_ADMIN_PASSWORD=admin_password,
                          RASPUTIN_DESKTOP_ONLY="0", RASPUTIN_LOCALHOST_BYPASS="0",
                          RASPUTIN_TEST_AUTH_BYPASS="0",
                          PORT=str(args.port), HOST="127.0.0.1", RASPUTIN_HTTPS="0")
        from backend.core import auth, security, workspace
        from backend.core import sandbox_execution as execution
        auth.bootstrap()
        auth.create_user("reviewmember", member_password, role="member")
        workspace.add(str(source), owner_username="admin", permission_profile={"read": True, "write": True})
        workspace.set_member(str(source), "reviewmember", "contributor")
        security.save({"allow_file_read": True, "allow_shell_execution": True})
        executable = shutil.which("node")
        if not executable:
            raise RuntimeError("The maintainer fixture requires an installed Node runtime.")
        fixtures = {}
        if not args.runtime_setup:
            execution.configure_toolchain(executable, "admin")
        for name, owner, code in ([] if args.runtime_setup else [
            ("passing", "admin", "// captured-version-marker\n// <img src=snapshot-xss onerror=alert(1)>\nconsole.log('captured-version-marker');"),
            ("denied", "admin", "console.log('denied fixture should never run');"),
            ("slow", "admin", "setInterval(() => {}, 1000);"),
            ("foreign", "reviewmember", "console.log('foreign-private-output');"),
        ]):
            (source / "worker_fixture.cjs").write_text(code, encoding="utf-8")
            request = execution.create_request(owner, str(source), ["worker_fixture.cjs"],
                        ["--preserve-symlinks", "--preserve-symlinks-main", "worker_fixture.cjs", "long-argument-" * 50], timeout=30)
            fixtures[name] = {"approvalId": request["approval_id"], "requestId": request["plan"]["request_id"]}
        (source / "worker_fixture.cjs").write_text("console.log('managed-runtime-ready', process.version);" if args.runtime_setup else "// later-source-version", encoding="utf-8")
        with (artifacts / "server.log").open("w", encoding="utf-8") as log:
            command = [str(args.backend_executable)] if args.backend_executable else [sys.executable, str(root / "server.py")]
            server = subprocess.Popen(command, cwd=root, stdout=log, stderr=log,
                                      env=os.environ.copy(), creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                deadline = time.monotonic() + 45
                while True:
                    if server.poll() is not None:
                        raise RuntimeError("Isolated server exited before readiness")
                    try:
                        with urllib.request.urlopen(base_url + "/api/auth/session", timeout=1) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        pass
                    if time.monotonic() > deadline:
                        raise TimeoutError("Isolated server readiness expired")
                    time.sleep(.2)
                test_env = {**os.environ, "RASPUTIN_TEST_BASE_URL": base_url,
                            "RASPUTIN_TEST_PASSWORD": admin_password, "RASPUTIN_TEST_MEMBER_PASSWORD": member_password,
                            "RASPUTIN_REVIEW_FIXTURES": json.dumps(fixtures), "RASPUTIN_RUNTIME_WORKSPACE": str(source)}
                result = subprocess.run(["node", str(root / "node_modules/@playwright/test/cli.js"), "test",
                                         "tests/ui/sandboxRuntimeSetup.spec.mjs" if args.runtime_setup else "tests/ui/sandboxApprovalReview.spec.mjs", "--project=chromium", "--reporter=list",
                                         "--output", str(artifacts / "browser")], cwd=root, env=test_env)
            finally:
                server.terminate()
                try:
                    server.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
                execution.recover()
                gc.collect()  # release SQLite context-managed connections before Windows cleanup
    print(f"Verification evidence: {artifacts}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
