# Native release evidence and source regression gates

This contract implements the first reliability wave from the [system improvement review](reviews/RASPUTIN_SYSTEM_IMPROVEMENT_REVIEW_2026-09-04.md). It supports the [v1 release contract](RASPUTIN_V1_RELEASE_CONTRACT.md); it does not widen that contract or certify an installation automatically.

## Run source checks

From the repository root, using the project virtual environment:

```powershell
.\.venv\Scripts\python.exe scripts/verify_source_regressions.py
```

The runner checks documentation, the backend suites, all top-level JavaScript contract/helper tests, Desktop syntax and lifecycle, a fresh frontend build, and authenticated browser fixtures. Every backend test module gets a separate child process and temporary data directory. The browser fixtures use a newly owned loopback Native Host, a generated administrator password, and a separate temporary store. The runner stops its test server and cleans up test state.

Process lifetime control requires Windows. The runner and release command launch each child suspended, assign it to a retained [Windows Job](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects), and then resume it. Cleanup stops all descendants even when their launcher has already exited. Ownership failures stop the check before execution; there is no unowned fallback. This helper manages trusted verification processes and does not enable the application's native Host Shell or provide filesystem/network isolation.

Optional flags:

| Flag | Meaning |
| --- | --- |
| `--json` | Emit a version 1 source report with checks, exit codes, test counts where available, and `buildVerified`. |
| `--groups documentation backend javascript desktop build browser` | Select specific check groups. Omitting this flag runs all groups. Backend or browser selection builds first because backend imports mount the generated frontend assets. |
| `--no-build` | Explicitly reuse existing frontend artifacts; the report sets `buildVerified: false`. |
| `--browser-artifacts PATH` | Save fixture screenshots in a selected scratch directory for review. |

Browser checks that discover no tests or skip because credentials are missing fail the gate. Fixture model operations and dry-run experiment responses remain fixture evidence; they do not establish real-model capability.

[Windows source regressions](../.github/workflows/windows-source-regressions.yml) runs this gate on pull requests, pushes to `main`, and manual dispatch. The workflow does not publish or install the application. Until the changes are pushed and the hosted workflow runs, local checks are the available proof.

## Select what is being evaluated

There are no automatic production endpoint probes. Select one native owner explicitly:

```powershell
# Read-only identity calculation: no server/model start, build, or endpoint probe.
.\.venv\Scripts\python.exe scripts/verify_release_candidate.py --target native-host --identity-only

# Run gates and probe an explicitly selected source Native Host.
.\.venv\Scripts\python.exe scripts/verify_release_candidate.py --endpoint native=http://127.0.0.1:8788
```

The legacy `native=URL` label remains accepted. Supported labels are `native`, `native-host`, and `desktop`. A Desktop target requires `--package` pointing to the actual tested installer or package file; Desktop endpoints must be loopback. Use the recorded owner URL from the [deployment guide](DEPLOYMENT_MATRIX.md), not an assumed port. Selecting a target without an endpoint permits identity inspection; a full run still needs a successful explicit deployment probe.

The subject contains:

- `source`: Git commit, dirty-state boolean, and a content hash of tracked and non-ignored untracked source files.
- `target`: `native-host` or `desktop`.
- `package`: `source` plus source hash for Native Host, or `desktop-package` plus the selected file's SHA-256.
- `models`: explicitly selected artifact/runtime/configuration hashes by role.

Source and package identities are checked again after verification. A source edit during the run invalidates that run's identity check. Keep evidence bundles outside the repository so their contents do not change the source digest they describe.

Model selection uses repeatable `--model ROLE=ARTIFACT_SHA256:RUNTIME_SHA256:CONFIG_SHA256` arguments. Supported roles are `main`, `coder`, `assistant`, `stt`, and `tts`. Supply real, measured identities; the checker compares these values with imported records, but it does not independently discover or launch those models.

## Evidence bundle version 1

Pass the JSON bundle with `--evidence PATH`. It contains exactly `schemaVersion` and `records`. Each record has the following fields:

| Field | Required contents |
| --- | --- |
| `id` | Unique bounded nonempty record identifier. |
| `row` | One required evidence row listed below. |
| `type` | The kind of proof actually collected, not the kind you hope to claim. |
| `source` | Exact selected `{commit, dirty, sha256}`. |
| `target` | Exact selected native owner. |
| `package` | Exact selected `{kind, sha256}`. |
| `environment` | `{kind, platform, machineId, owner, hardwareId}`. Platform is `windows`; kind is `source`, `installed`, or `clean-machine`; owner matches the selected target. Use opaque machine/hardware IDs, not private paths. |
| `models` | Role mapping to `{artifactSha256, runtimeSha256, configSha256}`; required role identities must match the selected subject. |
| `timestamp` | ISO timestamp including a timezone. |
| `outcome` | `passed` or `failed`. |
| `artifacts` | One to sixteen `{path, sha256}` entries identifying actual proof files relative to the bundle directory. |

