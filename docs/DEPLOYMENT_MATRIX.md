# Rasputin Deployment Matrix

Rasputin has four verified access shapes. They share one FastAPI backend, one React frontend, and
one account/permission model; only lifecycle, filesystem access, and network exposure differ.

| Shape | Lifecycle owner | Default address | Intended use |
| --- | --- | --- | --- |
| Desktop | Electron window and tray | Random loopback port | Personal daily driver with direct folders |
| Native Host | Native host controller | `localhost:8788` | Persistent browser host with direct folders |
| Docker Server | Docker Compose | `127.0.0.1:8787` | Shared appliance/server with explicit mounts |
| Private Remote Access | Tailscale Serve or reviewed Caddy config | Stable HTTPS name | Access to Native Host or Docker from other devices |

## Desktop

Development launch:

```powershell
npm run desktop
```

Build a self-contained unpacked application or Windows installer:

```powershell
npm run desktop:package:dir
npm run desktop:package
```

The build creates a PyInstaller backend runtime and places it inside Electron resources. The
resulting application does not require Python or Node.js on the target machine. Installer output
lands under `dist/electron/`. The installer is currently unsigned; Windows may display a publisher
warning until release signing is configured.

## Native Host

Native Host is the non-Docker multi-user option. It runs independently of Electron and records its
PID, URL, and data directory under `%LOCALAPPDATA%\Rasputin\data`.

```powershell
.\rasputin.ps1 native-host-start -Port 8788
.\rasputin.ps1 native-host-status
.\rasputin.ps1 native-host-restart
.\rasputin.ps1 native-host-stop
```

The controller waits for `/api/health`, performs a graceful Uvicorn shutdown, and falls back to
process-tree termination only after a timeout. Fresh credentials are printed once by the start
command and are not written to the persistent Native Host log.

Desktop and Native Host share this data store deliberately but never open two backends against it.
If Native Host is already running, Electron attaches to its stable URL; closing Electron leaves the
host serving browser users, while the explicit tray stop action shuts it down gracefully. Native
Host refuses to start when an Electron-owned backend already holds the store.

Start-at-login registration is available for the current Windows user:

```powershell
.\rasputin.ps1 native-host-install -Port 8788
.\rasputin.ps1 native-host-uninstall
```

This creates a per-user `HKCU\...\Run` entry and restarts Native Host at the next user logon; it is
not a machine-account Windows service and therefore does not claim access to folders the operator account cannot read. For a
dedicated always-on machine, keep that operator signed in or use Docker Server until a signed
machine-service installer with explicit service-account ACL management is added.

For direct LAN access, generate HTTPS first and then use `-Lan`. Plain HTTP LAN mode is rejected by
the underlying controller unless its low-level `--allow-http` escape hatch is supplied explicitly.

## Docker Server

```powershell
.\rasputin.ps1 start
.\rasputin.ps1 stop
```

Docker remains the preferred dedicated/shared appliance boundary. Use `setup-https` plus `start
-Lan` for direct private-LAN access. Accounts are created under **Settings → Accounts** and each
browser profile/device receives an independent session.

## Private remote access

Tailscale Serve keeps the backend on loopback and publishes it only to the machine's tailnet. Plan
the change first:

```powershell
.\.venv\Scripts\python.exe scripts\setup_remote_access.py tailscale --target http://127.0.0.1:8788
```

The command reports the stable private URL and the exact Native Host `--allowed-host` value. Add
`--apply` only after confirming the target. The helper deliberately does not configure Tailscale
Funnel or public Internet access. On a tailnet where Serve has not been enabled, Tailscale may
require an administrator to authorize the feature before the CLI can apply the plan.

Apply a reported hostname to the managed launcher with, for example,
`.\rasputin.ps1 native-host-install -Port 8788 -AllowedHost rasputin.tailnet.ts.net`.

For a conventional reverse proxy, generate a Caddyfile for review:

```powershell
.\.venv\Scripts\python.exe scripts\setup_remote_access.py caddy `
  --hostname rasputin.example.com `
  --target http://127.0.0.1:8788 `
  --output C:\Rasputin\Caddyfile
```

Add the hostname to Native Host with `--allowed-host`; the Host/Origin middleware intentionally
rejects proxy names that were not approved. `deploy/Caddyfile.example` is the tracked starting
point. Public access requires real DNS, a trusted certificate, hardened firewall rules, and an
operator review; mkcert is only for local/private trust.

## Verification

Run read-only endpoint checks against any active combination:

```powershell
.\.venv\Scripts\python.exe scripts\verify_deployment_matrix.py `
  --endpoint docker=http://127.0.0.1:8787 `
  --endpoint native=http://127.0.0.1:8788 `
  --require-desktop-artifacts
```

The verifier checks health, frontend serving, baseline security headers, and packaged desktop
artifacts. The Docker test harness also runs the backend and multi-user isolation suites inside the
container.
