# Project Prometheus

## An open-source roadmap for learning from Odysseus and building a stronger Rasputin

> **Status:** Active on `codex/project-prometheus-phase-0`
> **Reframed:** July 24, 2026
> **Rasputin baseline:** `bdb06f7`
> **Odysseus reference:** [`odysseus-dev/odysseus`](https://github.com/odysseus-dev/odysseus), default branch `dev`
> **Objective:** Open-source Rasputin, responsibly reuse compatible upstream work where it reduces risk or duplication, and build a distinct governed AI operations platform whose strongest features can flow back to the public.

---

## 1. Strategic decision

Rasputin will become an open-source project.

That changes Project Prometheus from a proprietary clean-room program into an
upstream-aware engineering program:

- Public ideas and documented behavior may always inform Rasputin.
- Upstream code may be adopted only after a file-level license and dependency
  review.
- Odysseus-derived code must retain required notices, history, and attribution.
- Reuse must serve Rasputin's architecture; Rasputin will not become an
  Odysseus fork with a different interface.
- Improvements that are generally useful should be contributed upstream when
  practical.
- Rasputin's safety, evidence, model orchestration, and coding workflows remain
  first-class differentiators even though their implementation is public.

### Product position

> **Rasputin is the open-source, governed workspace where local models research,
> build, test, and deliver reviewable work on your hardware.**

Odysseus is a broad personal AI workspace. Rasputin should remain the more
focused AI operations and engineering console.

---

## 2. License decision

Odysseus currently declares **AGPL-3.0-or-later**.

Rasputin is now licensed under **AGPL-3.0-or-later**. This provides a compatible
licensing foundation for bounded Odysseus source adoption when notices,
attribution, modification records, and corresponding-source obligations are
preserved.

AGPL compatibility does not make unattributed copying acceptable. Every source
adoption still requires:

- A file-level provenance record.
- Preserved upstream copyright and license notices.
- A bounded architectural review.
- Rasputin-facing tests and documentation.
- Consideration of an upstream contribution.

This is an engineering control, not legal advice. A lawyer should review the
final licensing plan before a commercial launch or large upstream import.

---

## 3. Upstream adoption policy

Every proposed adoption is classified before implementation.

### Class A — Product lesson

Examples: blind model comparison, hardware-aware recommendations, a document
workflow, or a clearer navigation hierarchy.

- Record the user outcome and observed strengths.
- Design the Rasputin version around existing Rasputin services and policies.
- No upstream code attribution is required for an abstract idea, but the
  inspiration is still recorded for transparency.

### Class B — Protocol or interoperable boundary

Examples: OpenAI-compatible model endpoints, MCP, CalDAV, IMAP, SMTP, Markdown,
or an import/export schema.

- Prefer published standards and upstream protocol documentation.
- Test compatibility independently.
- Do not copy an upstream implementation when a smaller maintained library or
  Rasputin adapter is sufficient.

### Class C — Dependency adoption

Examples: a third-party editor, search client, calendar library, or parser also
used by Odysseus.

- Review the dependency's own license, maintenance, security history, bundle
  impact, and transitive dependencies.
- Attribute the dependency itself, not Odysseus, unless Odysseus authored it.

### Class D — Source adoption

Examples: copying, adapting, or translating an Odysseus module, test, prompt,
schema, stylesheet, or asset.

- Requires an approved project license.
- Record upstream repository, commit, file paths, original license, authors,
  changes, and retained notices.
- Import the smallest coherent unit.
- Add tests that express Rasputin behavior rather than preserving accidental
  upstream structure.
- Keep the upstream relationship reviewable in Git history.

### Class E — Upstream contribution

If Rasputin fixes a generally useful Odysseus defect or improves a shared
standard integration:

- Prefer a focused upstream pull request.
- Avoid coupling the contribution to Rasputin internals.
- Record the upstream issue or pull request in the adoption register.

---

## 4. Architecture rules

Odysseus features must enter through Rasputin's existing boundaries:

```text
Operator or schedule
        |
        v
Mission contract
        |
        +----> policy and approval preview
        |
        v
Capability router ----> model fitness evidence
        |
        v
Governed agent loop
   |         |          |
 tools    workspace   connectors
   |         |          |
   +---------+----------+
             |
             v
Run receipt + reviewable artifacts
```

Non-negotiable rules:

1. Workspace and owner scope stay explicit.
2. Risky mutations keep previews, approvals, and audit evidence.
3. Local-first remains the default; new network destinations are visible and
   governable.
4. A connector cannot bypass the same policy merely because it came from an
   upstream feature.
5. UI additions upgrade the current layout instead of building a parallel
   Odysseus-shaped application.
6. Model capability is proven through trials or certificates, not inferred
   solely from a model name.
7. Successful work produces a durable result outside transient chat text.

---

## 5. What Rasputin should adopt

### Highest-value upstream lessons

| Odysseus strength | Rasputin adoption | Rasputin improvement |
|---|---|---|
| Cookbook and model guidance | WarSat Advisor | Hardware fit, parser compatibility, certification, reproducible deployment |
| Blind Compare | Expand Trials into blind comparisons | Mission-specific scoring and hardware-normalized evidence |
| Deep Research | Research missions and evidence graph | Claim-level provenance, contradictions, trust labels, reproducible receipts |
| Documents | Artifact studio attached to tasks | Patch review, source lineage, versions, export, approval-aware AI edits |
| Scheduled agents | Governed automations | Simulation, recipient/path preview, budgets, retry policy, receipts |
| Email/calendar breadth | Connector framework | Least privilege, scoped secrets, shadow mode, explicit outbound approval |
| 2FA and privilege management | Security hardening | Workspace ACL integration, recovery workflow, session visibility |
| Backup and restore | Portable encrypted operations bundle | Configuration, model manifests, policies, certificates, migration validation |

### Features not worth copying first

- A full personal email client.
- A general photo gallery or image editor.
- A route-for-route clone of Odysseus.
- A second model registry beside WarSat.
- A second task or memory system.
- Broad integrations before connector governance exists.

---

## 6. Rasputin's public differentiators

Open-source differentiators are still defensible. The moat becomes execution
quality, safety, community trust, interoperability, and accumulated evidence.

### Mission Contracts

Before execution, show:

- Objective and acceptance criteria.
- Model, tools, context, and workspace.
- Expected file, shell, network, and connector actions.
- Time, token, retry, and optional monetary budgets.
- Approval boundaries and output artifacts.

### Run Receipts

After execution, preserve:

- Model/runtime/parser/quantization configuration.
- Input and evidence references.
- Tool calls, approvals, file changes, validation results, and fallbacks.
- Final artifacts and unresolved risks.

### Model Fitness Certificates

Certify models for:

- Chat and structured output.
- Tool selection and arguments.
- Coding patch quality and test/fix iteration.
- Long-context retrieval and citation faithfulness.
- Vision/document understanding.
- Latency and memory behavior on known hardware.

Certificates expire when important runtime or hardware inputs change.

### Evidence Graph

Link claims to sources, passages, timestamps, trust classification, supporting
and contradicting evidence, and the inference joining them.

### Adaptive Capability Routing

Choose a model and tool set using mission requirements, certificates, policy,
health, hardware, context, latency, and budget. Explain the choice and fall back
before the operator waits on an incapable model.

### Shadow Mode

Run connectors and automations without mutations first. Show requested
recipients, paths, records, network destinations, and expected results before
promotion to live policy.

---

## 7. Phased execution plan

Each phase ends with an owner review gate. Later phases do not begin
automatically.

## Phase 0 — Stabilize and prepare the public project

### Work

- Finish the current coding and model-deployment baseline.
- Choose and add Rasputin's root license.
- Add contribution, security, governance, and code-of-conduct documents.
- Add an upstream adoption policy and adoption register.
- Inventory secrets, personal paths, generated state, screenshots, fixtures,
  and large binaries before publishing history.
- Add dependency-license and secret scanning to CI.
- Document supported native, Docker, and desktop paths exactly as they work.
- Run the definitive local-coder mission.

### Exit criteria

- Build, backend, desktop, and focused browser verification pass.
- A real local coding model completes the test/fix mission.
- Repository history is cleared for public release.
- License and contribution policy are visible from the README.
- No known secret, private fixture, or personal runtime data is tracked.

### Owner gate

**“Is this repository safe, licensed, understandable, and useful enough to make
public?”**

## Phase 1 — Upstream research and adoption register

### Work

- Pin the Odysseus commits used for research.
- Build a feature/module map for Cookbook, Compare, Research, Documents,
  schedules, connectors, auth, backup, and model serving.
- Classify every candidate as Product Lesson, Protocol, Dependency, Source
  Adoption, or Upstream Contribution.
- Record maintenance burden, license implications, security surface, and
  expected Rasputin value.
- Select the first three candidates by evidence rather than feature count.

### Exit criteria

- Every candidate has an owner, provenance, license class, and decision.
- No source import lacks a compatibility decision.
- The first implementation phase has bounded acceptance tests.

### Owner gate

**“Are we adopting the right things for the right reasons?”**

## Phase 2 — WarSat Advisor and model fitness

### Work

- Convert hardware discovery into explicit usable memory envelopes.
- Recommend model, quantization, runtime, parser, context, and GPU strategy.
- Explain why a model fits and what capability remains unproven.
- Turn Trials into job-specific fitness certificates.
- Feed certificate and live-health results into capability routing.

### Better-than-Odysseus target

A recommendation is not merely “this model fits.” It is “this configuration
fits this hardware and is certified for this mission.”

### Exit criteria

- Recommendations are reproducible and explainable.
- Parser/runtime mismatches are blocked before launch.
- At least one chat, coding, and research certificate can be produced.

## Phase 3 — Blind Compare and evidence-based routing

### Work

- Add blind side-by-side responses.
- Support repeatable datasets, judges, rubrics, and synthesis.
- Normalize latency and memory measurements.
- Promote successful results into fitness certificates.
- Allow the router to explain certificate-backed selection.

### Exit criteria

- Model identity can remain hidden during scoring.
- Results are reproducible from a saved trial definition.
- Routing can cite the evidence behind a choice.

## Phase 4 — Research missions and evidence graph

### Work

- Add multi-step research plans.
- Capture sources at retrieval time.
- Extract claim-level supporting and contradicting evidence.
- Generate reports with inspectable citations.
- Add budget, trust, and network policy to the mission contract.

### Exit criteria

- Every material report claim links to stored evidence.
- Unsupported synthesis is visibly distinguished from sourced fact.
- A research run can be reproduced or audited from its receipt.

## Phase 5 — Artifact studio

### Work

- Promote task outputs into versioned documents.
- Add Markdown-first editing, suggestions, source lineage, comments, and export.
- Reuse Rasputin's existing diff and approval concepts for AI edits.
- Keep artifacts workspace-scoped and searchable.

### Exit criteria

- A research or coding task can produce a durable, editable artifact.
- AI changes are reviewable before acceptance.
- Version history and evidence survive chat cleanup.

## Phase 6 — Governed automations

### Work

- Convert schedules into mission templates.
- Add simulation, approval previews, retry budgets, timeouts, and receipts.
- Prevent overlapping jobs unless explicitly allowed.
- Make disabled capability and secret failures visible before execution.

### Exit criteria

- Every automation can run in shadow mode.
- Mutations and destinations are previewable.
- Each execution produces a receipt and actionable failure state.

## Phase 7 — Connector platform

### First-class GitHub version control

GitHub will be the first substantial developer connector and will build on
Rasputin's existing local Git status, diff, and approval services.

#### Delivery stages

1. **Repository awareness**
   - Detect the active workspace's remotes, branch, upstream, ahead/behind
     state, dirty files, and linked GitHub repository.
   - Show local commits and remote pull-request/check context together without
     requiring a mutation-capable credential.
2. **Read-only GitHub integration**
   - Browse issues, pull requests, review comments, changed files, releases,
     workflow status, and check results.
   - Link task receipts and workspace changes to their originating issue or
     pull request.
3. **Governed local version-control actions**
   - Preview branch creation, staging scope, commit message, merge/rebase
     implications, and push destination.
   - Keep destructive history operations disabled by default.
   - Require explicit approval for push, force operations, branch deletion,
     merge, and conflict resolution that changes files.
4. **Governed GitHub mutations**
   - Draft issues and pull requests before submission.
   - Post comments, labels, review responses, releases, and workflow dispatches
     only through visible, scoped approval.
   - Display the exact repository, branch, recipients, payload, and permission
     scope before execution.
5. **Agent-assisted maintenance**
   - Triage issues, summarize pull requests, address selected review comments,
     diagnose CI failures, prepare release notes, and maintain changelogs.
   - Every automated change remains bound to a mission contract and produces a
     run receipt.

#### Security boundaries

- Prefer GitHub App or fine-grained token authentication over broad classic
  personal access tokens.
- Store credentials in Rasputin's secret backend; never expose them to models,
  logs, prompts, task outputs, or exported bundles.
- Use repository and organization allowlists.
- Separate read, issue, pull-request, workflow, release, and administration
  capabilities.
- Treat fork pull requests and repository content as untrusted input.
- Never let GitHub permissions bypass workspace permissions or local approval
  requirements.
- Record remote URL, base/head branches, commit SHAs, actor, requested scopes,
  approvals, API result, and resulting repository state.

#### Exit criteria

- An operator can connect a GitHub repository with read-only permissions.
- Rasputin can correlate the active workspace, branch, pull request, checks, and
  review comments.
- Branch, commit, push, and draft-PR flows show an exact preview before any
  external mutation.
- A coding mission can address selected review feedback, run validation, and
  prepare a draft pull request without silently staging unrelated files.
- Revoking the credential immediately disables remote actions without breaking
  local Git inspection.

### General connector platform

### Work

- Define a connector SDK for auth, capability declarations, health, read
  operations, drafts, and mutations.
- Store secrets through a pluggable secret backend.
- Start with one read-heavy integration and one approval-gated outbound action.
- Add connector-specific scopes, rate limits, audit events, and revocation.

### Exit criteria

- Connectors cannot bypass mission policy.
- Secrets never enter prompts, logs, receipts, or exported mission packs.
- Outbound actions name their recipient and payload before approval.

## Phase 8 — Portability, backup, and restoration

### Work

- Export encrypted configuration and policy bundles.
- Include model manifests, certificates, connector metadata without secrets,
  workspace mappings, and schema versions.
- Add dry-run restore validation and migration reports.
- Test native-to-Docker and machine-to-machine restoration.

### Exit criteria

- Restore is previewable and version-aware.
- A fresh installation can validate compatibility before importing.
- Missing models, paths, secrets, and capabilities are reported clearly.

## Phase 9 — Public security and multi-user hardening

### Work

- Add TOTP or passkeys, recovery codes, and session management.
- Complete owner/workspace isolation tests.
- Threat-model every connector, parser, and network destination.
- Publish vulnerability reporting and supported-version policy.
- Add security regression tests to release gates.

### Exit criteria

- Authentication recovery is tested.
- Workspace and owner boundaries have adversarial coverage.
- Public security documentation matches runtime behavior.

## Phase 10 — Optional multimodal workflows

Only after the core operations platform is proven:

- Image generation with model provenance.
- OCR and document extraction.
- Visual comparison and approval workflows.
- Audio transcription and meeting artifacts.

This phase should reuse the same mission, evidence, policy, and receipt systems
rather than creating an isolated media suite.

---

## 8. Public project workstream

Feature development and public-project health proceed together.

### Repository essentials

- Root license and SPDX policy.
- README quick start and architecture map.
- CONTRIBUTING.md.
- CODE_OF_CONDUCT.md.
- SECURITY.md.
- GOVERNANCE.md.
- Maintainer and release process.
- Issue and pull-request templates.
- Changelog and semantic versioning policy.

### Continuous checks

- Backend, frontend, desktop, and focused browser tests.
- Dependency vulnerability and license scan.
- Secret scan.
- Generated-file and oversized-binary checks.
- Attribution/adoption-register validation for imported code.
- Installer artifact smoke checks.

### Community principles

- Small reviewable pull requests.
- Public design records for cross-cutting changes.
- “Good first issue” work that teaches real architecture.
- Honest support tiers and platform status.
- No roadmap promise without an owner and acceptance test.

---

## 9. Immediate execution order

1. Preserve and finish the Phase 0 feature checkpoint already underway.
2. Add the upstream adoption policy and initial Odysseus register.
3. Audit the repository for public-release hazards.
4. Complete the AGPL attribution and dependency-license inventory.
5. Finalize the contribution-signing policy.
6. Restore a healthy local coder and run the definitive mission.
7. Close the Phase 0 owner gate.
8. Begin the module-level Odysseus adoption study with file-level provenance.
9. Preserve GitHub integration as the first major developer connector in Phase
   7; do not bolt remote mutations directly onto the current local Git UI.

---

## 10. Decisions still owned by the maintainer

1. Should copyright remain with the project owner, use a DCO, or require a CLA?
2. Will releases be community-only, or will paid support/hosted services exist?
3. Which operating systems are officially supported at the first public
   release?
4. Which Odysseus modules, if any, justify direct source adoption instead of a
   Rasputin-native implementation?
5. Should GitHub authentication use a Rasputin GitHub App, user-owned
   fine-grained tokens, or support both?
6. Which GitHub mutations, if any, may be pre-approved per repository instead
   of requiring confirmation every time?
