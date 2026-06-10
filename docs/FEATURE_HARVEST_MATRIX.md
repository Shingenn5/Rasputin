# Rasputin Feature Harvest Matrix

This matrix compares Rasputin against behavior patterns from the Odysseus `dev` README and roadmap, then converts useful patterns into Rasputin-native product language.

Reference sources:

- Odysseus README: https://github.com/pewdiepie-archdaemon/odysseus/blob/dev/README.md
- Odysseus roadmap: https://github.com/pewdiepie-archdaemon/odysseus/blob/dev/ROADMAP.md
- Rasputin current source: README, architecture guide, Warsat plan, backend routes, frontend feature modules.

Rules for this harvest:

- Borrow mechanics and workflow ideas only.
- Do not copy source code, UI copy, assets, names, icons, or branding.
- Keep Rasputin local-first, approval-gated, and workspace-scoped.
- Treat user-editable content, memory, documents, fetched pages, and tool output as untrusted.

## Rating Key

Status:

- `existing`: current implementation is usable for testing.
- `partial`: visible scaffolding or limited implementation exists, but the feature is not production-complete.
- `missing`: no meaningful implementation exists yet.

Effort:

- `S`: contained polish or integration work.
- `M`: one focused branch with backend, UI, and tests.
- `L`: multi-week subsystem work.
- `XL`: major product area.

Risk:

- `low`: local-only and mostly read-only.
- `medium`: reads private data, persists state, or has complex reliability needs.
- `high`: writes files, runs tools, touches Docker/shell/network, or exposes external integration risk.

## Chat And Sessions

| Reference source | Reference behavior | Rasputin name | Status | Value | Effort | Risk | Subsystems | Dependencies | Acceptance criteria | Attribution/licensing note |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| Odysseus README | Chat with local models and API providers | Home Chat | existing | 5 | M | medium | UI, backend, models | model registry, preferences | Actual model id is shown, sessions persist, message history loads, unhealthy models block sends with clear reason | Behavior reference only |
| Odysseus README | Simple provider setup for local/API models | Model Command Center | partial | 5 | M | high | UI, backend, models, security | provider adapters, secret store | Local endpoints and approved API providers can be registered, tested, selected, and stored without leaking keys | Behavior reference only |
| Odysseus README | Sessions and presets | Chat Directories And Presets | partial | 4 | M | low | UI, backend, preferences | sessions, chat folders | Chats can be foldered, searched, sorted, renamed, archived, and restored; presets can seed mode/model/workspace | Behavior reference only |
| Odysseus roadmap | Fresh install empty states and setup hints | First Run Guidance | partial | 4 | M | low | UI, docs, auth | setup flow | Fresh install tells user how to set password, connect model, add workspace, and send first test message | Behavior reference only |

## Agent Runtime And MCP

| Reference source | Reference behavior | Rasputin name | Status | Value | Effort | Risk | Subsystems | Dependencies | Acceptance criteria | Attribution/licensing note |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| Odysseus README | Agent can use MCP, web, files, shell, skills, memory | Warmind Runtime | partial | 5 | L | high | backend, MCP, memory, UI, audit | task runtime, approvals | Agent plans, selects allowed tools, executes calls, records trace, injects tool results, and pauses for approvals | Reimplement Rasputin-native |
| Odysseus README | MCP server/tool ecosystem | Tool Relay | partial | 5 | L | high | backend, MCP, security, audit | tool broker | Tools have schemas, risk levels, permission flags, timeouts, redacted args, durable calls, and UI traces | Reimplement Rasputin-native |
| Odysseus roadmap | Agent prompt/context bloat control | Context Governor | partial | 5 | M | medium | backend, models, memory, RAG | tool relay | Agent uses compact prompt packs, small default tool sets, context budgets, and role-specific model routing | Behavior reference only |
| Odysseus roadmap | Prompt injection audit for skills, notes, docs, pages, memory | Untrusted Context Guard | partial | 5 | L | high | backend, security, MCP, RAG, memory | tool relay, document intel | Retrieved context is labeled as untrusted; models are instructed not to obey embedded instructions; risky tool calls require approval | Behavior reference only |
| Odysseus README | Skills evolve over time | Protocol Skills | partial | 4 | M | medium | backend, memory, UI | skill registry | Skill packages can be created from sessions, previewed, enabled, disabled, imported, and audited | Behavior reference only |
| Odysseus README | Agent-aware scheduling | Directive Runner | partial | 4 | L | high | backend, schedules, approvals, UI | tool relay | Scheduled work can create pending tasks, but any risky tool call still requires approval | Behavior reference only |

## Model Runtime And Warsat

