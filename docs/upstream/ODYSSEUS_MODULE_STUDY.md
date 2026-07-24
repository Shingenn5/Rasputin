# Odysseus Module Study

## Pinned research baseline

| Field | Value |
|---|---|
| Repository | `https://github.com/odysseus-dev/odysseus` |
| Branch | `dev` |
| Commit | `d8a2059df8e53bc7275c45339849d14c8651e73c` |
| Commit date | 2026-07-23 |
| License | AGPL-3.0-or-later |
| Study type | Architecture and product behavior; no source copied |

This study records what Rasputin should learn from Odysseus before an
implementation is proposed. Source adoption is **not** approved by this
document. Any copied or translated source still requires a separate, file-level
entry in the adoption register.

## Decision matrix

| Candidate | Odysseus source reviewed | Useful architecture | Rasputin decision | Security and maintenance reading |
|---|---|---|---|---|
| Cookbook / hardware fit | `routes/cookbook_routes.py`, `static/js/cookbook-hwfit.js`, `src/cookbook_serve_lifecycle.py` | Hardware scan, model-fit ranking, backend recipes, download/serve lifecycle, local and SSH targets | **Adapt the product lesson**, not the source | Highest immediate value, but Odysseus concentrates thousands of lines of orchestration in route/UI modules. Rasputin should keep WarSat plans, execution, health, and certification separate. |
| Blind Compare | `routes/compare/compare_routes.py`, `static/js/compare/*`, `tests/test_blind_compare_redaction.py` | Two owner-scoped ephemeral sessions, identity hiding, vote-before-reveal, comparison history | **Adapt and improve** | A compact, valuable workflow. Rasputin should generalize beyond pairwise votes to saved datasets, rubrics, repeated trials, blinded judges, and fitness certificates. |
| Deep Research | `src/deep_research.py`, `services/research/service.py`, `routes/research/*`, `static/js/research/*` | Background jobs, progress, source extraction, report persistence and cancellation | **Adapt and improve** | Preserve Rasputin's brokered network permission and evidence graph. Do not treat a bibliography parsed from generated prose as sufficient claim-level evidence. |
| Documents | `routes/document_routes.py`, `services/docs/service.py`, `src/document_actions.py`, `src/agent_tools/document_tools.py` | Library, versions, PDF import/render/export, AI preview and restore | **Defer broad editor; adopt artifact versioning concepts** | The full surface is large and format-sensitive. Rasputin should first version task artifacts with provenance and reviewable AI patches. |
| Scheduler | `src/task_scheduler.py`, task routes and scheduler tests | Time zones, recurrence, cancellation, chained work, delivery targets, foreground/background coordination | **Adapt reliability lessons** | Rasputin already schedules prompts. Add idempotent leases, missed-run policy, shadow mode, budgets, and receipts before adding delivery channels. |
| Connectors | `routes/auth_routes.py`, `routes/email_routes.py`, `routes/calendar_routes.py`, MCP servers | Per-user integration records and broad application workflows | **Adopt protocol boundary only** | Avoid importing provider-specific product suites. Continue account-scoped, masked secrets; add least-privilege capability manifests and approval-gated writes. |
| Authentication / TOTP | `core/auth.py`, `routes/auth_routes.py`, related auth tests | Pending TOTP enrollment, confirmation, login challenge, backup codes, session revocation | **Propose a Rasputin-native implementation** | High security value and bounded scope. Store TOTP secrets encrypted or protected by the platform secret facility; hash single-use backup codes; never log either. |
| Backup / restore | `routes/backup_routes.py`, `scripts/odysseus-backup`, `docs/backup-restore.md` | User export/import plus operational filesystem backup | **Adapt and improve** | Rasputin needs schema/version manifests, encrypted secret handling, archive path validation, dry-run restore, integrity checks, and post-restore verification. |
| Model serving | Cookbook routes, lifecycle service, Docker and platform launchers | Multiple backends, dependency recipes, remote hosts, process lifecycle | **Keep WarSat architecture; adopt coverage lessons** | Rasputin's plan/approval/health boundary is stronger. Extend backend and remote-host coverage without collapsing it into one large controller. |

## First three implementation candidates

### 1. WarSat Advisor and mission fitness

**Why first:** it strengthens Rasputin's current differentiator and reuses live
hardware, deployment-plan, model-catalog, and Trials boundaries.

The first slice should return a deterministic recommendation record containing:

- observed usable RAM and per-device VRAM;
- candidate model, quantization, runtime, context, and parser;
- estimated memory envelope and safety margin;
- proposed GPU strategy and its assumptions;
- explicit blockers and unproven capabilities;
- commands or plan inputs needed to reproduce the recommendation.

No Odysseus source import is justified. Its hardware-fit experience is the
product lesson; Rasputin's implementation should remain a smaller, testable
domain service whose output feeds WarSat rather than driving launches directly.

### 2. Blind Trials Compare

**Why second:** the core interaction is bounded and it turns subjective model
choice into reusable evidence.

Rasputin should create a saved trial definition, randomize model labels, capture
identical inputs and generation settings, prevent model identity leakage until
scoring, and promote a completed comparison into a signed fitness certificate.
Tool use must be either disabled for all candidates or supplied from the same
recorded fixture.

### 3. Research missions with claim evidence

**Why third:** Rasputin already has research tasks, RAG, artifacts, and an
evidence graph, so it can improve on report-only deep research.

Every retrieved source should be stored at retrieval time. Report claims should
link to supporting and contradicting evidence, while unsourced synthesis is
marked explicitly. The mission contract should carry network permission,
allowed domains, source and token budgets, cancellation state, and a
reproducible receipt.

## Explicit rejections

- Do not copy Odysseus's route structure or reproduce its navigation
  application-for-application.
- Do not import the large Cookbook route/UI modules into WarSat.
- Do not expose shell, filesystem, model-server, or connector writes without
  Rasputin permissions and approvals.
- Do not treat a generated report's citation list as evidence that every claim
  is supported.
- Do not add mail, calendar, contacts, notes, and documents simultaneously.
- Do not import source until dependency licenses, upstream notices, tests,
  ongoing maintenance, and a removal plan are recorded.

## Bounded acceptance contract for the next pass

The first WarSat Advisor slice is complete only when:

1. the recommendation is generated from explicit hardware and model inputs;
2. memory arithmetic and safety margins have unit tests;
3. unsupported parser/runtime combinations produce blockers, not warnings;
4. the response distinguishes observed facts, estimates, and unproven
   capabilities;
5. the existing WarSat deployment plan can consume the recommendation without
   bypassing approval;
6. no Odysseus source code or dependency is introduced.

