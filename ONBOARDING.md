# Welcome to Rasputin

Welcome to the team! This document is designed to get you up to speed on the **Rasputin** architecture, the **WarSat** deployment layer, and how to start shipping code during your first week.

---

## 1. Project Overview

**Rasputin** is a local-first, autonomous AI orchestration system. It manages long-running agentic loops, contextual memory, and workspace routing.

**WarSat** is the operational deployment layer of Rasputin. It is responsible for discovering, downloading, validating, containerizing, and deploying AI models. 

> [!IMPORTANT]
> **Core Rule**: WarSat acts as the single source of truth for all infrastructure-changing operations. No model can be downloaded or deployed silently outside of WarSat. Every action requires an audit log, resource estimation, and rollback capability.

---

## 2. Tech Stack

### 🎨 Frontend
- **Framework**: React 18 & Vite
- **State Management**: Zustand
- **Data Fetching**: TanStack React Query
- **Styling**: React-Bootstrap & Vanilla CSS
- **Icons**: Lucide React
- **Entry point**: `frontend-src/index.html`

### ⚙️ Backend
- **Framework**: FastAPI (Python 3.12)
- **Server**: Uvicorn
- **AI/LLM Integrations**: HuggingFace Hub, OpenAI-compatible APIs, local `llama.cpp` containers.
- **Data Layer**: SQLite (`data/rasputin.db`)
- **Execution Sandboxes**: Ephemeral Docker Containers (`rasputin-sandbox`)
- **Entry point**: `backend/main.py`

---

## 3. Directory Structure & Architecture

Understanding where things live is half the battle:

* `frontend-src/src/features/` - The core UI modules (WarSat, Workspaces, Settings, Trials, Archive).
* `backend/` - The Python logic.
  * `main.py` - FastAPI routes.
  * `engine/agent.py` - The core AI orchestration and autonomous tool loop.
  * `mcp/` - Model Context Protocol servers and the REST API relay.
  * `core/sandbox.py` - Ephemeral Docker Sandbox engine for safely executing Action Skills.
  * `warsat/providers/` - Standardized deployment interfaces (Docker, Kubernetes, local).
  * `rag/` - Graphify memory and vector-search engine with background token consolidation.
  * `trials/` - The evaluation engine for testing deployed models.
* `data/` - The local database. Almost all state (sessions, messages, memory, skills) is stored in the SQLite database (`data/rasputin.db`), superseding the legacy flat JSON files.
* `sandbox/` - The HTTP API clients injected into Ephemeral Docker containers.

---

## 4. Local Development Setup

We use a decoupled frontend/backend setup for local development.

**Terminal 1 (Backend):**
```bash
# From the project root
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8787
```

**Terminal 2 (Frontend):**
```bash
# From the project root
cd frontend-src
npm install
npm run dev
```

---

## 5. Security & Action Skills

One of the most critical parts of Rasputin is how it handles dynamically generated code or scripts. We **never** execute Action Skills directly on the host machine. 

Whenever the agent triggers an Action Skill (e.g., `excel_data_entry`), Rasputin pipes the script into an **Ephemeral Docker Sandbox** (`rasputin-sandbox`). The script communicates back to Rasputin using an injected HTTP API Client (`sandbox/client.py`) before the container is instantly destroyed. Keep this security boundary in mind when writing new skills!

---

## 6. Testing Conventions

Before pushing any code, you must ensure you haven't broken the orchestration loop or WarSat interfaces.

We rely on a comprehensive suite of tests. Run them before every commit:

```bash
python -m unittest discover tests
```

Currently, the `testBackendSmoke.py` suite contains 48 checks covering everything from Graph ingestion to tool standardization. **Do not merge code unless all tests pass (`OK`).**

---

## 7. Your First Week (The Sandbox)

To get you familiar with how data moves through Rasputin without risking breaking the core LLM execution loop, you will be owning **The Trials Engine & The WarSat UI**. 

This is a low-risk, high-impact area. You will be writing isolated Python modules and connecting them to the React frontend.

**Your specific tasks:**
1. **The Trials & Scorecard Evaluation Engine**: Look at `backend/trials/engine.py`. You'll be building out the logic to test newly deployed models against standard prompts and score their outputs (soon to be migrated into the Sandbox Execution model).
2. **WarSat Deployment Dashboards**: Look at `frontend-src/src/features/warsat/WarsatView.jsx`. You'll be building the UI to display active model downloads and container health statuses. 
3. **Workspace Capability Routing**: Look at `frontend-src/src/features/workspaces/WorkspacesView.jsx`. You'll be building the UI dropdowns that allow users to assign the models they deployed in WarSat to specific agents.

> [!TIP]
> Always check `data/models.json` while working. This file is the absolute source of truth for what models are currently "active" in the system.

Welcome aboard! If you have questions about the core deployment engine or the orchestration loop, reach out to the Lead Developer.
