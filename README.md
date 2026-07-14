<div align="center">
  <h1>🛡️ Rasputin</h1>
  <p><b>Private, localhost AI workbench for autonomous agents, secure model routing, and brokered research.</b></p>

  ![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
  ![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
  ![React](https://img.shields.io/badge/react-%2320232a.svg?style=for-the-badge&logo=react&logoColor=%2361DAFB)
  ![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
  ![SQLite](https://img.shields.io/badge/sqlite-%2307405e.svg?style=for-the-badge&logo=sqlite&logoColor=white)
</div>

---

Rasputin is a privacy-first AI orchestration platform designed to run on your own machine. The
same wrapper supports a native workstation mode and a Docker server mode; it routes LLM tasks,
executes **Action Skills** in networkless ephemeral Docker sandboxes, processes RAG operations,
and gates sensitive capabilities through explicit permissions and approvals.

## 📑 Table of Contents
- [Core Architecture & Privacy](#-core-architecture--privacy)
- [Key Features](#-key-features)
- [Quick Start (Docker)](#-quick-start-docker)
- [Native Development](#-native-development)
- [Security & Approvals](#-security--approvals)
- [Model Integrations & WarSat](#-model-integrations--warsat)
- [Testing](#-testing)

---

## 🏗 Core Architecture & Privacy

Rasputin operates on a strict zero-trust privacy model:
```text
Approved Local Folders → Rasputin → Local Model Endpoints
Internet Access        → MCP Web Broker Only
```
Models **do not receive direct internet access**. Web search is brokered, query-guarded,
approval-gated by default, and heavily audited. Action Skills run in fresh
`rasputin-sandbox` containers with `--network none`; tool requests cross a private stdio RPC and
the container is destroyed after execution. Native-Windows Host Shell is a different execution
surface: it runs as the low-privilege `Rasputin_sbx` account inside the explicitly enabled
workspace. See `THREAT_MODEL.md` for the boundaries and residual caveats.

## ✨ Key Features

- **Secure Agent Execution:** Networkless ephemeral Skill containers plus a low-privilege,
  workspace-ACL-scoped Host Shell on native Windows.
- **Task Orchestration:** Live SSE updates, cancellation, multi-modal tracing, and human-in-the-loop approvals.
- **Graph RAG & Memory:** Persistent Warmind context engine that compacts old chat history into structured, graph-based local knowledge edges.
- **Warsat Deployment Layer:** Curated protocols to acquire, build, containerize, and deploy AI models natively inside your Docker engine.
- **Approval Gateways:** Pause/resume functionality with an asynchronous, persistent queue for risky actions (file writes, shell commands, model downloads).
- **SQLite Runtime:** Durable storage for sessions, messages, memory schemas, traces, and metrics inside `data/rasputin.db`.

---

## 🚀 Installation & Quick Start

Rasputin can run as a Docker-hosted wrapper (the default commands below) or as a native Windows
wrapper. Docker is still used for Action Skills and WarSat model containers in either topology.

### 🟢 Option 1: The Absolute Beginner's Guide (Windows)

If you have never used Docker, WSL, or coding tools before, follow these exact steps to get Rasputin running on a completely fresh Windows PC.

**Step 1: Enable BIOS Virtualization (Crucial First Step)**
Before Docker can run on Windows, your computer must allow "Virtualization." Sometimes this is turned off by default.
1. Open your Windows Start Menu, type **Task Manager**, and open it.
2. Go to the **Performance** tab and click on **CPU**.
3. Look at the bottom right. If **Virtualization: Enabled** is there, skip to Step 2!
4. If it says **Disabled**, you need to turn it on in your BIOS.
   <details>
   <summary><b>Click here for a quick guide on enabling Virtualization in BIOS</b></summary>

   - Restart your computer. As it turns on, repeatedly tap the BIOS key (usually `F2`, `F12`, `Delete`, or `Esc` depending on your PC brand).
   - Once in the BIOS, use your arrow keys to look for an "Advanced", "Configuration", or "Security" tab.
   - **For Intel CPUs:** Look for `Intel Virtualization Technology`, `Intel VT-x`, or `Virtualization`.
   - **For AMD CPUs:** Look for `SVM Mode`, `AMD-V`, or `Secure Virtual Machine`.
   - Change the setting from **Disabled** to **Enabled**.
   - Save and Exit (usually `F10`), and let Windows boot up normally.
   </details>

**Step 2: Install Docker Desktop**
Docker is the engine that runs Rasputin's isolated sandboxes.
1. Download **Docker Desktop for Windows** from the [official website](https://www.docker.com/products/docker-desktop/).
2. Run the installer. On the configuration screen, ensure the **"Use WSL 2 instead of Hyper-V"** option is checked (it usually is by default). *Note: This automatically installs the necessary Windows Subsystem for Linux (WSL) components for you.*
3. Finish the installation. Windows will likely ask you to **Restart your computer**.

**Step 3: Start the Docker Engine**
1. After your PC restarts, open the **Docker Desktop** application from your Start Menu.
2. Accept the Service Agreement.
3. Wait a few moments for the engine to start. You will know it is ready when the bottom-left of the Docker dashboard says "Engine running" and the icon turns green.

**Step 4: Run the Rasputin Bootstrapper**
You don't need to manually install Git or Python. This command handles everything.
1. Open **Windows PowerShell** (search for "PowerShell" in your start menu).
2. Paste the following command and hit **Enter**:
   ```powershell
   iwr https://raw.githubusercontent.com/Shingenn5/Rasputin/main/install.ps1 -useb | iex
   ```
3. The bootstrapper will download Rasputin, build the sandboxes, and automatically open your browser. **Check your PowerShell window** for your temporary Username and Password to log in!

---

### 🔵 Option 2: 1-Line Bootstrapper (For Devs)

If you already have Docker running, just run the bootstrapper:

**Windows (PowerShell):**
```powershell
iwr https://raw.githubusercontent.com/Shingenn5/Rasputin/main/install.ps1 -useb | iex
```

**macOS / Linux (Bash):**
```bash
curl -s https://raw.githubusercontent.com/Shingenn5/Rasputin/main/install.sh | bash
```

---

### Option 2: Manual Clone & CLI

If you prefer to clone the repository manually, you can use the interactive CLI tools provided in the project root:

```bash
git clone --recurse-submodules https://github.com/Shingenn5/Rasputin.git
cd Rasputin
```

The `token-optimizer` submodule is optional developer tooling; the Rasputin runtime does not
depend on it. A normal clone without submodules is sufficient when you only want to run the app.

Then, launch the manager:
- **Windows:** `.\rasputin.ps1 start`
- **macOS/Linux:** `./rasputin.sh start`

*Note: For the raw, unmanaged startup scripts, you can also use `scripts\start-wrapper.ps1` and `scripts\stop-wrapper.ps1` directly.*

### Interactive CLI Commands
The `rasputin` manager supports the following commands:
- `start` : Builds and runs Rasputin in the background.
- `start -Native [-Port 8788]` *(Windows)* : Runs the wrapper natively in the foreground; runtime data uses `%LOCALAPPDATA%` by default. `-Port` applies only to native mode.
- `start -Native [-Port 8788] [-Lan]` *(Windows)* : Add `-Lan` to listen on the host network after configuring HTTPS.
- `setup-https [-TlsName name,address]` *(Windows)* : Uses the installed `mkcert` executable to create a locally trusted leaf certificate under ignored `data/tls/`.
- `start -EnableWarSat` : Runs Rasputin with the Docker Control layer enabled (allowing it to deploy local models).
- `stop` : Safely tears down the containers.
- `credentials` : Reads the original generated login from current container logs, if that line still exists.
- `reset-password` *(Windows manager)* : Generates and prints a new Docker-mode admin password when the original is unavailable.

### Desktop daily driver

The native daily driver now has an Electron lifecycle shell. From a repository checkout, run
`npm run desktop` to build the frontend and open Rasputin as a desktop application. Closing the
window keeps it available in the system tray, where the Electron-owned Desktop Runtime can be started, stopped,
restarted, or fully quit. Docker remains the browser-based server/appliance deployment.

Development uses the checkout's Python environment. `npm run desktop:package` builds a
self-contained Windows installer with a bundled backend runtime, so target machines do not need
Python or Node.js. See [`docs/DEPLOYMENT_MATRIX.md`](docs/DEPLOYMENT_MATRIX.md) for Desktop, Native
Host, Docker Server, and private remote-access workflows.

The first-run password is generated only when a fresh data store creates its admin account.
`credentials` cannot recover a changed password and may find nothing after container replacement
or log loss even though the account persists. In that case run `.\rasputin.ps1 reset-password`.
On macOS/Linux use `docker compose exec rasputin-wrapper python -m backend.tools.reset_password`.
For native mode, use `python -m backend.tools.reset_password` against that instance's data dir.

### Local accounts and simultaneous users

An administrator can create multiple local accounts in **Settings → Accounts**. Accounts are
stored in the appliance's local data store; login sessions are persistent, revocable, hashed
server-side records. Each user gets private chats, tasks, preferences, and memory. Approved
workspaces are shared only through explicit viewer/contributor/developer/owner membership. Models,
security policy, WarSat, providers, and platform settings remain appliance-wide and admin-only.
This is a single-appliance account model, not SaaS tenant isolation: the machine administrator
still controls the data directory and process.

### Trusted local HTTPS with mkcert

Rasputin integrates with the official [mkcert project](https://github.com/FiloSottile/mkcert) for
development and private-LAN certificates. Install `mkcert` first (on Windows, `choco install
mkcert` or `scoop bucket add extras; scoop install mkcert`), then run:

```powershell
# localhost + loopback + this computer's hostname
.\rasputin.ps1 setup-https

# Include every DNS name/IP other devices will use
.\rasputin.ps1 setup-https -TlsName rasputin.home,192.168.1.25

# Docker server or native daily driver, reachable on the LAN
.\rasputin.ps1 start -Lan
.\rasputin.ps1 start -Native -Port 8788 -Lan
```

The launcher detects `data/tls/rasputin.pem` and `rasputin-key.pem`, enables TLS, and marks session
cookies Secure. For another device to trust the site, install the **public** mkcert `rootCA.pem` on
that device. Never copy or share `rootCA-key.pem`. mkcert is for local/private use; use a publicly
trusted certificate and reverse proxy for an Internet-facing deployment.

### Advanced Docker Profiles (Manual Mode)
- **RAG Vector Database:** `docker compose --profile rag up --build`
- **Search Broker (SearXNG):** `docker compose --profile search up --build`

---

## 💻 Native Development

For the supported native launcher on Windows, use `.\rasputin.ps1 start -Native`. For a manual
bare-metal development loop, ensure you have Python 3.12+ and Node.js v22+ installed.

### Run Docker and native side by side

Keep the normal Docker instance on `127.0.0.1:8787`, then start the native daily driver on 8788
from a second PowerShell window:

```powershell
# Docker remains detached on its normal port.
.\rasputin.ps1 start

# In a second PowerShell, use the canonical native data store and a separate port.
Remove-Item Env:\RASPUTIN_DATA_DIR -ErrorAction SilentlyContinue
.\rasputin.ps1 start -Native -Port 8788
```

Without HTTPS, open the two instances with these exact hostnames:

- Docker: `http://127.0.0.1:8787`
- Native: `http://localhost:8788`

Use `localhost` for native and `127.0.0.1` for Docker deliberately. The `rasputin_session` cookie is
scoped by hostname, not port; using `127.0.0.1` for both instances would make their cookies collide.
Native uses the separate `%LOCALAPPDATA%\Rasputin\data` store and therefore has its **own admin
account**. On the first native boot, use the credentials printed in that foreground console; Docker
credentials do not automatically work there. `Ctrl+C` stops only the native process.

`RASPUTIN_DATA_DIR`, when set, overrides `%LOCALAPPDATA%\Rasputin\data`; clear a leftover test value
as shown above before judging the canonical daily-driver state. The launcher reuses an existing
`.venv\Scripts\python.exe`, so Python needs to be on `PATH` only when that virtual environment must
be created for the first time.

To prove the native workspace path is direct: open **Workspaces** at `http://localhost:8788`, add a
normal project folder, approve it, and confirm it appears and is browsable immediately with no mount
request, restart badge, or wrapper restart. Docker's folder flow remains mount → restart → approve.

### 1. Start the Backend (FastAPI)
```powershell
pip install -r requirements.txt
python server.py
```

### 2. Start the Frontend (Vite/React)
```powershell
cd frontend-src
npm install
npm run dev
```

### 3. Build for Production
To bake the React frontend into static assets served natively by FastAPI:
```powershell
npm run build
```

---

## 🔒 Security & Approvals

Rasputin prioritizes local safety through stringent defaults:
- **Privacy Lock:** ON by default (disables remote model routing).
- **Remote Endpoints:** BLOCKED unless manually trusted.
- **Docker/Shell Control:** OFF by default.
- **Workspace Operations:** Read-only unless explicitly granted; moves/writes trigger approval reviews.
- **Web Brokering:** Searches are paused and sent to the approval queue.
- **Capability Split:** Trusted Dev Mode auto-approves file/git writes; Host Shell is a separate per-workspace opt-in.
- **Sandbox Isolation:** Skills have no container network. Native-Windows shell commands run as `Rasputin_sbx`; Docker/native-non-Windows shell and git paths have different boundaries documented in `THREAT_MODEL.md`.

> **Important:** Local models, memory databases, vector indexes, workspaces, and `data/model_secrets.json` are automatically ignored by Git.

---

## 🧠 Model Integrations & WarSat

### Local Models (vLLM / llama.cpp)
Rasputin defaults to a local vLLM endpoint (`http://127.0.0.1:8000/v1`). Any OpenAI-compatible backend (LM Studio, Ollama, text-generation-webui) can be natively registered in the interface.

### WarSat Automation
WarSat is Rasputin's model-runtime orchestration layer. It reads curated JSON protocols, generates safe Docker launch plans, approval-gates deployments, and manages local model endpoints directly through the host's Docker socket.

### Cloud Providers
You can configure OpenAI, Anthropic, or Gemini API keys within the UI (stored securely in `data/model_secrets.json`). However, the Privacy Lock **must** be disabled to route requests outside the host machine.

---

## 🧪 Testing

Rasputin includes a dedicated testing harness that runs in a completely isolated environment mapping to `testdata/`.

**Run Backend Smoke Tests (Windows):**
```powershell
.\scripts\test.ps1
```
*(Use `sh scripts/test.sh` on macOS/Linux)*

**Run E2E UI Tests (Playwright):**
```powershell
npm install
npx playwright install chromium
.\scripts\test.ps1 -Ui
```

**GUI Preview Environment:**
```powershell
npm run preview:gui
```
*(Preview UI available at `http://127.0.0.1:8899/preview/home`)*

---

*For detailed architectural insights, review the [Architecture Guide](docs/RASPUTIN_ARCHITECTURE_GUIDE.md) (frontend stack in §4).*
