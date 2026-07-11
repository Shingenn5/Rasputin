import sqlite3
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from .models import ArchiveItem, ArchiveRetentionRule
from backend.core.datadir import data_dir

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = data_dir() / "archive.sqlite3"

def _get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def _init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS archive_items (
                id TEXT PRIMARY KEY,
                name TEXT,
                type TEXT,
                source TEXT,
                workspace TEXT,
                created_at REAL,
                archived_at REAL,
                size INTEGER,
                tags TEXT,
                retention_policy_id TEXT,
                metadata TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_archive_type ON archive_items(type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_archive_workspace ON archive_items(workspace)")
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS retention_rules (
                id TEXT PRIMARY KEY,
                target_type TEXT,
                duration_days INTEGER,
                created_at REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                action TEXT,
                item_id TEXT,
                user TEXT,
                timestamp REAL,
                details TEXT
            )
        """)
        conn.commit()

_init_db()

class ArchiveService:
    @staticmethod
    def record_audit(action: str, item_id: str, user: str, details: Dict[str, Any]):
        import uuid
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO audit_logs (id, action, item_id, user, timestamp, details) VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), action, item_id, user, time.time(), json.dumps(details))
            )
            conn.commit()

    @staticmethod
    def sweep_retention():
        with _get_conn() as conn:
            # Simple retention policy example: Delete items past their retention date
            # In a real system, you'd match rules to types.
            conn.execute("DELETE FROM archive_items WHERE retention_policy_id = '30d' AND archived_at < ?", (time.time() - 30 * 86400,))
            conn.execute("DELETE FROM archive_items WHERE retention_policy_id = '90d' AND archived_at < ?", (time.time() - 90 * 86400,))
            conn.execute("DELETE FROM archive_items WHERE retention_policy_id = '1y' AND archived_at < ?", (time.time() - 365 * 86400,))
            conn.commit()

    @staticmethod
    def get_items(filters: Dict[str, Any] = None) -> List[ArchiveItem]:
        query = "SELECT * FROM archive_items WHERE 1=1"
        params = []
        if filters:
            if "type" in filters and filters["type"]:
                query += " AND type = ?"
                params.append(filters["type"])
            if "workspace" in filters and filters["workspace"]:
                query += " AND workspace = ?"
                params.append(filters["workspace"])
            if "search" in filters and filters["search"]:
                query += " AND (name LIKE ? OR metadata LIKE ?)"
                params.extend([f"%{filters['search']}%", f"%{filters['search']}%"])
        
        query += " ORDER BY archived_at DESC"
        
        with _get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            items = []
            for row in rows:
                row_dict = dict(row)
                row_dict["tags"] = json.loads(row_dict["tags"]) if row_dict["tags"] else []
                row_dict["metadata"] = json.loads(row_dict["metadata"]) if row_dict["metadata"] else {}
                items.append(ArchiveItem(**row_dict))
            return items

    @staticmethod
    def add_item(item: ArchiveItem):
        with _get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO archive_items
                (id, name, type, source, workspace, created_at, archived_at, size, tags, retention_policy_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.id, item.name, item.type, item.source, item.workspace,
                item.created_at, item.archived_at, item.size,
                json.dumps(item.tags), item.retention_policy_id, json.dumps(item.metadata)
            ))
            conn.commit()
            ArchiveService.record_audit("ADD", item.id, "system", {"name": item.name, "type": item.type})

    @staticmethod
    def delete_item(item_id: str):
        with _get_conn() as conn:
            conn.execute("DELETE FROM archive_items WHERE id = ?", (item_id,))
            conn.commit()
            ArchiveService.record_audit("DELETE", item_id, "system", {})

    @staticmethod
    def restore_item(item_id: str) -> bool:
        item = ArchiveService.get_item(item_id)
        if not item: return False
        ArchiveService.record_audit("RESTORE", item_id, "system", {"name": item.name})
        return True

    @staticmethod
    def get_item(item_id: str) -> Optional[ArchiveItem]:
        with _get_conn() as conn:
            row = conn.execute("SELECT * FROM archive_items WHERE id = ?", (item_id,)).fetchone()
            if row:
                row_dict = dict(row)
                row_dict["tags"] = json.loads(row_dict["tags"]) if row_dict["tags"] else []
                row_dict["metadata"] = json.loads(row_dict["metadata"]) if row_dict["metadata"] else {}
                return ArchiveItem(**row_dict)
            return None
