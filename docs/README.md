# Rasputin documentation index

This index is the map for the repository's documentation. The root
[`README.md`](../README.md) remains the user-facing installation guide; this
file explains which document to use for each job and prevents multiple
competing "current" roadmaps from forming.

## Start here

| Need | Use | Authority |
| --- | --- | --- |
| Install or run Rasputin | [`README.md`](../README.md) | User-facing commands and platform guidance |
| Join the project as a coding agent | [`CODEX_ONBOARDING.md`](CODEX_ONBOARDING.md) | Repository map, test workflow, and agent gotchas |
| Understand the architecture | [`RASPUTIN_ARCHITECTURE_GUIDE.md`](RASPUTIN_ARCHITECTURE_GUIDE.md) | Runtime and frontend architecture reference |
| Deploy or troubleshoot a runtime | [`DEPLOYMENT_MATRIX.md`](DEPLOYMENT_MATRIX.md) | Docker, native, desktop, and remote-access matrix |
| Prepare a release | [`RELEASE_SETUP.md`](RELEASE_SETUP.md) and [`PUBLIC_RELEASE_AUDIT.md`](PUBLIC_RELEASE_AUDIT.md) | Operational release steps and audit evidence |
| Change security-sensitive behavior | [`THREAT_MODEL.md`](../THREAT_MODEL.md), [`SECURITY.md`](../SECURITY.md) | Security boundaries and reporting policy |

## Current engineering work

These are the documents to consult before starting implementation work.

| Document | Scope | Status |
| --- | --- | --- |
| [`CODING_AGENT_IMPLEMENTATION_CHECKLIST.md`](CODING_AGENT_IMPLEMENTATION_CHECKLIST.md) | Coding-agent capability and verification queue | Active working checklist |
| [`RASPUTIN_APPLICATION_READINESS_GAP_REPORT.md`](RASPUTIN_APPLICATION_READINESS_GAP_REPORT.md) | Release-readiness gaps and evidence requirements | Current readiness report |
| [`RASPUTIN_IMPLEMENTATION_LEDGER.md`](RASPUTIN_IMPLEMENTATION_LEDGER.md) | Compact source/test evidence ledger for current workstation and Assistant status | Reconcile before roadmap edits |
| [`DESKTOP_ARCHITECTURE.md`](DESKTOP_ARCHITECTURE.md) | Windows desktop packaging and lifecycle | Current packaging reference |
| [`WRAPPER_RUNTIME_CONTRACT.md`](WRAPPER_RUNTIME_CONTRACT.md) | Native versus Docker runtime behavior | Runtime contract |
| [`REMAINING_WORK.md`](REMAINING_WORK.md) | Dual-mode/security residuals and packaging track | Track-specific status; not a replacement for the checklist |
| [`LASTING_MEMORY.md`](LASTING_MEMORY.md) | Owner/workspace-scoped durable memory contract and current API/UI | Implemented foundation; follow-up slices remain |
| [`MCP_CAPABILITY_CONTRACT.md`](MCP_CAPABILITY_CONTRACT.md) | Versioned MCP tool discovery and callable-only model surface | Implemented capability contract |
| [`ASSISTANT_COMMAND_ROUTING.md`](ASSISTANT_COMMAND_ROUTING.md) | Deterministic assistant command previews and approval states | Implemented preview boundary |
| [`LOCAL_VOICE_ADAPTER.md`](LOCAL_VOICE_ADAPTER.md) | Local speech-to-text and text-to-speech transport contract | Implemented device-free vertical slice |

## Product direction and design records

These documents describe direction, proposals, or lessons. They do not override
implemented behavior or security policy.

| Document | Purpose |
| --- | --- |
| [`RASPUTIN_PERSONAL_ASSISTANT_EVOLUTION_PROPOSAL.docx`](RASPUTIN_PERSONAL_ASSISTANT_EVOLUTION_PROPOSAL.docx) / [`PDF`](RASPUTIN_PERSONAL_ASSISTANT_EVOLUTION_PROPOSAL.pdf) | Reviewable visual proposal for Rasputin's personal-assistant direction |
| [`RASPUTIN_FEATURE_EXPANSION_STRATEGY.docx`](RASPUTIN_FEATURE_EXPANSION_STRATEGY.docx) | Earlier feature-expansion strategy artifact |
| [`RASPUTIN_VS_ODYSSEUS_COMPARISON.md`](RASPUTIN_VS_ODYSSEUS_COMPARISON.md) | Product and architecture comparison |
| [`ODYSSEUS_INSPIRED_RASPUTIN_ROADMAP.md`](ODYSSEUS_INSPIRED_RASPUTIN_ROADMAP.md) | Project Prometheus roadmap and adoption boundaries |
| [`PROJECT_PROMETHEUS_PHASE_0_STATUS.md`](PROJECT_PROMETHEUS_PHASE_0_STATUS.md) | Phase-0 milestone record |

## Governance, upstream, and audit records

| Area | Documents |
| --- | --- |
| Repository governance | [`GOVERNANCE.md`](../GOVERNANCE.md), [`CONTRIBUTING.md`](../CONTRIBUTING.md), [`CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md) |
| Upstream decisions | [`UPSTREAM_ADOPTION_POLICY.md`](UPSTREAM_ADOPTION_POLICY.md), [`upstream/ADOPTION_REGISTER.md`](upstream/ADOPTION_REGISTER.md), [`upstream/ODYSSEUS_MODULE_STUDY.md`](upstream/ODYSSEUS_MODULE_STUDY.md) |
| Public-release evidence | [`PUBLIC_RELEASE_AUDIT.md`](PUBLIC_RELEASE_AUDIT.md) |

## Repository map

| Path | Role | Edit policy |
| --- | --- | --- |
| `backend/` | FastAPI services, orchestration, security, model/runtime adapters | Source of truth |
| `frontend-src/` | React/Vite source | Source of truth; edit this tree |
| `frontend/` | Vite production output | Generated; never hand-edit |
| `tests/` | Backend, integration, and UI verification | Extend with behavior changes |
| `scripts/` | Verification, deployment, and maintenance helpers | Keep commands documented in README |
| `desktop/`, `deploy/`, `sandbox/` | Desktop shell, deployment assets, and sandbox runtime | Runtime-specific source |
| `workspace/`, `models/`, `data/` | Local mounts, model files, and runtime state | Local state; ignored by Git |
| `build/`, `dist/`, `node_modules/`, `.venv/` | Build output and local dependencies | Generated/local; ignored by Git |

## Documentation maintenance rules

1. Trust code and passing tests over a stale claim in a document.
2. Put user-facing installation and lifecycle commands in the root README.
3. Put per-runtime deployment details in `DEPLOYMENT_MATRIX.md`; link to it
   instead of copying the same command tables into another document.
4. Put active implementation work in the checklist or a dated readiness report.
   Keep proposals and milestone audits clearly labeled as design/history.
5. Add new proposal or research artifacts under a descriptive subdirectory
   when the collection grows; update this index in the same change.
6. Do not commit generated frontend output, runtime state, model weights,
   credentials, or test reports.
7. Run `C:\Users\elliott\OneDrive\Documents\WrapperProject\.venv\Scripts\python.exe scripts\verify_docs.py`
   after documentation changes to catch broken local links, stale generated-frontend instructions,
   missing onboarding commands, and incomplete ledger statuses.

If a document and the application disagree, fix the document or record the
known gap; do not silently widen the implementation to match stale prose.
