# Rasputin Release Setup Guide

This guide is for a clean local clone. It avoids machine-specific paths and does not require committing any runtime data.

## 1. Start The Wrapper (Docker mode)

```powershell
.\rasputin.ps1 start
```

Open the browser manually:

```text
http://127.0.0.1:8787
```

Rasputin binds to localhost. The manager builds the wrapper, waits for health, prints any
first-run credentials still present in the current container logs, and opens the browser.

### Side-by-side native daily-driver test

Leave Docker on its normal `127.0.0.1:8787` endpoint and launch native on 8788 in a second
PowerShell window:

```powershell
# Docker remains detached on its normal port.
.\rasputin.ps1 start

# Clear any isolated-QA data override, then start the canonical native daily driver.
Remove-Item Env:\RASPUTIN_DATA_DIR -ErrorAction SilentlyContinue
.\rasputin.ps1 start -Native -Port 8788
```

Open:

- Docker: `http://127.0.0.1:8787`
- Native: `http://localhost:8788`

The different hostnames are intentional: the `rasputin_session` cookie is scoped by hostname, not
port, so using `127.0.0.1` for both would make the two sessions collide. `-Port` overrides the
native port only; Docker remains on 8787 (use its existing `WRAPPER_PORT` mechanism if you
deliberately need a different Docker port).

Native runtime data defaults to `%LOCALAPPDATA%\Rasputin\data`, which means native has a **separate
admin account** from Docker. On a fresh native store, use the first-boot credentials printed in the
foreground console. Keep that console open; `Ctrl+C` stops the native process. A leftover
`RASPUTIN_DATA_DIR` overrides the canonical native store, so clear it as shown above unless the
override is intentional. If `.venv\Scripts\python.exe` already exists, the launcher reuses it even
when a system Python is not on `PATH`; Python on `PATH` is needed only to create the venv initially.

At `http://localhost:8788`, open **Workspaces**, add and approve a normal project folder, then verify
it appears and is browsable immediately with no mount request, restart badge, or wrapper restart.
That is the direct-folder native path; Docker retains its mount → restart → approve flow.

Docker is still required for Skills and WarSat model containers, but not for the native wrapper
process or its low-privilege Host Shell.

## 2. Get Or Reset The Admin Password

On the **first boot of a fresh data store**, Rasputin generates an admin password once. In Docker
mode, the manager normally prints it; you can read the same line from the current container logs:

```powershell
.\rasputin.ps1 credentials
```

Use the `admin` username unless you configured `RASPUTIN_ADMIN_USER`.

`credentials` does not read the password hash and cannot recover a changed password. It works only
while the **original generated password line remains in the current container logs**. Container
replacement or log loss can remove that line even though the admin account persists in the named
data volume. If it is missing or you no longer know the password, generate a new one:

```powershell
.\rasputin.ps1 reset-password
```

For native mode, run `python -m backend.tools.reset_password` with the same
`RASPUTIN_DATA_DIR` environment used by that instance (omit it for the native default). Restart the
running server/container afterward if you need to invalidate already-loaded sessions immediately.

The password is not displayed in the browser. Do not copy it into Git, screenshots, docs, tickets,
or issue comments.

## 3. Change The Admin Password

After login:

1. Open Settings.
2. Open Admin.
3. Enter the generated password as the current password.
4. Save a new local admin password.

The password hash stays in ignored local runtime data under `data/`.

## 4. Run The Setup Checklist

Open Settings -> General. The Release setup checklist should show:

- admin password state
- chat model connection state
- active workspace state
- privacy lock state
- Markdown output folder state

Use the checklist buttons to jump to Models, Workspaces, Safety, Output, or Admin.

## 5. Connect A Model

For an already-running local model endpoint:

1. Open Models.
2. Register or select the local endpoint.
3. Run Discover or Test health.
4. Confirm the model is reachable.

Privacy lock blocks non-local model URLs by default. Remote APIs require an explicit Safety change and API keys must come from environment variables or the ignored local secret store.

## 6. Select A Workspace

Open Workspaces and choose a project folder. Native mode registers the approved host path directly
with no mount or restart. Docker mode can browse only folders already visible inside the wrapper;
new host folders use the mount-request → restart → approve flow.

New folder access should start read-only. File writes, moves, shell execution, Docker control, and web-search broker use remain governed by Safety and approvals.

## 7. Check Output

Open Settings -> Output and confirm the Markdown export folder. Exports must stay inside Rasputin-visible paths.

## 8. Validate Before Sharing

Run:

```powershell
npm run checkRepoSafety
.\scripts\test.ps1 -Ui
```

Before pushing or packaging, verify Git does not stage:

- `data/`
- `workspace/`
- `models/`
- `testdata/`
- logs
- screenshots
- API keys
- generated RAG or graph indexes

