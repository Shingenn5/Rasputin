# Assistant command routing

Rasputin's assistant surface accepts a small, deterministic command vocabulary
for future voice and chat orchestration. The first endpoint is intentionally a
preview boundary:

```text
POST /api/assistant/command-preview
```

Example request:

```json
{"command":"Please check Docker status"}
```

The response identifies the matched allowlisted operation and returns its
current policy preview. It always reports `execution.mode: preview_only`,
`execution.started: false`, and `approval.created: false`. No process,
container, file, microphone, or speaker is started by this endpoint.

## Route states

- `recognized`: an alias maps to a concrete broker adapter and current policy
  permits a handoff preview;
- `blocked`: the alias is known, but a security flag, workspace boundary, or
  broker capability prevents it from proceeding;
- `needs_clarification`: no allowlisted alias matched the bounded input;
- `rejected`: shell-like syntax or other command composition was supplied.

Recognized operations still show `approval.state: review_required` when the
operation requires approval. The endpoint does not create that approval. The
operator must continue through the existing approved-plan → handoff → prepare
→ dispatch workflow. Models never receive arbitrary command text as a host
command.

The available aliases and the router contract version are published by
`GET /api/assistant/capabilities` under `commandRouter`. Adding an alias must
map to an existing `CONTROL_OPERATIONS` entry, remain broker-only, and include
a regression test for recognized, blocked, and non-executing behavior.
