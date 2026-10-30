# Rust performance assessment

Investigation date: 2026-10-30. Base commit: `c70dca7`.
Branch: `codex/rust-performance-investigation`.

## Decision

Investigate a **bounded Rust retrieval component** before committing to a full
rewrite. Keep React, FastAPI's existing policy boundaries, and llama.cpp for the
first experiment. Compare Rust against a better Python storage/indexing baseline,
not only against today's implementation. No Rust speedup has been measured yet.

A Tauri desktop migration is a separate candidate for startup, memory, and package
size. It should not be sold as a model-generation speed improvement. A complete
Rust backend remains possible, but the current evidence does not justify its cost.

This change adds a repeatable benchmark and this assessment. It does not change
the running application, install a runtime, or implement a Rust replacement.
The checkout contained unrelated edits when the branch was created; those edits
are excluded from this investigation's commit. Findings describe the inspected
working tree, not a clean certification of the base commit or installed product.

## What actually runs today

```text
Electron window -> React -> FastAPI/Python -> native llama-server process
                              |
                              +-> SQLite / retrieval / governed tools
```

The inference process is launched in
[`native_llamacpp.py`](../backend/warsat/providers/native_llamacpp.py), around line
514. The model request and SSE parser live in
[`providers.py`](../backend/models/providers.py), around lines 429-536.
Upstream [llama.cpp](https://github.com/ggml-org/llama.cpp) already implements
inference in C/C++. Replacing its Python caller does not replace its GPU kernels,
model quantization, KV-cache layout, or hardware placement.

The current
[`stream delta handler`](../backend/engine/agent.py), around line 1607,
throttles ordinary broadcast requests to 150 ms intervals. Perceived text cadence
can therefore differ from native decode throughput. Actual browser timing and
queue delay need measurement before blaming the language. Do not remove throttling
without measuring rendering cost and slow-consumer behavior.

## Measured retrieval baseline

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_retrieval.py
.\.venv\Scripts\python.exe scripts/benchmark_retrieval.py --chunks 50000 --repeats 3
```

[`benchmark_retrieval.py`](../scripts/benchmark_retrieval.py) creates a disposable
`RASPUTIN_DATA_DIR` before importing the backend. It uses the existing SQLite
store and real retrieval implementation, with synthetic chunks and a mocked active
workspace. It asserts that the in-memory and persisted search return identical
results and that returned hits belong to the fixture workspace. It never starts
a server or model and never reads the user's index.

Local Windows run, CPython 3.12.14, warm caches, five samples per measurement:

| Chunks | Serialized JSON bytes | Load SQLite + JSON, median | Search including load, median | Search with index already in memory, median |
|---:|---:|---:|---:|---:|
| 1,000 | 1,298,193 | 14.378 ms | 30.394 ms | 13.778 ms |
| 10,000 | 13,097,706 | 118.474 ms | 270.818 ms | 178.509 ms |
| 50,000 (3 samples) | 65,977,843 | 614.290 ms | 1,311.805 ms | 843.233 ms |

These are separate timed series, so the medians are not additive. The in-memory
case excludes persistence loading; it still filters, computes frequencies,
scores, sorts, and formats results. Fixture creation and initial database writes
are outside the measurements. The script prints maximum observed latency too;
five samples are not sufficient for a credible p95 claim.
The 50,000-chunk run used three samples and the same warm-cache procedure.

The fixture repeats short code-like text with shared vocabulary and distinct
module names. It is a scaling probe, not a representative production corpus,
ranking-quality evaluation, memory benchmark, cold-start result, or concurrent
load test. No installed-app timings or Rust comparison have been collected.

## Why retrieval is the first candidate

In [`vector.py`](../backend/rag/vector.py):

- `_load()` at line 46 fetches the whole `rag_vector` JSON value before filtering
  to the active workspace. `search()` at line 627 does this on each search.
- `search()` recomputes document frequencies, scans every scoped chunk, computes
  lexical/vector/path scores, and fully sorts positive matches before taking up
  to 20 hits. `_path_score()` also tokenizes each candidate's path for each query.
- `_embed()` at line 149 performs per-term hash-vector construction in Python.
  Its contribution to ingestion has not been timed by this benchmark.

[`runtime_store.py`](../backend/core/runtime_store.py), lines 52-97, calls schema
initialization on KV reads/writes, opens connections, and parses the JSON value.
That is an implementation overhead worth profiling, not evidence that SQLite or
Python must be replaced wholesale.

First compare a versioned in-memory index cache, cached document frequencies and
path terms, and bounded top-k selection with today's behavior. Cache invalidation
must cover ingest, reset, workspace changes, and concurrent operations. Longer
term, persist separately addressable chunks instead of reloading all workspaces.
An inverted index could reduce candidate scanning; this requires explicit ranking
and recall checks because today's hash-vector score can match nonlexical terms.

If Rust still offers a material win, use a coarse PyO3 call over a Rust-owned index
snapshot. Avoid converting every Python dictionary or transferring the entire JSON
blob on each query; that could preserve the dominant cost across a new boundary.
[PyO3](https://pyo3.rs/main/) supports Rust extension modules for Python. Shipping
one requires a Windows wheel/build and frozen-backend packaging verification.
It retains Python and does not shrink the application into one Rust executable.

## Rewrite options

| Scope | Plausible benefit to measure | Main cost | Recommendation |
|---|---|---|---|
| Improve current retrieval storage and algorithms | Query latency and ingestion overhead | Cache correctness, ranking parity | Establish this baseline first |
| Rust retrieval extension, existing UI/backend | CPU-heavy scoring/index work | FFI conversion, index lifetime, Windows extension packaging | First Rust experiment |
| Tauri + React + existing Python sidecar | Desktop startup, memory, installer footprint | Supervisor/IPC replacement, WebView2 behavior, installer/recovery parity | Separate shell experiment |
| Rust HTTP backend + React + llama.cpp | Remove Python host; potentially lower host overhead | Rebuild API, auth, stores, tools, streaming, integrations and packaging | Defer until profiles justify it |
| Rewrite inference engine or React in Rust | No demonstrated benefit here | New inference compatibility or UI migration burden | Outside the first performance scope |

[Tauri's architecture](https://tauri.app/concept/architecture/) uses a Rust core and
platform webviews. Its [sidecar support](https://v2.tauri.app/develop/sidecar/)
allows retaining a packaged backend. This makes a shell experiment feasible; it
does not establish that Rasputin would start faster or use less total memory.
Measure the entire process tree, including the Python sidecar and webview.

Model-file hashing is a lower-priority rewrite target: current download/artifact
code hashes 1 MiB blocks using `hashlib.sha256`. Python's
[hashlib documentation](https://docs.python.org/3/library/hashlib.html) notes that
large updates release the GIL. This is not a byte-at-a-time Python SHA loop.
Measure disk throughput and repeat verification passes before porting it.

## Acceptance gates for an implementation

1. **Define the symptom.** Measure click-to-interactive startup, process-tree
   memory, retrieval latency, time to first visible token, native prompt/decode
   timings, and cancellation latency separately. Use the existing
   [`benchmark runner`](../backend/warsat/benchmark_runner.py), around line 150,
   for model-side request/timing evidence, plus UI instrumentation for visibility.
2. **Compare fairly.** Same hardware, corpus, model/profile, query set, warm/cold
   conditions, and output token budget. Compare current Python, improved Python,
   and Rust. Use enough runs for median/p95 and record CPU/memory. Suggested
   decision gate, not a measured promise: at least 2x retrieval improvement over
   the improved Python baseline on an agreed workload, with acceptable memory.
3. **Prove compatibility.** Compare top-k IDs, ordering, scores within a declared
   tolerance, citations, workspace isolation, empty inputs, limits, ingest/reset
   invalidation, Unicode/path behavior, and concurrent reads/writes. Keep the
   current implementation available for rollback during the experiment.
4. **Preserve authority.** Keep owner/workspace filtering and approvals enforced
   before the Rust boundary; apply scoped index selection inside it as defense
   in depth. Preserve audit records, authentication, Desktop loopback behavior,
   atomic installation, process ownership, and fail-closed host-shell behavior.
   Memory safety does not automatically reproduce application authorization.
5. **Prove delivery.** Build the actual Windows package; test clean install,
   upgrade, rollback, crash recovery, stop/restart, and no orphaned model process.
   For Tauri, also verify CSP/origin rules, capabilities, WebView2 availability,
   keyboard behavior, and existing React interactions in the packaged application.

If a full Rust rewrite is later selected, migrate one bounded service at a time
behind the existing API contracts. A possible backend stack is Axum/Tokio,
Serde, a maintained SQLite binding, and an HTTP/SSE client; versions and dependency
choices require validation at implementation time. Keep llama.cpp as the engine
and React as the UI. Python document parsers, model acquisition, voice/training
workers, and other integrations need an explicit retain/replace inventory first.

## Current evidence boundary

Implemented: isolated synthetic Python benchmark and source-backed assessment.
Measured: current retrieval at 1,000, 10,000, and 50,000 chunks. Benchmark
correctness assertions passed for all three sizes. Documentation validation
passed for 49 Markdown files. Application regression suites were not run because
this change does not modify application code; the benchmark directly exercises
the existing retrieval path. The first sandboxed run could not open its temporary
SQLite database; both subsequent runs completed outside that restriction.
Unverified: Rust performance, real-corpus latency, concurrency, cold-start/package
size improvements, installed-app behavior, and full-rewrite effort. No speedup
claim or delivery estimate is justified by the current evidence.
