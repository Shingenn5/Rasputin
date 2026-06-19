from backend.core import audit as audit
from backend.core import runtime_store as store


def list_schedules():
    store.init_db()
    with store._lock, store.connect() as conn:
        rows = conn.execute("SELECT * FROM schedules ORDER BY updated_at DESC").fetchall()
    return {"schedules": [dict(row) for row in rows]}


def create(name, prompt, interval_seconds=0, enabled=False):
    if not str(name or "").strip():
        raise ValueError("schedule name is required")
    if not str(prompt or "").strip():
        raise ValueError("schedule prompt is required")
    schedule_id = store.new_id("sched")
    stamp = store.now()
    next_run_at = stamp + int(interval_seconds) if enabled and interval_seconds else None
    with store._lock, store.connect() as conn:
        conn.execute(
            """
            INSERT INTO schedules(id,name,prompt,enabled,interval_seconds,next_run_at,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (schedule_id, name, prompt, 1 if enabled else 0, max(0, int(interval_seconds or 0)), next_run_at, stamp, stamp),
        )
        conn.commit()
    audit.log("schedule_created", {"id": schedule_id, "name": name, "enabled": enabled})
    return get(schedule_id)


def get(schedule_id):
    store.init_db()
    with store._lock, store.connect() as conn:
        row = conn.execute("SELECT * FROM schedules WHERE id=?", (schedule_id,)).fetchone()
    if not row:
        raise ValueError("schedule missing")
    return dict(row)


def set_enabled(schedule_id, enabled):
    stamp = store.now()
    with store._lock, store.connect() as conn:
        row = conn.execute("SELECT * FROM schedules WHERE id=?", (schedule_id,)).fetchone()
        if not row:
            raise ValueError("schedule missing")
        next_run_at = stamp + int(row["interval_seconds"]) if enabled and row["interval_seconds"] else None
        conn.execute(
            "UPDATE schedules SET enabled=?, next_run_at=?, updated_at=? WHERE id=?",
            (1 if enabled else 0, next_run_at, stamp, schedule_id),
        )
        conn.commit()
    audit.log("schedule_enabled" if enabled else "schedule_disabled", {"id": schedule_id})
    return get(schedule_id)
