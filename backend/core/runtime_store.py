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

        approval_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(approvals)").fetchall()
        }
        if "owner_id" not in approval_columns:
            conn.execute("ALTER TABLE approvals ADD COLUMN owner_id TEXT NOT NULL DEFAULT ''")

        memory_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(memory_items)").fetchall()
        }
        if "owner_id" not in memory_columns:
            conn.execute("ALTER TABLE memory_items ADD COLUMN owner_id TEXT NOT NULL DEFAULT ''")
            
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
        conn.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_token ON auth_sessions(token_hash)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(username)")
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
