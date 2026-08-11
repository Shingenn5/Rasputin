# Runtime benchmark certificates

`backend/warsat/benchmarks.py` records numeric runtime observations under the
`rasputin.runtime-benchmark.v1` schema. It is intentionally an evidence store,
not a launcher: adapters submit samples, while the broker and approval layer
remain the only components allowed to decide whether a model can start.

Each certificate is keyed by the exact model revision, runtime/protocol,
visible device ids, context window, concurrency, quantization, and placement
mode. A certificate therefore cannot be silently reused as proof for a
different device set or tuning profile.

The certificate summarizes:

- sample count, success rate, total latency p50/p95;
- time-to-first-token p50/p95;
- prompt and decode throughput where token/timing counters are available;
- queue time and observed memory use;
- a freshness flag (30-day default);
- explicit limitations and an `unmeasured` quality section.

The API is local and approval-safe:

- `POST /api/warsat/benchmarks` records an admin-submitted certificate;
- `GET /api/warsat/benchmarks` lists certificates owned by the current user;
- `GET /api/warsat/benchmarks/{certificateId}` returns one owner-scoped record.

This slice does not make synthetic measurements or call a model. A future
runtime adapter should collect vLLM/llama.cpp timing and memory counters,
attach the exact manifest identity, and submit the resulting samples. Semantic
quality remains unmeasured until an objective rubric-backed trial supplies it.
