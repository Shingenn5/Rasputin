import json
import re
import time
from pathlib import Path

from . import audit
from . import runtime_store as store

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SKILLS_DIR = DATA_DIR / "skills"

BUILTINS = {
    "general": {
        "description": "Default conversational and planning behavior.",
        "allowed_task_modes": ["chat", "research", "code", "write", "organize", "analyze"],
        "allowed_tools": ["rag_search", "graph_search"],
        "default_model_role": "main",
        "required_permissions": ["allow_file_read"],
    },
    "folder_organizer": {
        "description": "Create a local folder organization plan and request approvals for moves.",
        "allowed_task_modes": ["organize"],
        "allowed_tools": ["fs_list", "fs_mkdir", "fs_move"],
        "default_model_role": "organizer",
        "required_permissions": ["allow_file_read", "allow_file_reorganize"],
    },
    "web_research": {
        "description": "Use the brokered web-search tool after approval.",
        "allowed_task_modes": ["research"],
        "allowed_tools": ["web_search"],
        "default_model_role": "researcher",
        "required_permissions": ["allow_web_search"],
    },
    "paper_writer": {
        "description": "Draft structured writing from local context.",
        "allowed_task_modes": ["write"],
        "allowed_tools": ["rag_search", "graph_search"],
        "default_model_role": "writer",
        "required_permissions": ["allow_file_read"],
    },
    "excel_data_entry": {
        "description": "Plan spreadsheet-oriented data entry workflows.",
        "allowed_task_modes": ["write", "analyze"],
        "allowed_tools": ["rag_search"],
        "default_model_role": "executor",
        "required_permissions": ["allow_file_read"],
    },
}


def _slug(name):
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(name or "")).strip("-").lower()[:64] or "skill"


def _skill_path(name):
    return SKILLS_DIR / _slug(name) / "SKILL.md"


def _markdown(name, metadata):
    lines = [
        f"# {name}",
        "",
        metadata.get("description", "Reusable Rasputin skill."),
        "",
        "```json",
        json.dumps(metadata, indent=2, ensure_ascii=True),
        "```",
        "",
        "## Workflow",
        "",
        "- Read the task and active workspace.",
        "- Use only allowed tools.",
        "- Ask for approval before risky actions.",
        "- Return a concise result with outputs when useful.",
    ]
    return "\n".join(lines) + "\n"


def init_skills():
    store.init_db()
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = store.now()
    with store._lock, store.connect() as conn:
        for name, metadata in BUILTINS.items():
            path = _skill_path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text(_markdown(name, metadata), encoding="utf-8")
            conn.execute(
                """
                INSERT INTO skills(name,description,metadata,enabled,builtin,path,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(name) DO UPDATE SET description=excluded.description, metadata=excluded.metadata, builtin=1, path=excluded.path, updated_at=excluded.updated_at
                """,
                (name, metadata.get("description", ""), json.dumps(metadata), 1, 1, str(path), stamp, stamp),
            )
        conn.commit()


def _public(row, include_content=False):
    data = dict(row)
    data["metadata"] = store._loads(data.get("metadata"), {})
    data["enabled"] = bool(data.get("enabled"))
    data["builtin"] = bool(data.get("builtin"))
    if include_content:
        try:
            data["content"] = Path(data.get("path", "")).read_text(encoding="utf-8")
        except Exception:
            data["content"] = ""
    return data


def list_skills(include_disabled=True):
    init_skills()
    where = "" if include_disabled else "WHERE enabled=1"
    with store._lock, store.connect() as conn:
        rows = conn.execute(f"SELECT * FROM skills {where} ORDER BY builtin DESC, name").fetchall()
    return {"skills": [_public(row) for row in rows]}


def enabled_names():
    return [item["name"] for item in list_skills(False)["skills"]]


def get_skill(name):
    init_skills()
    with store._lock, store.connect() as conn:
        row = conn.execute("SELECT * FROM skills WHERE name=?", (_slug(name),)).fetchone()
    if not row:
        raise ValueError("skill missing")
    return _public(row, include_content=True)


def save_skill(name, description, content=None, metadata=None, builtin=False):
    init_skills()
    name = _slug(name)
    metadata = metadata or {}
    metadata.setdefault("description", description or "Reusable Rasputin skill.")
    path = _skill_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content or _markdown(name, metadata), encoding="utf-8")
    stamp = store.now()
    with store._lock, store.connect() as conn:
        conn.execute(
            """
            INSERT INTO skills(name,description,metadata,enabled,builtin,path,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(name) DO UPDATE SET description=excluded.description, metadata=excluded.metadata, path=excluded.path, updated_at=excluded.updated_at
            """,
            (name, description or metadata.get("description", ""), json.dumps(metadata), 1, int(bool(builtin)), str(path), stamp, stamp),
        )
        conn.commit()
    audit.log("skill_saved", {"name": name, "builtin": builtin})
    return get_skill(name)


def import_skill(name, content, metadata=None):
    if not str(content or "").strip():
        raise ValueError("skill content is required")
    return save_skill(name, (metadata or {}).get("description", "Imported Rasputin skill."), content, metadata or {})


def set_enabled(name, enabled):
    init_skills()
    with store._lock, store.connect() as conn:
        row = conn.execute("SELECT name FROM skills WHERE name=?", (_slug(name),)).fetchone()
        if not row:
            raise ValueError("skill missing")
        conn.execute("UPDATE skills SET enabled=?, updated_at=? WHERE name=?", (1 if enabled else 0, store.now(), _slug(name)))
        conn.commit()
    audit.log("skill_enabled" if enabled else "skill_disabled", {"name": _slug(name)})
    return get_skill(name)


def create_from_session(session_id, name=None, save=False):
    store.init_db()
    with store._lock, store.connect() as conn:
        session = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not session:
            raise ValueError("session missing")
        messages = conn.execute(
            "SELECT role, content FROM messages WHERE session_id=? ORDER BY created_at ASC LIMIT 20",
            (session_id,),
        ).fetchall()
    title = name or session["title"] or "Session Skill"
    skill_name = _slug(title)
    metadata = {
        "name": skill_name,
        "description": f"Reusable workflow distilled from session {session_id}.",
        "allowed_task_modes": [session["mode"]],
        "allowed_tools": ["rag_search", "graph_search"],
        "default_model_role": session["model"] or "main",
        "required_permissions": ["allow_file_read"],
        "workspace_constraints": session["workspace"],
    }
    content = _markdown(skill_name, metadata) + "\n## Session Notes\n\n"
    for row in messages[-8:]:
        content += f"- **{row['role']}**: {row['content'][:600]}\n"
    preview = {"name": skill_name, "metadata": metadata, "content": content, "preview": not save}
    if save:
        return save_skill(skill_name, metadata["description"], content, metadata)
    audit.log("skill_preview_created", {"session_id": session_id, "name": skill_name})
    return preview


init_skills()
