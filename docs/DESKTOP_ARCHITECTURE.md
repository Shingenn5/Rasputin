# Rasputin Desktop Architecture

Status: lifecycle shell and self-contained Windows packaging implemented on 2026-07-13.

Rasputin's two supported product shapes share the same FastAPI backend and React frontend:

| Shape | Primary user | Lifecycle | Workspace behavior | Network surface |
| --- | --- | --- | --- | --- |
| Rasputin Desktop | One workstation operator | Electron owns the native backend process | Direct host folders | Random loopback-only HTTP port inside Electron |
| Rasputin Server | Multiple local or LAN users | Docker Compose and the CLI own the service | Explicit server/container mounts | Configured HTTP/HTTPS listener |

Electron is a host shell, not a second Rasputin implementation. It starts `server.py`, waits for
`/api/health`, and loads the existing frontend in a hardened `BrowserWindow`. The desktop
window has no Node.js integration, uses context isolation and renderer sandboxing, denies new
windows, and sends ordinary HTTPS links to the system browser.

## Current desktop milestone

From the repository root on Windows:

```powershell
npm install
npm run desktop
```

`npm run desktop` builds the React frontend, launches Electron, and starts the native backend.
The backend uses the established native data store at `%LOCALAPPDATA%\Rasputin\data`. Set
`RASPUTIN_DATA_DIR` before launch to use an isolated store. `RASPUTIN_DESKTOP_PORT` can reserve a
specific development port; normal desktop launches choose an available loopback port. Set
`RASPUTIN_DISABLE_HARDWARE_ACCELERATION=1` only when working around a problematic GPU or
remote-desktop driver.

Closing the window minimizes Rasputin to the system tray. The tray owns these lifecycle actions:

- Open Rasputin
- Start, stop, or restart the native engine
- Show the persistent desktop log
- Quit Rasputin and stop its managed backend

When the persistent Native Host already owns the same native data directory, Desktop attaches to
that instance instead of starting another backend. Closing or quitting the window leaves the host
running for browser users; choosing the explicit tray stop action shuts the host down gracefully.

On a fresh data store, Electron shows the generated administrator credentials once and can copy
the password to the clipboard. The password is redacted from the persistent desktop log.

The legacy `rasputin.ps1 start -Native` command remains the foreground development/headless
fallback. Do not run it against the same data directory while Rasputin Desktop is open.

## Packaging boundary

Repository development reuses `.venv`, or a Python 3.12+ interpreter supplied through
`RASPUTIN_PYTHON`. Distribution uses PyInstaller plus electron-builder:

1. `npm run build` produces `frontend/`.
2. `npm run desktop:backend` produces a standalone onedir backend runtime containing the frontend.
3. electron-builder copies that runtime into Electron resources; packaged Electron selects the
   executable automatically.
4. NSIS creates a user-scoped installer while preserving data on uninstall.

The unpacked application and bundled backend have passed local lifecycle smoke tests. Remaining
release gates are a production icon, Authenticode signing, update signing/channel metadata, and a
clean-machine install/upgrade/uninstall test outside the development workstation.

## Security and ownership rules

- Desktop always binds FastAPI to `127.0.0.1`; LAN access belongs to server mode.
- Electron forces native runtime semantics and removes inherited Docker/TLS environment flags.
- The desktop process owns only the backend process it launched.
- Browser renderer code cannot invoke Electron or Node APIs.
- Existing Rasputin authentication, workspace approval, audit, and Host Shell isolation remain in
  force; Electron does not bypass them.
- Docker remains the shared-account server/appliance deployment and the supported remote-access
  boundary.
