# Rasputin Deployment Matrix

Rasputin has one cross-platform server shape and two Windows-specific application shapes. All shapes
use the same FastAPI backend, React frontend, account model, permissions, and audit system; the
lifecycle owner and filesystem boundary differ.

| Shape | Platforms | Lifecycle owner | Default address | Intended use |
| --- | --- | --- | --- | --- |
| Docker Server | Windows, macOS, Linux | Docker Compose | 127.0.0.1:8787 | Recommended shared/local appliance |
| Native Server | Windows | Native host controller | localhost:8788 | Direct access to approved Windows folders |
| Desktop | Windows | Electron window and tray | Loopback port | One-operator desktop experience |
| Private remote access | Any existing server shape | Tailscale Serve or reviewed reverse proxy | Stable HTTPS name | Trusted LAN or tailnet access |

## Docker Server

Docker Server is the supported deployment for Windows, macOS, and Linux. The image contains the
backend, built frontend, Git, and Python dependencies. The host needs Docker Desktop (Windows/macOS)
or Docker Engine plus Compose v2 (Linux); Python and Node are not required for a Docker-only install.

The standard deployment binds to loopback and keeps application state in the named volume
rasputin-data. It also mounts workspace/ and models/ from the checkout. Do not use
docker compose down -v during normal operations.

macOS/Linux:

~~~bash
./rasputin.sh config
./rasputin.sh start --no-open
./rasputin.sh status
./rasputin.sh logs
./rasputin.sh credentials
./rasputin.sh reset-password
./rasputin.sh stop
~~~

Windows PowerShell:

~~~powershell
powershell.exe -ExecutionPolicy Bypass -File .\rasputin.ps1 config
powershell.exe -ExecutionPolicy Bypass -File .\rasputin.ps1 start -NoOpen
powershell.exe -ExecutionPolicy Bypass -File .\rasputin.ps1 status
powershell.exe -ExecutionPolicy Bypass -File .\rasputin.ps1 logs
powershell.exe -ExecutionPolicy Bypass -File .\rasputin.ps1 credentials
powershell.exe -ExecutionPolicy Bypass -File .\rasputin.ps1 reset-password
powershell.exe -ExecutionPolicy Bypass -File .\rasputin.ps1 stop
~~~

The start command builds/rebuilds the local image and recreates the container without deleting
named volumes. Use WRAPPER_PORT to choose another host port. Keep WRAPPER_BIND=127.0.0.1 unless
direct LAN access is intentionally configured with HTTPS.

### WarSat Docker control

The normal Docker Server does not mount the host Docker socket. WarSat control is an explicit
overlay because the socket can control sibling containers and the Docker host.

macOS/Linux:

~~~bash
./rasputin.sh stop
./rasputin.sh start --enable-warsat --no-open
~~~

Windows PowerShell:

~~~powershell
powershell.exe -ExecutionPolicy Bypass -File .\rasputin.ps1 stop
powershell.exe -ExecutionPolicy Bypass -File .\rasputin.ps1 start -EnableWarSat -NoOpen
~~~

An administrator must also enable Docker control in Settings -> Safety. Run WarSat readiness before
deploying a model. GPU/model-image compatibility remains runtime-specific.

### Optional profiles

The rag and search Compose profiles add Chroma and SearXNG:

~~~bash
docker compose --profile rag up --build -d
docker compose --profile search up --build -d
~~~

Use the same commands in PowerShell. Stop them with:

~~~bash
docker compose --profile rag --profile search down
~~~

## Native Server (Windows)

Native Server is the managed non-Docker option for Windows. It runs independently of Electron,
records its PID, URL, and data directory under %LOCALAPPDATA%\Rasputin\data, and gives approved
workspaces direct host-folder access. Docker remains optional for the backend but is required for
Action Skills and WarSat model containers.

~~~powershell
.\rasputin.ps1 native-host-start -Port 8788
.\rasputin.ps1 native-host-status
.\rasputin.ps1 native-host-restart
.\rasputin.ps1 native-host-stop
~~~

The controller waits for /api/health, attempts a graceful Uvicorn shutdown, and falls back to
process-tree termination only after a timeout. Fresh credentials are printed once by the start
command and are not written to the persistent host log.

Desktop and Native Server share this data store deliberately; never open two independent backends
against it. If Native Server is already running, Electron attaches to its stable URL. Native Host
refuses to start when an Electron-owned backend already holds the store.

Start-at-login is available for the current Windows user:

~~~powershell
.\rasputin.ps1 native-host-install -Port 8788
.\rasputin.ps1 native-host-uninstall
~~~

This creates a per-user startup entry, not a machine service. The user must remain signed in.

For direct LAN access, generate HTTPS first and then use -Lan. Plain HTTP LAN mode is rejected.

## Desktop (Windows)

Desktop is an Electron lifecycle shell around the same native backend and frontend. It binds to
loopback, manages the backend from the window/tray, and uses the native data store.

~~~powershell
npm run desktop
npm run desktop:package:dir
npm run desktop:package
~~~

Packages are currently unsigned and may trigger a Windows publisher warning. The packaged target
does not need Python or Node, but Docker is still required for Action Skills and WarSat.

## Private remote access

Keep the server bound to loopback and use a reviewed private transport. Do not expose an unencrypted
HTTP instance directly to the public internet.

Tailscale planning (run from a Python-enabled checkout):

~~~bash
python3 scripts/setup_remote_access.py tailscale --target http://127.0.0.1:8787
~~~

~~~powershell
.\.venv\Scripts\python.exe scripts\setup_remote_access.py tailscale --target http://127.0.0.1:8787
~~~

Review the reported URL and allowed host, then add --apply only after confirming the target. The
helper does not enable Tailscale Funnel or public internet access.

For Caddy, generate a reviewed configuration:

~~~bash
python3 scripts/setup_remote_access.py caddy --hostname rasputin.example.com --target http://127.0.0.1:8787 --output ./Caddyfile
~~~

~~~powershell
.\.venv\Scripts\python.exe scripts\setup_remote_access.py caddy --hostname rasputin.example.com --target http://127.0.0.1:8787 --output C:\Rasputin\Caddyfile
~~~

Add the proxy hostname to the managed native launcher when using Native Server. Public access also
requires real DNS, a trusted certificate, hardened firewall rules, and a security review.

## Verification

The verifier checks health, frontend serving, and baseline security headers. Run it against every
active endpoint:

macOS/Linux:

~~~bash
./.venv/bin/python scripts/verify_deployment_matrix.py --endpoint docker=http://127.0.0.1:8787
~~~

Windows PowerShell:

~~~powershell
.\.venv\Scripts\python.exe scripts\verify_deployment_matrix.py --endpoint docker=http://127.0.0.1:8787 --endpoint native=http://127.0.0.1:8788
~~~

Add --insecure only for a private certificate during local verification.
