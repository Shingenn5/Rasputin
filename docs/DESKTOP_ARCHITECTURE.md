# Rasputin Desktop Architecture

Status: compact Windows desktop packaging with hardware-selected llama.cpp acquisition.

The Windows product and its source-development runtime share FastAPI and React:

| Shape | Primary user | Lifecycle | Workspace behavior | Network surface |
| --- | --- | --- | --- | --- |
| Rasputin Desktop | One workstation operator | Electron owns the native backend process | Direct host folders | Random loopback-only HTTP port inside Electron |
| Source Native Host | Developer/browser operator | Native Host controller owns its process | Direct approved host folders | Loopback :8788 by default |

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

Electron sets `RASPUTIN_DESKTOP_ONLY=1`. `auth.public_session()` automatically supplies the local
administrator identity to loopback requests, so installed Desktop opens without a login screen
or a first-run credentials dialog. This is a single-operator host trust boundary, not isolation
from other local processes. Generated bootstrap secrets remain redacted from persistent logs.

For source/browser development, use the explicit Native Host module commands in
[deployment guidance](DEPLOYMENT_MATRIX.md) and a separate data directory.

## Packaging boundary

Repository development reuses `.venv`, or a Python 3.12+ interpreter supplied through
`RASPUTIN_PYTHON`. Distribution uses PyInstaller plus electron-builder:

1. npm run build produces frontend/.
2. npm run desktop:runtime validates the pinned CPU/CUDA manifest without downloading payloads.
3. npm run desktop:backend produces a standalone onedir backend runtime containing the frontend.
4. electron-builder copies the backend and runtime manifest into Electron resources. First model
   load detects hardware, downloads only the highest compatible runtime, verifies every SHA-256,
   smoke-checks it, and stores it under user-local application data.
5. The NSIS install hook grants Electron's restricted AppContainer read/execute ACL and creates a
   user-scoped installer while preserving data on uninstall.

The unpacked application, packaged backend, runtime acquisition contract, and ordinary sandboxed
launch path have passed local smoke tests. The application icon is implemented. Remaining release gates
are Authenticode signing, update signing/channel metadata, and a clean-machine install/upgrade/uninstall test outside
the development workstation.

## Security and ownership rules

- Desktop always binds FastAPI to `127.0.0.1`; reviewed LAN access belongs to a separately configured Native Host.
- Electron forces native runtime semantics and removes inherited Docker/TLS environment flags.
- The desktop process owns only the backend process it launched.
- Browser renderer code cannot invoke Electron or Node APIs.
- Desktop supplies a loopback-only local administrator session; source Native Host uses password
  authentication and session cookies. Workspace approval and audit controls apply to both.
  Native/Desktop Host Shell is fail-closed and unavailable until a proven
  Windows AppContainer runner exists.
- The product uses native model processes. Retained server-era code is historical compatibility,
  not an alternative installation or model-loading instruction.
