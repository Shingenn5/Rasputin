import json
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from threading import RLock

from backend.core.datadir import data_dir

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
    DATA_DIR.mkdir(exist_ok=True)
    with _lock, connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runtime_kv (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL,
              updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS auth_sessions (
              id TEXT PRIMARY KEY,
              token_hash TEXT NOT NULL UNIQUE,
              username TEXT NOT NULL,
              role TEXT NOT NULL,
              created_at REAL NOT NULL,
              last_seen REAL NOT NULL,
              expires_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'active',
              workspace TEXT NOT NULL DEFAULT '.',
              model TEXT NOT NULL DEFAULT 'dry-run',
              mode TEXT NOT NULL DEFAULT 'chat',
              skill TEXT NOT NULL DEFAULT 'general',
              summary TEXT NOT NULL DEFAULT '',
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
              id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL,
              task_id TEXT,
              role TEXT NOT NULL,
              content TEXT NOT NULL,
              evicted INTEGER NOT NULL DEFAULT 0,
              created_at REAL NOT NULL,
              FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS eviction_log (
              id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL,
              kind TEXT NOT NULL,
              content TEXT NOT NULL,
              created_at REAL NOT NULL,
              FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tasks (
              id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL,
              parent_id TEXT,
              objective TEXT NOT NULL,
              model TEXT NOT NULL,
              skill TEXT NOT NULL,
              mode TEXT NOT NULL,
              status TEXT NOT NULL,
              progress INTEGER NOT NULL DEFAULT 0,
              result TEXT NOT NULL DEFAULT '',
              workspace TEXT NOT NULL DEFAULT '.',
              permission_snapshot TEXT NOT NULL DEFAULT '{}',
              paused INTEGER NOT NULL DEFAULT 0,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL,
              FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS task_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              task_id TEXT NOT NULL,
              kind TEXT NOT NULL,
              detail TEXT NOT NULL DEFAULT '{}',
              created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS inbox_events (
              id TEXT PRIMARY KEY,
              owner_id TEXT NOT NULL,
              kind TEXT NOT NULL,
              severity TEXT NOT NULL DEFAULT 'info',
              title TEXT NOT NULL,
              body TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL DEFAULT 'unread',
              task_id TEXT,
              action_type TEXT NOT NULL DEFAULT '',
              action_payload TEXT NOT NULL DEFAULT '{}',
              created_at REAL NOT NULL,
              read_at REAL,
              archived_at REAL
            );

            CREATE TABLE IF NOT EXISTS connectors (
              id TEXT PRIMARY KEY,
              owner_id TEXT NOT NULL,
              provider TEXT NOT NULL,
              display_name TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'configured',
              config TEXT NOT NULL DEFAULT '{}',
              credentials TEXT NOT NULL DEFAULT '{}',
              last_tested_at REAL,
              last_error TEXT NOT NULL DEFAULT '',
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tool_calls (
              id TEXT PRIMARY KEY,
              task_id TEXT,
              name TEXT NOT NULL,
              risk TEXT NOT NULL DEFAULT 'safe',
              status TEXT NOT NULL DEFAULT 'created',
              args_redacted TEXT NOT NULL DEFAULT '{}',
              result_redacted TEXT NOT NULL DEFAULT '{}',
              approval_id TEXT,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS approvals (
              id TEXT PRIMARY KEY,
              code TEXT NOT NULL UNIQUE,
              task_id TEXT,
              tool_call_id TEXT,
              action_type TEXT NOT NULL,
              risk_level TEXT NOT NULL,
              workspace TEXT NOT NULL DEFAULT '.',
              summary TEXT NOT NULL,
              redacted_detail TEXT NOT NULL DEFAULT '{}',
              status TEXT NOT NULL DEFAULT 'pending',
              expires_at REAL NOT NULL,
              created_at REAL NOT NULL,
              decided_at REAL,
              executed_at REAL,
              decision_source TEXT,
              decision_note TEXT
            );

            CREATE TABLE IF NOT EXISTS outputs (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              kind TEXT NOT NULL,
              title TEXT NOT NULL,
              content TEXT NOT NULL,
              filename TEXT NOT NULL DEFAULT '',
              mime_type TEXT NOT NULL DEFAULT 'text/plain',
              size_bytes INTEGER NOT NULL DEFAULT 0,
              pinned INTEGER NOT NULL DEFAULT 0,
              created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agent_traces (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              task_id TEXT NOT NULL,
              kind TEXT NOT NULL,
              detail TEXT NOT NULL DEFAULT '{}',
              created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memory_items (
              id TEXT PRIMARY KEY,
              kind TEXT NOT NULL,
              scope TEXT NOT NULL DEFAULT 'global',
              workspace_id TEXT,
              content TEXT NOT NULL,
              sensitive INTEGER NOT NULL DEFAULT 0,
              status TEXT NOT NULL DEFAULT 'saved',
              source_task_id TEXT,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memory_jobs (
              id TEXT PRIMARY KEY,
              owner_id TEXT NOT NULL,
              session_id TEXT NOT NULL,
              task_id TEXT NOT NULL UNIQUE,
              workspace_id TEXT,
              source_message_ids TEXT NOT NULL DEFAULT '[]',
              status TEXT NOT NULL DEFAULT 'pending',
              attempts INTEGER NOT NULL DEFAULT 0,
              max_attempts INTEGER NOT NULL DEFAULT 5,
              last_error TEXT NOT NULL DEFAULT '',
              next_attempt_at REAL,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL,
              completed_at REAL,
              FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE,
              FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS skills (
              name TEXT PRIMARY KEY,
              description TEXT NOT NULL DEFAULT '',
              metadata TEXT NOT NULL DEFAULT '{}',
              enabled INTEGER NOT NULL DEFAULT 1,
              builtin INTEGER NOT NULL DEFAULT 0,
              path TEXT NOT NULL DEFAULT '',
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS schedules (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              prompt TEXT NOT NULL,
              enabled INTEGER NOT NULL DEFAULT 0,
              interval_seconds INTEGER NOT NULL DEFAULT 0,
              next_run_at REAL,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL
            );
            """
        )
        session_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()
        }
        if "folder" not in session_columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN folder TEXT NOT NULL DEFAULT ''")
        if "owner_id" not in session_columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN owner_id TEXT NOT NULL DEFAULT ''")

        task_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
        }
        if "owner_id" not in task_columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id TEXT NOT NULL DEFAULT ''")
        task_migrations = {
            "reasoning": "TEXT NOT NULL DEFAULT 'auto'",
            "subagents": "INTEGER NOT NULL DEFAULT 0",
            "priority": "INTEGER NOT NULL DEFAULT 0",
            "queue_order": "REAL NOT NULL DEFAULT 0",
            "scheduled_for": "REAL",
            "started_at": "REAL",
            "completed_at": "REAL",
            "attempt_count": "INTEGER NOT NULL DEFAULT 0",
            "max_attempts": "INTEGER NOT NULL DEFAULT 1",
            "source_task_id": "TEXT",
        }
        for name, definition in task_migrations.items():
            if name not in task_columns:
                conn.execute(f"ALTER TABLE tasks ADD COLUMN {name} {definition}")

        approval_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(approvals)").fetchall()
        }
        if "owner_id" not in approval_columns:
            conn.execute("ALTER TABLE approvals ADD COLUMN owner_id TEXT NOT NULL DEFAULT ''")

        output_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(outputs)").fetchall()
        }
        output_migrations = {
            "filename": "TEXT NOT NULL DEFAULT ''",
            "mime_type": "TEXT NOT NULL DEFAULT 'text/plain'",
            "size_bytes": "INTEGER NOT NULL DEFAULT 0",
            "pinned": "INTEGER NOT NULL DEFAULT 0",
        }
        for name, definition in output_migrations.items():
            if name not in output_columns:
                conn.execute(f"ALTER TABLE outputs ADD COLUMN {name} {definition}")

        memory_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(memory_items)").fetchall()
        }
        if "owner_id" not in memory_columns:
            conn.execute("ALTER TABLE memory_items ADD COLUMN owner_id TEXT NOT NULL DEFAULT ''")
        memory_migrations = {
            "canonical_key": "TEXT NOT NULL DEFAULT ''",
            "confidence": "REAL NOT NULL DEFAULT 0.5",
            "importance": "REAL NOT NULL DEFAULT 0.5",
            "source_session_id": "TEXT",
            "source_message_ids": "TEXT NOT NULL DEFAULT '[]'",
            "supersedes_id": "TEXT",
            "content_hash": "TEXT NOT NULL DEFAULT ''",
            "last_used_at": "REAL",
            "recall_count": "INTEGER NOT NULL DEFAULT 0",
        }
        for name, definition in memory_migrations.items():
            if name not in memory_columns:
                conn.execute(f"ALTER TABLE memory_items ADD COLUMN {name} {definition}")
            
        messages_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(messages)").fetchall()
        }
        if "evicted" not in messages_columns:
            conn.execute("ALTER TABLE messages ADD COLUMN evicted INTEGER NOT NULL DEFAULT 0")
            
        skills_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(skills)").fetchall()
        }
        if "content" not in skills_columns:
            conn.execute("ALTER TABLE skills ADD COLUMN content TEXT NOT NULL DEFAULT ''")
            
        if "folder_id" in session_columns:
            old_table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='chat_folders'"
            ).fetchone()
            if old_table:
                old_names = [
                    str(row["name"])
                    for row in conn.execute("SELECT name FROM chat_folders WHERE name IS NOT NULL AND name!=''").fetchall()
                ]
                if old_names:
                    kv = conn.execute("SELECT value FROM runtime_kv WHERE key=?", ("chat_folder_registry",)).fetchone()
                    registry = _loads(kv["value"], []) if kv else []
                    if not isinstance(registry, list):
                        registry = []
                    seen = {str(item).casefold() for item in registry}
                    for name in old_names:
                        if name.casefold() not in seen:
                            registry.append(name)
                            seen.add(name.casefold())
                    conn.execute(
                        "INSERT INTO runtime_kv(key,value,updated_at) VALUES(?,?,?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                        ("chat_folder_registry", _json(registry), now()),
                    )
                conn.execute(
                    """
                    UPDATE sessions
                    SET folder=(
                      SELECT name FROM chat_folders WHERE chat_folders.id=sessions.folder_id
                    )
                    WHERE (folder IS NULL OR folder='') AND folder_id IS NOT NULL AND folder_id!=''
                    """
                )
                conn.execute("DROP TABLE IF EXISTS chat_folders")
        legacy_output_table = "arti" + "facts"
        existing = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (legacy_output_table,),
        ).fetchone()
        if existing:
            conn.execute(
                f"""
                INSERT OR IGNORE INTO outputs(id,task_id,kind,title,content,created_at)
                SELECT id,task_id,kind,title,content,created_at FROM {legacy_output_table}
                """
            )
        try:
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(id UNINDEXED, kind, content)"
            )
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS session_fts USING fts5(id UNINDEXED, session_id UNINDEXED, task_id UNINDEXED, content)"
            )
        except sqlite3.OperationalError:
            pass
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_owner_updated ON sessions(owner_id, updated_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_owner_created ON tasks(owner_id, created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_owner_queue ON tasks(owner_id, status, priority DESC, queue_order ASC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_inbox_owner_status ON inbox_events(owner_id, status, created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_connectors_owner ON connectors(owner_id, provider, updated_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_token ON auth_sessions(token_hash)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(username)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_owner_status ON memory_items(owner_id, status, updated_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_owner_key ON memory_items(owner_id, canonical_key)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_jobs_ready ON memory_jobs(status, next_attempt_at, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_jobs_owner ON memory_jobs(owner_id, status, updated_at DESC)")
        conn.commit()


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