| Reference source | Reference behavior | Rasputin name | Status | Value | Effort | Risk | Subsystems | Dependencies | Acceptance criteria | Attribution/licensing note |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| Odysseus README | Hardware scan, model recommendation, click to download and serve | Warsat Runtime Deployment | partial | 5 | L | high | Warsat, Docker, UI, backend | safety, approvals | User can search models, score fit, generate plan, approve deploy, view pull/start logs, test endpoint, and select model | Behavior reference only |
| Odysseus README | VRAM-aware GGUF/FP8/AWQ serving | Warsat Fit Scoring | missing | 5 | L | high | Warsat, Docker, models | hardware inventory | Models are ranked by available hardware, runtime support, quantization, context needs, and reliability hints | Research third-party model data licenses before caching |
| Odysseus roadmap | Cookbook error feedback and logging | Warsat Mission Logs | partial | 5 | M | medium | Warsat, UI, audit | deployment lifecycle | Failed download/deploy/preflight shows actual safe command summary, logs, failure reason, and next step | Behavior reference only |
| Odysseus roadmap | GPU passthrough diagnostics without automatic host edits | Warsat Hardware Probe | missing | 5 | M | medium | Warsat, Docker, docs | none | Read-only probe reports Docker, GPU visibility, VRAM if visible, model mount state, and exact manual fix guidance | Behavior reference only |
| Odysseus README | vLLM, llama.cpp, Ollama, API providers | Runtime Protocol Library | partial | 4 | M | high | Warsat, models, docs | protocol validation | Protocol files cover vLLM, llama.cpp, Ollama, TGI/SGLang candidate, embeddings, reranker with tests | Behavior reference only |

## Knowledge, RAG, And Graph

| Reference source | Reference behavior | Rasputin name | Status | Value | Effort | Risk | Subsystems | Dependencies | Acceptance criteria | Attribution/licensing note |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| Odysseus README | ChromaDB/fastembed vector + keyword retrieval | Knowledge Index V2 | partial | 5 | L | medium | RAG, backend, UI, Docker | workspace browser | Workspace indexing uses local embeddings/vector store, incremental reindexing, citations, and clear storage location | Do not vendor external code without license review |
| Odysseus README | Memory import/export | Warmind Memory Export | partial | 4 | M | medium | memory, UI, docs | SQLite memory | Memory has review queue, search, local markdown export, import/export, and clear privacy boundaries | Behavior reference only |
| Odysseus README | File uploads including PDF | Document Intel | partial | 5 | L | medium | RAG, Graphify, workspace, UI | Knowledge Index V2 | PDF/DOCX/XLSX/CSV/text files can be parsed locally, indexed, and cited; richer preview UX remains future work | Uses local parser packages only; no external parser service |
| Rasputin goal | Typed graph relationships with evidence | Graphify Evidence V2 | partial | 4 | M | medium | Graphify, RAG, UI | document intel | Graph search explains why items are related with source snippets, file paths, and relationship type | Rasputin-native |

## Documents

| Reference source | Reference behavior | Rasputin name | Status | Value | Effort | Risk | Subsystems | Dependencies | Acceptance criteria | Attribution/licensing note |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| Odysseus README | Multi-tab editor for markdown, HTML, CSV, syntax highlighting | Archive Editor | missing | 5 | XL | high | UI, backend, output, workspace | tool relay, file preview | User can edit markdown first, preview output, ask AI for suggestions, accept/reject edits, and export safely | Behavior reference only |
| Odysseus README | AI suggestions, user remains writer | Archive Suggestions | missing | 5 | L | high | UI, agent, output | Archive Editor | AI proposes diffs or comments; user approves before file writes | Behavior reference only |
| User goal | DOCX/PDF support for any workflow | Archive Document Formats | partial | 5 | XL | high | backend, RAG, output, UI | Document Intel, Archive Editor | DOCX/PDF/XLSX text can be extracted and cited; safe rewrite/edit workflows remain approval-gated future work | Uses local parser packages only; no external parser service |

## Research

| Reference source | Reference behavior | Rasputin name | Status | Value | Effort | Risk | Subsystems | Dependencies | Acceptance criteria | Attribution/licensing note |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| Odysseus README | Multi-step source gathering and synthesis | Recon Research | missing | 4 | L | high | MCP, web broker, UI, output | tool relay, approval queue | Research runs collect approved web sources, summarize, cite, and export report without sending local files | Behavior reference only |
| Odysseus roadmap | Model presets by hardware for research | Recon Profiles | missing | 3 | M | medium | Warsat, models, UI | Warsat fit scoring | Research mode recommends small/medium/large model profiles based on hardware and context window | Behavior reference only |
| Rasputin safety goal | Web broker only, models no direct internet | Recon Privacy Gate | partial | 5 | M | high | security, MCP, audit | tool relay | Every outbound query is redacted, approval-gated, audited, and never includes raw local file content | Rasputin-native |

## Compare And Evaluation

| Reference source | Reference behavior | Rasputin name | Status | Value | Effort | Risk | Subsystems | Dependencies | Acceptance criteria | Attribution/licensing note |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| Odysseus README | Blind side-by-side model comparison | Trials | missing | 4 | M | low | UI, models, backend | model registry | User can send one prompt to multiple models, vote blind, reveal models, and save preferred role defaults | Behavior reference only |
| Odysseus README | Multi-model synthesis | Trials Synthesis | missing | 3 | M | medium | models, agent, UI | Trials | A selected model or judge role can synthesize outputs, with source labels after reveal | Behavior reference only |
| Rasputin need | Evaluate deployed Warsat models | Trials Runtime Bench | missing | 4 | M | medium | Warsat, models, UI | Warsat deployment lifecycle | Deployed models can be smoke-tested for latency, context, streaming, and basic instruction following | Rasputin-native |

