# Rasputin Application Readiness Gap Report

**Assessment date:** 2026-08-10
**Basis:** the current repository, implementation inspection, focused backend/UI tests, release-candidate certification, deployment verification, and the project’s current operational documents. The compact source/test map is `docs/RASPUTIN_IMPLEMENTATION_LEDGER.md`.

## Executive conclusion

Rasputin is no longer a prototype in the narrow sense: it has a working local-first web/desktop application, authentication and local multi-user boundaries, governed workspace tools, model deployment, streaming task visibility, and meaningful review surfaces. The gap is not “build the application from scratch.” The gap is turning a set of strong subsystems into a **dependable daily-driver product** whose core promises are repeatedly proven, easy to install, recoverable, and understandable without developer intervention.

The nearest definition of *fully working* should be:

> An owner can install or upgrade Rasputin, choose a verified local model, connect a workspace, give it a real task, safely review and accept its work, recover from mistakes, and keep the installation healthy—without needing source-code knowledge or an ad-hoc terminal session.

Today, the central architecture exists. The largest remaining risks are end-to-end reliability, productization, workflow completion, and evidence—not the absence of raw capabilities.

## What is already real

These are foundations to preserve, not rewrite:

- Local-first FastAPI/React application with Docker, Native Server, and Electron Desktop shapes.
- Local accounts, session auth, owner-scoped records, workspace roles, approvals, audit trails, and trusted-workspace controls.
- Agent modes with bounded execution, token/tool-event streaming, patch-based edits, shell execution, Git status/diff/commit tools, and a test/fix loop.
- Workspace browsing, RAG/knowledge-graph tools, artifact/archive/inbox surfaces, memory review/job APIs, and bounded conversation summaries.
- WarSat planning/deployment for local model runtimes, including GPU probing, model health, and multi-GPU planning tests.
- Persisted model capability probes, conservative mode preflight/fallback, per-deploy parser contracts, Assistant readiness/command-preview contracts, and device-free local voice adapters.
- Bounded application backup/integrity verification, owner metadata export/deletion confirmation,
  live operational diagnostics, a sarcastic-but-respectful Assistant profile contract, and a
  browser push-to-talk/local playback console layered over the device-free voice adapters.
- Task-change review endpoints and UI surfaces; workspace test/build/lint settings are visibly implemented and covered by the smoke UI test.

This means proposed work should complete user journeys and tighten guarantees. It should not replace these systems with a parallel app.

## Readiness scorecard

| Product outcome | Current status | What prevents “complete” |
| --- | --- | --- |
| Ask, receive, and manage ordinary AI work | Functional | Secondary views and user-facing lifecycle polish remain uneven. |
| Safely perform coding work in a trusted workspace | Substantially implemented | A real coder-model, multi-file edit → test → repair → review → commit run is not yet the release-grade proof. |
| Deploy and route local models | Functional but operator-heavy | Persisted capability certification and conservative preflight now exist; live mission evidence, certificate freshness, and deploy ergonomics still need to make safe choices obvious. |
| Run a dependable personal desktop app | Partial | Clean-machine install/upgrade evidence, signing, update channel, and production release identity are missing. |
| Operate a shared/local appliance | Functional for a knowledgeable owner | Diagnostics and bounded backup/export/delete flows exist; isolated clean-instance restore is rehearsed, while active-data upgrade and support-grade recovery remain open. |
| Evaluate models and make routing decisions | Partial | Trials scorecards contain placeholder reasoning, safety, and usability scores; they must not be presented as measured truth. |
| Connect outside services into governed workflows | Partial | Connector setup exists, but the product needs complete, visible, reliable workflows rather than configuration screens alone. |

## The gaps, in priority order

### P0 — prove the core daily-driver loop

**Why it matters:** This is the product promise most likely to determine whether Rasputin replaces a separate coding agent for real work.

#### 1. Release-grade coding-task validation

The agent loop, tool streaming, patch editing, Git tools, diff/revert endpoints, and workspace validation commands are present. What is still missing is a repeatable proof that a correctly configured local coder model can complete a realistic task end to end:

