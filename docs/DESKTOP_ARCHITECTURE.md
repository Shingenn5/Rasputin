# Rasputin Desktop Architecture

Status: self-contained Windows desktop packaging with bundled llama.cpp implemented on 2026-08-23.

Rasputin's two supported product shapes share the same FastAPI backend and React frontend:

| Shape | Primary user | Lifecycle | Workspace behavior | Network surface |
| --- | --- | --- | --- | --- |
| Rasputin Desktop | One workstation operator | Electron owns the native backend process | Direct host folders | Random loopback-only HTTP port inside Electron |
| Rasputin Server | Multiple local or LAN users | Docker Compose and the CLI own the service | Explicit server/container mounts | Configured HTTP/HTTPS listener |

Electron is a host shell, not a second Rasputin implementation. In repository development it can
start server.py; in the installed application it starts the PyInstaller backend shipped inside the
installer, waits for /api/health, and loads the existing frontend in a hardened BrowserWindow. The desktop
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

By default, closing the window minimizes Rasputin to the system tray. The tray's **Keep running
when window closes** setting can instead make window close perform a full quit. The preference is
stored under Electron's per-user application data directory. The tray owns these lifecycle actions:

- Open Rasputin
- Start, stop, or restart the Electron-owned Desktop Runtime
- Show the persistent desktop log
- Quit Rasputin and stop its managed backend

The installed Desktop application owns its packaged backend and does not attach to a separately
launched Native Server. Keep the source-development Native Server and Desktop process on separate
data directories; the installed app is the only supported daily-driver path for this branch.

Before starting a Desktop Runtime, Electron checks `desktop-runtime.json`. If a previous Electron
process crashed but left its backend alive, the new app terminates that abandoned process tree and
removes the stale ownership record. A live Electron owner is never replaced.

On a fresh data store, Electron shows the generated administrator credentials once and can copy
the password to the clipboard. The password is redacted from the persistent desktop log.

The legacy `rasputin.ps1 start -Native` command remains the foreground development/headless
fallback. Do not run it against the same data directory while Rasputin Desktop is open.

## Packaging boundary

Repository development reuses `.venv`, or a Python 3.12+ interpreter supplied through
`RASPUTIN_PYTHON`. Distribution uses PyInstaller plus electron-builder:

1. npm run build produces frontend/.
2. npm run desktop:runtime downloads, verifies, and stages the pinned CPU/CUDA llama.cpp builds
   under runtime/llama/bundled/ at build time.
3. npm run desktop:backend produces a standalone onedir backend runtime containing the frontend.
4. electron-builder copies the backend and all llama.cpp binaries into Electron resources; the
   packaged app selects the correct native engine automatically.
5. The NSIS install hook grants Electron's restricted AppContainer read/execute ACL and creates a
   user-scoped installer while preserving data on uninstall.

The unpacked application, bundled backend, bundled CPU/CUDA engines, and ordinary sandboxed launch
path have passed local smoke tests. Remaining release gates are a production icon, Authenticode
signing, update signing/channel metadata, and a clean-machine install/upgrade/uninstall test outside
the development workstation.

## Security and ownership rules

- Desktop always binds FastAPI to `127.0.0.1`; LAN access belongs to server mode.
- Electron forces native runtime semantics and removes inherited Docker/TLS environment flags.
- The desktop process owns only the backend process it launched.
- Browser renderer code cannot invoke Electron or Node APIs.
- Existing Rasputin authentication, workspace approval, audit, and Host Shell isolation remain in
  force; Electron does not bypass them.
- Docker remains legacy server-mode code only; it is not part of the packaged Desktop runtime,
  model-loading path, or agentic coding path on this branch.