## Notes, Tasks, And Scheduling

| Reference source | Reference behavior | Rasputin name | Status | Value | Effort | Risk | Subsystems | Dependencies | Acceptance criteria | Attribution/licensing note |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| Odysseus README | Notes and todos with reminders | Directives | partial | 3 | L | medium | UI, backend, schedules, memory | task runtime | User can create notes/todos/reminders, assign to agent only by explicit action, and store locally | Behavior reference only |
| Odysseus roadmap | Better scheduler defaults and visibility | Directive Timeline | partial | 3 | M | medium | UI, backend, schedules | approvals | Scheduled tasks show next run, last run, status, and pending approvals | Behavior reference only |
| Odysseus README | Notification channels | Alert Relay | partial | 3 | M | high | Telegram, UI, schedules | approvals | Telegram remains redacted; future channels must disclose what leaves the machine | Behavior reference only |

## Integrations

| Reference source | Reference behavior | Rasputin name | Status | Value | Effort | Risk | Subsystems | Dependencies | Acceptance criteria | Attribution/licensing note |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| Odysseus README | Email triage over IMAP/SMTP | Mail Relay | missing | 2 | XL | high | integrations, UI, security | tool relay, secrets | Not started until core local workflows are stable; must keep credentials local and require explicit send approval | Defer |
| Odysseus README | CalDAV calendar sync | Timeline Sync | missing | 2 | XL | high | integrations, UI, schedules | Directives | Not started until schedules are useful locally; external sync must be opt-in | Defer |
| Odysseus README | Web search | Web Relay | partial | 5 | M | high | MCP, security, audit | tool relay | Search is approval-gated, redacted, logged, and disconnected from direct model access | Rasputin-native |
| Odysseus README | Image editor and vision uploads | Visual Relay | missing | 2 | XL | high | UI, models, workspace | Document Intel | Defer until document/file workflow is stable | Defer |

## Mobile, PWA, And Onboarding

| Reference source | Reference behavior | Rasputin name | Status | Value | Effort | Risk | Subsystems | Dependencies | Acceptance criteria | Attribution/licensing note |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| Odysseus README | Works on mobile, installable PWA | Field Console | partial | 3 | L | medium | UI, frontend, auth | shell stability | Main workflows work on mobile; PWA install is optional and local-first | Behavior reference only |
| Odysseus roadmap | Fresh install smoke tests across OS/runtime paths | Setup Trial | partial | 5 | M | low | scripts, Docker, docs, tests | test harness | Docker, native, Windows, macOS/Linux docs are tested enough for new users | Behavior reference only |
| Odysseus roadmap | Clear degraded-state reporting | Health Console | partial | 4 | M | medium | UI, backend, models, Docker | existing probes | Missing model, Docker, vector DB, search broker, and provider issues show actionable status | Behavior reference only |
| Odysseus roadmap | Accessibility pass | Accessibility Baseline | partial | 5 | M | low | UI, tests | existing UI | Keyboard, focus, contrast, reduced motion, error announcements, and mobile overflow pass smoke checks | Behavior reference only |

## Security And Admin

| Reference source | Reference behavior | Rasputin name | Status | Value | Effort | Risk | Subsystems | Dependencies | Acceptance criteria | Attribution/licensing note |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| Odysseus roadmap | Security hardening around admin tools | Safety Kernel V2 | partial | 5 | L | high | security, audit, approvals, UI | tool relay | Admin tools have explicit permissions, confirmation flows, audit events, and default-off behavior | Behavior reference only |
| Odysseus roadmap | Backup/restore guide for local data | Recovery Guide | missing | 4 | M | medium | docs, scripts, data | stable data layout | User can backup/restore ignored local `data/` safely without leaking secrets to Git | Behavior reference only |
| Odysseus README | 2FA | Local Admin 2FA | missing | 2 | L | medium | auth, UI | onboarding | Defer until core setup and auth flows are stable | Defer |
| Rasputin principle | No direct model internet/file access | Privacy Lock V2 | partial | 5 | M | high | security, models, MCP | tool relay | Remote endpoints, outbound web, Docker, shell, and file writes are blocked or approval-gated by policy | Rasputin-native |

## Ranked Findings

1. Tool Relay is the highest leverage gap. It unlocks real MCP behavior, safe file tools, web broker use, and traceable agent action.
2. Warsat is the best product differentiator after Tool Relay. It turns model deployment from manual Docker work into a guided, approval-gated flow.
3. Knowledge Index V2 is required before document, research, and file companion workflows feel reliable.
4. Archive Editor should start with markdown and suggestions before DOCX/PDF mutation.
5. Recon and Trials are valuable but should wait until tools, model routing, and RAG are stable.
6. Email, calendar, image editor, broad PWA polish, and 2FA should stay out of the next implementation wave.
