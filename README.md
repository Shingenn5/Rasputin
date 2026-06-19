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

Rasputin is a privacy-first, secure AI orchestration platform designed to run entirely on your local machine. It provides a robust backend to route LLM tasks, execute **Action Skills** via ephemeral Docker sandboxes, process RAG operations, and perform approval-gated capabilities, all while guaranteeing zero unbrokered outbound internet access for your models.

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
Models **do not receive direct internet access**. Web search is brokered, query-guarded, approval-gated by default, and heavily audited. Action Skills (like generating or running code) are executed inside strictly isolated, ephemeral Docker Sandboxes (`rasputin-sandbox`) that are immediately destroyed after execution.

## ✨ Key Features

- **Secure Agent Execution:** Run capabilities through isolated Ephemeral Docker Sandboxes.
- **Task Orchestration:** Live SSE updates, cancellation, multi-modal tracing, and human-in-the-loop approvals.
- **Graph RAG & Memory:** Persistent Warmind context engine that compacts old chat history into structured, graph-based local knowledge edges.
- **Warsat Deployment Layer:** Curated protocols to acquire, build, containerize, and deploy AI models natively inside your Docker engine.
- **Approval Gateways:** Pause/resume functionality with an asynchronous, persistent queue for risky actions (file writes, shell commands, model downloads).
- **SQLite Runtime:** Durable storage for sessions, messages, memory schemas, traces, and metrics inside `data/rasputin.db`.

---

## 🚀 Quick Start (Docker)

The fastest and most robust way to launch Rasputin is using the provided Docker wrapper scripts.

```powershell
# Clone the repository
cd path\to\Rasputin

# Launch the orchestrator
.\start-wrapper.ps1
```

Once the container reports as healthy, access the UI at:
**[http://127.0.0.1:8787](http://127.0.0.1:8787)**

> **Note:** First-run administrator credentials are automatically generated and printed in the container logs. Retrieve them using:
> ```powershell
> docker compose logs rasputin-wrapper
> ```

### Advanced Docker Profiles
- **Detached Mode:** `.\start-wrapper.ps1 -Detached`
- **Docker Control Layer (WarSat):** `.\start-wrapper-docker-control.ps1`
- **RAG Vector Database:** `docker compose --profile rag up --build`
- **Search Broker (SearXNG):** `docker compose --profile search up --build`
- **Stop Rasputin:** `.\stop-wrapper.ps1`

---

## 💻 Native Development

If you prefer to run the application bare-metal without Docker, ensure you have Python 3.12+ and Node.js v22+ installed.

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
- **Sandbox Isolation:** AI-generated python execution is fenced in an unprivileged alpine container.

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

*For detailed architectural insights, review the [Architecture Guide](docs/RASPUTIN_ARCHITECTURE_GUIDE.md) and [Frontend Planning](docs/FRONTEND_REDESIGN_PLAN.md) documents.*
