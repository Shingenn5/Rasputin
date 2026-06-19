# Welcome to Rasputin 🧠

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
- **Framework**: FastAPI (Python)
- **Server**: Uvicorn
- **AI/LLM Integrations**: HuggingFace Hub, OpenAI-compatible APIs, local `llama.cpp` containers.
- **Entry point**: `backend/main.py`

---

## 3. Directory Structure

Understanding where things live is half the battle:

* `frontend-src/src/features/` - The core UI modules (WarSat, Workspaces, Settings, Trials, Archive).
* `backend/` - The Python logic.
  * `main.py` - FastAPI routes.
  * `agent.py` - The core AI orchestration loop.
  * `model_registry.py` - Manages the `data/models.json` state and Docker containers.
  * `model_acquisition.py` - Background threads for HuggingFace downloads.
  * `rag.py` & `graphify.py` - The memory and vector-search engine.
  * `trials/` - The evaluation engine for testing deployed models.
* `data/` - The local database. Everything is saved here as flat JSON files (`models.json`, `archive_sessions.json`).

---

## 4. Local Development Setup

We use a decoupled frontend/backend setup for local development.

**Terminal 1 (Backend):**
```bash
# From the project root
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8080
```

**Terminal 2 (Frontend):**
```bash
# From the project root
npm install
npm run dev
```

---

## 5. Your First Week (The Sandbox)

To get you familiar with how data moves through Rasputin without risking breaking the core LLM execution loop, you will be owning **The Trials Engine & The WarSat UI**. 

This is a low-risk, high-impact area. You will be writing isolated Python modules and connecting them to the React frontend.

**Your specific tasks:**
1. **The Trials & Scorecard Evaluation Engine**: Look at `backend/trials/engine.py`. You'll be building out the logic to test newly deployed models against standard prompts and score their outputs.
2. **WarSat Deployment Dashboards**: Look at `frontend-src/src/features/warsat/WarsatView.jsx`. You'll be building the UI to display active model downloads and container health statuses. 
3. **Workspace Capability Routing**: Look at `frontend-src/src/features/workspaces/WorkspacesView.jsx`. You'll be building the UI dropdowns that allow users to assign the models they deployed in WarSat to specific agents.

> [!TIP]
> Always check `data/models.json` while working. This file is the absolute source of truth for what models are currently "active" in the system.

Welcome aboard! If you have questions about the core deployment engine or the orchestration loop, reach out to the Lead Developer, who will be managing the `backend/warsat/providers/` structural refactoring.
