# Rasputin Current Baseline

Last reviewed: 2026-06-10

This document records the known-good baseline after the first ten autonomous build passes. It is intended as the reset point before new feature work resumes.

## Product State

Rasputin is a Docker-first, localhost-bound AI workbench with a FastAPI backend, React/Vite frontend, SQLite runtime state, approved workspaces, local model routing, RAG, Graphify, Tool Relay, Warsat runtime planning, approvals, memory, and first-run setup guidance.

The expected local UI is:

```text
http://127.0.0.1:8787
```

The isolated test harness UI is:

```text
http://127.0.0.1:8877
```

## Completed Baseline Capabilities

- Local admin login, password change flow, and setup checklist.
- Durable sessions, tasks, messages, traces, artifacts, approvals, skills, memory, schedules, and preferences in ignored local data.
- Chat-first Home with workflow lanes and task detail visibility.
- Approved workspace browser, safe file preview/read tools, and mutation preview plans.
- Tool Relay registry with redacted durable tool calls.
- Local stdio MCP relay support with registration approval, start/stop/discover, and tool classification.
- RAG indexing UX with local citations and visible indexed state.
- Graphify evidence UI with typed node/edge relationship evidence.
- Warsat launch planning, deployment approval flow, hardware probe, and model fit scoring.
- Trials model comparison with mode-routing preference save.
- Release setup docs for a clean local clone.

## Current Safety Defaults

- Runtime data, credentials, model files, generated indexes, logs, screenshots, and test data stay ignored.
- Docker control remains disabled unless explicitly enabled.
- External MCP tools remain disabled until classified.
- Risky tools require approval.
- Models do not receive direct internet access.
- Remote MCP transports remain deferred.
- Model downloads from the UI remain deferred.

## Known Next Work

The next queued implementation pass is MCP Relay V2 Compatibility Hardening. It should improve real-world local stdio MCP reliability, diagnostics, resources/prompts visibility, and UI clarity without adding remote transports or broad new execution powers.

## Validation Baseline

Pass 10 completed with:

- full backend smoke tests passing
- Playwright UI smoke passing
- Vite frontend build passing
- whitespace diff check passing
- repo safety check passing

Pass 11 should re-run the same validation suite before committing this baseline.
