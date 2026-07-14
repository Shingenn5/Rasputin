"""Lifecycle manager for Rasputin's persistent native host.

The desktop application owns an ephemeral loopback backend. Native Host is the
long-running alternative for multiple browser users: it has a stable port,
survives the controlling terminal, and can be started at Windows logon.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import json
import os
import secrets
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import psutil

from backend.core.datadir import data_dir


ROOT = Path(__file__).resolve().parents[2]
AUTOSTART_NAME = "Rasputin Native Host"
AUTOSTART_KEY = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
DEFAULT_PORT = 8788


WINDOWS_PROCESS_BROKER_SCRIPT = r"""
$ErrorActionPreference = "Stop"
$environmentVariables = @(
    [System.Environment]::GetEnvironmentVariables().GetEnumerator() |
        Where-Object { $_.Key -notlike "RASPUTIN_NATIVE_BROKER_*" } |
        ForEach-Object { "{0}={1}" -f $_.Key, $_.Value }
)
$startupClass = Get-CimClass -ClassName Win32_ProcessStartup
$startup = New-CimInstance -CimClass $startupClass -ClientOnly -Property @{
    ShowWindow = [uint16]0
    EnvironmentVariables = [string[]]$environmentVariables
}
$result = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = $env:RASPUTIN_NATIVE_BROKER_COMMAND
    CurrentDirectory = $env:RASPUTIN_NATIVE_BROKER_CWD
    ProcessStartupInformation = $startup
}
if ($result.ReturnValue -ne 0) {
    throw "Win32_Process.Create failed with return value $($result.ReturnValue)."
}
[PSCustomObject]@{
    returnValue = [int]$result.ReturnValue
    processId = [int]$result.ProcessId
} | ConvertTo-Json -Compress
"""


def _paths(selected_data_dir: Path | None = None) -> dict[str, Path]:
    root = Path(selected_data_dir or data_dir()).resolve()
    return {
        "data": root,
        "state": root / "native-host.json",
        "config": root / "native-host-config.json",
        "stop": root / "native-host.stop",
        "desktop": root / "desktop-runtime.json",
        "log": root / "logs" / "native-host.log",
    }


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _pid_alive(pid: object) -> bool:
    try:
        process = psutil.Process(int(pid))
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except (TypeError, ValueError, psutil.Error):
        return False


def _state(paths: dict[str, Path]) -> dict:
    state = _read_json(paths["state"])
    if state and not _pid_alive(state.get("pid")):
        paths["state"].unlink(missing_ok=True)
        return {}
    return state


def _desktop_runtime(paths: dict[str, Path]) -> dict:
    state = _read_json(paths["desktop"])
    if state and not (_pid_alive(state.get("ownerPid")) or _pid_alive(state.get("pid"))):
        paths["desktop"].unlink(missing_ok=True)
        return {}
    return state


def _health_ready(url: str, timeout: float = 1.0) -> bool:
    context = ssl._create_unverified_context() if url.startswith("https://") else None
    try:
        with urllib.request.urlopen(f"{url}/api/health", timeout=timeout, context=context) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def _tls_config(require_https: bool) -> tuple[Path | None, Path | None, list[str]]:
    tls_dir = Path(os.environ.get("RASPUTIN_TLS_DIR") or ROOT / "data" / "tls")
    cert = tls_dir / "rasputin.pem"
    key = tls_dir / "rasputin-key.pem"
    if not cert.is_file() or not key.is_file():
        if require_https:
            raise RuntimeError(
                "Native Host LAN mode requires HTTPS. Run '.\\rasputin.ps1 setup-https' first, "
                "or pass --allow-http only on a trusted isolated network."
            )
        return None, None, []
    hosts_path = tls_dir / "hosts.txt"
    hosts = []
    if hosts_path.is_file():
        hosts = [line.strip() for line in hosts_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return cert, key, hosts


def _effective_config(args: argparse.Namespace, paths: dict[str, Path]) -> dict:
    saved = _read_json(paths["config"])
    port = args.port if args.port is not None else int(saved.get("port") or DEFAULT_PORT)
    lan = args.lan if args.lan is not None else bool(saved.get("lan", False))
    allow_http = args.allow_http if args.allow_http is not None else bool(saved.get("allow_http", False))
    allowed_hosts = args.allowed_host if args.allowed_host is not None else list(saved.get("allowed_hosts") or [])
    return {"port": int(port), "lan": lan, "allow_http": allow_http, "allowed_hosts": allowed_hosts}


def _run_server(args: argparse.Namespace, paths: dict[str, Path]) -> int:
    desktop = _desktop_runtime(paths)
    if desktop:
        print(f"Rasputin Desktop already owns this data store at {desktop.get('url')}.", file=sys.stderr)
        return 2
    existing = _state(paths)
    if existing and int(existing.get("pid", 0)) != os.getpid():
        print(f"Native Host is already running (PID {existing['pid']}).", file=sys.stderr)
        return 2

    host = os.environ.get("RASPUTIN_HOST_BIND") or ("0.0.0.0" if args.lan else "127.0.0.1")
    port = int(args.port or os.environ.get("PORT", str(DEFAULT_PORT)))
    scheme = "https" if os.environ.get("RASPUTIN_HTTPS") == "1" else "http"
    browser_host = os.environ.get("RASPUTIN_BROWSER_HOST", "localhost")
    url = f"{scheme}://{browser_host}:{port}"
    state = {
        "pid": os.getpid(),
        "host": host,
        "port": port,
        "url": url,
        "dataDir": str(paths["data"]),
        "startedAt": datetime.now(timezone.utc).isoformat(),
    }
    _atomic_json(paths["state"], state)
    paths["stop"].unlink(missing_ok=True)
    try:
        os.environ["HOST"] = host
        os.environ["PORT"] = str(port)
        os.environ["RASPUTIN_DATA_DIR"] = str(paths["data"])
        os.environ.pop("WRAPPER_RUNTIME", None)
        from server import _tls_config
        import uvicorn

        tls = _tls_config()
        print(f"Rasputin Native Host: {url}", flush=True)
        config = uvicorn.Config(
            "backend.main:app",
            host=host,
            port=port,
            log_level=os.environ.get("LOG_LEVEL", "info"),
            **tls,
        )
        server = uvicorn.Server(config)

        def watch_for_stop() -> None:
            while not server.should_exit:
                if paths["stop"].exists():
                    server.should_exit = True
                    return
                time.sleep(0.2)

        threading.Thread(target=watch_for_stop, name="native-host-stop", daemon=True).start()
        return 0 if server.run() is not False else 1
    finally:
        paths["stop"].unlink(missing_ok=True)
        current = _read_json(paths["state"])
        if int(current.get("pid", 0)) == os.getpid():
            paths["state"].unlink(missing_ok=True)


def _run(args: argparse.Namespace, paths: dict[str, Path]) -> int:
    if args.log_file is None:
        return _run_server(args, paths)
    log_path = Path(args.log_file).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", buffering=1) as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            return _run_server(args, paths)


def _spawn_windows_brokered(command: list[str], cwd: Path, environment: dict[str, str]) -> int:
    """Create a process through WMI so it is not owned by the launcher's job.

    Some application launchers close an entire Windows job when their command
    finishes, which also kills children created with DETACHED_PROCESS. WMI is
    the OS-owned broker here. The environment is supplied through
    Win32_ProcessStartup instead of the command line so first-run credentials
    are not exposed in process listings.
    """
    broker_environment = environment.copy()
    broker_environment["RASPUTIN_NATIVE_BROKER_COMMAND"] = subprocess.list2cmdline(command)
    broker_environment["RASPUTIN_NATIVE_BROKER_CWD"] = str(cwd)
    encoded_script = base64.b64encode(WINDOWS_PROCESS_BROKER_SCRIPT.encode("utf-16le")).decode("ascii")
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-EncodedCommand",
            encoded_script,
        ],
        text=True,
        capture_output=True,
        env=broker_environment,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown Windows process broker error").strip()
        raise RuntimeError(detail)
    try:
        response = next(line for line in reversed(completed.stdout.splitlines()) if line.strip())
        result = json.loads(response)
        return int(result["processId"])
    except (StopIteration, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        response_detail = completed.stdout.strip()
        raise RuntimeError(f"Windows process broker returned an invalid response: {response_detail}") from error


def _spawn_direct(command: list[str], cwd: Path, environment: dict[str, str], log) -> int:
    creationflags = 0
    popen_options: dict = {}
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        popen_options["start_new_session"] = True
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        close_fds=True,
        creationflags=creationflags,
        **popen_options,
    )
    return process.pid


def _start(args: argparse.Namespace, paths: dict[str, Path]) -> int:
    desktop = _desktop_runtime(paths)
    if desktop:
        print(
            f"Rasputin Desktop already owns this data store at {desktop.get('url')}. "
            "Quit Desktop before starting Native Host.",
            file=sys.stderr,
        )
        return 2
    existing = _state(paths)
    if existing:
        print(f"Rasputin Native Host is already running at {existing.get('url')} (PID {existing['pid']}).")
        return 0

    config = _effective_config(args, paths)
    port = config["port"]
    lan = config["lan"]
    cert, key, certificate_hosts = _tls_config(require_https=lan and not config["allow_http"])
    allowed_hosts = sorted(set([*certificate_hosts, *config["allowed_hosts"]]))
    use_https = bool(cert and key)
    browser_host = os.environ.get("COMPUTERNAME", "localhost") if lan and use_https else "localhost"
    url = f"{'https' if use_https else 'http'}://{browser_host}:{port}"

    paths["data"].mkdir(parents=True, exist_ok=True)
    paths["log"].parent.mkdir(parents=True, exist_ok=True)
    fresh_store = not (paths["data"] / "rasputin.db").exists()
    initial_password = secrets.token_urlsafe(18) if fresh_store else None

    environment = os.environ.copy()
    environment.update({
        "PYTHONUNBUFFERED": "1",
        "RASPUTIN_DATA_DIR": str(paths["data"]),
        "RASPUTIN_HOST_BIND": "0.0.0.0" if lan else "127.0.0.1",
        "RASPUTIN_BROWSER_HOST": browser_host,
        "PORT": str(port),
        "RASPUTIN_HTTPS": "1" if use_https else "0",
    })
    environment.pop("WRAPPER_RUNTIME", None)
    if initial_password:
        environment["RASPUTIN_ADMIN_PASSWORD"] = initial_password
    if allowed_hosts:
        environment["RASPUTIN_ALLOWED_HOSTS"] = ",".join(allowed_hosts)
    if use_https:
        environment["RASPUTIN_TLS_CERT_FILE"] = str(cert)
        environment["RASPUTIN_TLS_KEY_FILE"] = str(key)
    else:
        environment.pop("RASPUTIN_TLS_CERT_FILE", None)
        environment.pop("RASPUTIN_TLS_KEY_FILE", None)

    command = [
        sys.executable,
        "-m",
        "backend.tools.native_host",
        "run",
        "--data-dir",
        str(paths["data"]),
    ]

    with paths["log"].open("a", encoding="utf-8", buffering=1) as log:
        log.write(f"\n--- Native Host {datetime.now(timezone.utc).isoformat()} ---\n")
        if os.name == "nt":
            try:
                _spawn_windows_brokered([*command, "--log-file", str(paths["log"])], ROOT, environment)
            except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                log.write(f"Windows process broker unavailable; using direct launch: {error}\n")
                _spawn_direct(command, ROOT, environment, log)
        else:
            _spawn_direct(command, ROOT, environment, log)

    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        state = _state(paths)
        if state and _health_ready(url):
            print(f"Rasputin Native Host is running at {url} (PID {state['pid']}).")
            if initial_password:
                print("First-run administrator credentials:")
                print("  username: admin")
                print(f"  password: {initial_password}")
                print("Change this password after signing in; it was not written to the host log.")
            return 0
        time.sleep(0.25)

    print(f"Native Host did not become healthy. See {paths['log']}", file=sys.stderr)
    return 1


def _stop(paths: dict[str, Path]) -> int:
    state = _state(paths)
    if not state:
        print("Rasputin Native Host is stopped.")
        return 0
    process = psutil.Process(int(state["pid"]))
    paths["stop"].write_text("stop\n", encoding="utf-8")
    try:
        process.wait(timeout=10)
        paths["state"].unlink(missing_ok=True)
        print("Rasputin Native Host stopped gracefully.")
        return 0
    except psutil.TimeoutExpired:
        pass

    children = process.children(recursive=True)
    for child in reversed(children):
        child.terminate()
    process.terminate()
    _, alive = psutil.wait_procs([*children, process], timeout=5)
    for remaining in alive:
        remaining.kill()
    psutil.wait_procs(alive, timeout=3)
    paths["state"].unlink(missing_ok=True)
    paths["stop"].unlink(missing_ok=True)
    print("Rasputin Native Host required a forced stop after the graceful-shutdown timeout.")
    return 0


def _status(paths: dict[str, Path], as_json: bool) -> int:
    state = _state(paths)
    result = {
        "running": bool(state),
        "healthy": bool(state and _health_ready(str(state.get("url")))),
        "state": state or None,
        "log": str(paths["log"]),
    }
    if as_json:
        print(json.dumps(result))
    elif state:
        health = "healthy" if result["healthy"] else "not responding"
        print(f"Rasputin Native Host is running at {state.get('url')} (PID {state['pid']}, {health}).")
    else:
        print("Rasputin Native Host is stopped.")
    return 0 if result["healthy"] else 3


def _autostart(args: argparse.Namespace, paths: dict[str, Path], install: bool) -> int:
    if os.name != "nt":
        print("Automatic Native Host registration is currently implemented for Windows only.", file=sys.stderr)
        return 2
    if not install:
        result = subprocess.run(["reg", "delete", AUTOSTART_KEY, "/v", AUTOSTART_NAME, "/f"], check=False)
        return result.returncode

    config = _effective_config(args, paths)
    _atomic_json(paths["config"], config)
    launcher = ROOT / "scripts" / "start-native-host.ps1"
    action = f'powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{launcher}"'
    result = subprocess.run([
        "reg", "add", AUTOSTART_KEY, "/v", AUTOSTART_NAME, "/t", "REG_SZ", "/d", action, "/f",
    ], check=False)
    if result.returncode == 0:
        print("Native Host will start automatically when this Windows user signs in.")
    return result.returncode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m backend.tools.native_host")
    parser.add_argument("command", choices=("run", "start", "stop", "restart", "status", "install", "uninstall"))
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--lan", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--allow-http", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--allowed-host", action="append", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--log-file", type=Path, default=None, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    paths = _paths(args.data_dir)
    if args.command == "run":
        return _run(args, paths)
    if args.command == "start":
        return _start(args, paths)
    if args.command == "stop":
        return _stop(paths)
    if args.command == "restart":
        _stop(paths)
        return _start(args, paths)
    if args.command == "status":
        return _status(paths, args.json)
    return _autostart(args, paths, install=args.command == "install")


if __name__ == "__main__":
    raise SystemExit(main())
