import secrets
import time
from pathlib import Path

from backend.core import audit as audit
from backend.core import runtime_store as store

DEFAULT_TTL_SECONDS = 15 * 60
SECRET_KEYS = {"content", "diff", "prompt", "model_output", "raw_output", "file_text", "text"}


def _short(value, max_len=120):
    text = str(value or "")
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _redact(value):
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if str(key).lower() in SECRET_KEYS:
                out[key] = "[redacted]"
            elif "path" in str(key).lower() or key in {"source", "target"}:
                out[key] = _short(str(item), 160)
            else:
                out[key] = _redact(item)
        return out
    if isinstance(value, list):
        return [_redact(item) for item in value[:20]]
    if isinstance(value, (str, Path)):
        return _short(value)
    return value


def _code():
    return secrets.token_hex(3).upper()


def create(action_type, detail=None, risk_level="approval_required", task_id=None, tool_call_id=None, workspace=".", ttl=DEFAULT_TTL_SECONDS):
    store.init_db()
    approval_id = store.new_id("appr")
    code = _code()
    redacted = _redact(detail or {})
    summary = _summary(action_type, redacted)
    stamp = store.now()
    expires = stamp + max(60, int(ttl or DEFAULT_TTL_SECONDS))
    with store._lock, store.connect() as conn:
        while conn.execute("SELECT id FROM approvals WHERE code=?", (code,)).fetchone():
            code = _code()
        conn.execute(
            """
            INSERT INTO approvals(id,code,task_id,tool_call_id,action_type,risk_level,workspace,summary,redacted_detail,status,expires_at,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (approval_id, code, task_id, tool_call_id, action_type, risk_level, workspace or ".", summary, store._json(redacted), "pending", expires, stamp),
        )
        conn.commit()
    event = audit.log("approval_created", {
        "id": approval_id,
        "code": code,
        "action_type": action_type,
        "risk_level": risk_level,
        "workspace": workspace,
        "summary": summary,
    })
    try:
        from . import telegram
        telegram.notify_approval(get(approval_id))
    except Exception as exc:
        audit.log("telegram_approval_notify_failed", {"approval_id": approval_id, "error": str(exc)})
    return get(approval_id)


def _summary(action_type, detail):
    bits = [str(action_type).replace("_", " ")]
    for key in ("path", "source", "target", "query", "workspace"):
        if detail.get(key):
            bits.append(_short(detail[key], 80))
    return " | ".join(bits)


def mutation_preview(kind, detail, actor="local-user", task_id=None, tool_call_id=None):
    approval = create(kind, detail, task_id=task_id, tool_call_id=tool_call_id, workspace=(detail or {}).get("workspace", "."))
    event = {
        "preview": True,
        "approval_id": approval["id"],
        "approval_code": approval["code"],
        "kind": kind,
        "detail": approval["redacted_detail"],
        "created_at": time.time(),
        "message": "Approval required before this mutation is applied.",
    }
    audit.log("approval_preview", event, actor=actor)
    return event


def _public(row):
    if not row:
        return None
    data = dict(row)
    data["redacted_detail"] = store._loads(data.get("redacted_detail"), {})
    return data


def get(approval_id):
    expire_old()
    with store._lock, store.connect() as conn:
        row = conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
    return _public(row)


def get_by_code(code):
    expire_old()
    with store._lock, store.connect() as conn:
        row = conn.execute("SELECT * FROM approvals WHERE upper(code)=upper(?)", (str(code or ""),)).fetchone()
    return _public(row)


def list_approvals(status=None, limit=100):
    expire_old()
    store.init_db()
    if status:
        sql = "SELECT * FROM approvals WHERE status=? ORDER BY created_at DESC LIMIT ?"
        args = (status, max(1, min(int(limit), 500)))
    else:
        sql = "SELECT * FROM approvals ORDER BY created_at DESC LIMIT ?"
        args = (max(1, min(int(limit), 500)),)
    with store._lock, store.connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return {"approvals": [_public(row) for row in rows]}


def decide(approval_id, status, source="ui", note=""):
    if status not in {"approved", "denied", "expired"}:
        raise ValueError("bad approval status")
    stamp = store.now()
    with store._lock, store.connect() as conn:
        row = conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        if not row:
            raise ValueError("approval missing")
        current = row["status"]
        if current not in {"pending"}:
            raise ValueError(f"approval already {current}")
        if row["expires_at"] < stamp and status == "approved":
            status = "expired"
        conn.execute(
            "UPDATE approvals SET status=?, decided_at=?, decision_source=?, decision_note=? WHERE id=?",
            (status, stamp, source, _short(note, 300), approval_id),
        )
        conn.commit()
    audit.log(f"approval_{status}", {"id": approval_id, "source": source})
    return get(approval_id)


def approve(approval_id, source="ui", note=""):
    return decide(approval_id, "approved", source, note)


def deny(approval_id, source="ui", note=""):
    return decide(approval_id, "denied", source, note)


def expire(approval_id, source="ui"):
    return decide(approval_id, "expired", source)


def expire_old():
    store.init_db()
    stamp = store.now()
    with store._lock, store.connect() as conn:
        conn.execute(
            "UPDATE approvals SET status='expired', decided_at=? WHERE status='pending' AND expires_at < ?",
            (stamp, stamp),
        )
        conn.commit()


def require_approved(approval_id, action_type=None):
    approval = get(approval_id)
    if not approval:
        raise PermissionError("approval missing")
    if approval["status"] != "approved":
        raise PermissionError(f"approval is {approval['status']}")
    if action_type and approval["action_type"] != action_type:
        raise PermissionError("approval action mismatch")
    with store._lock, store.connect() as conn:
        row = conn.execute("SELECT status, executed_at FROM approvals WHERE id=?", (approval_id,)).fetchone()
        if row["executed_at"]:
            raise PermissionError("approval already used")
        conn.execute(
            "UPDATE approvals SET status='executed', executed_at=? WHERE id=?",
            (store.now(), approval_id),
        )
        conn.commit()
    audit.log("approval_executed", {"id": approval_id, "action_type": action_type})
    return True
