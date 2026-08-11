# Lasting memory contract

**Status:** implemented foundation (owner/workspace-safe memory lifecycle,
provenance, retention, duplicate, and reviewed supersession controls)

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
- a review status (`saved`, `pending`, `rejected`, `expired`, or `superseded`);
- an explicit retention policy (`persistent`, `7_days`, `30_days`, or `90_days`)
  and computed expiry timestamp when applicable;
- an optional supersession link for a reviewed correction;
- deterministic duplicate and canonical-key conflict handling.

Persistent and active retained items survive process restarts and are searchable
through the local FTS index. Search updates `last_used_at` and `recall_count` so
the UI can show how often an item has influenced recall. Expiration changes an
item to `expired` and removes it from normal search/context; the record remains
visible to the owner for audit, restoration, or deletion. An approved correction
changes the prior item to `superseded` instead of deleting it.

## Owner and workspace boundary

Every API query is owner-scoped. Workspace-scoped items are associated with a
workspace reference; global items can be recalled from any workspace owned by
that user. Agent `memory_search` calls derive the owner and workspace from the
persisted task instead of trusting model-authored arguments.

Sensitive items remain excluded from ordinary Assistant context previews unless
the owner explicitly opts into sensitive context. Retrieved memory is wrapped
as untrusted evidence before it reaches a model, so saved text cannot become a
policy instruction by itself.

## Per-task recall controls

Every task carries a `memoryMode` (`auto`, `include`, or `suppress`) and the
setting is persisted with the task so it survives queueing and restarts:

- `auto` is the backwards-compatible default and recalls owner/workspace-safe
  memory using the normal context budget;
- `include` records that recall was explicitly requested and keeps the memory
  section available even when a task is otherwise using a reduced context
  profile;
- `suppress` skips the memory search entirely and omits the memory section from
  the model prompt. The task trace records the suppression reason without
  exposing saved memory contents.

The Chat composer exposes this as a per-task selector. The selected default is
stored in user preferences, while the value sent with each task remains visible
in task details and can be audited alongside the `memory_recall` trace.

When memory is included, each search result carries a transient explanation:
matched query terms, the global or same-workspace eligibility reason, and the
ranking factors used by local search. The task inspector renders these details
under “Why memory was recalled?” without sending the explanation back into the
model prompt. The Memory view also renders a dedicated recall explainer for each
search, with the query, eligible-result count, workspace boundary, matched terms,
scope rule, relevance score, and importance. Workspace-scoped records from
another workspace are excluded; only global records and records matching the
active workspace can be recalled.

## User workflow

The Memory view supports:

1. saving a new global or workspace-scoped memory;
2. searching saved memory;
3. reviewing pending suggestions;
4. editing saved content;
5. choosing persistent or time-bounded retention;
6. inspecting provenance (task/session/message ids) and expiry;
7. expanding a recall explanation without exposing memory to a model;
8. restoring an expired item as persistent memory;
9. permanently deleting an item after confirmation.

The HTTP surface is:

- `POST /api/memory` — save a memory item;
- `GET /api/memory/items` — list owner-visible items;
- `POST /api/memory/search` — search saved items;
- `PATCH /api/memory/items/{id}` — edit an item without losing provenance;
- `DELETE /api/memory/items/{id}` — delete the item and its FTS entry;
- `GET /api/memory/review` and `POST /api/memory/review` — approve or reject suggestions.

Exact repeats are idempotent: the existing active item is returned with
`deduplicated=true` and no second record is created. A different value using
the same non-empty canonical key is stored as `pending` and links to the prior
item through `supersedesId`; approval promotes the correction and marks the
older item `superseded`. Explicit corrections can provide `supersedesId` on
`POST /api/memory` when the owner has already reviewed the change.

## Deliberate next steps

This is the durable foundation, not the final memory intelligence. The next
memory slices should add:

- richer visible source/session links and correction history in the UI;
- richer conflict explanations and correction history in the UI;
- export/delete-all workflows;
- measured consolidation from completed conversations, with suggestions kept
  pending until reviewed;
- semantic/hybrid recall only after the owner-controlled lifecycle is stable.

## Provenance and retention controls (implemented)

Memory records now expose source task/session/message ids when available. The
owner can choose `persistent`, `7_days`, `30_days`, or `90_days` retention from
the Memory view or API. When a due timestamp is reached, the record becomes
`expired`, is removed from normal recall and context previews, and remains
available to the owner for audit, restoration as persistent memory, or deletion.

Use `GET /api/memory/items?status=expired` to inspect expired records.
