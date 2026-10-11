"""Shared SQLite persistence for Rasputin's owner-scoped runtime state.

This module owns connections and low-level storage helpers used across API,
agent, workspace, approval, memory, and model-runtime features. Callers should
use the feature-specific stores where they exist instead of issuing SQL here.
Tests must redirect it with `RASPUTIN_DATA_DIR` before importing the backend.
"""

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from threading import RLock

from backend.core.datadir import data_dir
from backend.core.runtime_schema import initialize_schema

ROOT = Path(__file__).resolve().parents[1]
# RASPUTIN_DATA_DIR redirects all runtime storage (sqlite + kv). The test
# suite sets it to a temp dir so test runs stop polluting the live dev data
# (each smoke run used to permanently register its fixture workspaces,
# sessions, and tasks in backend/data/rasputin.db).
DATA_DIR = data_dir()
DB_FILE = DATA_DIR / "rasputin.db"

_lock = RLock()


def now():
    return time.time()


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _json(value):
    return json.dumps(value if value is not None else {}, ensure_ascii=True)


def _loads(value, fallback=None):
    if value is None:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def connect():
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_FILE, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create and migrate the runtime schema under the shared store lock."""
    DATA_DIR.mkdir(exist_ok=True)
    with _lock, connect() as conn:
        initialize_schema(conn, now=now, decode=_loads, encode=_json)


def claim_legacy_ownership(username):
    """Assign pre-multi-user records to the appliance's original administrator."""
    owner = str(username or "admin").strip() or "admin"
    init_db()
    with _lock, connect() as conn:
        conn.execute("UPDATE sessions SET owner_id=? WHERE owner_id IS NULL OR owner_id=''", (owner,))
        conn.execute("UPDATE tasks SET owner_id=? WHERE owner_id IS NULL OR owner_id=''", (owner,))
        conn.execute("UPDATE approvals SET owner_id=? WHERE owner_id IS NULL OR owner_id=''", (owner,))
        conn.execute("UPDATE memory_items SET owner_id=? WHERE owner_id IS NULL OR owner_id=''", (owner,))
        conn.commit()


def get_kv(key, fallback=None):
    init_db()
    with _lock, connect() as conn:
        row = conn.execute("SELECT value FROM runtime_kv WHERE key=?", (key,)).fetchone()
    return _loads(row["value"], fallback) if row else fallback


def set_kv(key, value):
    init_db()
    with _lock, connect() as conn:
        conn.execute(
            "INSERT INTO runtime_kv(key,value,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, _json(value), now()),
        )
        conn.commit()
    return value


def row_dict(row):
    return dict(row) if row else None


