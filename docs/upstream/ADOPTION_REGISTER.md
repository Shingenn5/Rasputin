# Upstream Adoption Register

This register tracks external inspiration, dependencies, source imports, and
upstream contributions associated with Project Prometheus.

## Status legend

| Status | Meaning |
|---|---|
| Research | Behavior or architecture is being studied |
| Proposed | A bounded adoption has been designed |
| Approved | License and architecture review passed |
| Implementing | Work is active |
| Adopted | Verified and merged |
| Rejected | Decision and rationale are recorded |
| Upstreamed | A generally useful change was contributed back |

## Odysseus baseline

| Field | Value |
|---|---|
| Repository | `https://github.com/odysseus-dev/odysseus` |
| Default branch | `dev` |
| License observed | AGPL-3.0-or-later |
| Current use | Product and architecture research; source adoption candidates require file-level approval |
| Pinned research commit | `d8a2059df8e53bc7275c45339849d14c8651e73c` (2026-07-23) |
| Source copied into Rasputin | No |
| Rasputin license | AGPL-3.0-or-later |

## Candidate register

| ID | Candidate | Class | Status | Intended Rasputin outcome | Source adoption approved? |
|---|---|---|---|---|---|
| ODY-001 | Cookbook and hardware-aware model guidance | Product lesson | Implementing | WarSat Advisor with reproducible fit and fitness evidence | No |
| ODY-002 | Blind model Compare | Product lesson | Proposed | Trials with blind scoring and certificate promotion | No |
| ODY-003 | Deep Research workflow | Product lesson | Proposed | Evidence graph and claim-level research receipts | No |
| ODY-004 | Document workspace | Product lesson | Research | Versioned artifact studio tied to tasks and evidence | No |
| ODY-005 | Scheduled agents | Product lesson | Research | Governed automations with shadow mode and receipts | No |
| ODY-006 | Email and calendar integrations | Protocol | Research | Least-privilege connector SDK and approval-gated outbound actions | No |
| ODY-007 | TOTP and session security | Product lesson | Proposed | Multi-user authentication hardening | No |
| ODY-008 | Backup and restore | Product lesson | Proposed | Encrypted portable operations bundles and restore validation | No |

Detailed source paths, decisions, and the bounded contract for the first
implementation are in
[`ODYSSEUS_MODULE_STUDY.md`](./ODYSSEUS_MODULE_STUDY.md).

## Rasputin-native work completed before source adoption

| Work | Relationship | Notes |
|---|---|---|
| Workspace validation command editor | Rasputin-native baseline | Exposes existing governed test/build/lint commands |
| Task Changes and Terminal inspection | Rasputin-native baseline | Uses existing task, git, and approval services |
| WarSat tool-call parser selection | Rasputin-native baseline | Extends Rasputin's existing deployment planner |
| WarSat absent-GPU-layer fix | Rasputin-native defect fix | Restores automatic combined-GPU planning |
| WarSat Advisor recommendation service | Odysseus product lesson, Rasputin-native implementation | Deterministic observed/estimated/unproven evidence, hard blockers, and approval-preserving plan seeds |

No item in this section contains Odysseus source code.

## Entry template

Copy this section for each approved adoption:

```text
ID:
Status:
Owner:
User outcome:
Classification:
Upstream repository:
Upstream commit:
Upstream paths:
Upstream authors/notices:
License:
Compatibility decision:
Rasputin design:
Security review:
Dependencies:
Acceptance evidence:
Local modifications:
Upstream issue or pull request:
Removal/migration plan:
```
