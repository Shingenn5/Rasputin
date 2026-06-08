# Rasputin Staged Implementation Backlog

This backlog turns the feature harvest matrix into implementation-ready branches. The order is dependency-first, then user value, then safety risk.

Backlog rules:

- Build in vertical slices: backend, UI, safety, tests, docs.
- Keep every risky capability approval-gated and audited.
- Do not copy source code, UI copy, assets, names, or branding from reference projects.
- Do not start deferred integrations until local tool, model, knowledge, and document workflows are stable.

## Stage 1: Foundation

### Branch: `codex/tool-relay-v1`

Goal: replace ad hoc MCP-style calls with a typed tool broker that agents can use safely.

Scope:

- Add a tool registry with tool id, display name, schema, risk level, permission flag, timeout, and redaction policy.
- Route existing safe tools through the registry: RAG search, Graphify search, workspace browse, file preview, memory search, model health.
- Persist every tool call and result summary to existing runtime storage.
- Surface tool calls in task details with redacted args and status.

Affected subsystems: backend, MCP, security, audit, tasks UI.

API/interface changes:

- Add `GET /api/tools`.
- Add task detail fields for normalized tool calls if current shape is insufficient.
- Keep existing task and MCP-related endpoints backward-compatible.

UI changes:

- Add a Tools section in task details.
- Add clear labels for safe, guarded, and approval-required tools.

Security requirements:

- File, shell, Docker, web, and write-like tools are not executable in this branch unless explicitly registered as approval-required stubs.
- Tool args and results must be redacted before audit or UI display.

Tests required:

- Tool registry returns expected tools.
- Safe tool calls persist traces.
- Approval-required tool stubs do not execute.
- Task detail displays redacted calls.

Definition of done:

- Agent planning can inspect the registry.
- Safe tools run through one broker path.
- No tool can bypass permissions or audit.

### Branch: `codex/mcp-relay-v1`

Goal: turn Tool Relay into a real local MCP-compatible layer for approved tool servers.

Scope:

- Add MCP server registry, enable/disable state, health check, and tool discovery.
- Support local-only MCP transports first.
- Map discovered tools into Tool Relay risk and permission policy.
- Keep external/network MCP servers disabled unless explicitly allowed later.

Affected subsystems: MCP, backend, settings UI, audit.

API/interface changes:

- Add `GET /api/mcp/servers`.
- Add `POST /api/mcp/servers`.
- Add `POST /api/mcp/servers/{id}/enable`.
- Add `POST /api/mcp/servers/{id}/disable`.
- Add `POST /api/mcp/servers/{id}/discover`.

UI changes:

- Add Settings > Tool Relays.
- Show server status, discovered tools, risk labels, and enable controls.

Security requirements:

- MCP servers default disabled.
- All discovered tools default guarded or approval-required until classified.
- No direct model access to MCP transport.

Tests required:

- Disabled server exposes no executable tools.
- Discovery result is normalized and redacted.
- Unsafe transport is rejected.

Definition of done:

- Rasputin can safely register local MCP-style tools without giving models direct filesystem or network access.

### Branch: `codex/context-governor-v1`

Goal: reduce model context bloat and make smaller local models more usable.

Scope:

- Add context budget calculation by selected model context window.
- Add compact prompt packs by mode: chat, analyze, code, write, organize, research.
- Limit default tool schemas shown to the model.
- Summarize long session/tool context before it reaches the model.

Affected subsystems: agent, models, memory, RAG.

API/interface changes:

- No new public API required.
- Add trace fields showing selected context budget and omitted context counts.

UI changes:

- Task details show context budget and what was included or omitted.

Security requirements:

- Never include raw secrets or disallowed file contents in context summaries.

Tests required:

- Small context model receives shortened prompt.
- Tool schemas are limited by task mode.
- Task detail shows context inclusion summary.

Definition of done:

- A 4k or 8k context model can handle a simple chat/task without context-window errors from Rasputin-generated prompt bloat.

## Stage 2: Warsat

### Branch: `codex/warsat-deploy-lifecycle`

Goal: make Warsat deployment testable end to end from model search to running endpoint.

Scope:

- Keep current plan-first flow.
- Add deployment status phases: planned, approval pending, pulling, starting, probing, registered, failed.
- Show live logs and next steps.
- Register endpoint only after health probe succeeds or clearly mark it unhealthy.
- Add retry and clear failed deployment state.

Affected subsystems: Warsat, Docker, model registry, approvals, UI.

API/interface changes:

- Extend `/api/warsat/deploy` response with lifecycle status.
- Add or extend logs/status response with phase, last error, and model key.

UI changes:

- Warsat launch plan shows approval, deploy, health, and model registration as separate steps.
- Deploy approval button is visible and readable.

Security requirements:

- Docker execution requires docker-control compose overlay, safety flag, and one-time approval.
- Containers must bind to `127.0.0.1`.
- Model folders mount read-only.

Tests required:

- Plan creation works without Docker control.
- Deploy request creates approval when Docker control is disabled or approval missing.
- Approved deploy path is covered with mocked Docker.
- Failed health probe does not mark model healthy.

Definition of done:

