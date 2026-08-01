"""Terminal client for Rasputin's governed local coding workflow.

This deliberately talks to the same authenticated task API as the browser.  It
does not run an agent directly or grant itself filesystem permissions, so code
tasks created from a terminal still honor Rasputin's workspace and approval
policy.
"""

import argparse
import getpass
import json
import os
import sys
import time
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener


DEFAULT_URL = "http://127.0.0.1:8788"
TERMINAL_STATES = {"completed", "failed", "cancelled"}


class RasputinClient:
    def __init__(self, base_url: str):
        self.base_url = str(base_url).rstrip("/")
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def request(self, method: str, path: str, payload=None):
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=20) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(body).get("error", {}).get("message")
            except json.JSONDecodeError:
                detail = body
            raise RuntimeError(detail or f"Rasputin returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(
                f"Rasputin is not reachable at {self.base_url}. Start it with '.\\rasputin.ps1 native'."
            ) from exc
        try:
            envelope = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Rasputin returned an invalid response.") from exc
        if not envelope.get("ok"):
            error = envelope.get("error") or {}
            raise RuntimeError(error.get("message") or "Rasputin rejected the request.")
        return envelope.get("data")


def _parser():
    parser = argparse.ArgumentParser(
        prog="rasputin code",
        description="Submit and follow a governed Rasputin coding task from this terminal.",
    )
    parser.add_argument("objective", nargs="*", help="Coding objective. Omit it to be prompted.")
    parser.add_argument("--url", default=os.environ.get("RASPUTIN_URL", DEFAULT_URL))
    parser.add_argument("--workspace", default=str(Path.cwd()), help="Workspace Rasputin may modify.")
    parser.add_argument("--model", default="auto", help="Registered coder model key, or auto (default).")
    parser.add_argument("--reasoning", default="auto", choices=("off", "auto", "on"))
    parser.add_argument("--subagents", type=int, default=0, choices=range(0, 5))
    parser.add_argument("--no-watch", action="store_true", help="Submit the task and print its id without following it.")
    parser.add_argument("--poll-seconds", type=float, default=2.0, help=argparse.SUPPRESS)
    return parser


def _authenticate(client: RasputinClient):
    session = client.request("GET", "/api/auth/session")
    if session.get("authenticated"):
        return session
    username = os.environ.get("RASPUTIN_USERNAME") or input("Rasputin username: ").strip()
    password = os.environ.get("RASPUTIN_PASSWORD") or getpass.getpass("Rasputin password: ")
    if not username or not password:
        raise RuntimeError("A Rasputin username and password are required.")
    return client.request("POST", "/api/auth/login", {"username": username, "password": password})


def _coder_model(client: RasputinClient, requested: str):
    if requested and requested.lower() != "auto":
        return requested
    models = client.request("GET", "/api/models") or []
    for model in models:
        if model.get("role") == "coder" and model.get("runtimeStatus") not in {"unhealthy", "stopped", "unreachable", "error"}:
            return model.get("key")
    raise RuntimeError(
        "No reachable model has the coder role. Start a coding model and assign it the Coder role in Models."
    )


def _print_update(task, previous):
    status = task.get("status") or "unknown"
    progress = task.get("progress")
    phase = task.get("phase") or ""
    fingerprint = (status, progress, phase, task.get("streamText", "")[-240:])
    if fingerprint == previous:
        return fingerprint
    label = f"[{status}]"
    if isinstance(progress, (int, float)):
        label += f" {int(progress)}%"
    if phase:
        label += f" {phase}"
    print(label)
    text = str(task.get("streamText") or "").strip()
    if text:
        print(text[-1200:])
    return fingerprint


def run(argv=None, *, client_factory=RasputinClient, sleep=time.sleep, output=print):
    args = _parser().parse_args(argv)
    objective = " ".join(args.objective).strip() or input("Coding objective: ").strip()
    if not objective:
        output("No coding objective supplied.")
        return 2
    client = client_factory(args.url)
    try:
        session = _authenticate(client)
        model = _coder_model(client, args.model)
        task = client.request("POST", "/api/tasks", {
            "objective": objective,
            "model": model,
            "mode": "code",
            "skill": "general",
            "reasoning": args.reasoning,
            "subagents": args.subagents,
            "workspacePath": str(Path(args.workspace).resolve()),
        })
    except RuntimeError as exc:
        output(f"Rasputin code: {exc}")
        return 1

    task_id = task.get("id")
    output(f"Submitted coding task {task_id} as {session.get('username')} using {model}.")
    if args.no_watch:
        return 0
    previous = None
    try:
        while True:
            previous = _print_update(task, previous)
            if task.get("status") in TERMINAL_STATES:
                result = str(task.get("result") or "").strip()
                if result:
                    output("\nResult:\n" + result)
                return 0 if task.get("status") == "completed" else 1
            sleep(max(0.2, args.poll_seconds))
            task = client.request("GET", f"/api/tasks/{task_id}").get("task", {})
    except KeyboardInterrupt:
        output("\nTask left running in Rasputin. Use the app or task controls to pause or cancel it.")
        return 130
    except RuntimeError as exc:
        output(f"Rasputin code: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
