# Rasputin vs. Odysseus

> Comparison scope: upstream observations retain the date of the original review. Rasputin runtime wording was reconciled to the Windows native direction on 2026-08-29. Upstream Docker features describe Odysseus, not a Rasputin setup requirement; historical benchmarks are not current release certification.

## A practical comparison of two self-hosted AI workspaces

> **Assessment date:** July 24, 2026
> **Rasputin reviewed:** `main` at `bdb06f7`
> **Odysseus reviewed:** `dev` at `d8a2059`
> **Bottom line:** Odysseus is currently the broader, more complete personal-AI workspace. Rasputin is the more deliberately governed local-agent and coding workbench.

---

## Executive summary

Rasputin and [Odysseus](https://github.com/odysseus-dev/odysseus) begin from the same attractive premise: your AI workspace should be self-hosted, should work with local models, and should keep the operator in control. They diverge in what they optimize.

**Odysseus optimizes for breadth.** It brings chat, autonomous agents, deep research, documents, email, notes, todos, calendars, contacts, image workflows, web search, model comparison, memory, MCP, and model serving into one large personal workspace. It is much closer to a self-hosted replacement for several everyday productivity applications.

**Rasputin optimizes for governed execution.** It treats the AI as an operator working inside explicit workspaces, roles, approvals, audit trails, model routes, task budgets, and trust boundaries. Its strongest differentiators are controlled file and shell access, coding-oriented agent loops, reviewable diffs, test-loop integration, model certification, and WarSat's inspect-before-deploy model-runtime workflow.

### The short verdict

| Question | Winner today | Why |
|---|---|---|
| Which is the better all-purpose personal AI workspace? | **Odysseus** | Its daily-use surface is dramatically broader. |
| Which is better for email, calendar, notes, documents, research, and images? | **Odysseus** | These are real first-class product areas, not future placeholders. |
| Which has the safer agent execution design? | **Rasputin** | Approvals, trusted-workspace boundaries, audit, declarative skills, and fail-closed native Windows Host Shell are core architecture. |
| Which is more purpose-built for local coding agents? | **Rasputin** | Patch tools, Git review, task streaming, bounded agent loops, workspace commands, test/fix retries, and coding trials are integrated. |
| Which has the larger implementation and test footprint? | **Odysseus** | The reviewed branch contains roughly 1,239 relevant files, 746 Python test files, and more than 4,100 discovered Python test functions. |
| Which is more polished and proven across all claimed environments? | **Neither completely** | Both acknowledge cross-platform and integration gaps. Odysseus has more surface to stabilize; Rasputin has less breadth and several important end-to-end validation gaps. |

---

## What Rasputin currently does

Rasputin is not merely a local chat UI. The current application is a private, multi-user AI appliance with several connected systems.

### 1. Chat and governed agent runs

- Persistent chat sessions, folders, cleanup, search, and deletion.
- Multiple operating modes, including chat and tool-dependent agentic modes.
- Preflight model-capability checks so a chat-only local model does not remain selected for a tool-dependent run.
- A governed multi-phase agent loop with explicit budgets, bounded tool calls, context control, live events, cancellation, pause/resume, retries, and failure states.
- Prompt recipes: five structured starting recipes for every supported mode.
- A task inbox and activity center with priorities, schedules, artifacts, and detailed run inspection.

### 2. Coding-agent workflow

- Approved workspaces with per-user membership roles.
- Read, write, patch, Git status, Git diff, and Git restore tools.
- A coding review drawer with touched files, diffs, terminal output, and per-file revert.
- Per-workspace test, build, and lint commands in the backend.
- A bounded edit → test → diagnose → fix loop inside the same agent time budget.
- Code-structure graph extraction and workspace RAG.
- Coding trials, blind comparisons, datasets, benchmarks, experiments, scorecards, and reports.

This is Rasputin's most coherent competitive lane. It is building toward “give a local model a real repository and let it work safely,” rather than only “chat with files.”

### 3. Native local models

- Registration and discovery of local or remote OpenAI-compatible endpoints.
- Hugging Face and local GGUF catalog scanning.
- Model health tests, compatibility certification, repair, logs, start/stop, and role routing.
- Exact GGUF acquisition and native llama.cpp load planning; separately registered local endpoints retain their own requirements.
- Host hardware inspection, native runtime discovery, load profiles, device placement, and governed lifecycle operations.
- Explicit model-tool parser configuration rather than silently assuming that every model speaks the same tool-call format.
- Installed Windows Desktop and source Native Host workflows with distinct lifecycle ownership.

WarSat's key advantage is not that it can start a model—Odysseus can do that too. Its advantage is that model deployment is represented as a reviewable plan with security checks and an expected registry result before execution.

### 4. Memory and knowledge

- Owner-scoped persistent memory with search and review queues.
- Workspace document ingestion and retrieval.
- A knowledge graph with relation search and evidence.
- Code-aware graph construction.
- Obsidian-oriented graph export.
- Bounded cross-workspace conversational recall.

Rasputin's knowledge model is more workspace- and evidence-oriented than Odysseus's personal-assistant memory. The tradeoff is that it lacks Odysseus's surrounding notes, document library, mail, and calendar corpus.

### 5. Security and administration

- Local accounts with restart-safe sessions.
- Appliance roles plus per-workspace viewer, contributor, developer, and owner membership.
- Admin-only model, security, provider, approval, and WarSat actions.
- Per-action approval queue for sensitive mutations.
- Trusted-workspace and host-shell capabilities that must be enabled separately.
- Audit records for trusted and untrusted actions.
- Privacy Lock and remote-model restrictions.
- Prompt-injection labeling for retrieved content and tool results.
- Declarative `SKILL.md` packages governed by the normal model/tool policy in every runtime; the
  obsolete containerized Python runner has been removed.
- Native/Desktop Host Shell is fail-closed pending a proven Windows AppContainer runner; it does
  not create a dedicated Windows account or run as the operator account.
- Optional local HTTPS and private remote-access paths.

### 6. What is demonstrably working

The current checkout passed the following review:

| Check | Result |
|---|---|
| Frontend production build | **Passed** — Vite transformed 3,153 modules and produced the production bundle. |
| Backend and security suites | **Passed** — 158 tests, 1 environment-dependent skip. |
| Prompt-recipe and theme suites | **Passed** — 8 tests. |
| Local model inference | **Previously live-verified and represented in current tests/code** — plain chat and a tool-using local Qwen task have run through WarSat. |
| Desktop lifecycle suite | **Not clean in this review** — four displayed cases passed, one abandoned-process-tree case failed, and the combined Node process did not exit before the 120-second limit. |
| Full browser suite | **Not rerun for this report.** Existing Playwright coverage exercises routing, settings, MCP, responsive layouts, chat folders, trials, archives, and dry-run WarSat flows. |

The build completed with non-fatal warnings: a large vendor chunk and browser externalization warnings from Pyodide's Node imports.

### 7. Rasputin's important gaps

Rasputin's shortcomings are not hidden by the size of its API:

- The most important coding-agent proof is still missing: a real local coder model completing a multi-file edit, running tests, diagnosing a failure, fixing it, and presenting the final diff in one end-to-end session.
- The backend supports workspace test/build/lint commands, but the intended settings form is still unfinished.
- The task diff/terminal/revert interface exists, but its full browser interaction and keyboard/mouse accessibility matrix is not yet automated.
- The model deploy UI does not yet expose every tool-parser hint supported by the backend.
- Several secondary views are functional but visibly thinner than the main chat, workspace, model, and WarSat areas.
- The UI still mixes the newer Tailwind/shadcn design system with legacy React Bootstrap.
- There is no Odysseus-style document editor, email client, CalDAV calendar, contacts manager, personal notes suite, deep-research product, or image gallery/editor.
- Installer generation exists, but signing, update channels, and upgrade testing remain distribution work.

---

## What Odysseus currently does

Odysseus describes itself as a self-hosted AI workspace for “chat, agents, research, documents, email, notes, calendar, and local model workflows.” The reviewed code supports that description.

### Its strongest product areas

#### Everyday assistant workspace

- Multi-turn chat and autonomous tool-using agents.
- Personal notes, todos, reminders, scheduled agent work, and digests.
- CalDAV calendars and CardDAV contacts.
- IMAP/SMTP email with multiple accounts, triage, search, tags, summaries, reply generation, scheduled sending, unsubscribe flows, attachments, and OAuth paths.
- A writing-first document editor with versions, AI edits, imports, PDF rendering, export, form workflows, and a personal library.
- A gallery with generation, editing, inpainting, and background removal.

#### Research and model evaluation

- Dedicated multi-step Deep Research with source reading and cited report generation.
- Blind side-by-side model comparison, voting, history, and synthesis.
- Web search backed by SearXNG and other provider options.
- Vector memory through ChromaDB.

#### Model and tool ecosystem

- Local and API providers.
- MCP management and browser automation.
- A hardware-aware Cookbook for model recommendation, download, dependency setup, local or remote serving, and server adoption.
- llama.cpp, Ollama, vLLM, SGLang, remote SSH servers, NVIDIA, AMD/ROCm, and Apple Silicon paths.
- Docker Compose bundles for Odysseus, ChromaDB, SearXNG, and ntfy.
- API tokens, webhooks, CLI/companion integrations, and Codex/Claude-oriented routes.

#### Accounts and security features

- Authentication, multiple users, detailed per-user privileges, and administrator boundaries.
- TOTP two-factor authentication with backup codes.
- Owner scoping across many personal records.
- Prompt-injection wrappers for external content.
- CSP and other browser security headers.
- Private-network-first deployment guidance and loopback bindings by default.

### Odysseus's important gaps

Odysseus's own roadmap and threat model are unusually candid:

- Fresh-install smoke coverage across Linux, macOS, Windows, Docker, native Python, and WSL is still high-priority work.
- Integrations need a systematic “does this actually work?” audit.
- Cookbook reliability varies across GPUs, drivers, shells, runtimes, and host platforms.
- Agent context is too heavy for some small local models.
- Degraded-state reporting needs improvement across ChromaDB, SearXNG, email, ntfy, and provider probes.
- Email performance and provider setup remain active audit areas.
- Accessibility, empty states, onboarding, mobile/editor polish, CSS cleanup, dead-code removal, and modal positioning remain open.
- Its `dev` branch is explicitly the newest and potentially unstable branch; `main` is the curated choice.
- Most significantly, its threat model says there is **no shell/filesystem sandbox**. Agent shell and file tools run with the application process user's authority, without filesystem confinement or network-egress filtering.
- The reviewed threat model also records an SSRF gap in a chat API `base_url` path.

That last point is the sharpest architectural difference between these projects.

---

## Capability matrix

Legend: **● strong**, **◐ present but incomplete/uneven**, **○ absent or not first-class**

| Capability | Rasputin | Odysseus | Practical reading |
|---|:---:|:---:|---|
| Local/API model chat | ● | ● | Both cover the core use case. |
| Autonomous tool-using agents | ● | ● | Rasputin emphasizes governed phases; Odysseus emphasizes breadth of tools. |
| Capability-aware model routing | ● | ◐ | Rasputin explicitly blocks or falls back before unsupported agentic modes. |
| Model download and serving | ● | ● | WarSat is plan/approval oriented; Cookbook is recommendation/dependency/serve oriented. |
| Hardware-aware recommendations | ◐ | ● | Odysseus has the richer Cookbook experience. |
| Workspace/repository boundaries | ● | ◐ | Rasputin makes approved workspaces and ACL roles foundational. |
| File and shell approvals | ● | ◐ | Odysseus uses admin/privilege gating; Rasputin adds per-action approvals and workspace trust. |
| Shell/filesystem sandboxing | ◐ | ○ | Odysseus explicitly acknowledges no sandbox. Rasputin has isolated skill and native Windows execution paths, but not every runtime uses the same boundary. |
| Git-aware coding workflow | ● | ◐ | Rasputin has diff/revert/test-loop concepts in the primary task UI. |
| Automated edit/test/fix loop | ● | ◐ | Rasputin has a bounded backend loop, though the definitive local-coder run is still pending. |
| Coding benchmarks/trials | ● | ◐ | Both compare models; Rasputin has a more explicit coding-trial system. |
| Blind general model comparison | ● | ● | Odysseus's Compare is more visible as a mainstream product feature. |
| Persistent memory | ● | ● | Different emphasis: workspace evidence vs personal-assistant context. |
| RAG/vector search | ● | ● | Rasputin includes workspace controls; Odysseus uses ChromaDB broadly. |
| Knowledge graph/code graph | ● | ○ | A meaningful Rasputin differentiator. |
| Dedicated deep research | ◐ | ● | Rasputin can run research-mode tasks; Odysseus has the fuller research product. |
| Document editor/library | ○ | ● | Major Odysseus advantage. |
| Email client/assistant | ○ | ● | Major Odysseus advantage. |
| Notes and personal todos | ◐ | ● | Rasputin has tasks/memory; Odysseus has dedicated personal productivity surfaces. |
| Calendar and contacts | ○ | ● | Major Odysseus advantage. |
| Image generation/gallery/editor | ○ | ● | Major Odysseus advantage. |
| Schedules/reminders | ◐ | ● | Rasputin schedules agent prompts; Odysseus integrates scheduling across more applications. |
| MCP support | ● | ● | Both support connected tools and server management. |
| Multi-user support | ● | ● | Rasputin adds workspace ACLs; Odysseus adds more granular personal privileges and 2FA. |
| Two-factor authentication | ○ | ● | Odysseus advantage. |
| Audit log and approval queue | ● | ◐ | Core Rasputin product surface. |
| Desktop distribution | ◐ | ◐ | Rasputin has Electron/NSIS; Odysseus has Windows portable and macOS wrapper paths. Neither is a frictionless signed consumer release. |
| Public ecosystem | ◐ | ● | Both projects use AGPL-3.0-or-later. Odysseus is already public; Rasputin is completing its public-release and contribution infrastructure. |

---

## Architecture and engineering comparison

### Rasputin

- FastAPI backend split into focused packages.
- React 18 + Vite frontend with routed feature components.
- SQLite-backed local state.
- Electron wrapper and packaged Python backend for Windows.
- Approximately 204 FastAPI route decorators in the reviewed backend.
- A comparatively compact repository whose feature boundaries remain understandable.
- Strong central concepts: workspace, model route, task, approval, audit event, artifact, trial, and deployment plan.

The main engineering risk is **incomplete product closure**: many foundational systems are thoughtfully designed, but several still need the last UI, browser-test, and end-to-end real-model pass.

### Odysseus

- FastAPI application with a very large collection of route, service, and source modules.
- Mostly static HTML/CSS/JavaScript frontend rather than a modern component framework.
- SQLite plus JSON stores and ChromaDB-backed vector memory.
- Approximately 488 FastAPI route decorators in the reviewed application.
- Roughly 746 Python test files and more than 4,100 discovered Python test functions.
- Extensive CI, security scanning, Docker publishing, contributor guidance, and release-branch conventions.

The main engineering risk is **surface-area and cohesion**. The project is impressively broad, but its own roadmap calls out CSS sprawl, duplicated scaffolding, fragile windows/modals, dead code, integration uncertainty, and partial module consolidation. A very large regression suite reduces risk; it does not erase the maintenance cost.

### A useful way to frame the difference

```text
Odysseus:  many complete rooms in one large house
Rasputin:  a smaller command center with stronger locks and operating procedures
```

---

## Security comparison

### Where Rasputin is stronger

Rasputin applies defense in depth to agent execution:

1. A user needs the correct appliance and workspace role.
2. The relevant global capability must be enabled.
3. Host shell requires a separate workspace grant.
4. Untrusted workspaces still require mutation approval.
5. Actions are audited.
6. Skills are declarative in every runtime and do not execute Python or require Docker.
7. Native/Desktop Host Shell is unavailable until AppContainer isolation is proven; no dedicated
   Windows account is created and no operator-account fallback is allowed.

This is closer to a controlled agent appliance than a conventional self-hosted web app. The
Desktop migration is intentionally conservative: it removes the former account-backed native shell
path and keeps Host Shell unavailable until a stronger AppContainer boundary is verified.

### Where Odysseus is stronger

Odysseus has features Rasputin should consider:

- TOTP 2FA and backup codes.
- More granular per-user privilege controls.
- Mature CSP/security-header work.
- A substantial security regression suite and public review surface.
- Better documented API-token and integration boundaries.

### The decisive difference

Odysseus's own threat model says its shell and filesystem tools execute as the application user with no sandbox or egress filtering. For a trusted single-user machine this may be an accepted tradeoff. For a product whose defining promise is allowing autonomous local models to act safely, Rasputin's design is materially stronger.

Rasputin should not become complacent: prompt labeling is not a security boundary, native process execution still requires explicit boundaries, the local administrator remains omnipotent, and not every execution mode has identical isolation. Still, the intended layers are better aligned with high-consequence agent operation.

---

## Product-positioning implications

Rasputin should **not** try to beat Odysseus by copying every feature.

That would turn a focused operations workbench into a sprawling mail/calendar/docs suite and inherit the exact integration and maintenance burden Odysseus's roadmap describes. Odysseus already occupies that territory credibly.

Rasputin's strongest defensible position is:

> **The safest, clearest way to deploy local models and let them do real work inside approved repositories and knowledge workspaces.**

The product story should center on:

- “Know which model can do the job before the run starts.”
- “See exactly what the agent is allowed to touch.”
- “Review risky actions before execution.”
- “Watch the plan, tools, tests, and evidence live.”
- “Run locally without sending private code or documents to a hosted model.”
- “Compare and certify models on your own hardware.”
- “Inspect and reproduce how a model runtime was deployed.”

Odysseus can be the self-hosted AI life hub. Rasputin can be the self-hosted AI operations and engineering console.

---

## What Rasputin should borrow from Odysseus

### Priority 1 — Finish the current promise

Before adding major new categories:

1. Run and record the definitive local-coder task: multi-file edit, test failure, fix, pass, diff review.
2. Finish the workspace command settings UI.
3. Complete browser and accessibility coverage for diff, terminal, and revert.
4. Make tool-parser selection and model-certification status obvious during deployment.
5. Fix the failing/hanging desktop lifecycle test and keep installer/update work honest.

These close Rasputin's existing value proposition rather than expanding it.

### Priority 2 — Borrow the best model-onboarding ideas

Odysseus's Cookbook is its most relevant competitive lesson:

- Scan hardware and make ranked recommendations.
- Explain expected RAM/VRAM fit and runtime compatibility in plain language.
- Show dependency and launch failures with copyable logs and next actions.
- Support local and remote model servers through one understandable workflow.

Rasputin already has much of the backend machinery. The opportunity is to finish the native model workflow as a guided path to a working GGUF model.

### Priority 3 — Add one polished knowledge deliverable

Do not build an email client or calendar. Instead, add a focused **Research Report / Workspace Document** artifact:

- Built from a governed research task.
- Carries citations and graph/RAG evidence.
- Editable and exportable as Markdown, HTML, DOCX, or PDF.
- Stored as a task artifact inside the workspace.

This would connect Rasputin's research, memory, graph, archive, and artifact systems without opening five unrelated product fronts.

### Priority 4 — Borrow account-security wins

- Add optional TOTP 2FA.
- Add session/device management and revocation.
- Improve backup/restore and encrypted secret portability.
- Continue expanding adversarial prompt-injection and confinement tests.

### Priority 5 — Improve public-facing clarity, even if the repo stays private

Odysseus is easier to understand in sixty seconds. Rasputin's README is operationally thorough, but the product hierarchy is harder to absorb.

A stronger Rasputin landing story should show:

1. Select or deploy a certified local model.
2. Approve a workspace.
3. Choose Chat, Analyze, Code, or Research.
4. Review the model route and permissions.
5. Watch the task work.
6. Inspect evidence, tests, artifacts, and changes.

---

## Recommendation

### If choosing one application today

Choose **Odysseus** if the goal is a broad self-hosted assistant for personal productivity: email, calendars, notes, documents, images, research, chat, and model experimentation.

Choose **Rasputin** if the goal is to let local models operate on repositories or sensitive knowledge with explicit scopes, approvals, model certification, evidence, tests, and auditability. Its public-release preparation is active, so prospective adopters should review the current license and release status before redistribution.

### If deciding what Rasputin should become

Do not chase Odysseus feature-for-feature. Finish the controlled local coding/research agent loop, finish the guided native GGUF discovery-to-inference experience, and make every successful task produce a reviewable result.

That gives Rasputin a smaller market surface but a much sharper reason to exist.

---

## Evidence and confidence

### Rasputin

This report inspected the current source tree, routes, frontend views, security model, packaging configuration, tests, and project checklists. It also ran the frontend production build and the principal backend, security, recipe, theme, and desktop lifecycle tests described above.

Key local sources:

- [`README.md`](../README.md)
- [`THREAT_MODEL.md`](../THREAT_MODEL.md)
- [`backend/engine/agent.py`](../backend/engine/agent.py)
- [`backend/mcp/layer.py`](../backend/mcp/layer.py)
- [`backend/warsat/__init__.py`](../backend/warsat/__init__.py)
- [`backend/models/providers.py`](../backend/models/providers.py)
- [`frontend-src/src/app/App.jsx`](../frontend-src/src/app/App.jsx)
- [`docs/CODING_AGENT_IMPLEMENTATION_CHECKLIST.md`](CODING_AGENT_IMPLEMENTATION_CHECKLIST.md)
- [`docs/DEPLOYMENT_MATRIX.md`](DEPLOYMENT_MATRIX.md)

### Odysseus

This report inspected the linked repository's `dev` branch locally at commit `d8a2059`, including its routes, services, frontend, tests, setup guide, roadmap, threat model, CI, and packaging files. Odysseus was **not installed or launched**, and its full test suite was **not executed** for this report. Claims about runtime behavior therefore have strong code/documentation support but are not independent live certification.

Primary upstream sources:

- [Odysseus repository and README](https://github.com/odysseus-dev/odysseus)
- [Setup guide](https://github.com/odysseus-dev/odysseus/blob/dev/docs/setup.md)
- [Roadmap](https://github.com/odysseus-dev/odysseus/blob/dev/ROADMAP.md)
- [Threat model](https://github.com/odysseus-dev/odysseus/blob/dev/THREAT_MODEL.md)
- [Contributing and test guidance](https://github.com/odysseus-dev/odysseus/blob/dev/CONTRIBUTING.md)

Feature counts are orientation aids, not quality scores. A route or test existing does not prove that every real-world provider, GPU, mail server, calendar server, browser, or operating system behaves correctly.