- User can test Warsat deployment flow without guessing which step is stuck.

### Branch: `codex/warsat-hardware-probe`

Goal: add read-only hardware and Docker visibility checks.

Scope:

- Detect OS, Docker CLI availability, Docker socket access, container GPU visibility, visible VRAM when available, and mounted model paths.
- Never install drivers, edit host config, or alter `.env`.
- Provide copyable manual next steps.

Affected subsystems: Warsat, Docker, UI, docs.

API/interface changes:

- Add `GET /api/warsat/hardware`.

UI changes:

- Warsat adds Hardware panel with readiness checks and blocked reasons.

Security requirements:

- Read-only commands only.
- Hardware probe unavailable unless admin is authenticated.

Tests required:

- Probe handles missing Docker.
- Probe handles no GPU.
- Probe redacts host-sensitive data.

Definition of done:

- User can tell whether their machine is ready for Warsat without leaving Rasputin.

### Branch: `codex/warsat-fit-scoring`

Goal: rank model catalog candidates by practical local fit.

Scope:

- Score catalog models by parameter estimate, quantization/runtime support, context, VRAM estimate, and current hardware profile.
- Show small, balanced, large, and experimental recommendations.
- Keep model metadata cache local.

Affected subsystems: Warsat, model catalog, UI.

API/interface changes:

- Extend model catalog items with `fitScore`, `fitLabel`, `fitReasons`, and `blockedReasons`.

UI changes:

- Warsat model finder sorts by fit and supports filters for use, VRAM, runtime, and quantization.

Security requirements:

- Remote model catalog refresh remains user-triggered.
- Cache contains metadata only, not user data.

Tests required:

- Fit score changes with mocked VRAM.
- Unsupported runtime is clearly blocked.
- Offline fallback catalog still works.

Definition of done:

- User can pick a deployable model without manually interpreting VRAM and runtime compatibility.

## Stage 3: Knowledge

### Branch: `codex/rag-v2-document-intel`

Goal: replace the lightweight hash retrieval with a production local knowledge index.

Scope:

- Add local vector store behind existing RAG endpoints.
- Add embedding model role and local-only enforcement.
- Add incremental indexing by modified time and content hash.
- Parse text/code/markdown/json/csv first.
- Add document parser layer for PDF, DOCX, and XLSX as optional modules after license review.

Affected subsystems: RAG, workspace, models, UI, Docker.

API/interface changes:

- Preserve `/api/rag/stats`, `/api/rag/ingest`, and `/api/rag/search`.
- Extend responses with index backend, chunk count, citation metadata, and parser status.

UI changes:

- Workspaces page shows index status per approved folder.
- Knowledge view explains where indexes live and what files were indexed.

Security requirements:

- Indexes stay under ignored local `data/`.
- RAG search requires file-read permission.
- No indexed content leaves the machine.

Tests required:

- Incremental reindex skips unchanged files.
- Search returns file path and line/page metadata.
- Unsupported/binary/large files are skipped with reason.

Definition of done:

- User can index a workspace and get cited local retrieval results that are inspectable in task details.

### Branch: `codex/graphify-evidence-v2`

Goal: make Graphify useful as an evidence-backed local relationship layer.

Scope:

- Tie graph nodes and edges to source snippets or file metadata.
- Add relationship explanation response.
- Ingest document sections and code structure where available.

Affected subsystems: Graphify, RAG, workspace, UI.

API/interface changes:

- Extend `/api/graph/search` with evidence snippets and confidence fields.

UI changes:

- Knowledge and task details show relationship evidence.

Security requirements:

- Graph evidence obeys file-read permission and workspace scope.

Tests required:

- Graph build creates typed nodes and edges.
- Search returns evidence and source.
- Path traversal is rejected.

Definition of done:

- User can understand why Rasputin connected two files, concepts, or entities.

## Stage 4: Workflows

### Branch: `codex/archive-editor-v1`

Goal: add a local document workbench without risky file mutation.

Scope:

- Build markdown editor with preview.
- Add output folder selection and save/export.
- Add AI suggestion mode that produces proposed edits, not direct writes.
- Add accept/reject flow for suggestions.

Affected subsystems: UI, output, agent, workspace.

API/interface changes:

- Add document session endpoints only if existing output APIs are insufficient.
- File writes require existing approval/file-write policy.

UI changes:

- New Archive view or Settings-linked workspace initially.
- Editor, preview, suggestions panel, export controls.

Security requirements:

- No overwrite without preview and approval.
- Generated content is local.

Tests required:

- Markdown edit and preview work.
- Suggestions can be accepted/rejected.
- Export respects output settings and file-write permission.

Definition of done:

- User can draft and revise markdown documents with Rasputin assistance.

### Branch: `codex/recon-research-v1`

Goal: add approval-gated web research that never leaks local file contents.

Scope:

- Create research task mode backed by Tool Relay.
- Add query preview and approval.
- Add source collection, summary, citations, and markdown report output.

Affected subsystems: MCP, security, agent, output, UI.

API/interface changes:

- Use Tool Relay web tool.
- Extend task artifacts for research reports if needed.

UI changes:

