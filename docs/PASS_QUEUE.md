# Rasputin Pass Queue

This queue is the execution source for `docs/AUTONOMOUS_PASS_RUNBOOK.md`.

Rules:

- Work from top to bottom.
- Execute one pass per Codex run.
- Keep scope tight.
- Preserve accessibility.
- Commit after validation.
- Do not push without explicit operator approval.

Status values:

- `[ ] queued`
- `[~] running`
- `[!] blocked`
- `[x] complete`
- `[-] deferred`

## Current Queue

### [ ] 01. Agent Lanes V1

Branch: `codex/agent-lanes-v1`

Commit message: `Add agent lanes workflow`

Goal: add separate AI workflow lanes/tabs without cluttering Home. This implements the separate-AI workflow direction the operator likes while keeping Home chat-first.

Scope:

- add lane state and UI primitives for Chat, Research, Code, Write, Organize, and Review
- each lane should show mode, routed model, workspace, status, and recent task
- lanes should be accessible tabs or segmented controls
- no new model autonomy beyond existing task APIs
- no new file mutation

Affected subsystems:

- `frontend-src/src/features/chat/`
- `frontend-src/src/features/tasks/`
- `frontend-src/src/app/App.jsx`
- `frontend-src/src/styles/rasputin.css`
- `tests/ui/rasputinSmoke.spec.mjs`

Required tests:

- `npm.cmd run build`
- `docker compose -f docker-compose.test.yml up --build -d`
- `npx.cmd playwright test tests/ui/rasputinSmoke.spec.mjs --project=chromium --reporter=list`
- `git diff --check`
- `powershell.exe -ExecutionPolicy Bypass -File .\scripts\check-repo-safety.ps1`

Acceptance criteria:

- Home remains clean and chat-first
- lane controls are keyboard reachable
- active lane is visually and semantically selected
- mobile does not overflow
- no duplicated task submission
- existing task flow still works

Stop conditions:

- new backend task orchestration is required
- UI direction requires operator choice
- two repeated Playwright failures expose a broader shell regression

### [ ] 02. MCP Relay V2 Stdio

Branch: `codex/mcp-relay-v2-stdio`

Commit message: `Add local stdio MCP relay runtime`

Goal: support approved local stdio MCP servers through Rasputin Tool Relay without giving models direct tool transport access.

Scope:

- register stdio MCP server command, args, env, cwd
- approval-gate command registration
- start, stop, restart server process
- initialize MCP protocol
- discover tools/resources/prompts
- normalize discovered tool schemas into Tool Relay
- show status/logs in UI

Affected subsystems:

- `backend/mcp_relay.py`
- `backend/tool_relay.py`
- `backend/main.py`
- `frontend-src/src/features/settings/`
- `frontend-src/src/features/runtime/`
- backend and UI tests

Required tests:

- backend smoke
- MCP bad command test
- MCP disabled server test
- MCP schema discovery test with fixture server
- full UI smoke if UI changes
- repo safety

Acceptance criteria:

- disabled server exposes no executable tools
- bad command returns structured error
- discovered tools default to guarded or approval-required
- tool execution routes through Tool Relay policy
- no remote/network MCP transports are enabled

Stop conditions:

- requires remote MCP
- requires package install without approval
- requires Docker socket access
- discovered tool could bypass permissions

### [ ] 03. Warsat Hardware Probe

Branch: `codex/warsat-hardware-probe`

Commit message: `Add Warsat hardware probe`

Goal: add read-only diagnostics for Docker, GPU visibility, VRAM estimate, model mount visibility, and runtime support.

Scope:

- no host mutation
- no Docker deployment
- no model download
- probe Docker availability
- report GPU visibility if available
- report model mount paths visible inside container
- show plain-English remediation guidance

Affected subsystems:

- `backend/warsat.py`
- `warsat/protocols/`
- `frontend-src/src/features/runtime/RuntimeViews.jsx`
- `tests/testBackendSmoke.py`
- UI smoke if layout changes

Required tests:

- backend smoke
- hardware probe shape test
- Docker unavailable mocked test
- UI smoke if frontend changes
- repo safety

Acceptance criteria:

- probe is read-only
- unavailable Docker/GPU returns clean structured status
- Warsat UI shows hardware readiness without requiring deployment
- no Docker socket mount is added

Stop conditions:

- implementation needs privileged host access
- implementation needs system package install
- implementation attempts to modify Docker config

### [ ] 04. Warsat Fit Scoring

Branch: `codex/warsat-fit-scoring`

Commit message: `Add Warsat model fit scoring`

Goal: rank catalog models by practical local fit using model metadata, runtime, quantization, context window, and hardware probe output.

Scope:

- score models from existing catalog data
- show fit bands such as strong, possible, risky, not recommended
- explain why a model fits or does not fit
- allow sending a selected model to launch plan
- no deployment changes

Affected subsystems:

- `backend/model_catalog.py`
- `backend/warsat.py`
- `frontend-src/src/features/models/`
- `frontend-src/src/features/runtime/RuntimeViews.jsx`
- tests

Required tests:

- backend fit scoring unit/smoke tests
- UI smoke for model catalog and Warsat send-to-plan
- frontend build
- repo safety

Acceptance criteria:

- fit score is deterministic
- missing hardware data degrades gracefully
- explanations are plain English
- no fake certainty about VRAM

Stop conditions:

- needs live external model download
- needs GPU-specific host commands that fail outside Docker

### [ ] 05. RAG UX V2

Branch: `codex/rag-ux-v2`