1. select a healthy coder-capable local model;
2. work in a trusted workspace with an explicit test command;
3. inspect and edit multiple files;
4. run tests, interpret a failure, and repair the change;
5. show progress while work is running;
6. present a useful diff; and
7. commit locally only when the operator chooses.

The proof should be an isolated, recorded acceptance scenario, not a mocked test or a single successful chat. It should include a deliberately failing fixture, expected changed files, pass/fail assertions, tool-call trace, and a documented manual approval path for untrusted workspaces.

**Done when:** this scenario passes against at least one live, locally hosted coder model on the intended hardware and is repeatable in CI where practical (with the live-model portion separately labeled as hardware acceptance).

#### 2. Model readiness and capability contracts — foundation implemented, release proof open

WarSat has substantial planning and runtime coverage, and Rasputin now has a first-class persisted certification profile per model/runtime combination. `backend/models/compatibility.py` probes bounded chat, context retention, ordinary response, and tool calling; `backend/models/registry.py` stores the result; and task creation falls back before execution when the requested mode is not certified or tools are unavailable.

The remaining release-proof requirements are:

- ordinary chat returns non-empty answers;
- streaming works;
- the context window is detected or explicitly bounded;
- tool calling works, or tool-dependent modes are blocked before launch;
- code mode identifies a model as suitable only after a real capability test;
- the UI explains a bad configuration and offers a safe fallback.

This is especially important because local OpenAI-compatible runtimes vary by tool parser, chat template, context behavior, and hidden-reasoning behavior.

**Foundation done when:** model cards/routing use persisted capability results rather than only static catalog hints, and unsupported modes cannot silently start an execution task. **Release proof remains open until:** at least one live coder-capable local model completes the file-editing acceptance mission, certification inputs are refreshed when runtime identity changes, and the UI explains the evidence and freshness boundary.

### P1 — make the core trustworthy and operable

#### 3. Product-grade recovery: backup, restore, export, and repair

Rasputin stores the owner’s chats, tasks, approvals, memory, credentials/configuration metadata, workspaces, and model runtime state across local files, SQLite, and (in Docker) volumes. The first recovery slice now exists, but a fully working local-first application still needs a complete recovery story:

- one supported backup command/UI flow with scope and secret-handling disclosure (implemented);
- restore into a clean instance, with version/migration checks and a non-destructive dry-run (isolated restore and migration rehearsal implemented; active-data upgrade rehearsal remains open);
- export/delete controls for user-owned data (owner-safe metadata export and explicit deletion confirmation implemented);
- disaster-recovery instructions for Docker volumes and native data;
- a tested upgrade/rollback strategy.

**Done when:** a fresh machine or data directory can restore a representative backup and pass health, login, workspace, and model-configuration checks. `scripts/rehearse_restore.py --rehearse` now proves the isolated archive, clean target, SQLite initialization, and restored admin state; a stopped active-instance rehearsal is still required.

#### 4. Installation, updates, and identity

Electron packaging works, but the desktop release boundary is incomplete: the current architecture document explicitly lists production icon, Authenticode signing, update signing/channel metadata, and clean-machine install/upgrade/uninstall verification as remaining gates.

Required work:

- signed, versioned installer artifacts and release notes;
- an update channel with user-visible version/status/failure handling;
- clean-machine install, upgrade, uninstall, and data-preservation tests;
- a supported compatibility matrix for Windows, Docker Desktop/WSL, NVIDIA drivers, and native fallback;
- a clear support path when Docker/WSL is unavailable.

**Done when:** a non-developer can install, update, and recover the supported desktop/server shapes without cloning the repository or manually assembling Python/Node/Docker dependencies.

#### 5. Operational health and diagnostics

Health endpoints exist, and the first consolidated diagnostics view/command is now implemented. The remaining work is to make it complete across clean-machine and authenticated browser verification. It reports:

- app version, storage location, migration status, and backup freshness;
- server/desktop ownership and port conflicts;
- Docker/WSL availability and container health where relevant;
- GPU/runtime/model health, installed capability certification, and logs safe to share;
- workspace access, Host Shell status, and an explanation of the next blocked permission.