- Research mode shows pending queries, collected sources, report artifacts, and privacy warnings.

Security requirements:

- Every outbound query is redacted, approval-gated, and audited.
- Local file snippets are never sent as queries.

Tests required:

- Suspicious query is blocked.
- Approval creates one outbound query.
- Report includes citations and source URLs.

Definition of done:

- User can run a small research task with visible approvals and cited output.

### Branch: `codex/trials-model-compare`

Goal: compare local and approved API models without bias.

Scope:

- Send one prompt to multiple selected models.
- Hide model labels until user votes.
- Record latency, error, and selected winner.
- Allow user to set winner as role default.

Affected subsystems: models, UI, preferences.

API/interface changes:

- Add `POST /api/trials/run`.
- Add optional saved trial result storage.

UI changes:

- New Trials panel under Models or Activity.

Security requirements:

- Remote API models only run when remote models are enabled.
- Trial prompts follow the same privacy rules as normal model calls.

Tests required:

- Local dry-run trial works.
- Failed model shows clear error.
- Winner can update selected role preference.

Definition of done:

- User can compare models before assigning them to Rasputin roles.

## Stage 5: Companion Layer

### Branch: `codex/directives-v1`

Goal: make local notes, todos, reminders, and schedules useful without broad external integrations.

Scope:

- Add Directives view for notes, todos, reminders, and scheduled Rasputin tasks.
- Allow assigning a directive to an agent only by explicit user action.
- Link directives to sessions, workspaces, and memory when approved.

Affected subsystems: schedules, memory, UI, agent.

API/interface changes:

- Extend schedule APIs only if needed.
- Add local notes/todos endpoints if existing runtime storage is insufficient.

UI changes:

- Directives area under Activity or sidebar secondary panel.

Security requirements:

- Scheduled risky tool calls create approvals.
- External notifications remain opt-in and redacted.

Tests required:

- Note/todo/reminder CRUD.
- Reminder creates visible pending item.
- Agent assignment creates task with trace.

Definition of done:

- User can track simple work items and choose when Rasputin acts on them.

### Branch: `codex/telegram-approval-polish`

Goal: harden the optional Telegram approval flow.

Scope:

- Improve setup validation, test messages, status display, and failure recovery.
- Keep redacted approval summaries only.

Affected subsystems: Telegram, approvals, settings UI.

API/interface changes:

- Preserve existing Telegram endpoints.
- Extend status response if needed.

UI changes:

- Clear enabled/disabled/error states and privacy warning.

Security requirements:

- Wrong chat id is rejected.
- No prompts, file contents, diffs, secrets, or raw model output in Telegram messages.

Tests required:

- Mock Bot API approve/deny.
- Wrong chat id rejected.
- Offline Telegram leaves UI approval usable.

Definition of done:

- Telegram approval is reliable enough for private testing but still optional.

## Stage 6: Release Polish

### Branch: `codex/setup-trial-v1`

Goal: make a fresh install predictable for another user.

Scope:

- Add first-run setup checklist.
- Add model connection test, workspace approval, safety summary, and sample dry-run task.
- Add docs for Docker, native, Windows, macOS/Linux, and common failure modes.

Affected subsystems: auth, UI, docs, scripts.

API/interface changes:

- Extend bootstrap config with setup-complete flags if needed.

UI changes:

- First-run checklist in Settings or onboarding overlay.

Security requirements:

- Never expose secrets or local paths beyond what the user selected.

Tests required:

- Fresh testdata boot shows checklist.
- Setup completion persists.
- Password change and model test are reachable.

Definition of done:

- A new user can start Rasputin, log in, add a workspace, connect a model, and run a test task without reading source code.

### Branch: `codex/accessibility-release-pass`

Goal: make the current app shippable across desktop, split-screen, tablet, and mobile.

Scope:

- Fix keyboard navigation, focus rings, aria-live status, contrast, overflow, and reduced motion.
- Keep screenshots updated for Home, Workspaces, Activity, Models, Warsat, Settings, and mobile.

Affected subsystems: UI, tests.

API/interface changes:

- None.

UI changes:

- Focus and responsive fixes only.

Security requirements:

- None beyond preserving existing behavior.

Tests required:

- Playwright keyboard smoke.
- Responsive no-overflow smoke.
- Theme contrast spot checks.

Definition of done:

- Main workflows are usable without a mouse and do not break at common monitor widths.

## Explicitly Deferred

Do not start these until Stages 1 through 4 are stable:

- Mail Relay: external email brings credential, privacy, latency, and send-side-effect risk.
- Timeline Sync: CalDAV adds external sync and account complexity.
- Visual Relay: image editing and vision uploads are broad and not needed for the local file/workflow core.
- Field Console PWA: mobile/PWA polish is useful, but the app needs stable workflows first.
- Local Admin 2FA: valuable later, but setup and core auth must be stable first.

## First Three Executable Branches

1. `codex/tool-relay-v1`
2. `codex/warsat-deploy-lifecycle`
3. `codex/rag-v2-document-intel`

These should be implemented in order. Warsat and RAG can start after Tool Relay establishes the common permission, tracing, and approval behavior.