Supported proof types are `source-test`, `mocked-workflow`, `browser-test`, `source-probe`, `installed-package`, `clean-machine`, `model-runtime`, `live-coder`, `live-voice`, and `recovery`. A recognized type does not automatically satisfy a row.

The evaluator rejects malformed or duplicate fields, duplicate record IDs, unsupported types, mismatched identities, future timestamps beyond the bounded tolerance, records older than seven days, escaped/missing artifacts, and attachment hash mismatches. It bounds the JSON to 1 MiB, records to 128, attachments to 16 per record, each attachment to 256 MiB, and total attachment hashing to 512 MiB. A newer failure takes precedence over an older pass, including tied timestamps.

These records are **operator attestations with verified attachment hashes**, not signed certificates. Hashes establish that the referenced bytes match; they do not prove that a screenshot or report contains truthful observations. The operator must review the actual artifacts and their collection method. Never relabel mocked output as live-model or installed-package proof.

## How rows close

| Row | Required proof |
| --- | --- |
| `automatedRegression` | The current automated gate, including a fresh build; imported claims cannot replace it. |
| `nativeDeployment` | Native Host: source probe. Desktop: both installed-package and clean-machine deployment proof. |
| `modelRuntime` | Real model-runtime evidence with selected main-model and hardware identity. |
| `coderMission` | Real live-coder mission with selected coder and hardware identity. |
| `voiceTurn` | Real live-voice turn with selected Assistant/STT/TTS and hardware identity. |
| `lastingMemory` | Browser proof of the memory lifecycle in the target environment. |
| `safeOrchestration` | Browser proof of governed discovery, previews, approval, and execution/fallback behavior. |
| `recovery` | Recovery evidence; Desktop requires a clean-machine environment. |
| `operatorUx` | Browser operator workflow proof in the target environment. |

For Desktop, live/model/browser rows require an installed or clean-machine environment. Source fixtures cannot close them. Native Host uses its source environment but still requires actual live model/voice proof for the applicable rows.

The report separates `automatedChecksPassed`, `buildVerified`, `releaseReady`, row status, and rejected records. By default, a candidate may exit successfully while required human/hardware rows remain open. Use `--require-ready` for a release decision: it returns failure until every required row is satisfied. `--no-build` can never certify release readiness.

## Backup behavior after the reliability fix

Application backups stage immutable files, snapshot SQLite databases with the online backup API, hash and archive those staged bytes, inspect the finished archive, and only then publish it. SQLite snapshots include the main, Trials, and Archive stores and detected SQLite files, including committed content that still resides in WAL.

Responses distinguish `created`, `integrityVerified`, and `restoreRehearsed`. The compatibility field `verified` now means archive integrity was actually checked. Creation does not claim a restore rehearsal.

Each database snapshot is consistent independently; sidecar files are checked for changes while being copied. There is **no single transaction across all databases and sidecars**. The manifest states `crossFileAtomic: false`. Use a stopped source if the workflow requires one consistent point across those stores. Models, cache, TLS/private-key files, and workspace source retain their documented exclusions.

Restore checks hashes and paths, refuses active/overlapping/nonempty destinations, extracts into a staging directory, verifies the extracted bytes, and publishes the completed directory. The Windows rehearsal puts fixture creation in a child process so that process exit closes database handles before strict scratch cleanup. It verifies representative users, sessions, and workspace membership in a separate restored instance.

## Scorecard interpretation

Generic Trials cards now measure only request completion when actual outcome counts exist. Completion is not semantic accuracy, reasoning ability, safety, or coding competence. Unsupported dimensions are `null` and display “Not measured.” The measured average excludes missing dimensions and is also unmeasured when no dimensions have evidence.

Cards show provenance, sample count, timing observations where available, dataset-version limitations, and uncertainty. Partial radar charts show measured points without filling unmeasured axes. Older cards without provenance retain their historical stored payloads, but the read/UI surface hides those unproven scores and asks for regeneration. Fitness certificates keep their separate contract.

Implementation: [backup service](../backend/core/backup.py), [scorecards](../backend/trials/scorecards.py), [evidence evaluator](../scripts/release_evidence.py), [source runner](../scripts/verify_source_regressions.py), and [release verifier](../scripts/verify_release_candidate.py).