**Done when:** the top recurring failures—stopped model, unavailable tool capability, Docker unavailable, stale runtime owner, and denied workspace action—can be diagnosed from the application with a clear remediation path.

### P1 — turn existing features into complete workflows

#### 6. Finish task review and workspace ergonomics

The current implementation includes task detail review endpoints and workspace validation-command controls. The gap is finishing their user-facing quality bar:

- comprehensive UI/a11y coverage for task changes (added/modified/deleted/renamed files, large diffs, error/retry states, keyboard navigation, and safe per-file revert);
- a clear completion state that distinguishes “model replied” from “edits/tests/commit actually succeeded”;
- an operator-visible test/build/lint result summary and links back to relevant output;
- safe ways to select or switch the workspace/model without routing a task to an unhealthy model.

**Done when:** a keyboard-only and mouse-only user can start, observe, inspect, approve/reject, and recover a coding task in a live isolated instance.

#### 7. Make connectors useful, not merely configurable

Connector records, settings, and read-only GitHub repository context exist. A mature application needs each advertised connector to answer four questions in the UI: what data is read, where it is stored, what the agent can do with it, and how the owner revokes it.

Prioritize a small number of complete, governed workflows rather than adding broad integrations:

- GitHub: connect → select repository → retrieve context → cite source/revision → disconnect;
- notifications: one reliable completion/approval notification path with delivery test and failure state;
- document/intake workflows: ingest → permission/retention choice → task use → expiration/deletion;
- any write-capable integration: explicit preview, approval, audit record, and revocation.

**Done when:** the owner can complete at least two integrations end-to-end without manually interpreting raw configuration fields or logs.

#### 8. Make memory a dependable user-controlled feature

The code has owner-scoped memory records/jobs and review APIs, but the user experience must establish predictable boundaries:

- show what was extracted, why, sources, scope, and retention;
- provide approve/reject/edit/delete and a way to correct a bad memory;
- deduplicate and resolve conflicts deterministically;
- make cross-workspace behavior explicit and opt-in;
- show whether a memory was injected into the current task and let the user suppress it.

**Done when:** a user can inspect, correct, and delete a memory without SQL, and no memory crosses user/workspace boundaries without a deliberate policy.

### P2 — correct trust, safety, and product-scope gaps

#### 9. Replace misleading evaluation scores with measured evaluation

`backend/trials/scorecards.py` assigns fixed placeholder values for reasoning, safety, and usability. Those scores are useful scaffolding but are not valid evidence for model selection.

Required work:

- label unavailable dimensions as “not measured,” not a number;
- define benchmark datasets and ground-truth/graded evaluation per score;
- keep safety evaluation separate from simple runtime success;
- record model, runtime, parameters, prompt version, dataset revision, and hardware for reproducibility;
- make routing recommendations explain their evidence and uncertainty.

**Done when:** every displayed score has a visible measurement method and a repeatable source dataset, or is explicitly unavailable.

#### 10. Define and complete the tool boundary

`docker_control` remains intentionally disabled/implemented as a policy stub while WarSat follows its own approved deployment path. This is safe, but product behavior should be clearer. Decide whether Docker control is:

- permanently out of scope for agents (then remove it from user expectations and explain the WarSat-only path), or
- a future governed capability (then define explicit operation allowlists, previews, approval classes, rollback, logging, and tests).

Do not expose generic Docker authority simply to make the feature list look broader.

#### 11. Address known security and runtime caveats honestly

The native Host Shell is meaningful containment but not a VM-grade isolation boundary; Docker shell execution also has different persistence/network properties. Product work must keep these distinctions understandable in the UI and docs. Remaining hardening should focus on:

- security posture labels per runtime/mode;
- remediation for missing sandbox account/toolchain/network controls;
- secrets lifecycle and safe diagnostic redaction;
- regular dependency/vulnerability and release artifact scanning;
- threat-model review whenever new connector, network, or execution authority is added.

**Done when:** owners can choose a runtime with an accurate explanation of its authority and risk, and releases have a repeatable security gate.

### P3 — quality, coherence, and growth work

#### 12. Complete the design-system migration and thin views

