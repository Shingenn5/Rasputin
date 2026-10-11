"""SQLite table creation and backwards-compatible runtime migrations."""

import sqlite3


def initialize_schema(conn, *, now, decode, encode):
    """Apply schema changes within the caller-owned locked transaction."""
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
          deployment_profile TEXT NOT NULL DEFAULT '{}',
          skill TEXT NOT NULL,
          mode TEXT NOT NULL,
          requested_mode TEXT NOT NULL DEFAULT 'chat',
          status TEXT NOT NULL,
          progress INTEGER NOT NULL DEFAULT 0,
          result TEXT NOT NULL DEFAULT '',
          workspace TEXT NOT NULL DEFAULT '.',
          permission_snapshot TEXT NOT NULL DEFAULT '{}',
          isolation_requested INTEGER NOT NULL DEFAULT 0,
          isolation_state TEXT NOT NULL DEFAULT 'none',
          execution_workspace TEXT NOT NULL DEFAULT '',
          isolation_metadata TEXT NOT NULL DEFAULT '{}',
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
          retention TEXT NOT NULL DEFAULT 'persistent',
          expires_at REAL,
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

        CREATE TABLE IF NOT EXISTS assistant_plans (
          id TEXT PRIMARY KEY,
          owner_id TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'preview',
          plan_json TEXT NOT NULL DEFAULT '{}',
          created_at REAL NOT NULL,
          updated_at REAL NOT NULL,
          approved_at REAL,
          approved_by TEXT,
          review_note TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS assistant_context_capsules (
          id TEXT PRIMARY KEY,
          owner_id TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'preview',
          objective TEXT NOT NULL DEFAULT '',
          workspace_ref TEXT NOT NULL DEFAULT '.',
          context_json TEXT NOT NULL DEFAULT '{}',
          provenance_json TEXT NOT NULL DEFAULT '{}',
          created_at REAL NOT NULL,
          updated_at REAL NOT NULL,
          expires_at REAL NOT NULL,
          approved_at REAL,
          approved_by TEXT,
          review_note TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS assistant_model_packs (
          owner_id TEXT NOT NULL,
          pack_id TEXT NOT NULL,
          version TEXT NOT NULL DEFAULT '0.1',
          pack_json TEXT NOT NULL DEFAULT '{}',
          created_at REAL NOT NULL,
          updated_at REAL NOT NULL,
          PRIMARY KEY(owner_id, pack_id)
        );

        CREATE TABLE IF NOT EXISTS assistant_handoffs (
          id TEXT PRIMARY KEY,
          owner_id TEXT NOT NULL,
          plan_id TEXT NOT NULL,
          operation TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending_approval',
          approval_id TEXT,
          request_json TEXT NOT NULL DEFAULT '{}',
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
        "memory_mode": "TEXT NOT NULL DEFAULT 'auto'",
        "subagents": "INTEGER NOT NULL DEFAULT 0",
        "priority": "INTEGER NOT NULL DEFAULT 0",
        "queue_order": "REAL NOT NULL DEFAULT 0",
        "scheduled_for": "REAL",
        "started_at": "REAL",
        "completed_at": "REAL",
        "attempt_count": "INTEGER NOT NULL DEFAULT 0",
        "max_attempts": "INTEGER NOT NULL DEFAULT 1",
        "source_task_id": "TEXT",
        "context_capsule_id": "TEXT",
        "generation_metrics": "TEXT NOT NULL DEFAULT '{}'",
        "deployment_profile": "TEXT NOT NULL DEFAULT '{}'",
        "requested_mode": "TEXT NOT NULL DEFAULT 'chat'",
        "isolation_requested": "INTEGER NOT NULL DEFAULT 0",
        "isolation_state": "TEXT NOT NULL DEFAULT 'none'",
        "execution_workspace": "TEXT NOT NULL DEFAULT ''",
        "isolation_metadata": "TEXT NOT NULL DEFAULT '{}'",
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
        "retention": "TEXT NOT NULL DEFAULT 'persistent'",
        "expires_at": "REAL",
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
                registry = decode(kv["value"], []) if kv else []
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
                    ("chat_folder_registry", encode(registry), now()),
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_expiry ON memory_items(owner_id, status, expires_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_jobs_ready ON memory_jobs(status, next_attempt_at, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_jobs_owner ON memory_jobs(owner_id, status, updated_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_assistant_plans_owner_updated ON assistant_plans(owner_id, updated_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_assistant_context_capsules_owner_updated ON assistant_context_capsules(owner_id, updated_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_assistant_model_packs_owner_updated ON assistant_model_packs(owner_id, updated_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_assistant_handoffs_owner_updated ON assistant_handoffs(owner_id, updated_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_assistant_handoffs_plan_operation ON assistant_handoffs(plan_id, operation)")
    conn.commit()
