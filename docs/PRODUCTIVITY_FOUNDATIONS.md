# Productivity Foundations

*Implemented on `codex/productivity-foundations`, 2026-07-13.*

## Durable task queue and activity inbox

Tasks enter SQLite as `queued` before execution. A per-user dispatcher runs the highest-priority
eligible task first and defaults to one concurrent root task per account
(`RASPUTIN_TASK_CONCURRENCY` can raise the limit). Queued tasks recover on startup; an interrupted
running task is paused for explicit review. Activity inbox events are owner-scoped and are created
for task completion, failure, cancellation, and approval requests.

The Activity Center exposes Inbox, Queue, Scheduled, active, completed, and failed views. Queue
priority, cancellation, resume, and retry actions call the backend; the chat queue is no longer
browser memory.

## Search and command palette

`GET /api/search` searches only the signed-in user's messages, task objectives/results, and task
outputs. `Ctrl/Cmd+K` opens the global palette for history search and application navigation.

## Artifact Workspace

Task outputs carry filename, MIME type, byte size, and pinned state. `GET /api/artifacts` and the
Artifact Workspace provide search, content preview, pinning, copy, download, and source-task
provenance. Artifact access is enforced through the owning task's account.

## Connector platform

The connector registry supports Gmail, Outlook, Microsoft Teams, and generic HTTPS webhooks.
Configuration and credentials are account-scoped; API responses expose only masked presence, not
secret values. Provider validation distinguishes `needs_configuration`, `ready_for_authorization`,
and `ready` states.

This pass does not claim provider data access. Gmail, Outlook, and Teams require an external OAuth
application registration and a completed authorization/token-refresh flow before synchronization
or sending can be enabled. Webhook validation does not transmit a payload.

## HTTPS and remote access

The existing mkcert/Uvicorn dual-mode path remains the private-network option. Custom SANs are now
additive to the standard loopback and machine-name SANs. See `docs/RELEASE_SETUP.md` for friendly
name, LAN trust, and public-deployment boundaries.