def create_inbox_event(owner_id, kind, title, body="", severity="info", task_id=None, action_type="", action_payload=None):
    init_db()
    event_id = new_id("inbox")
    stamp = now()
    with _lock, connect() as conn:
        conn.execute(
            """
            INSERT INTO inbox_events(
              id,owner_id,kind,severity,title,body,status,task_id,action_type,action_payload,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                event_id,
                str(owner_id or "admin"),
                str(kind or "system"),
                str(severity or "info"),
                str(title or "Rasputin activity"),
                str(body or ""),
                "unread",
                task_id,
                str(action_type or ""),
                _json(action_payload or {}),
                stamp,
            ),
        )
        conn.commit()
    return event_id


def list_inbox_events(owner_id, status=None, limit=100):
    init_db()
    args = [str(owner_id or "admin")]
    where = "owner_id=? AND status!='archived'"
    if status in {"unread", "read", "archived"}:
        where = "owner_id=? AND status=?"
        args.append(status)
    args.append(max(1, min(int(limit or 100), 500)))
    with _lock, connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM inbox_events WHERE {where} ORDER BY created_at DESC LIMIT ?",
            tuple(args),
        ).fetchall()
    events = []
    for row in rows:
        item = dict(row)
        item["action_payload"] = _loads(item.get("action_payload"), {})
        events.append(item)
    return events


def update_inbox_event(owner_id, event_id, status):
    if status not in {"unread", "read", "archived"}:
        raise ValueError("invalid inbox status")
    stamp = now()
    read_at = stamp if status == "read" else None
    archived_at = stamp if status == "archived" else None
    with _lock, connect() as conn:
        cursor = conn.execute(
            """
            UPDATE inbox_events
            SET status=?, read_at=COALESCE(?,read_at), archived_at=COALESCE(?,archived_at)
            WHERE id=? AND owner_id=?
            """,
            (status, read_at, archived_at, event_id, str(owner_id or "admin")),
        )
        conn.commit()
    return cursor.rowcount > 0


def mark_all_inbox_read(owner_id):
    stamp = now()
    with _lock, connect() as conn:
        cursor = conn.execute(
            "UPDATE inbox_events SET status='read', read_at=? WHERE owner_id=? AND status='unread'",
            (stamp, str(owner_id or "admin")),
        )
        conn.commit()
    return cursor.rowcount


def universal_search(owner_id, query, limit=30):
    """Search a user's chats, tasks, and generated outputs without crossing account boundaries."""
    init_db()
    needle = str(query or "").strip()
    if not needle:
        return {"query": "", "results": [], "count": 0}
    cap = max(1, min(int(limit or 30), 100))
    pattern = f"%{needle.replace('%', r'\%').replace('_', r'\_')}%"
    owner = str(owner_id or "admin")
    with _lock, connect() as conn:
        messages = conn.execute(
            """
            SELECT m.id,m.session_id,m.task_id,m.content,m.created_at,s.title
            FROM messages m JOIN sessions s ON s.id=m.session_id
            WHERE s.owner_id=? AND m.evicted=0 AND m.content LIKE ? ESCAPE '\\'
            ORDER BY m.created_at DESC LIMIT ?
            """,
            (owner, pattern, cap),
        ).fetchall()
        tasks = conn.execute(
            """
            SELECT id,session_id,objective,result,status,created_at
            FROM tasks
            WHERE owner_id=? AND (objective LIKE ? ESCAPE '\\' OR result LIKE ? ESCAPE '\\')
            ORDER BY created_at DESC LIMIT ?
            """,
            (owner, pattern, pattern, cap),
        ).fetchall()
        outputs = conn.execute(
            """
            SELECT o.id,o.task_id,o.kind,o.title,o.content,o.created_at,t.session_id
            FROM outputs o JOIN tasks t ON t.id=o.task_id
            WHERE t.owner_id=? AND (o.title LIKE ? ESCAPE '\\' OR o.content LIKE ? ESCAPE '\\')
            ORDER BY o.created_at DESC LIMIT ?
            """,
            (owner, pattern, pattern, cap),
        ).fetchall()
    results = [
        {
            "type": "chat",
            "id": row["id"],
            "title": row["title"] or "Chat message",
            "snippet": row["content"][:280],
            "sessionId": row["session_id"],
            "taskId": row["task_id"],
            "createdAt": row["created_at"],
        }
        for row in messages
    ]
    results.extend(
        {
            "type": "task",
            "id": row["id"],
            "title": row["objective"][:140],
            "snippet": (row["result"] or row["objective"])[:280],
            "sessionId": row["session_id"],
            "taskId": row["id"],
            "status": row["status"],
            "createdAt": row["created_at"],
        }
        for row in tasks
    )
    results.extend(
        {
            "type": "artifact",
            "id": row["id"],
            "title": row["title"],
            "snippet": row["content"][:280],
            "sessionId": row["session_id"],
            "taskId": row["task_id"],
            "kind": row["kind"],
            "createdAt": row["created_at"],
        }
        for row in outputs
    )
    results.sort(key=lambda item: float(item.get("createdAt") or 0), reverse=True)
    results = results[:cap]
    return {"query": needle, "results": results, "count": len(results)}


def list_artifacts(owner_id, query="", kind="", pinned=False, limit=200):
    init_db()
    where = ["t.owner_id=?"]
    args = [str(owner_id or "admin")]
    if query:
        where.append("(o.title LIKE ? OR o.content LIKE ?)")
        pattern = f"%{str(query).strip()}%"
        args.extend([pattern, pattern])
    if kind:
        where.append("o.kind=?")
        args.append(str(kind))
    if pinned:
        where.append("o.pinned=1")
    args.append(max(1, min(int(limit or 200), 500)))
    with _lock, connect() as conn:
        rows = conn.execute(
            f"""
            SELECT o.id,o.task_id,o.kind,o.title,o.content,o.filename,o.mime_type,o.size_bytes,o.pinned,o.created_at,
                   t.objective,t.session_id,t.workspace,t.status
            FROM outputs o JOIN tasks t ON t.id=o.task_id
            WHERE {' AND '.join(where)}
            ORDER BY o.pinned DESC,o.created_at DESC LIMIT ?
            """,
            tuple(args),
        ).fetchall()
    return [
        {
            **dict(row),
            "preview": row["content"][:360],
            "content": row["content"],
            "size_bytes": row["size_bytes"] or len(row["content"].encode("utf-8")),
        }
        for row in rows
    ]


def get_artifact(owner_id, artifact_id):
    with _lock, connect() as conn:
        row = conn.execute(
            """
            SELECT o.id,o.task_id,o.kind,o.title,o.content,o.filename,o.mime_type,o.size_bytes,o.pinned,o.created_at,
                   t.objective,t.session_id,t.workspace,t.status
            FROM outputs o JOIN tasks t ON t.id=o.task_id
            WHERE o.id=? AND t.owner_id=?
            """,
            (artifact_id, str(owner_id or "admin")),
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["preview"] = item["content"][:360]
    item["size_bytes"] = item["size_bytes"] or len(item["content"].encode("utf-8"))
    return item


def set_artifact_pinned(owner_id, artifact_id, pinned):
    with _lock, connect() as conn:
        cursor = conn.execute(
            """
            UPDATE outputs SET pinned=?
            WHERE id=? AND task_id IN (SELECT id FROM tasks WHERE owner_id=?)
            """,
            (1 if pinned else 0, artifact_id, str(owner_id or "admin")),
        )
        conn.commit()
    return cursor.rowcount > 0


_ASSISTANT_PLAN_STATUSES = {"preview", "approved", "rejected"}


def _public_assistant_plan(row):
    if not row:
        return None
    item = dict(row)
    item["plan"] = _loads(item.pop("plan_json", "{}"), {})
    return item


def create_assistant_plan(owner_id, plan, plan_id=None):
    """Persist a preview without starting a task, model, or host operation."""

    init_db()
    owner = str(owner_id or "admin").strip() or "admin"
    identifier = str(plan_id or new_id("aplan"))
    stamp = now()
    with _lock, connect() as conn:
        conn.execute(
            """
            INSERT INTO assistant_plans(
              id,owner_id,status,plan_json,created_at,updated_at,approved_at,approved_by,review_note
            ) VALUES(?,?, 'preview', ?, ?, ?, NULL, NULL, '')
            """,
            (identifier, owner, _json(plan or {}), stamp, stamp),
        )
        row = conn.execute("SELECT * FROM assistant_plans WHERE id=? AND owner_id=?", (identifier, owner)).fetchone()
        conn.commit()
    return _public_assistant_plan(row)


def get_assistant_plan(owner_id, plan_id):
    init_db()
    owner = str(owner_id or "admin").strip() or "admin"
    with _lock, connect() as conn:
        row = conn.execute(
            "SELECT * FROM assistant_plans WHERE id=? AND owner_id=?",
            (str(plan_id), owner),
        ).fetchone()
    return _public_assistant_plan(row)


def list_assistant_plans(owner_id, limit=50):
    init_db()
    owner = str(owner_id or "admin").strip() or "admin"
    cap = max(1, min(int(limit or 50), 200))
    with _lock, connect() as conn:
        rows = conn.execute(
            "SELECT * FROM assistant_plans WHERE owner_id=? ORDER BY updated_at DESC LIMIT ?",
            (owner, cap),
        ).fetchall()
    return [_public_assistant_plan(row) for row in rows]


def transition_assistant_plan(owner_id, plan_id, status, actor=None, review_note=""):
    """Move a plan through the review ledger; execution is intentionally absent."""

    if status not in _ASSISTANT_PLAN_STATUSES:
        raise ValueError("invalid assistant plan status")
    init_db()
    owner = str(owner_id or "admin").strip() or "admin"
    identifier = str(plan_id)
    stamp = now()
    approved_at = stamp if status == "approved" else None
    approved_by = str(actor or owner) if status == "approved" else None
    note = str(review_note or "").strip()[:500]
    with _lock, connect() as conn:
        current = conn.execute(
            "SELECT * FROM assistant_plans WHERE id=? AND owner_id=?",
            (identifier, owner),
        ).fetchone()
        if not current:
            return None
        if current["status"] != "preview":
            raise ValueError("assistant plan has already been reviewed")
        conn.execute(
            """
            UPDATE assistant_plans
            SET status=?, updated_at=?, approved_at=?, approved_by=?, review_note=?
            WHERE id=? AND owner_id=? AND status='preview'
            """,
            (status, stamp, approved_at, approved_by, note, identifier, owner),
        )
        row = conn.execute("SELECT * FROM assistant_plans WHERE id=? AND owner_id=?", (identifier, owner)).fetchone()
        conn.commit()
    return _public_assistant_plan(row)


_ASSISTANT_CONTEXT_CAPSULE_STATUSES = {"preview", "approved", "rejected", "expired"}


def _context_capsule_status(row):
    status = str(row["status"] or "preview")
    if status in {"preview", "approved"} and float(row["expires_at"] or 0) <= now():
        return "expired"
    return status


def _public_assistant_context_capsule(row, include_context=True):
    if not row:
        return None
    item = dict(row)
    item["status"] = _context_capsule_status(row)
    if include_context:
        item["context"] = _loads(item.pop("context_json", "{}"), {})
    else:
        item.pop("context_json", None)
    item["provenance"] = _loads(item.pop("provenance_json", "{}"), {})
    return item


def create_assistant_context_capsule(
    owner_id,
    objective,
    workspace_ref,
    context,
    provenance=None,
    expires_in_seconds=3600,
    capsule_id=None,
):
    """Persist a bounded context snapshot for explicit review before orchestration."""

    init_db()
    owner = str(owner_id or "admin").strip() or "admin"
    identifier = str(capsule_id or new_id("ctx"))
    clean_objective = str(objective or "Shared context").strip()[:1200] or "Shared context"
    clean_workspace = str(workspace_ref or ".").strip()[:500] or "."
    ttl = max(300, min(int(expires_in_seconds or 3600), 604800))
    stamp = now()
    expires_at = stamp + ttl
    with _lock, connect() as conn:
        conn.execute(
            """
            INSERT INTO assistant_context_capsules(
              id,owner_id,status,objective,workspace_ref,context_json,provenance_json,
              created_at,updated_at,expires_at,approved_at,approved_by,review_note
            ) VALUES(?,?, 'preview', ?, ?, ?, ?, ?, ?, ?, NULL, NULL, '')
            """,
            (
                identifier,
                owner,
                clean_objective,
                clean_workspace,
                _json(context or {}),
                _json(provenance or {}),
                stamp,
                stamp,
                expires_at,
            ),
        )
        row = conn.execute(
            "SELECT * FROM assistant_context_capsules WHERE id=? AND owner_id=?",
            (identifier, owner),
        ).fetchone()
        conn.commit()
    return _public_assistant_context_capsule(row)


def get_assistant_context_capsule(owner_id, capsule_id):
    init_db()
    owner = str(owner_id or "admin").strip() or "admin"
    with _lock, connect() as conn:
        row = conn.execute(
            "SELECT * FROM assistant_context_capsules WHERE id=? AND owner_id=?",
            (str(capsule_id), owner),
        ).fetchone()
    return _public_assistant_context_capsule(row)


def list_assistant_context_capsules(owner_id, limit=50):
    init_db()
    owner = str(owner_id or "admin").strip() or "admin"
    cap = max(1, min(int(limit or 50), 200))
    with _lock, connect() as conn:
        rows = conn.execute(
            "SELECT * FROM assistant_context_capsules WHERE owner_id=? ORDER BY updated_at DESC LIMIT ?",
            (owner, cap),
        ).fetchall()
    return [_public_assistant_context_capsule(row, include_context=False) for row in rows]


def transition_assistant_context_capsule(owner_id, capsule_id, status, actor=None, review_note=""):
    """Approve or reject a capsule without starting a task, model, or host action."""

    if status not in {"approved", "rejected"}:
        raise ValueError("invalid assistant context capsule status")
    init_db()
    owner = str(owner_id or "admin").strip() or "admin"
    identifier = str(capsule_id)
    stamp = now()
    note = str(review_note or "").strip()[:500]
    with _lock, connect() as conn:
        current = conn.execute(
            "SELECT * FROM assistant_context_capsules WHERE id=? AND owner_id=?",
            (identifier, owner),
        ).fetchone()
        if not current:
            return None
        if _context_capsule_status(current) == "expired":
            raise ValueError("assistant context capsule has expired")
        if current["status"] != "preview":
            raise ValueError("assistant context capsule has already been reviewed")
        conn.execute(
            """
            UPDATE assistant_context_capsules
            SET status=?, updated_at=?, approved_at=?, approved_by=?, review_note=?
            WHERE id=? AND owner_id=? AND status='preview'
            """,
            (
                status,
                stamp,
                stamp if status == "approved" else None,
                str(actor or owner) if status == "approved" else None,
                note,
                identifier,
                owner,
            ),
        )
        row = conn.execute(
            "SELECT * FROM assistant_context_capsules WHERE id=? AND owner_id=?",
            (identifier, owner),
        ).fetchone()
        conn.commit()
    return _public_assistant_context_capsule(row)


def _public_assistant_model_pack(row):
    if not row:
        return None
    item = dict(row)
    item["pack"] = _loads(item.pop("pack_json", "{}"), {})
    return item


def upsert_assistant_model_pack(owner_id, pack_id, version, pack):
    """Store a declarative model fleet; this never mutates the live registry."""

    init_db()
    owner = str(owner_id or "admin").strip() or "admin"
    identifier = str(pack_id or "").strip()
    if not identifier:
        raise ValueError("model pack id is required")
    clean_version = str(version or "0.1").strip()[:40] or "0.1"
    stamp = now()
    with _lock, connect() as conn:
        conn.execute(
            """
            INSERT INTO assistant_model_packs(owner_id,pack_id,version,pack_json,created_at,updated_at)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(owner_id,pack_id) DO UPDATE SET
              version=excluded.version,
              pack_json=excluded.pack_json,
              updated_at=excluded.updated_at
            """,
            (owner, identifier, clean_version, _json(pack or {}), stamp, stamp),
        )
        row = conn.execute(
            "SELECT * FROM assistant_model_packs WHERE owner_id=? AND pack_id=?",
            (owner, identifier),
        ).fetchone()
        conn.commit()
    return _public_assistant_model_pack(row)


def get_assistant_model_pack(owner_id, pack_id):
    init_db()
    owner = str(owner_id or "admin").strip() or "admin"
    with _lock, connect() as conn:
        row = conn.execute(
            "SELECT * FROM assistant_model_packs WHERE owner_id=? AND pack_id=?",
            (owner, str(pack_id)),
        ).fetchone()
    return _public_assistant_model_pack(row)


def list_assistant_model_packs(owner_id, limit=50):
    init_db()
    owner = str(owner_id or "admin").strip() or "admin"
    cap = max(1, min(int(limit or 50), 200))
    with _lock, connect() as conn:
        rows = conn.execute(
            "SELECT * FROM assistant_model_packs WHERE owner_id=? ORDER BY updated_at DESC LIMIT ?",
            (owner, cap),
        ).fetchall()
    return [_public_assistant_model_pack(row) for row in rows]


def delete_assistant_model_pack(owner_id, pack_id):
    init_db()
    owner = str(owner_id or "admin").strip() or "admin"
    with _lock, connect() as conn:
        cursor = conn.execute(
            "DELETE FROM assistant_model_packs WHERE owner_id=? AND pack_id=?",
            (owner, str(pack_id)),
        )
        conn.commit()
    return cursor.rowcount > 0


def _public_assistant_handoff(row):
    if not row:
        return None
    item = dict(row)
    item["request"] = _loads(item.pop("request_json", "{}"), {})
    return item


def find_assistant_handoff(owner_id, plan_id, operation):
    init_db()
    owner = str(owner_id or "admin").strip() or "admin"
    with _lock, connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM assistant_handoffs
            WHERE owner_id=? AND plan_id=? AND operation=?
            ORDER BY created_at DESC LIMIT 1
            """,
            (owner, str(plan_id), str(operation)),
        ).fetchone()
    return _public_assistant_handoff(row)


def create_assistant_handoff(owner_id, plan_id, operation, approval_id, request, status="pending_approval"):
    init_db()
    owner = str(owner_id or "admin").strip() or "admin"
    handoff_id = new_id("handoff")
    stamp = now()
    with _lock, connect() as conn:
        existing = conn.execute(
            """
            SELECT * FROM assistant_handoffs
            WHERE owner_id=? AND plan_id=? AND operation=?
              AND status NOT IN ('denied', 'expired')
            ORDER BY created_at DESC LIMIT 1
            """,
            (owner, str(plan_id), str(operation)),
        ).fetchone()
        if existing:
            return _public_assistant_handoff(existing)
        conn.execute(
            """
            INSERT INTO assistant_handoffs(
              id,owner_id,plan_id,operation,status,approval_id,request_json,created_at,updated_at
            ) VALUES(?,?,?,?, ?, ?, ?, ?, ?)
            """,
            (handoff_id, owner, str(plan_id), str(operation), str(status or "pending_approval"), approval_id, _json(request or {}), stamp, stamp),
        )
        row = conn.execute("SELECT * FROM assistant_handoffs WHERE id=? AND owner_id=?", (handoff_id, owner)).fetchone()
        conn.commit()
    return _public_assistant_handoff(row)


def get_assistant_handoff(owner_id, handoff_id):
    init_db()
    owner = str(owner_id or "admin").strip() or "admin"
    with _lock, connect() as conn:
        row = conn.execute(
            "SELECT * FROM assistant_handoffs WHERE id=? AND owner_id=?",
            (str(handoff_id), owner),
        ).fetchone()
    return _public_assistant_handoff(row)


def list_assistant_handoffs(owner_id, limit=50):
    init_db()
    owner = str(owner_id or "admin").strip() or "admin"
    cap = max(1, min(int(limit or 50), 200))
    with _lock, connect() as conn:
        rows = conn.execute(
            "SELECT * FROM assistant_handoffs WHERE owner_id=? ORDER BY updated_at DESC LIMIT ?",
            (owner, cap),
        ).fetchall()
    return [_public_assistant_handoff(row) for row in rows]


_ASSISTANT_HANDOFF_STATUSES = {"pending_approval", "ready_for_broker", "completed", "failed", "denied", "expired"}


def transition_assistant_handoff(owner_id, handoff_id, status, request=None):
    """Advance a handoff ledger record without executing the requested operation."""

    if status not in _ASSISTANT_HANDOFF_STATUSES:
        raise ValueError("invalid assistant handoff status")
    init_db()
    owner = str(owner_id or "admin").strip() or "admin"
    identifier = str(handoff_id)
    stamp = now()
    with _lock, connect() as conn:
        current = conn.execute(
            "SELECT * FROM assistant_handoffs WHERE id=? AND owner_id=?",
            (identifier, owner),
        ).fetchone()
        if not current:
            return None
        if current["status"] in {"denied", "expired", "completed"} and status == "ready_for_broker":
            raise ValueError("assistant handoff is no longer active")
        request_json = _json(request) if request is not None else current["request_json"]
        conn.execute(
            """
            UPDATE assistant_handoffs
            SET status=?, request_json=?, updated_at=?
            WHERE id=? AND owner_id=?
            """,
            (status, request_json, stamp, identifier, owner),
        )
        row = conn.execute(
            "SELECT * FROM assistant_handoffs WHERE id=? AND owner_id=?",
            (identifier, owner),
        ).fetchone()
        conn.commit()
    return _public_assistant_handoff(row)
