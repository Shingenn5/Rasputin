import json
import shutil
import time
from pathlib import Path

from backend.core import audit as audit
from backend.core import runtime_store as store
from backend.core.datadir import data_dir

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = data_dir()
MEMORY_JSON = DATA_DIR / "memory.json"
MEMORY_DIR = DATA_DIR / "memory"
MASTER_CONTEXT_DIR = DATA_DIR / "warmind-context"

from backend.models import providers as model_providers
from backend.models import registry as model_registry

async def _chat(model_key, messages, tools=None):
    cfg = model_registry.get_model(model_key) or model_registry.get_model("dry-run")
    if model_key == "dry-run" or not cfg or cfg.get("provider") == "mock":
        user_msg = messages[-1]["content"] if messages else ""
        return f"This is a dry-run response to: {user_msg}"
        
    try:
        text, calls = await model_providers.chat(cfg, messages, 2048, 0.2, tools=tools)
        return text
    except Exception as exc:
        raise RuntimeError(str(exc)) from None

KINDS = {
    "preference",
    "fact",
    "project_note",
    "workflow_lesson",
    "tool_lesson",
    "blocked_pattern",
    "session",
}


def _text(value):
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _parse(value):
    try:
        return json.loads(value)
    except Exception:
        return value


def _normalize_kind(kind):
    if kind == "pref":
        return "preference"
    if kind in {"project", "projectNote"}:
        return "project_note"
    if kind in KINDS:
        return kind
    return "fact"


def init_memory():
    store.init_db()
    store.set_kv("memory_json_imported", True)
    export_markdown()


def queue_turn(task_id, session_id, workspace_id=None, owner_id="admin", connection=None):
    """Durably queue one completed turn for background memory extraction.

    When ``connection`` is supplied, the caller owns the transaction. AgentHub
    uses that path so the assistant message and its extraction job commit
    atomically: a stopped model or process can delay learning, but cannot lose
    the turn that still needs to be processed.
    """
    task_id = str(task_id or "").strip()
    session_id = str(session_id or "").strip()
    owner_id = str(owner_id or "admin").strip() or "admin"
    if not task_id or not session_id:
        raise ValueError("task_id and session_id are required")

    managed_connection = connection is None
    if managed_connection:
        store.init_db()
        connection = store.connect()
    try:
        rows = connection.execute(
            "SELECT id FROM messages WHERE session_id=? AND task_id=? ORDER BY created_at ASC",
            (session_id, task_id),
        ).fetchall()
        source_message_ids = [row["id"] for row in rows]
        stamp = store.now()
        connection.execute(
            """
            INSERT INTO memory_jobs(
              id,owner_id,session_id,task_id,workspace_id,source_message_ids,status,
              attempts,max_attempts,last_error,next_attempt_at,created_at,updated_at
            ) VALUES(?,?,?,?,?,?, 'pending',0,5,'',NULL,?,?)
            ON CONFLICT(task_id) DO UPDATE SET
              owner_id=excluded.owner_id,
              session_id=excluded.session_id,
              workspace_id=excluded.workspace_id,
              source_message_ids=excluded.source_message_ids,
              updated_at=excluded.updated_at
            """,
            (
                store.new_id("memjob"),
                owner_id,
                session_id,
                task_id,
                workspace_id,
                json.dumps(source_message_ids),
                stamp,
                stamp,
            ),
        )
        row = connection.execute(
            "SELECT * FROM memory_jobs WHERE task_id=?",
            (task_id,),
        ).fetchone()
        if managed_connection:
            connection.commit()
        return _public_job(row)
    finally:
        if managed_connection:
            connection.close()


def _public_job(row):
    if not row:
        return None
    data = dict(row)
    data["source_message_ids"] = _parse(data.get("source_message_ids") or "[]")
    return data


def list_jobs(status=None, limit=100, owner_id="admin"):
    store.init_db()
    owner_id = str(owner_id or "admin").strip() or "admin"
    params = [owner_id]
    where = "owner_id=?"
    if status:
        where += " AND status=?"
        params.append(str(status))
    params.append(max(1, min(int(limit), 500)))
    with store._lock, store.connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM memory_jobs WHERE {where} ORDER BY updated_at DESC LIMIT ?",
            params,
        ).fetchall()
    return {"jobs": [_public_job(row) for row in rows]}


