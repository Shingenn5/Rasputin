# Rasputin v1 release contract

**Status:** native product direction reconciled 2026-08-29; ten-slice acceptance scope retained

**Purpose:** define the smallest useful Rasputin release that can be called a
dependable local workstation and Assistant platform. This document is a scope
boundary, not a claim that every acceptance item is already complete.

## Product promise

Rasputin v1 lets an owner run a local-first Workstation and Assistant separately
or together while retaining explicit control over models, workspaces, memory,
tools, and host actions. A release is complete only when the evidence matrix in
this document passes; feature presence alone is not sufficient.

## Supported deployment paths

- **Windows Desktop:** the native product, with an Electron-owned packaged backend and bundled llama.cpp.
- **Native Server / Native Host:** the Windows source/browser workflow with approved host folders;
  it must not share a live data store with Desktop.
- **Native models:** exact compatible GGUF artifacts, local llama.cpp processes, and explicit
  installation/loading/health states. Separately registered local endpoints and speech adapters
  retain their own capability requirements.

Docker Server is retired from the current product. Prior Linux/macOS container evidence is
historical; neither those platforms nor a container deployment are current release requirements.

Remote model endpoints remain disabled by the default privacy policy. A remote
endpoint is not required for v1 acceptance.

## Required v1 capabilities

### Workstation track

1. Register and select a model with visible health and capability evidence.
2. Choose a trusted workspace with owner and workspace boundaries intact.
3. Run a governed coding task that can edit multiple files, run a configured
   test, repair a failure, and present a reviewable diff.
4. Keep supported shell, file moves, commits, and other host mutations approval
   gated and auditable.
5. Expose model fit, placement, runtime, and failure reasons before launch.

### Assistant track

1. Keep Assistant and Coding workflows independently usable.
2. Preserve the bounded sarcastic-but-respectful personality profile.
3. Recall owner-scoped lasting memory with provenance, suppression, correction,
   and supersession controls.
4. Route natural-language commands through previews, allowlists, approvals, and
   the internal MCP capability contract.
5. Complete one local speech-to-text -> Assistant -> text-to-speech turn using
   registered local models and explicit browser audio permission.

### Operations and recovery

1. Admit model work against measured resources, leases, placement policy, and
   fresh runtime evidence.
2. Start, stop, inspect, and troubleshoot the supported deployment paths with
   documented commands and redacted diagnostics.
3. Back up and restore a representative installation into a clean target without
   modifying the source backup or leaking secrets.
4. Make the release state visible in the UI and in the release-candidate report.

## Evidence matrix

Every required capability must have the corresponding evidence before v1 is
tagged:

| Evidence | Required proof | Authority |
| --- | --- | --- |
| Automated regression | Isolated backend, UI-contract, documentation, and artifact checks pass. | `scripts/verify_release_candidate.py` |
| Native deployment | The actual Desktop/Native Host owner passes health, frontend, and security-header probes; installed builds are tested as packages. | `scripts/verify_deployment_matrix.py` |
| Model runtime | A selected local model has fresh capability, placement, and measured benchmark evidence. | Native runtime/model certificates and registry state |
| Coder mission | A live model completes edit -> test failure -> repair -> diff review without unapproved host mutation. | Coding acceptance evidence and task review record |
| Voice turn | A real authenticated browser turn completes local STT -> Assistant -> TTS and plays bounded audio. | Voice readiness API, browser evidence, and audit record |
| Lasting memory | A memory can be recalled, explained, suppressed, corrected, superseded, and deleted within owner/workspace scope. | Memory API/UI tests and live review evidence |
| Safe orchestration | Tool discovery is fail-closed; command previews and host mutations require the documented approval state. | MCP/Assistant contracts and audit records |
| Recovery | A representative backup restores into a clean target and passes health/login/workspace checks. | `scripts/rehearse_restore.py` and recovery runbook |
| Operator UX | Workstation/Assistant separation, model fit, voice readiness, memory provenance, and approval states are understandable by keyboard and mouse. | Authenticated browser checks and UI contracts |

## Ten-slice completion boundary

The completion batch has exactly ten slices. The sequence is intentionally
finite; a slice may fix defects discovered by its own acceptance checks but may
not add a new product capability.

### Slice 1: Freeze the release contract

Add and machine-check this document, supported paths, evidence matrix, and
explicit non-goals.

### Slice 2: Integrate resource admission

Connect resource leases, manifests, benchmarks, and placement decisions to
native model and model-pack launch previews. Oversized or contradictory launches must
be blocked before starting work.

### Slice 3: Certify the local model fleet

Deploy one approved main/coder model configuration on the intended hardware and
record fresh health, capability, placement, and throughput evidence.

### Slice 4: Complete the live coder mission

Run the real multi-file edit -> failing test -> repair -> review workflow with
the certified local model and preserve the evidence.

### Slice 5: Package one local voice pair

Provide one supported STT profile and one supported TTS profile with local
endpoint setup, model-pack registration, and health-check instructions.

### Slice 6: Verify one live voice turn

Use the browser push-to-talk flow with explicit permission and verify local STT,
Assistant reasoning, TTS, playback, timeout, and abort behavior.

### Slice 7: Finish lasting-memory controls

Complete cross-chat review, correction/supersession, inclusion/suppression,
provenance, deletion, and restart evidence.

### Slice 8: Certify safe orchestration

Certify MCP discovery, command routing, previews, approvals, dry-run behavior,
audit records, and safe fallbacks without granting arbitrary host authority.

### Slice 9: Complete deployment and recovery

Finish Windows Desktop and source Native Host onboarding, packaged update validation,
clean restore, ownership/port-conflict handling, and isolated recovery rehearsal.

### Slice 10: Run the release gate and lock scope

Run the source-level UI contract certification and publish the authenticated
operator evidence runbook. Run the full release-candidate gate and move all new
ideas to the post-v1 backlog. Tag v1 only after the human evidence rows are
green; an automated candidate with open boundaries must remain explicitly
untagged.

## Explicit non-goals

The following are deliberately deferred and must not be pulled into the ten
slices:

- custom Rasputin fine-tuning or a new foundation model;
- an always-listening microphone, wake word, or background audio service;
- arbitrary autonomous computer control or unreviewed shell execution;
- a public cloud/SaaS control plane or synchronized cloud memory;
- an external MCP server unless the internal contract is proven insufficient;
- blind mixed-card vLLM tensor parallelism or a claim of pooled VRAM safety;
- a plugin marketplace, broad connector expansion, or a major UI redesign;
- public-store signing, update channels, or enterprise collaboration features.

## Stop rule

After Slice 10, Rasputin v1 is considered complete when every evidence row is
green, no P0/P1 defect remains, and the automated release report is green with
its remaining boundaries explicitly empty or accepted. The project then enters
maintenance mode: only regressions, security issues, data-loss risks, and
deployment failures may extend the v1 implementation. New capabilities belong
in a separately prioritized post-v1 plan.
