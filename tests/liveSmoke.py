import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


baseUrl = os.environ.get("RASPUTIN_TEST_BASE_URL", "http://127.0.0.1:8787").rstrip("/")
username = os.environ.get("RASPUTIN_TEST_USERNAME", "admin")
password = os.environ.get("RASPUTIN_TEST_PASSWORD", "")

cookieJar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookieJar))


class SmokeFailure(Exception):
    pass


def requestJson(method, path, body=None, expectStatus=None):
    url = baseUrl + path
    payload = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        response = opener.open(request, timeout=20)
        status = response.status
        raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8")
    if expectStatus is not None and status != expectStatus:
        raise SmokeFailure(f"{method} {path} returned {status}, expected {expectStatus}: {raw[:500]}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SmokeFailure(f"{method} {path} did not return JSON: {raw[:500]}") from exc
    return status, data


def requestText(method, path, expectStatus=200):
    request = urllib.request.Request(baseUrl + path, method=method)
    response = opener.open(request, timeout=20)
    if response.status != expectStatus:
        raise SmokeFailure(f"{method} {path} returned {response.status}, expected {expectStatus}")
    return response.read().decode("utf-8")


def assertOk(method, path, body=None):
    status, data = requestJson(method, path, body, 200)
    if not data.get("ok"):
        raise SmokeFailure(f"{method} {path} returned ok=false: {data}")
    return data.get("data")


def loginIfNeeded():
    session = assertOk("GET", "/api/auth/session")
    if session.get("authenticated"):
        return session
    if not password:
        raise SmokeFailure(
            "Rasputin is not authenticated. Run the test compose harness or set RASPUTIN_TEST_PASSWORD."
        )
    assertOk("POST", "/api/auth/login", {"username": username, "password": password})
    session = assertOk("GET", "/api/auth/session")
    if not session.get("authenticated"):
        raise SmokeFailure("Login succeeded but session is still unauthenticated.")
    return session


def waitForTask(taskId):
    deadline = time.time() + 30
    while time.time() < deadline:
        tasks = assertOk("GET", "/api/tasks")
        current = next((task for task in tasks if task.get("id") == taskId), None)
        if current and current.get("status") in {"done", "error", "cancelled"}:
            return current
        time.sleep(0.5)
    raise SmokeFailure(f"Task {taskId} did not finish in time.")


def main():
    indexHtml = requestText("GET", "/")
    assets = re.findall(r'''(?:src|href)=["'](/static/[^"']+)["']''', indexHtml)
    if not assets:
        raise SmokeFailure("Index did not reference any built frontend assets.")
    for asset in assets:
        requestText("GET", asset)

    health = assertOk("GET", "/api/health")
    if "privacyLock" not in health.get("privacy", {}):
        raise SmokeFailure(f"Health payload is not camelCase: {health}")

    session = loginIfNeeded()
    if not session.get("authenticated"):
        raise SmokeFailure("Session is not authenticated.")

    bootstrap = assertOk("GET", "/api/ui/bootstrap")
    for key in ["models", "tasks", "security", "workspace", "output", "preferences"]:
        if key not in bootstrap:
            raise SmokeFailure(f"Bootstrap missing {key}.")

    securityBefore = assertOk("GET", "/api/security")
    try:
        fileReadBlocked = dict(securityBefore)
        fileReadBlocked["allowFileRead"] = False
        assertOk("POST", "/api/security", fileReadBlocked)
        status, deniedRag = requestJson("POST", "/api/rag/search", {"query": "blocked", "limit": 2}, 403)
        if deniedRag.get("error", {}).get("code") != "permissionDenied":
            raise SmokeFailure(f"RAG search should respect disabled file read: {deniedRag}")

        fileWriteBlocked = dict(securityBefore)
        fileWriteBlocked["allowFileWrite"] = False
        assertOk("POST", "/api/security", fileWriteBlocked)
        status, deniedOutput = requestJson("POST", "/api/output", {"markdownFolder": "workspace/markdown-output"}, 403)
        if deniedOutput.get("error", {}).get("code") != "permissionDenied":
            raise SmokeFailure(f"Output save should respect disabled file write: {deniedOutput}")
    finally:
        assertOk("POST", "/api/security", securityBefore)

    prefs = assertOk("POST", "/api/preferences", {
        "theme": "rasputin-dark",
        "sidebarCollapsed": True,
        "selectedModel": "dry-run",
        "skill": "general",
        "taskMode": "chat",
        "subagents": 0,
        "activeView": "home",
        "activeSettingsSection": "general",
    })
    if prefs.get("theme") != "rasputin-dark" or prefs.get("selectedModel") != "dry-run":
        raise SmokeFailure(f"Preference save failed: {prefs}")
    assertOk("POST", "/api/preferences", {
        "theme": "rasputin-light",
        "sidebarCollapsed": False,
        "selectedModel": "dry-run",
        "skill": "general",
        "taskMode": "chat",
        "subagents": 0,
        "activeView": "home",
        "activeSettingsSection": "general",
    })

    discovery = assertOk("POST", "/api/model-registry/discover", {"key": "dry-run"})
    if discovery.get("status") != "reachable" or "latencyMs" not in discovery:
        raise SmokeFailure(f"Dry-run discovery failed: {discovery}")

    status, deniedLogs = requestJson("POST", "/api/model-registry/logs", {"key": "dry-run"}, 403)
    if deniedLogs.get("error", {}).get("code") != "permissionDenied":
        raise SmokeFailure(f"Model logs should be blocked while Docker control is disabled: {deniedLogs}")

    ggufScan = assertOk("POST", "/api/model-registry/scan-gguf", {})
    for key in ["models", "roots", "count"]:
        if key not in ggufScan:
            raise SmokeFailure(f"GGUF scan missing {key}: {ggufScan}")

    roots = assertOk("GET", "/api/workspace/roots")
    if not roots.get("roots"):
        raise SmokeFailure(f"No approved workspace roots returned: {roots}")
    root = next((item for item in roots["roots"] if item.get("id") == "workspace-folder"), roots["roots"][0])
    browsed = assertOk("POST", "/api/workspace/browse", {"rootId": root["id"]})
    if "entries" not in browsed or "displayName" not in browsed:
        raise SmokeFailure(f"Workspace browse shape is wrong: {browsed}")
    mountPlan = assertOk("POST", "/api/workspace/mount-plan", {
        "hostPath": "C:/Users/example/Documents",
        "name": "Documents",
        "readOnly": True,
    })
    if not mountPlan.get("requiresRestart") or not mountPlan.get("readOnly"):
        raise SmokeFailure(f"Mount plan is not safe by default: {mountPlan}")
    assertOk("POST", "/api/workspace/select", {"path": "."})
    status, deniedMount = requestJson(
        "POST",
        "/api/workspace/mount-apply",
        {"hostPath": "C:/Users/example/Documents", "name": "Documents", "readOnly": True},
        403,
    )
    if deniedMount.get("error", {}).get("code") != "permissionDenied":
        raise SmokeFailure(f"Mount apply should be blocked by default: {deniedMount}")

    status, badGguf = requestJson(
        "POST",
        "/api/model-registry/import-gguf",
        {"path": "Z:/definitely/missing/model.gguf"},
        400,
    )
    if badGguf.get("error", {}).get("code") != "modelFileMissing":
        raise SmokeFailure(f"Bad GGUF error is not structured: {badGguf}")

    task = assertOk("POST", "/api/tasks", {
        "objective": "Testing the Rasputin live smoke harness.",
        "model": "dry-run",
        "skill": "general",
        "mode": "chat",
        "subagents": 0,
        "workspacePath": ".",
    })
    finished = waitForTask(task["id"])
    if finished.get("status") != "done":
        raise SmokeFailure(f"Dry-run task did not complete cleanly: {finished}")
    detail = assertOk("GET", f"/api/tasks/{task['id']}")
    for key in ["task", "session", "events", "trace", "outputs", "children", "approvals", "toolCalls"]:
        if key not in detail:
            raise SmokeFailure(f"Task detail missing {key}: {detail}")
    if detail["task"].get("id") != task["id"]:
        raise SmokeFailure(f"Task detail returned the wrong task: {detail}")
    status, missingTask = requestJson("GET", "/api/tasks/definitely-missing-task", None, 404)
    if missingTask.get("error", {}).get("code") != "taskNotFound":
        raise SmokeFailure(f"Missing task did not return structured 404: {missingTask}")

    print(json.dumps({
        "ok": True,
        "baseUrl": baseUrl,
        "session": session,
        "taskId": task["id"],
        "taskStatus": finished.get("status"),
    }, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
