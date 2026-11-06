# Startup and resource optimization — 2026-11-05

## Outcome

Two measured startup costs were removed: eager document-parser imports during
bootstrap and eager loading/mounting of four secondary React pages. The existing
Electron source fixture starts faster and uses less memory; a Rust rewrite is
not required to obtain these improvements. The installed application has not
been rebuilt or updated by this change.

## Causes and changes

`/api/ui/bootstrap` calls retrieval statistics. Previously, its parser-availability
check imported `pypdf`, `docx`, and `openpyxl`; the latter also loaded NumPy. A fresh
backend increased from 78.8 MiB to 585.7 MiB private commit during that request,
even without opening a document. Profiling attributed approximately one second
to parser imports. Package discovery now uses `importlib.util.find_spec`, without
executing those packages. Real imports remain in the PDF/Word/Excel read functions;
actual parsing failures retain the existing `parse_failed` result. Availability
reports installation, not a complete runtime compatibility test.

An equivalent fresh optimized profile increased from 78.5 MiB to 82.8 MiB during
bootstrap, with none of the optional parsers or NumPy loaded. Profiled bootstrap
time was 0.726 seconds versus 1.611 seconds before; these are single diagnostic
samples, not standalone statistical benchmarks.

The frontend eagerly imported and mounted Dashboard, Models, Settings, and
Workspaces, including chart and settings dependencies, while opening Chat.
These pages now load on their first explicit visit. The decision waits until
bootstrap resolves the initial route, so Desktop's temporary `home` state does
not unnecessarily load Dashboard. Once visited, pages stay mounted to preserve
drafts and filters. Each has loading feedback and an error boundary with an
accessible reload action. The Chat component and its layout are unchanged.

The main production JavaScript chunk decreased from approximately 1,568 kB to
841 kB (46%). This describes the main chunk, not total installed size or all
JavaScript eventually loaded. Browser tests confirm the four deferred chunks are
absent from initial Chat resources.

Changed implementation: [parser availability](../backend/rag/vector.py),
[route imports and mounts](../frontend-src/src/app/App.jsx), and
[deferred view boundary](../frontend-src/src/components/DeferredView.jsx).
The boundary reuses the pattern from the earlier UI audit implementation rather
than introducing another routing framework.

## Whole-process comparison

The [shell benchmark](../prototypes/rust-desktop/README.md) used identical source
backends/frontends for each shell, fresh data and browser profiles, no model,
three alternating pairs, and ten seconds of sampling after the same UI probe.
The earlier baseline is documented in [prototype results](../prototypes/rust-desktop/RESULTS.md).
These are before/after source-worktree experiments, not installed-app evidence or
a guarantee for populated databases and loaded-model workloads. OS caches and
other workstation activity were not controlled; three repetitions do not support
a p95 or significance claim.

Medians across three runs for each shell:

| Measurement | Electron before | Electron after | Rust/Tauri before | Rust/Tauri after |
|---|---:|---:|---:|---:|
| UI ready from launch | 8.672 s | 6.916 s | 8.543 s | 7.323 s |
| Private committed memory | 1,163.28 MiB | 615.92 MiB | 1,134.63 MiB | 615.93 MiB |
| Summed working set | 614.90 MiB | 543.64 MiB | 666.43 MiB | 610.48 MiB |

Electron improved approximately **20% in readiness time**, **47% in private
commit**, and **12% in summed working set**. Private committed memory measures
virtual memory commitment, not physical RAM. Working-set sums include shared
pages. Do not describe the 547 MiB private-commit reduction as 547 MiB of physical
RAM saved.

Local benchmark evidence lives under Windows TEMP, directory suffixes:

- `rasputin-shell-benchmark-7yy8kr5v`: earlier six-launch baseline.
- `rasputin-shell-benchmark-u099o_zr`: optimized six-launch comparison.
- `rasputin-shell-benchmark-_wib74zb`: separate optimized Rust navigation smoke.

The same mixed worktree was preserved throughout; unrelated user edits are not
part of this optimization commit. Temporary databases/profiles are removed after
the benchmark verifies its process cleanup; measurement JSON and screenshots remain.

## Verification and limits

- Frontend production build passed. Existing Pyodide externalization and large
  chunk warnings remain; the largest main chunk is still approximately 841 kB.
- `python -m unittest tests.testStartupResources tests.testMcpRagRegressions`:
  **13 passed**. Fresh-process coverage checks that bootstrap does not load the
  optional parsers, missing packages are reported, discovery executes no parser
  code, and ingest still handles an import failure.
- `python -m unittest tests.testBackendSmoke`: **162 passed, 6 failed** out of
  168. PDF, DOCX, and XLSX ingestion/search coverage passed. The same six failures
  reproduced in a separate process with the unchanged HEAD parser implementation:
  `testCodingTrialBlindCompareScoresAndPinsCoderRole`,
  `testStage6CodeLoopUsesApprovedCapsuleDuringEditTestRepair`,
  `testStage6TestLoopPassFirstRunNoReopen`,
  `testStage6TestLoopReopensOnFailureThenStopsOnPass`,
  `testStage6TestLoopSkipsWhenNoCommandOrShellDenied`, and
  `testStage6TestLoopStopsAtRetryBudget`. They concern native execution/training
  expectations in the existing worktree, not optional parser loading. This change
  does not relax those execution boundaries to make the tests green.
- `playwright test tests/ui/startupResources.spec.mjs`: **3 passed** against an
  isolated Native Host using real authentication. Checks cover deferred requests,
  all four first-visit pages plus Discover, keyboard navigation, preserved drafts,
  and a failed-chunk recovery action.
- Actual Rust WebView source smoke checks app readiness, Desktop bootstrap,
  Settings/Chat navigation, keyboard and mouse interaction, blocked external
  navigation/popups, and owned-process cleanup. This is not installation evidence.

Document parser memory is deferred until it is needed, not eliminated for later
document ingestion. Visited pages retain state and some memory intentionally.
Production packaging, installed-app verification, real inference, populated-store
latency, and sustained background CPU use remain separate checks.

The next profiling targets are backend imports/initialization, startup model
discovery, repeated schema initialization, and remaining eager UI dependencies.
Do not move authentication, pending-task recovery, approval enforcement, or
process ownership off the startup path merely to improve a timing number.
