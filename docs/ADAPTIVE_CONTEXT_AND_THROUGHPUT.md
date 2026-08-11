# Adaptive context and child-work budgets

`backend/engine/context.py:adaptive_profile()` is the bounded policy bridge
between model evidence and agent budgets. It accepts evidence only when the
caller explicitly attaches it to a registry model:

- a resource manifest may provide a measured KV-cache bytes-per-token value,
  available VRAM, and estimated weight memory;
- a fresh runtime benchmark certificate may provide the tested context window,
  tested concurrency, success rate, and TTFT p95.

The policy then:

1. caps context to the measured KV-cache envelope, leaving a fixed safety
   margin for runtime allocations;
2. caps context to the certificate's tested window;
3. caps child work to `tested concurrency - 1`, preserving one slot for the
   parent task; and
4. lowers the output ceiling when the certificate is partial or its TTFT p95
   is above five seconds.

All paths retain the existing hard minimum/maximum context and output limits.
Missing, stale, or unmeasured evidence is reported in the adaptive trace and
does not change the static defaults. `AgentHub.start()` records the requested
and resolved child count as an `adaptive_budget` trace event, so an operator can
see why a task was queued with fewer children.

This is a policy foundation, not a performance promise. A real runtime adapter
must attach certificates for the exact model revision, device set, context,
and concurrency before the adaptive path can improve throughput.
