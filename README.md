<div align="center">
  <h1>Rasputin</h1>
  <p><b>Private, local-first AI workbench for agentic coding, model routing, and brokered research.</b></p>

  ![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
  ![FastAPI](https://img.shields.io/badge/FastAPI-005571.svg?style=for-the-badge&logo=fastapi)
  ![React](https://img.shields.io/badge/react-%2320232a.svg?style=for-the-badge&logo=react&logoColor=%2361DAFB)
  ![Python](https://img.shields.io/badge/python-3670A0.svg?style=for-the-badge&logo=python&logoColor=ffdd54)
</div>

Rasputin runs on your own computer. It combines a FastAPI backend, React frontend, local and remote
model providers, durable tasks, workspaces, approvals, memory, and an explicit permission model.
The Docker deployment is the supported cross-platform server for Windows, macOS, and Linux. A
managed native server and a desktop application are also available on Windows.

## Choose the right installation

| Platform | Recommended path | Host requirements | Default URL |
| --- | --- | --- | --- |
| Windows | Docker Server, or Native Server/Desktop for direct Windows folders | Docker Desktop for Docker; Python 3.12+ for native; Node 22+ for source builds | Docker http://127.0.0.1:8787; native http://localhost:8788 |
| macOS | Docker Server | Docker Desktop; Git or curl/unzip for installation | http://127.0.0.1:8787 |
| Linux | Docker Server | Docker Engine plus the Compose v2 plugin; Git or curl/unzip for installation | http://127.0.0.1:8787 |

Docker is the supported shared/server boundary on every platform. The managed Native Server and
packaged Desktop runtime are Windows-specific today. Linux and macOS users can still run the
backend from source for development, but Docker is the simplest production-like installation.

## Contents

- [Choose the right installation](#choose-the-right-installation)
- [Quick start: Docker Server](#quick-start-docker-server)
- [Docker lifecycle commands](#docker-lifecycle-commands)
- [First login and safe setup](#first-login-and-safe-setup)
- [Upgrades, backup, and restore](#upgrades-backup-and-restore)
- [Optional Docker integrations](#optional-docker-integrations)
- [LAN and private remote access](#lan-and-private-remote-access)
- [Windows-native options](#windows-native-options)
- [Source development on any platform](#source-development-on-any-platform)
- [Verification and troubleshooting](#verification-and-troubleshooting)
- [Documentation index](docs/README.md)

## Architecture and privacy

Approved local folders flow through Rasputin to explicitly registered model endpoints. Models do
not receive unrestricted internet access: web search is brokered and audited, and Action Skills run
in fresh networkless Docker containers. Docker control, remote models, Host Shell, risky file moves,
and LAN publishing are opt-in capabilities. Read [THREAT_MODEL.md](THREAT_MODEL.md) before changing
security-sensitive settings.

## What Docker runs and what it stores

The standard Compose deployment contains one rasputin-wrapper service. The image includes Python,
the built frontend, Git, and the runtime dependencies; Python and Node do not need to be installed
on a Docker-only host.

| Data | Location | Persistence |
| --- | --- | --- |
| Accounts, settings, tasks, approvals, memory | Docker named volume rasputin-data | Persistent across rebuilds and docker compose down |
| Approved project files | ./workspace on the host, mounted at /app/workspace | Host files; approve folders in the UI |
| Optional local model files | ./models on the host, read-only at /app/models | Host files |
| Hugging Face and llama.cpp caches | Named Docker volumes | Persistent model-weight caches |
| Optional TLS leaf certificate | ./data/tls on the host | Ignored local files; never commit keys |

Do not use docker compose down -v unless you intentionally want to delete the application volume.
The data/, workspace/, and models/ directories are created by the launchers and are ignored by Git.

## Quick start: Docker Server

Docker Server is the recommended first installation for Windows, macOS, and Linux.

### Prerequisites

Install and start one of the following before launching Rasputin:

- Windows or macOS: [Docker Desktop](https://www.docker.com/products/docker-desktop/).
- Linux: [Docker Engine](https://docs.docker.com/engine/install/) and the
  [Docker Compose v2 plugin](https://docs.docker.com/compose/install/). Verify with docker version
  and docker compose version.

On Linux, a non-root user normally needs access to the Docker socket. Adding a user to the docker
group grants root-equivalent control of the machine; use your distribution's documented Docker
installation procedure and log in again after changing group membership.

The convenience installers also need curl and unzip on macOS/Linux. A manual Git clone avoids unzip.

### Option A: convenience installer

Review the installer before piping it to a shell on a machine you care about. The installer
downloads the repository, creates a local checkout, builds the image, and starts the server. It
does not install Docker for you. Use a manual clone when you need to pin and review a specific ref.

macOS/Linux:

~~~bash
curl -fsSL https://raw.githubusercontent.com/Shingenn5/Rasputin/main/install.sh | bash
~~~

Windows PowerShell:

~~~powershell
iwr https://raw.githubusercontent.com/Shingenn5/Rasputin/main/install.ps1 -UseBasicParsing | iex
~~~

The installer places the checkout in a Rasputin folder under the current directory. For a
reviewable, repeatable install, use the manual clone below instead.

### Option B: manual clone (recommended for upgrades)

macOS/Linux:

~~~bash
git clone https://github.com/Shingenn5/Rasputin.git
cd Rasputin
chmod +x rasputin.sh
./rasputin.sh config
./rasputin.sh start --no-open
~~~

Windows PowerShell:

~~~powershell
git clone https://github.com/Shingenn5/Rasputin.git
Set-Location Rasputin
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\rasputin.ps1 config
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\rasputin.ps1 start -NoOpen
~~~

Open http://127.0.0.1:8787 after the health check succeeds. Omit --no-open/-NoOpen if you
want the launcher to open the browser automatically.

The launcher builds the image on every start, so the first launch downloads the base images and
installs the frontend and Python dependencies inside Docker. Later starts use Docker's build cache.

### Configure the Docker deployment

The repository includes .env.example. Copy it to .env only when you need to change defaults;
Compose loads .env automatically.

macOS/Linux:

~~~bash
cp .env.example .env
~~~

Windows PowerShell:

~~~powershell
Copy-Item .env.example .env
~~~

Important settings:

| Variable | Default | Use |
| --- | --- | --- |
| WRAPPER_PORT | 8787 | Host port; for example WRAPPER_PORT=8790 |
| WRAPPER_BIND | 127.0.0.1 | Host bind address; keep loopback unless HTTPS/LAN access is intentional |
| RASPUTIN_HTTPS | 0 | Set automatically by the launchers when data/tls contains a leaf certificate |
| MAIN_VLLM_BASE_URL | http://host.docker.internal:8000/v1 | Host model endpoint reachable from the wrapper container |
| RASPUTIN_LOCALHOST_BYPASS | 0 | Development-only compatibility switch; keep disabled for normal use |

For a one-off port change:

~~~bash
WRAPPER_PORT=8790 ./rasputin.sh start --no-open
~~~

~~~powershell
$env:WRAPPER_PORT = "8790"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\rasputin.ps1 start -NoOpen
~~~

## Docker lifecycle commands

Run these from the repository directory.

| Action | macOS/Linux | Windows PowerShell |
| --- | --- | --- |
| Start/rebuild | ./rasputin.sh start | powershell -ExecutionPolicy Bypass -File .\rasputin.ps1 start |
| Start without opening a browser | ./rasputin.sh start --no-open | powershell -ExecutionPolicy Bypass -File .\rasputin.ps1 start -NoOpen |
| Status and health | ./rasputin.sh status | powershell -ExecutionPolicy Bypass -File .\rasputin.ps1 status |
| Recent logs | ./rasputin.sh logs | powershell -ExecutionPolicy Bypass -File .\rasputin.ps1 logs |
| First-run credentials | ./rasputin.sh credentials | powershell -ExecutionPolicy Bypass -File .\rasputin.ps1 credentials |
| Reset admin password | ./rasputin.sh reset-password | powershell -ExecutionPolicy Bypass -File .\rasputin.ps1 reset-password |
| Validate Compose | ./rasputin.sh config | powershell -ExecutionPolicy Bypass -File .\rasputin.ps1 config |
| Stop, keep data | ./rasputin.sh stop | powershell -ExecutionPolicy Bypass -File .\rasputin.ps1 stop |

start rebuilds the local image and recreates the container without removing named volumes. Use
docker compose ps and docker compose logs --tail 120 rasputin-wrapper directly when the launcher
is unavailable.

## First login and safe setup

1. Get the generated credentials with the launcher's credentials command, or read them from
   docker compose logs rasputin-wrapper during the first boot.
2. Sign in at the local URL and immediately change the generated administrator password in
   Settings -> Admin.
3. Register or deploy a model in Models. Docker reaches a model running on the host through
   host.docker.internal, not 127.0.0.1 inside the container.
4. Approve a project folder in Workspaces. Docker workspaces must be visible inside the container;
   approving a new host folder may write a Compose mount override and require a restart.
5. Review Settings -> Safety before enabling Docker control, remote models, web access, Host Shell,
   or other capabilities.
6. Add other local users under Settings -> Accounts only after the administrator account is
   protected.

Privacy Lock is enabled by default. Remote model routing, Docker control, Host Shell, risky file
moves, and other privileged actions remain gated by explicit settings and/or approvals.

## Upgrades, backup, and restore

### Upgrade without deleting application data

~~~bash
git pull --ff-only
./rasputin.sh start --no-open
~~~

~~~powershell
git pull --ff-only
powershell.exe -ExecutionPolicy Bypass -File .\rasputin.ps1 start -NoOpen
~~~

The named volume is intentionally retained. Never run docker compose down -v as part of a normal
upgrade.

### Back up the application volume

Stop the server first for a consistent SQLite snapshot, then create a backup directory.

macOS/Linux:

~~~bash
./rasputin.sh stop
mkdir -p backups
docker run --rm -v rasputin-data:/source -v "$PWD/backups:/backup" alpine \
  sh -c 'tar czf /backup/rasputin-data.tgz -C /source .'
~~~

Windows PowerShell:

~~~powershell
powershell.exe -ExecutionPolicy Bypass -File .\rasputin.ps1 stop
New-Item -ItemType Directory -Force backups | Out-Null
docker run --rm -v rasputin-data:/source -v "$PWD\backups:/backup" alpine sh -c "tar czf /backup/rasputin-data.tgz -C /source ."
~~~

Also back up project files under workspace/ and any model files under models/ separately. Keep
archives private: they can contain accounts, task history, memory, configuration, and secrets.

Restore only after stopping Rasputin and confirming the target volume. A volume restore is
deliberately not automated by the launcher because replacing application state is destructive.

## Optional Docker integrations

### WarSat model deployment

The normal Docker Server does not mount the host Docker socket. WarSat control is an explicit,
powerful opt-in because the socket can control sibling containers and the host Docker engine.

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

After signing in, an administrator must also enable Docker control in Settings -> Safety. Run WarSat
readiness before deploying a model. GPU support and model images are runtime-specific; the wrapper
itself does not guarantee that every model image supports every host GPU.

### RAG and search profiles

These profiles add optional services and their own local storage:

~~~bash
docker compose --profile rag up --build -d
docker compose --profile search up --build -d
~~~

Use the same commands in PowerShell. Stop them with docker compose --profile rag --profile search
down when they are no longer needed.

## LAN and private remote access

Keep the default loopback bind for local use. Do not publish an unencrypted HTTP instance directly
to a LAN or the public internet.

### Direct private-LAN HTTPS

Install the official [mkcert](https://github.com/FiloSottile/mkcert) binary and Python 3, then
generate a local certificate containing every hostname/IP clients will use.

macOS/Linux:

~~~bash
python3 scripts/setup_https.py --output-dir data/tls --name rasputin.home --name 192.168.1.25
./rasputin.sh start --lan --no-open
~~~

Windows PowerShell:

~~~powershell
py -3 scripts\setup_https.py --output-dir data\tls --name rasputin.home --name 192.168.1.25
powershell.exe -ExecutionPolicy Bypass -File .\rasputin.ps1 start -Lan -NoOpen
~~~

The launchers refuse direct --lan/-Lan mode until both leaf certificate files exist. Install only
mkcert's public rootCA.pem on trusted client devices. Never copy rootCA-key.pem or expose the
generated leaf key. mkcert is for private trust, not a public-internet certificate.

### Tailscale or a reverse proxy

For remote access, keep Rasputin bound to loopback and put it behind a reviewed private transport.
See docs/DEPLOYMENT_MATRIX.md, deploy/Caddyfile.example, and scripts/setup_remote_access.py for
Tailscale Serve and Caddy planning. Do not enable Tailscale Funnel or expose a raw Docker port
without an explicit security review.

## Windows-native options

Windows users who need direct access to host folders can run the managed Native Server instead of
Docker. Docker remains optional for the native backend, but is still required for Action Skills and
WarSat model containers.

### Native Server

Requirements: Windows PowerShell 5.1 or newer and Python 3.12+. From the repository:

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\rasputin.ps1 install-cli
rasputin native -NoOpen
rasputin native-status
rasputin native-rebuild -NoOpen
rasputin native-stop
~~~

Native Server uses %LOCALAPPDATA%\Rasputin\data by default and listens on http://localhost:8788.
Do not run two independent native backends against the same data directory. Native workspaces are
available after approval without Docker mount restarts.

For start-at-login:

~~~powershell
rasputin native-host-install -Port 8788
rasputin native-host-status
rasputin native-host-uninstall
~~~

This is a current-user startup entry, not a Windows service. The user must remain signed in.

### Desktop

Desktop is an Electron window/tray around the same native backend and data store:

~~~powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci
npm run desktop
~~~

Build a Windows package with npm run desktop:package. The current package is unsigned and may
show a Windows publisher warning. See docs/DESKTOP_ARCHITECTURE.md.

## Source development on any platform

Docker is recommended for normal use. For backend/frontend development, install Python 3.12+ and
Node 22+, then create an isolated environment outside the production data store.

macOS/Linux:

~~~bash
python3.12 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
npm ci
npm run build
RASPUTIN_DATA_DIR="$HOME/.cache/rasputin-dev-data" PORT=8899 ./.venv/bin/python server.py
~~~

Windows PowerShell:

~~~powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci
npm run build
$env:RASPUTIN_DATA_DIR = "$env:TEMP\rasputin-dev-data"
$env:PORT = "8899"
.\.venv\Scripts\python.exe server.py
~~~

Open http://127.0.0.1:8899/#chat. Never point a test instance at the real native data directory
or the Docker volume.

## Verification and troubleshooting

Validate an active Docker instance with:

~~~bash
./.venv/bin/python scripts/verify_deployment_matrix.py --endpoint docker=http://127.0.0.1:8787
~~~

~~~powershell
.\.venv\Scripts\python.exe scripts\verify_deployment_matrix.py --endpoint docker=http://127.0.0.1:8787
~~~

The verifier checks /api/health, frontend serving, and baseline security headers. Add the native
endpoint on Windows when it is running.

Common fixes:

| Symptom | What to check |
| --- | --- |
| Docker command says the engine is unavailable | Start Docker Desktop, or start the Linux Docker service; run docker info |
| Port 8787 is already in use | Set WRAPPER_PORT to another host port and use that URL |
| Container is unhealthy | Run ./rasputin.sh logs or rasputin.ps1 logs, then check docker compose ps |
| No credentials appear | The first-boot log may be gone; run reset-password while the container is running |
| Host model is unreachable from Docker | Use host.docker.internal, not 127.0.0.1, in the model URL |
| A new Docker workspace is missing | Approve the folder, allow the mount override, restart, then approve it inside the container |
| LAN mode is refused | Generate data/tls/rasputin.pem and data/tls/rasputin-key.pem with mkcert first |
| Linux permission errors | Confirm the Docker user can access the Docker socket and the checkout/workspace directories |

For security-sensitive behavior, read THREAT_MODEL.md. For the full runtime matrix and
private-remote workflow, read docs/DEPLOYMENT_MATRIX.md.

## Development checks

~~~bash
npm run build
./.venv/bin/python -m unittest tests.testBackendSmoke tests.testMultiUser
npm run checkRepoSafety
~~~

On Windows, replace ./.venv/bin/python with .\.venv\Scripts\python.exe. The Docker harness is
available as ./scripts/test.sh on macOS/Linux and .\scripts\test.ps1 on Windows.

## Project status and license

The repository can be run from source and can build a self-contained Windows application. A
publicly hosted image, signed desktop installer, automated update channel, and clean-machine release
certification remain separate release tasks. Track them in docs/REMAINING_WORK.md.

Rasputin is licensed under the GNU AGPL v3.0 or later (LICENSE). Contributions and upstream reuse
follow CONTRIBUTING.md and docs/UPSTREAM_ADOPTION_POLICY.md.
