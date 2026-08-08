# Lasting memory contract

**Status:** implemented foundation (owner/workspace-safe memory lifecycle)

Rasputin's name is temporary, but this memory contract is intended to survive a
future product rename. It defines what the assistant may retain across chats
and how the owner can inspect or remove it.

## What exists now

Memory is persisted in the local SQLite runtime store (`memory_items`) and is
separate from short-lived task context. Each item carries:

- an owner id;
- a `global` or `workspace` scope;
- a kind such as preference, fact, project note, or workflow lesson;
- sensitivity, confidence, and importance metadata;
- source task/session/message provenance when available;
- a content hash and recall counters;
- a review status (`saved`, `pending`, or `rejected`).

Saved items survive process restarts and are searchable through the local FTS
index. Search updates `last_used_at` and `recall_count` so the UI can show how
often an item has influenced recall.

## Owner and workspace boundary

Every API query is owner-scoped. Workspace-scoped items are associated with a
workspace reference; global items can be recalled from any workspace owned by
that user. Agent `memory_search` calls derive the owner and workspace from the
persisted task instead of trusting model-authored arguments.

Sensitive items remain excluded from ordinary Assistant context previews unless
the owner explicitly opts into sensitive context. Retrieved memory is wrapped
as untrusted evidence before it reaches a model, so saved text cannot become a
policy instruction by itself.

## User workflow

The Memory view supports:

1. saving a new global or workspace-scoped memory;
2. searching saved memory;
3. reviewing pending suggestions;
4. editing saved content;
5. permanently deleting an item after confirmation.

The HTTP surface is:

- `POST /api/memory` — save a memory item;
- `GET /api/memory/items` — list owner-visible items;
- `POST /api/memory/search` — search saved items;
- `PATCH /api/memory/items/{id}` — edit an item without losing provenance;
- `DELETE /api/memory/items/{id}` — delete the item and its FTS entry;
- `GET /api/memory/review` and `POST /api/memory/review` — approve or reject suggestions.

## Deliberate next steps

This is the durable foundation, not the final memory intelligence. The next
memory slices should add:

- visible source/session links and a “why was this recalled?” explanation;
- correction, supersession, conflict resolution, and duplicate detection;
- retention/expiry controls and export/delete-all workflows;
- explicit per-task memory inclusion/suppression controls;
- measured consolidation from completed conversations, with suggestions kept
  pending until reviewed;
- semantic/hybrid recall only after the owner-controlled lifecycle is stable.