The frontend is split between the current Tailwind/shadcn token system and legacy `react-bootstrap` screens. This produces inconsistent controls, accents, save feedback, focus behavior, and theme behavior. Finish the incremental migration, beginning with screens used daily, and test light/dark/high-contrast/reduced-motion states.

Then deepen currently thin secondary surfaces (Agents, Activity, Memory, Approvals, Archive) only around concrete owner workflows. Every view should answer: what happened, what needs attention, what action is safe, and what the action changes.

#### 13. Collaboration and administration beyond a local appliance

Local multi-user roles are implemented, but a broader team product would still need deliberate policy for invitations/onboarding, workspace transfer/ownership recovery, audit retention/export, concurrent work visibility, notifications, and supportable remote access. This is not a P0 daily-driver blocker; it becomes essential before positioning Rasputin for organizational use.

#### 14. Documentation and release discipline

Roadmap claims have drifted as implementation moved forward (for example, workspace validation settings and parser configuration are now in the UI/API). The implementation ledger now provides the lightweight release-readiness checkpoint. Keep it updated only after verification and record:

- feature status: implemented, automated-tested, live-verified, or planned;
- supported environments and known exclusions;
- owner-facing runbooks and recovery steps;
- release acceptance evidence.

This keeps the onboarding document, checklist, roadmap, and product claims aligned with source of truth.

## Recommended execution sequence

| Phase | Outcome | Dependencies | Exit evidence |
| --- | --- | --- | --- |
| 1. Core proof | Live local coder-model task edits, tests, repairs, and presents reviewable changes | certified model, isolated fixture workspace | recorded acceptance run + targeted automated tests |
| 2. Reliability UX | Model/readiness warnings, task terminal outcomes, review a11y, diagnostics | Phase 1 failure modes | live browser pass in light/dark and keyboard/mouse paths |
| 3. Operability | Backup/restore, data export/delete, diagnostics, upgrade/recovery procedure | stable data schema + versioning | clean-store restore and upgrade rehearsal |
| 4. Productization | signed installer, update channel, clean-machine matrix | Phase 3 recovery plan | independent install/upgrade/uninstall acceptance |
| 5. Workflow depth | two complete governed connectors; controlled memory workflow | permissions/audit conventions | end-to-end user journeys with revocation |
| 6. Expansion | measured Trials, collaboration, optional Docker-control decision, broader integrations | trusted base and support model | published measurement/policy contracts |

## Explicit non-priorities until the above is complete

- Expanding the number of modes, integrations, or agent tools before their current equivalents are reliable end to end.
- Building generic agent Docker control without a narrow, audited operation model.
- Treating static catalog metadata or synthetic scorecards as proof that a model is suitable for production work.
- Marketing broad team/public distribution before installation, updates, backup/recovery, support boundaries, and licensing decisions are settled.

## Evidence consulted

- `docs/CODEX_ONBOARDING.md` — project contract and current coding-agent status.
- `docs/CODING_AGENT_IMPLEMENTATION_CHECKLIST.md` — implementation/verification history and remaining coding workflow proof.
- `docs/RASPUTIN_IMPLEMENTATION_LEDGER.md` — current source/test evidence and explicit status boundaries.
- `docs/REMAINING_WORK.md`, `docs/DEPLOYMENT_MATRIX.md`, and `docs/DESKTOP_ARCHITECTURE.md` — deployment, security, and packaging status.
- `backend/mcp/tools.py` — the intentional `docker_control` policy stub.
- `backend/trials/scorecards.py` — current unmeasured scorecard dimensions.
- `frontend-src/src/features/workspaces/WorkspacesView.jsx` and `tests/ui/rasputinSmoke.spec.mjs` — validation-command UI and current coverage.
- `tests/testBackendSmoke.py` — coverage for WarSat, streaming, memory, and Git-review capabilities.

## Bottom line

Rasputin’s next milestone should not be “more features.” It should be a **verified, recoverable, installable local-agent workflow**: a certified local model performs a real coding task safely, the owner can understand and review every result, the system survives ordinary failures and upgrades, and the release can be installed by someone who is not the developer. Once that is true, the existing WarSat, memory, connector, trials, and multi-user foundations become credible platforms for expansion rather than promising subsystems that still require operator expertise to trust.
