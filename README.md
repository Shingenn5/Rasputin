<div align="center">
  <h1>🛡️ Rasputin</h1>
  <p><b>Private, local-first AI workbench for autonomous agents, secure model routing, and brokered research.</b></p>

  ![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
  ![FastAPI](https://img.shields.io/badge/FastAPI-005571.svg?style=for-the-badge&logo=fastapi)
  ![React](https://img.shields.io/badge/react-%2320232a.svg?style=for-the-badge&logo=react&logoColor=%2361DAFB)
  ![Python](https://img.shields.io/badge/python-3670A0.svg?style=for-the-badge&logo=python&logoColor=ffdd54)
  ![SQLite](https://img.shields.io/badge/sqlite-%2307405e.svg?style=for-the-badge&logo=sqlite&logoColor=white)
</div>

Rasputin runs on your own machine. One FastAPI backend and one React frontend support a desktop
application, a persistent native Windows server, a Docker server, and private remote access. The
same permission and approval model governs every shape.

## Table of contents

- [Architecture and privacy](#architecture-and-privacy)
- [Choose how to run Rasputin](#choose-how-to-run-rasputin)
- [Prerequisites](#prerequisites)
- [Option 1: Docker Server](#option-1-docker-server)
- [Option 2: Native Server on Windows](#option-2-native-server-on-windows)
- [Option 3: Rasputin Desktop](#option-3-rasputin-desktop)
- [Option 4: Foreground native development](#option-4-foreground-native-development)
- [Private LAN and remote access](#private-lan-and-remote-access)
- [First-run setup](#first-run-setup)
- [Models and WarSat](#models-and-warsat)
- [Security defaults](#security-defaults)
- [Development and testing](#development-and-testing)
- [Distribution status](#distribution-status)

## Architecture and privacy

```text
Approved Local Folders → Rasputin → Local Model Endpoints
Internet Access        → Brokered and policy-gated services
```

Models do not receive unrestricted internet access. Web search is brokered and audited. Action
Skills run in fresh Docker containers with `--network none`. Native Windows Host Shell is a
separate capability that runs as the low-privilege `Rasputin_sbx` account inside explicitly
enabled workspaces. Read [THREAT_MODEL.md](THREAT_MODEL.md) before changing security-sensitive
behavior.

Core features include:

- agentic chat, plan, execute, and reflect workflows;
- durable tasks, approvals, audit records, memory, and local accounts;
- direct native workspaces or explicit Docker mounts;
- local and remote model registration;
- WarSat-managed Docker model deployment;
- networkless Action Skills and an opt-in native Host Shell.

## Choose how to run Rasputin

| Option | Best for | Lifecycle | Default address | Main requirements |
| --- | --- | --- | --- | --- |
| **Docker Server** | Shared browser appliance and repeatable server boundary | Docker Compose | `http://127.0.0.1:8787` | Docker Desktop or Docker Engine |
| **Native Server** | Persistent Windows daily driver with direct folders | Background native controller | `http://localhost:8788` | Windows and Python 3.12+; Docker for Skills/WarSat |
| **Desktop** | One Windows operator using an app window and tray | Electron | Random loopback port | Source launch: Python 3.12+ and Node 22+ |
| **Foreground native** | Development, logs, and manual debugging | Current terminal | Configurable | Windows, Python 3.12+, Node 22+ for frontend rebuilds |
| **Private remote access** | Other trusted devices on a LAN or tailnet | Native or Docker plus TLS/proxy | Stable HTTPS name | An existing server option plus Tailscale or Caddy |

Desktop and Native Server share `%LOCALAPPDATA%\Rasputin\data`. Do not run two independent native
backends against that store. Desktop attaches to an already-running Native Server instead.

Docker uses its own named volume and account database. Native and Docker are intentionally
separate installations even when they run on the same computer.

## Prerequisites

### Docker-backed features

Install and start [Docker Desktop](https://www.docker.com/products/docker-desktop/) on Windows or
macOS, or Docker Engine with the Compose plugin on Linux. On Windows, Docker Desktop normally uses
WSL 2 and requires hardware virtualization.

Docker is required for:

- Docker Server;
- Action Skill containers;
- WarSat-managed model containers.

Native Server and Desktop can open without Docker, but those Docker-backed features remain
unavailable until the Docker engine is running.

### Source-based Windows options

- Windows PowerShell 5.1 or newer;
- Python 3.12+ for Native Server, foreground native, and Desktop development;
- Node.js 22+ when rebuilding the frontend or launching/packaging Desktop;
- Git only when cloning manually.

## Option 1: Docker Server

Docker Server is the simplest cross-platform source deployment and the preferred shared appliance
boundary. Python and Node are not required on the host because the image builds them into the
container.

### One-line Windows bootstrap

Start Docker Desktop, open PowerShell, and run:

```powershell
iwr https://raw.githubusercontent.com/Shingenn5/Rasputin/main/install.ps1 -UseBasicParsing | iex
```

The installer downloads the `main` branch into a `Rasputin` folder under the current directory,
builds the Docker image, starts the server, opens the browser, and prints fresh first-run
credentials. The GitHub repository must be accessible to the person running this command.

### One-line macOS/Linux bootstrap

```bash
curl -fsSL https://raw.githubusercontent.com/Shingenn5/Rasputin/main/install.sh | bash
```

This requires `curl`, `unzip`, Docker, and Docker Compose.

### Manual clone

```powershell
git clone https://github.com/Shingenn5/Rasputin.git
cd Rasputin
.\rasputin.ps1 start
```

On macOS/Linux:

```bash
git clone https://github.com/Shingenn5/Rasputin.git
cd Rasputin
./rasputin.sh start
```

The optional `token-optimizer` submodule is developer tooling; the application does not require it.

### Docker lifecycle commands

```powershell
.\rasputin.ps1 start
.\rasputin.ps1 stop
.\rasputin.ps1 credentials
.\rasputin.ps1 reset-password
```

Use `./rasputin.sh` with `start`, `stop`, or `credentials` on macOS/Linux. To use a different Docker
port in PowerShell, set `$env:WRAPPER_PORT` before `start`.

### Docker Server with WarSat control

The normal Docker Server does not mount the host Docker socket. To let WarSat create sibling model
containers, start the opt-in Docker-control overlay:

```powershell
.\rasputin.ps1 stop
.\rasputin.ps1 start -EnableWarSat
```

On macOS/Linux:

```bash
./rasputin.sh stop
./rasputin.sh start -EnableWarSat
```

After login, an administrator must also enable **Docker control** in **Settings → Safety**. The
socket grants powerful host control, so both the launch-time overlay and the in-app safety setting
are deliberate gates.

### Optional Docker profiles

```powershell
docker compose --profile rag up --build -d
docker compose --profile search up --build -d
```

The `rag` profile adds Chroma; the `search` profile adds SearXNG.

## Option 2: Native Server on Windows

Native Server runs FastAPI directly on Windows, gives workspaces direct access to approved host
folders, and remains running after the launching terminal exits. Docker Desktop may run alongside
it for Action Skills and WarSat.

### Clone and install the global command

```powershell
git clone https://github.com/Shingenn5/Rasputin.git
cd Rasputin
powershell -NoProfile -ExecutionPolicy Bypass -File .\rasputin.ps1 install-cli
```

The one-time installer creates a user-level `rasputin` command. From any later PowerShell window:

```powershell
rasputin native
```

This creates `.venv` if needed, installs Python dependencies, builds the frontend only when it is
missing, starts the persistent server on port 8788, and opens the browser.

### Native lifecycle commands

```powershell
rasputin native
rasputin native-status
rasputin native-restart
rasputin native-stop
```

After pulling source or dependency changes, rebuild and restart with:

```powershell
rasputin native-rebuild
```

Use `-NoOpen` with `native`, `native-restart`, or `native-rebuild` when no browser should open. Use
`-Port <number>` to override port 8788.

To remove the global command:

```powershell
rasputin uninstall-cli
```

### Start Native Server at login

```powershell
rasputin native-host-install -Port 8788
rasputin native-host-status
rasputin native-host-uninstall
```

This creates a current-user startup entry, not a Windows service. The Windows user must remain
signed in for an always-on Native Server.

### Native Server plus Docker/WarSat

Starting Native Server does not start Docker Desktop. For WarSat deployments:

1. Start Docker Desktop and wait for the engine to report ready.
2. Start Native Server with `rasputin native`.
3. Sign in as an administrator.
4. Enable **Docker control** in **Settings → Safety**.
5. Open WarSat, run readiness, create a plan, approve it, and deploy.

Native WarSat calls the host `docker` CLI directly; it does not use `-EnableWarSat` or the Docker
socket Compose overlay.

### Run Native and Docker side by side

```powershell
# Docker Server
.\rasputin.ps1 start

# Native Server
rasputin native
```

Use `http://127.0.0.1:8787` for Docker and `http://localhost:8788` for Native. The different
hostnames prevent their host-scoped login cookies from colliding.

## Option 3: Rasputin Desktop

Desktop is an Electron lifecycle shell around the same native backend and frontend. It binds only
to loopback, manages the backend from the window and system tray, and uses the native data store.

### Launch Desktop from source

```powershell
git clone https://github.com/Shingenn5/Rasputin.git
cd Rasputin
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci
npm run desktop
```

Closing the window keeps Rasputin in the tray by default. The tray can open, start, stop, restart,
or fully quit the Desktop Runtime.

### Build the Windows application or installer

```powershell
npm run desktop:package:dir
npm run desktop:package
```

Outputs land under `dist/electron/`. The packaged application bundles the backend runtime, so a
target computer does not need Python or Node. Current packages are unsigned and may trigger a
Windows publisher warning. Docker Desktop is still required on the target for Action Skills and
WarSat.

See [docs/DESKTOP_ARCHITECTURE.md](docs/DESKTOP_ARCHITECTURE.md) for lifecycle and packaging
details.

## Option 4: Foreground native development

Use the foreground launcher when you want server logs in the current terminal or want `Ctrl+C` to
stop the backend:

```powershell
git clone https://github.com/Shingenn5/Rasputin.git
cd Rasputin
.\rasputin.ps1 start -Native -Port 8788
```

It uses the same native data store as Desktop and Native Server. Stop those first unless you set an
isolated `RASPUTIN_DATA_DIR`.

For a decoupled hot-reload loop:

```powershell
# Terminal 1: backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8787

# Terminal 2: frontend
npm ci
npm run dev
```

Edit `frontend-src/`, never generated `frontend/`. Build production assets with `npm run build`.

## Private LAN and remote access

Do not expose a default HTTP instance directly to the public internet.

### Trusted LAN HTTPS with mkcert

Install the official [`mkcert`](https://github.com/FiloSottile/mkcert) binary, then generate a leaf
certificate containing every hostname or IP clients will use:

```powershell
rasputin setup-https -TlsName rasputin.home,192.168.1.25

# Native Server on the LAN
rasputin native-restart -Lan

# Or Docker Server on the LAN
rasputin start -Lan
```

Install only mkcert's public `rootCA.pem` on trusted client devices. Never copy `rootCA-key.pem`.
mkcert is for private trust, not public internet deployment.

### Tailscale Serve

The helper plans a loopback-only Tailscale Serve configuration before changing anything:

```powershell
.\.venv\Scripts\python.exe scripts\setup_remote_access.py tailscale `
  --target http://127.0.0.1:8788
```

Review the reported URL and allowed hostname, then rerun with `--apply`. Add the reported hostname
to start-at-login configuration when needed:

```powershell
rasputin native-host-install -Port 8788 -AllowedHost rasputin.tailnet.ts.net
```

The helper does not enable Tailscale Funnel or public internet access.

### Caddy reverse proxy

Generate a Caddyfile for review:

```powershell
.\.venv\Scripts\python.exe scripts\setup_remote_access.py caddy `
  --hostname rasputin.example.com `
  --target http://127.0.0.1:8788 `
  --output C:\Rasputin\Caddyfile
```

Public access additionally requires real DNS, a trusted certificate, hardened firewall rules, an
approved Host/Origin name, and an operator security review. Start from
[deploy/Caddyfile.example](deploy/Caddyfile.example).

See [docs/DEPLOYMENT_MATRIX.md](docs/DEPLOYMENT_MATRIX.md) for the complete remote-access and
verification workflow.

## First-run setup

### Credentials

- **Docker Server:** first-run credentials print in the launcher/container logs. Use
  `.\rasputin.ps1 credentials` while that log line remains, or `.\rasputin.ps1 reset-password`.
- **Native Server:** fresh credentials print once when `rasputin native` creates the data store.
- **Desktop:** fresh credentials appear once in the Desktop UI and can be copied before dismissal.

Change the generated administrator password after signing in. Never place credentials in Git,
screenshots, documentation, or issue reports.

### Complete the application setup

1. Open **Settings → Admin** and change the generated password.
2. Open **Models** and register, discover, or deploy a model.
3. Open **Workspaces** and approve a project folder.
4. Review **Settings → Safety** before enabling shell, Docker, remote model, or web capabilities.
5. Open **Settings → Output** and choose a visible Markdown export folder.
6. Add additional local users under **Settings → Accounts** when sharing an appliance.

Native workspaces are available immediately after approval. Docker workspaces must already be
visible inside the container; new host folders follow the mount request → restart → approve flow.

## Models and WarSat

### Existing local endpoints

Register any OpenAI-compatible endpoint, including vLLM, llama.cpp, Ollama, LM Studio, or
text-generation-webui, from **Models**. Native endpoints normally use `127.0.0.1`; Docker Server
reaches host endpoints through `host.docker.internal`.

### WarSat deployments

WarSat reads curated protocols, checks hardware, creates approval-gated Docker launch plans, pulls
images, starts model containers bound to loopback, probes health, and registers successful models.

- **Native Server/Desktop:** Docker Desktop running + Docker control enabled in Safety.
- **Docker Server:** launch with `-EnableWarSat` + Docker control enabled in Safety.

Model-specific GPU, VRAM, runtime, and tool-call-parser requirements still apply. Run WarSat
readiness before deploying.

### Cloud providers

OpenAI, Anthropic, Gemini, and other supported remote endpoints can be configured in the UI. Remote
routing remains blocked while Privacy Lock or remote-model restrictions are enabled. Store API keys
only in the ignored local secret store or environment variables.

## Security defaults

- Privacy Lock is on.
- Remote model routing is blocked.
- Docker control and Host Shell are off.
- File moves and risky writes require approval.
- Web access is brokered and audited.
- Native Host Shell is a separate per-workspace opt-in from Trusted Dev Mode.
- Local databases, secrets, models, workspaces, logs, and generated indexes are ignored by Git.

Rasputin is a single-appliance account model, not SaaS tenant isolation. The machine administrator
ultimately controls the process and data directory.

## Development and testing

Install development dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci
npx playwright install chromium
```

Common checks:

```powershell
# Frontend production build
npm run build

# Backend tests
.\.venv\Scripts\python.exe -m unittest tests.testBackendSmoke tests.testMultiUser

# Repository safety and Docker/UI harness
npm run checkRepoSafety
.\scripts\test.ps1 -Ui
```

On macOS/Linux, use `sh scripts/test.sh`. For isolated native UI verification, set a temporary
`RASPUTIN_DATA_DIR` and use a non-production port such as 8899.

Validate active deployment shapes with:

```powershell
.\.venv\Scripts\python.exe scripts\verify_deployment_matrix.py `
  --endpoint docker=http://127.0.0.1:8787 `
  --endpoint native=http://127.0.0.1:8788 `
  --require-desktop-artifacts
```

## Distribution status

The repository can be run from source and can build a self-contained Windows installer. It is not
yet a polished public release channel:

- Desktop packages are unsigned.
- No installer artifact or container image is automatically published.
- Update-channel metadata and upgrade testing remain open.
- Clean-machine installation must be verified before a release.
- Licensing and public-distribution terms must be decided before making the repository public.

Track those items in [docs/REMAINING_WORK.md](docs/REMAINING_WORK.md) and use
[docs/RELEASE_SETUP.md](docs/RELEASE_SETUP.md) for release validation.

## How this project used Codex and GPT-5.6

Rasputin was built with a human-directed engineering workflow using Codex as a coding partner and
GPT-5.6 as the reasoning model available through that environment. The project owner set product
direction and security boundaries, reviewed meaningful changes, and controlled commits and
publication. Generated work was inspected against the codebase and verified with repository build,
test, and running-app workflows before acceptance.

For architecture details, see [docs/RASPUTIN_ARCHITECTURE_GUIDE.md](docs/RASPUTIN_ARCHITECTURE_GUIDE.md).