def add_item(kind, content, scope="global", workspace_id=None, sensitive=False, status="saved", source_task_id=None, export=True, owner_id="admin"):
    kind = _normalize_kind(kind)
    item_id = store.new_id("mem")
    stamp = store.now()
    with store._lock, store.connect() as conn:
        conn.execute(
            """
            INSERT INTO memory_items(id,kind,scope,workspace_id,content,sensitive,status,source_task_id,created_at,updated_at,owner_id)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (item_id, kind, scope, workspace_id, _text(content), int(bool(sensitive)), status, source_task_id, stamp, stamp, owner_id),
        )
        try:
            conn.execute(
                "INSERT INTO memory_fts(id,kind,content) VALUES(?,?,?)",
                (item_id, kind, _text(content)),
            )
        except Exception:
            pass
        conn.commit()
    audit.log("memory_item_saved" if status == "saved" else "memory_item_suggested", {
        "id": item_id,
        "kind": kind,
        "scope": scope,
        "workspace_id": workspace_id,
        "status": status,
    })
    if status == "saved" and export:
        export_markdown()
    return get_item(item_id, owner_id)


def get_item(item_id, owner_id="admin"):
    store.init_db()
    with store._lock, store.connect() as conn:
        row = conn.execute("SELECT * FROM memory_items WHERE id=? AND owner_id=?", (item_id, owner_id)).fetchone()
    return _public(row)


def _public(row):
    if not row:
        return None
    data = dict(row)
    data["content"] = _parse(data.get("content", ""))
    data["sensitive"] = bool(data.get("sensitive"))
    return data


def list_items(status="saved", limit=200, owner_id="admin"):
    init_memory()
    with store._lock, store.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM memory_items WHERE status=? AND owner_id=? ORDER BY updated_at DESC LIMIT ?",
            (status, owner_id, max(1, min(int(limit), 500))),
        ).fetchall()
    return [_public(row) for row in rows]


def pending_review(owner_id="admin"):
    return {"items": list_items("pending", 200, owner_id)}


def approve_item(item_id, owner_id="admin"):
    stamp = store.now()
    with store._lock, store.connect() as conn:
        row = conn.execute("SELECT * FROM memory_items WHERE id=? AND owner_id=?", (item_id, owner_id)).fetchone()
        if not row:
            raise ValueError("memory item missing")
        conn.execute("UPDATE memory_items SET status='saved', updated_at=? WHERE id=? AND owner_id=?", (stamp, item_id, owner_id))
        conn.commit()
    audit.log("memory_item_approved", {"id": item_id})
    export_markdown()
    return get_item(item_id, owner_id)


def reject_item(item_id, owner_id="admin"):
    stamp = store.now()
    with store._lock, store.connect() as conn:
        row = conn.execute("SELECT * FROM memory_items WHERE id=? AND owner_id=?", (item_id, owner_id)).fetchone()
        if not row:
            raise ValueError("memory item missing")
        conn.execute("UPDATE memory_items SET status='rejected', updated_at=? WHERE id=? AND owner_id=?", (stamp, item_id, owner_id))
        conn.commit()
    audit.log("memory_item_rejected", {"id": item_id})
    return get_item(item_id, owner_id)


def suggest_from_task(task_id, objective, result, workspace_id=None, owner_id="admin"):
    lower = f"{objective}\n{result}".lower()
    if any(word in lower for word in ["prefer", "always", "never", "remember"]):
        return add_item("preference", {
            "source": "task_review",
            "objective": objective[:500],
            "note": result[:1000],
        }, status="pending", source_task_id=task_id, sensitive=True, owner_id=owner_id)
    if result:
        return add_item("workflow_lesson", {
            "source": "task_review",
            "objective": objective[:500],
            "summary": result[:1000],
        }, workspace_id=workspace_id, status="pending", source_task_id=task_id, owner_id=owner_id)
    return None


def search(query, limit=10, owner_id="admin", workspace_id=None):
    init_memory()
    query = str(query or "").strip()
    if not query:
        return {"query": query, "items": []}
    owner_id = str(owner_id or "admin").strip() or "admin"
    workspace_id = str(workspace_id or "").strip()
    with store._lock, store.connect() as conn:
        try:
            rows = conn.execute(
                """
                SELECT m.*, bm25(memory_fts) AS score
                FROM memory_fts
                JOIN memory_items m ON m.id = memory_fts.id
                WHERE memory_fts MATCH ? AND m.status='saved' AND m.owner_id=?
                ORDER BY
                  CASE
                    WHEN m.scope='global' THEN 0
                    WHEN ?!='' AND m.workspace_id=? THEN 0
                    ELSE 1
                  END,
                  m.importance DESC,
                  score
                LIMIT ?
                """,
                (query, owner_id, workspace_id, workspace_id, max(1, min(int(limit), 50))),
            ).fetchall()
        except Exception:
            rows = conn.execute(
                """
                SELECT *, 0 AS score
                FROM memory_items
                WHERE status='saved' AND owner_id=? AND content LIKE ?
                ORDER BY
                  CASE
                    WHEN scope='global' THEN 0
                    WHEN ?!='' AND workspace_id=? THEN 0
                    ELSE 1
                  END,
                  importance DESC,
                  updated_at DESC
                LIMIT ?
                """,
                (owner_id, f"%{query}%", workspace_id, workspace_id, max(1, min(int(limit), 50))),
            ).fetchall()
    items = [_public(row) for row in rows]
    return {"query": query, "items": items, "workspace_id": workspace_id}


def load_memory(owner_id="admin"):
    init_memory()
    items = list_items("saved", 500, owner_id)
    prefs = {}
    facts = []
    sessions = []
    for item in items:
        content = item.get("content")
        if item["kind"] == "preference":
            if isinstance(content, dict) and "key" in content:
                prefs[str(content["key"])] = content.get("value")
            else:
                prefs[item["id"]] = content
        elif item["kind"] == "session":
            sessions.append(content)
        else:
            facts.append(content)
    return {"prefs": prefs, "facts": facts[-250:], "sessions": sessions[-100:]}


def save_memory(data, owner_id="admin"):
    if not isinstance(data, dict):
        return load_memory(owner_id)
    for key, value in (data.get("prefs") or {}).items():
        add_item("preference", {"key": key, "value": value}, owner_id=owner_id)
    for value in data.get("facts") or []:
        add_item("fact", value, owner_id=owner_id)
    for value in data.get("sessions") or []:
        add_item("session", value, owner_id=owner_id)
    return load_memory(owner_id)


def remember(kind, value, owner_id="admin"):
    kind = _normalize_kind(kind)
    if kind == "preference" and isinstance(value, dict):
        for key, pref in value.items():
            add_item("preference", {"key": key, "value": pref}, owner_id=owner_id)
    else:
        add_item(kind, value, owner_id=owner_id)
    return load_memory(owner_id)


def export_markdown():
    store.init_db()
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    (MEMORY_DIR / "projects").mkdir(exist_ok=True)
    with store._lock, store.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM memory_items WHERE status='saved' ORDER BY updated_at DESC LIMIT 500"
        ).fetchall()
    items = [_public(row) for row in rows]

    prefs = [item for item in items if item["kind"] == "preference"]
    facts = [item for item in items if item["kind"] not in {"preference", "project_note", "session"}]
    projects = [item for item in items if item["kind"] == "project_note"]

    user_lines = ["# User Memory", ""]
    for item in prefs:
        user_lines.append(f"- {_text(item['content'])}")
    (MEMORY_DIR / "user.md").write_text("\n".join(user_lines).strip() + "\n", encoding="utf-8")

    memory_lines = ["# Rasputin Memory", ""]
    for item in facts:
        memory_lines.append(f"- **{item['kind']}**: {_text(item['content'])}")
    (MEMORY_DIR / "memory.md").write_text("\n".join(memory_lines).strip() + "\n", encoding="utf-8")

    grouped = {}
    for item in projects:
        grouped.setdefault(item.get("workspace_id") or "global", []).append(item)
    for wid, group in grouped.items():
        lines = [f"# Project Memory: {wid}", ""]
        for item in group:
            lines.append(f"- {_text(item['content'])}")
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in wid)[:80] or "project"
        (MEMORY_DIR / "projects" / f"{safe}.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    export_master_context()


def export_master_context():
    store.init_db()
    MASTER_CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    # read-only-ish export; don't block normal task writes
    with store.connect() as conn:
        sessions = conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT 200"
        ).fetchall()
        messages = conn.execute(
            "SELECT * FROM messages ORDER BY created_at DESC LIMIT 800"
        ).fetchall()
        tasks = conn.execute(
            "SELECT id,session_id,objective,model,mode,status,result,workspace,created_at,updated_at FROM tasks ORDER BY updated_at DESC LIMIT 300"
        ).fetchall()
        memory_rows = conn.execute(
            "SELECT * FROM memory_items WHERE status='saved' ORDER BY updated_at DESC LIMIT 500"
        ).fetchall()

    session_lines = ["# Warmind Context", "", "Local cross-session context for Rasputin.", ""]
    for session in sessions:
        session_lines.extend([
            f"## {session['title']}",
            "",
            f"- Session: `{session['id']}`",
            f"- Model: `{session['model']}`",
            f"- Workspace: `{session['workspace']}`",
            f"- Mode: `{session['mode']}`",
            f"- Status: `{session['status']}`",
            "",
        ])
        related_messages = [m for m in messages if m["session_id"] == session["id"]]
        for message in reversed(related_messages[-20:]):
            session_lines.append(f"**{message['role']}**: {_text(message['content'])}")
            session_lines.append("")

    task_lines = ["# Task And Model Runs", ""]
    for task in tasks:
        task_lines.extend([
            f"## {task['objective'][:160]}",
            "",
            f"- Task: `{task['id']}`",
            f"- Session: `{task['session_id']}`",
            f"- Model: `{task['model']}`",
            f"- Mode: `{task['mode']}`",
            f"- Workspace: `{task['workspace']}`",
            f"- Status: `{task['status']}`",
            "",
        ])
        if task["result"]:
            task_lines.append(_text(task["result"]))
            task_lines.append("")

    memory_lines = ["# Saved Memory", ""]
    for row in memory_rows:
        item = _public(row)
        memory_lines.append(f"- **{item['kind']}** `{item.get('workspace_id') or 'global'}`: {_text(item['content'])}")

    readme_lines = [
        "# Rasputin Master Context",
        "",
        "This folder is local-only and generated from Rasputin's SQLite runtime.",
        "",
        "- `sessions.md`: recent chat context across sessions.",
        "- `tasks.md`: task results grouped by model, mode, and workspace.",
        "- `memory.md`: saved Warmind recall items.",
        "",
        "Do not commit this folder. It lives under ignored local `data/` storage.",
    ]

    (MASTER_CONTEXT_DIR / "README.md").write_text("\n".join(readme_lines).strip() + "\n", encoding="utf-8")
    (MASTER_CONTEXT_DIR / "sessions.md").write_text("\n".join(session_lines).strip() + "\n", encoding="utf-8")
    (MASTER_CONTEXT_DIR / "tasks.md").write_text("\n".join(task_lines).strip() + "\n", encoding="utf-8")
    (MASTER_CONTEXT_DIR / "memory.md").write_text("\n".join(memory_lines).strip() + "\n", encoding="utf-8")


async def consolidate_long_term_memory(session_id, messages, owner_id="admin", workspace_id=None):
    if not messages:
        return
    
    try:
        from backend.models.registry import key_for_role
        from backend.rag import graph as graphify
    except ImportError:
        return
        
    prompt = (
        "You are a long-term memory background worker. "
        "Summarize the following old conversation turns into a dense paragraph of key facts, "
        "user preferences, and system architecture details. "
        "IMPORTANT: To ensure our knowledge graph extracts these entities, write core concepts "
        "in PascalCase (e.g., UserPreference, PythonBackend, LocalDatabase). Mention specific file paths "
        "like `foo.py` if relevant. Do not include chatty filler.\n\n"
    )
    for m in messages:
        prompt += f"{m['role'].upper()}: {m['content']}\n\n"

    try:
        model_key = key_for_role("memory", fallback=key_for_role("summarizer"))
        text = await _chat(model_key, [{"role": "user", "content": prompt}])
        if text:
            add_item(
                "session",
                f"Consolidated Memory for Session {session_id}:\n{text}",
                scope="workspace" if workspace_id else "global",
                workspace_id=workspace_id,
                owner_id=owner_id,
            )
            graphify.build()
            audit.log("memory_consolidation_success", {
                "session": session_id,
                "owner_id": owner_id,
                "workspace_id": workspace_id,
            })
    except Exception as exc:
        audit.log("memory_consolidation_failed", {"session": session_id, "error": str(exc)})

init_memory()