Commit message: `Improve RAG indexing and search UX`

Goal: make indexing understandable and useful across Workspaces, Knowledge, Archive, and task details.

Scope:

- show index location under ignored `data/`
- show what indexing does in plain language
- update indexed state immediately after ingest
- clarify RAG vs Graphify roles
- improve search result grouping and citations
- no vector database replacement in this pass

Affected subsystems:

- `frontend-src/src/features/workspaces/`
- `frontend-src/src/features/settings/`
- `frontend-src/src/features/runtime/RuntimeViews.jsx`
- `backend/rag.py`
- `backend/graphify.py`
- tests

Required tests:

- backend RAG smoke
- UI smoke for workspaces and archive
- frontend build
- repo safety

Acceptance criteria:

- clicking Index this folder visibly updates indexed state
- user can see where local index data is stored
- search results distinguish files, chunks, graph nodes, and graph edges
- no local content leaves the machine

Stop conditions:

- requires replacing RAG storage backend
- requires adding external embedding service

### [ ] 06. Workspace Tool Read V1

Branch: `codex/workspace-tool-read-v1`

Commit message: `Add workspace read tools`

Goal: make Rasputin reliably read approved workspaces through Tool Relay/MCP-style tools.

Scope:

- file tree tool
- file search tool
- file preview/read tool
- structured evidence output
- task trace shows what was read
- no writes, moves, deletes, or shell

Affected subsystems:

- `backend/tool_relay.py`
- `backend/mcp_layer.py`
- `backend/workspace.py`
- `backend/agent.py`
- task details UI
- tests

Required tests:

- path traversal rejection
- approved workspace read succeeds
- unapproved path read fails
- task trace records tool use
- full backend smoke
- UI task detail smoke if UI changes

Acceptance criteria:

- approved files can be read by agent tasks
- unapproved paths cannot be read
- reads are logged as tool calls
- summaries do not expose full private files in UI summaries

Stop conditions:

- write/move/delete becomes necessary
- shell execution becomes necessary

### [ ] 07. Safe Workspace Mutation Preview V1

Branch: `codex/workspace-mutation-preview-v1`

Commit message: `Add workspace mutation previews`

Goal: add preview-only planning for file writes, renames, moves, mkdir, and folder organization.

Scope:

- generate mutation plans
- show affected paths
- show before/after paths
- show rollback notes where possible
- no execution unless existing approval path is extended in a later pass

Affected subsystems:

- backend workspace tooling
- Tool Relay
- Approvals UI
- Workspaces UI
- tests

Required tests:

- dry run produces no filesystem changes
- path traversal rejected
- UI displays plan accessibly
- repo safety

Acceptance criteria:

- user can inspect planned mutations before anything changes
- write/reorganize remains disabled by default
- audit event records preview request

Stop conditions:

- implementation requires actual mutation execution
- rollback cannot be described for a planned operation

### [ ] 08. Graphify Evidence UI V2

Branch: `codex/graphify-evidence-ui-v2`

Commit message: `Improve Graphify evidence UI`

Goal: make Graphify explain why files, concepts, and documents are connected.

Scope:

- typed node and edge display
- evidence snippets with citations
- relationship panel in Knowledge and task details
- context budget friendly summaries

Affected subsystems:

- `backend/graphify.py`
- Knowledge UI
- task details UI
- Archive sources UI if useful
- tests

Required tests:

- graph build/search smoke
- evidence citation test
- UI smoke
- repo safety

Acceptance criteria:

- graph search returns readable relationships
- every relationship shows source evidence
- UI distinguishes node vs edge vs citation

Stop conditions:

- requires graph database migration
- requires sending local content externally

### [ ] 09. Trials Routing V1

Branch: `codex/trials-routing-v1`

Commit message: `Connect Trials results to model routing`

Goal: use blind model comparisons to save preferred models by task mode.

Scope:

- compare models for a prompt
- reveal after scoring
- save preferred model for Chat, Code, Research, Write, Analyze, Organize
- update preferences
- no automatic routing changes without user action

Affected subsystems:

- `backend/trials.py`
- preferences
- Models UI
- Trials UI
- tests

Required tests:

- trials backend smoke
- preference save/load
- UI smoke
- repo safety

Acceptance criteria:

- selected winner can be saved for a mode
- user sees before/after routing
- dry-run remains hidden from normal path unless testing mode is enabled

Stop conditions:

- requires judging with remote model by default
- requires automatic preference mutation without user action

### [ ] 10. Release Setup V1

Branch: `codex/release-setup-v1`

Commit message: `Add first-run setup checklist`

Goal: make a fresh clone predictable for another user without exposing local data.

Scope:

- first-run checklist
- admin password guidance
- model connection test
- workspace add/browse guidance
- privacy lock explanation
- docs update

Affected subsystems:

- UI settings/general
- auth docs
- README
- architecture guide
- tests

Required tests:

- UI smoke
- docs/repo safety
- frontend build

Acceptance criteria:

- a new user can start Docker and understand next steps
- no private local data is referenced
- setup guidance is local-first and safe

Stop conditions:

- requires publishing installer
- requires public repo secrets or tokens

## Deferred

### [-] Remote MCP Transports

Reason: local stdio MCP must be stable first.

### [-] Model Downloads From UI

Reason: large downloads and licensing need explicit approval and storage policy.

### [-] Email And Calendar Integrations

Reason: external credentials and side effects are higher risk than local tool/runtime work.

### [-] PDF/DOCX Mutation

Reason: read, cite, summarize, and export should stabilize before editing binary office documents.
