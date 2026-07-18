import asyncio
import importlib
import json
import os
import re
import time
import uuid
from pathlib import Path

from backend.mcp.layer import McpLayer
from backend.models import providers as model_providers
from backend.models import compatibility as model_compatibility

async def _chat(model_key, messages, tools=None, on_delta=None, reasoning="auto"):
    cfg = model_registry.get_model(model_key) or model_registry.get_model("dry-run")
    if model_key == "dry-run" or not cfg or cfg.get("provider") == "mock":
        user_msg = messages[-1]["content"] if messages else ""
        reply = f"This is a dry-run response to: {user_msg}"
        if on_delta:
            try:
                on_delta({"type": "text", "text": reply})
            except Exception:
                pass
        return reply, []

    cfg_for_limits = dict(cfg or {})
    max_tokens = context_governor.normalize_limits(cfg_for_limits)["maxTokens"]

    try:
        return await model_providers.chat(cfg, messages, max_tokens, 0.2, tools=tools, on_delta=on_delta, reasoning=reasoning)
    except Exception as exc:
        audit.log("model_chat_failed", {
            "key": model_key,
            "model": cfg.get("model"),
            "provider": cfg.get("provider"),
            "error": str(exc),
        })
        raise RuntimeError(str(exc)) from None

from backend.engine import context as context_governor
from backend.engine import prompt_security
from backend.rag import memory as memory
from backend.models import registry as model_registry
from backend.core import runtime_store as store
from backend.core import security as security
from backend.core import audit as audit
from backend.mcp import tools as tool_relay
from backend.core import workspace

TEXT_FILE_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css",
    ".json", ".csv", ".yml", ".yaml", ".toml", ".ini", ".cfg",
}
# File-mutating tools whose successful execution means the workspace actually
# changed, so the Stage 6 test loop should re-run the configured test command.
FILE_MUTATING_TOOLS = {"fs_write", "fs_patch", "fs_move"}
WORKSPACE_CONTEXT_TERMS = (
    "file", "files", "folder", "folders", "directory", "directories", "workspace",
    "codebase", "repo", "repository", "project", "read my", "inspect", "scan",
    "look through", "file base", "filebase", "read", "analyze", "summarize", "review",
)
FILE_SNIPPET_TERMS = (
    "read", "inspect", "scan", "analyze", "summarize", "review", "look through",
    "file base", "filebase", "codebase", "repo", "repository", "project",
)


class AgentTask:
    def __init__(self, objective, model, skill, parent_id=None, workspace_path=None, mode="chat", task_id=None, session_id=None, reasoning="auto", priority=0, scheduled_for=None, subagents=0, max_attempts=1, source_task_id=None):
        self.id = task_id or str(uuid.uuid4())[:8]
        self.session_id = session_id or store.new_id("sess")
        self.objective = objective
        self.model = model
        self.skill = skill or "general"
        self.mode = mode or "chat"
        self.reasoning = reasoning if reasoning in {"auto", "off", "low", "medium", "high"} else "auto"
        self.priority = max(-10, min(int(priority or 0), 10))
        self.scheduled_for = float(scheduled_for) if scheduled_for else None
        self.subagents = max(0, min(int(subagents or 0), 4))
        self.max_attempts = max(1, min(int(max_attempts or 1), 5))
        self.attempt_count = 0
        self.source_task_id = source_task_id
        self.queue_order = time.time()
        self.started_at = None
        self.completed_at = None
        self.parent_id = parent_id
        self.status = "queued"
        self.progress = 0
        self.logs = []
        self.result = ""
        self.sources = []
        self.graph = []
        self.outputs = []
        self.trace = []
        # Live-streaming state: current phase's partial model output and the
        # running step list (phases + tool calls). Written from the provider
        # worker thread; plain field assignment keeps it GIL-safe.
        self.stream_text = ""
        self.steps = []
        self.cancel_requested = False
        self.paused_requested = False
        self.workspace = workspace_path or workspace.get_active()["active_path"]
        self.permission_snapshot = security.load()
        self.created_at = time.time()
        self.event_sink = None
        self.output_sink = None
        self.trace_sink = None

    def log(self, msg):
        stamp = time.strftime("%H:%M:%S")
        line = f"[{stamp}] {msg}"
        self.logs.append(line)
        self.logs = self.logs[-500:]
        if self.event_sink:
            self.event_sink(self.id, "log", {"message": line})

    def seen(self, kind, detail):
        item = {"at": time.time(), "kind": kind, "detail": detail}
        self.trace.append(item)
        self.trace = self.trace[-120:]
        if self.trace_sink:
            self.trace_sink(self.id, kind, detail)

    def output(self, kind, title, content):
        item = {"kind": kind, "title": title, "content": content, "createdAt": time.time()}
        self.outputs.append(item)
        self.outputs = self.outputs[-40:]
        if self.output_sink:
            self.output_sink(self.id, kind, title, content)


class AgentHub:
    def __init__(self):
        store.init_db()
        self.tasks = {}
        self.listeners = {}
        self.mcp = McpLayer()
        self._memory_export_task = None
        self._loop = None
        self._owner_semaphores = {}
        self._queued_runners = {}
        self._mark_interrupted()

    def _trigger_broadcast(self, task_id):
        if not hasattr(self, "_loop") or not self._loop or not self.listeners:
            return
        task = self.tasks.get(task_id)
        if not task:
            return
        # Wrapped as {"task": ...} — the frontend event handler dispatches on
        # that key; a bare snapshot is silently ignored on the client.
        data = {"task": self.snapshot_task(task)}

        def push_to_queues():
            dead = []
            owner_id = getattr(task, "owner_id", "admin")
            for q, listener_owner in list(self.listeners.items()):
                if listener_owner != owner_id:
                    continue
                try:
                    q.put_nowait(data)
                except Exception:
                    dead.append(q)
            for q in dead:
                self.listeners.pop(q, None)
                
        try:
            self._loop.call_soon_threadsafe(push_to_queues)
        except Exception:
            pass

    def _mark_interrupted(self):
        with store._lock, store.connect() as conn:
            conn.execute(
                "UPDATE tasks SET status='paused', paused=1, updated_at=? WHERE status='running'",
                (store.now(),),
            )
            conn.commit()

    def _wire(self, task):
        task.event_sink = self.record_event
        task.output_sink = self.record_output
        task.trace_sink = self.record_trace

    def _concurrency_limit(self):
        try:
            value = int(os.environ.get("RASPUTIN_TASK_CONCURRENCY", "1"))
        except (TypeError, ValueError):
            value = 1
        return max(1, min(value, 8))

    def _owner_semaphore(self, owner_id):
        owner = str(owner_id or "admin")
        semaphore = self._owner_semaphores.get(owner)
        if semaphore is None:
            semaphore = asyncio.Semaphore(self._concurrency_limit())
            self._owner_semaphores[owner] = semaphore
        return semaphore

    def _task_from_row(self, row):
        task = AgentTask(
            row["objective"],
            row["model"],
            row["skill"],
            row["parent_id"],
            row["workspace"],
            row["mode"],
            task_id=row["id"],
            session_id=row["session_id"],
            reasoning=row["reasoning"] or "auto",
            priority=row["priority"],
            scheduled_for=row["scheduled_for"],
            subagents=row["subagents"],
            max_attempts=row["max_attempts"],
            source_task_id=row["source_task_id"],
        )
        task.owner_id = row["owner_id"] or "admin"
        task.created_at = row["created_at"]
        task.queue_order = row["queue_order"] or row["created_at"]
        task.progress = row["progress"]
        task.result = row["result"]
        task.attempt_count = row["attempt_count"]
        task.started_at = row["started_at"]
        task.completed_at = row["completed_at"]
        task.status = row["status"]
        task.paused_requested = bool(row["paused"])
        self._wire(task)
        return task

    def _schedule_queued_task(self, task):
        runner = self._queued_runners.get(task.id)
        if runner and not runner.done():
            return runner
        runner = asyncio.create_task(self._run_when_ready(task))
        self._queued_runners[task.id] = runner
        return runner

    async def recover_pending(self):
        """Restore queued tasks after restart; interrupted running tasks remain paused."""
        with store._lock, store.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status='queued' ORDER BY owner_id, priority DESC, queue_order ASC"
            ).fetchall()
        for row in rows:
            if row["id"] in self.tasks:
                continue
            task = self._task_from_row(row)
            self.tasks[task.id] = task
            self._schedule_queued_task(task)
        return len(rows)

    async def _run_when_ready(self, task):
        owner = getattr(task, "owner_id", "admin")
        try:
            while task.status == "queued" and not task.cancel_requested:
                now = store.now()
                with store._lock, store.connect() as conn:
                    row = conn.execute(
                        """
                        SELECT id FROM tasks
                        WHERE owner_id=? AND status='queued'
                          AND (scheduled_for IS NULL OR scheduled_for<=?)
                        ORDER BY priority DESC, queue_order ASC LIMIT 1
                        """,
                        (owner, now),
                    ).fetchone()
                if row and row["id"] == task.id:
                    async with self._owner_semaphore(owner):
                        if task.status != "queued" or task.cancel_requested:
                            return
                        await self.run_task(task, subagents=task.subagents)
                        return
                await asyncio.sleep(0.35)
        finally:
            self._queued_runners.pop(task.id, None)

    def record_event(self, task_id, kind, detail):
        with store._lock, store.connect() as conn:
            conn.execute(
                "INSERT INTO task_events(task_id,kind,detail,created_at) VALUES(?,?,?,?)",
                (task_id, kind, store._json(detail), store.now()),
            )
            conn.commit()
        self._trigger_broadcast(task_id)

    def record_trace(self, task_id, kind, detail):
        with store._lock, store.connect() as conn:
            conn.execute(
                "INSERT INTO agent_traces(task_id,kind,detail,created_at) VALUES(?,?,?,?)",
                (task_id, kind, store._json(detail), store.now()),
            )
            conn.commit()
        self._trigger_broadcast(task_id)

    def record_output(self, task_id, kind, title, content):
        text = str(content or "")
        normalized_kind = str(kind or "text").lower()
        mime_type = "text/markdown" if normalized_kind in {"markdown", "report"} else "application/json" if normalized_kind == "json" else "text/plain"
        extension = "md" if mime_type == "text/markdown" else "json" if mime_type == "application/json" else "txt"
        filename = f"{re.sub(r'[^a-zA-Z0-9_.-]+', '-', str(title or 'artifact')).strip('-').lower() or 'artifact'}.{extension}"
        with store._lock, store.connect() as conn:
            conn.execute(
                "INSERT INTO outputs(id,task_id,kind,title,content,filename,mime_type,size_bytes,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (store.new_id("out"), task_id, kind, title, text, filename, mime_type, len(text.encode("utf-8")), store.now()),
            )
            conn.commit()
        self._trigger_broadcast(task_id)

    def _persist_session(self, task):
        stamp = store.now()
        title = task.objective.strip().splitlines()[0][:140] or "Rasputin session"
        with store._lock, store.connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions(id,title,status,workspace,model,mode,skill,summary,created_at,updated_at,folder,owner_id)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                  title=CASE
                    WHEN sessions.title IN ('New chat','Untitled chat','Rasputin session') THEN excluded.title
                    ELSE sessions.title
                  END,
                  status=excluded.status,
                  workspace=excluded.workspace,
                  model=excluded.model,
                  mode=excluded.mode,
                  skill=excluded.skill,
                  updated_at=excluded.updated_at
                """,
                (task.session_id, title, "active", task.workspace, task.model, task.mode, task.skill, "", stamp, stamp, "", getattr(task, "owner_id", "admin")),
            )
            conn.commit()

    def _add_message(self, session_id, task_id, role, content):
        msg_id = store.new_id("msg")
        stamp = store.now()
        with store._lock, store.connect() as conn:
            conn.execute(
                "INSERT INTO messages(id,session_id,task_id,role,content,created_at) VALUES(?,?,?,?,?,?)",
                (msg_id, session_id, task_id, role, str(content or ""), stamp),
            )
            try:
                conn.execute(
                    "INSERT INTO session_fts(id,session_id,task_id,content) VALUES(?,?,?,?)",
                    (msg_id, session_id, task_id, str(content or "")),
                )
            except Exception:
                pass
            conn.commit()
        self._schedule_master_context_export()

    def _schedule_master_context_export(self):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            try:
                memory.export_master_context()
            except Exception:
                pass
            return
        if self._memory_export_task and not self._memory_export_task.done():
            return
        self._memory_export_task = loop.create_task(self._export_master_context())

    async def _export_master_context(self):
        try:
            await asyncio.to_thread(memory.export_master_context)
        except Exception:
            pass

    def _persist_task(self, task):
        self._persist_session(task)
        previous_status = None
        with store._lock, store.connect() as conn:
            previous = conn.execute("SELECT status FROM tasks WHERE id=?", (task.id,)).fetchone()
            previous_status = previous["status"] if previous else None
            conn.execute(
                """
                INSERT INTO tasks(
                  id,session_id,parent_id,objective,model,skill,mode,status,progress,result,
                  workspace,permission_snapshot,paused,created_at,updated_at,owner_id,reasoning,
                  subagents,priority,queue_order,scheduled_for,started_at,completed_at,attempt_count,
                  max_attempts,source_task_id
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                  status=excluded.status,
                  progress=excluded.progress,
                  result=excluded.result,
                  paused=excluded.paused,
                  priority=excluded.priority,
                  queue_order=excluded.queue_order,
                  scheduled_for=excluded.scheduled_for,
                  started_at=excluded.started_at,
                  completed_at=excluded.completed_at,
                  attempt_count=excluded.attempt_count,
                  updated_at=excluded.updated_at
                """,
                (
                    task.id,
                    task.session_id,
                    task.parent_id,
                    task.objective,
                    task.model,
                    task.skill,
                    task.mode,
                    task.status,
                    int(task.progress),
                    task.result,
                    task.workspace,
                    json.dumps(task.permission_snapshot),
                    1 if task.paused_requested or task.status == "paused" else 0,
                    task.created_at,
                    store.now(),
                    getattr(task, "owner_id", "admin"),
                    task.reasoning,
                    task.subagents,
                    task.priority,
                    task.queue_order,
                    task.scheduled_for,
                    task.started_at,
                    task.completed_at,
                    task.attempt_count,
                    task.max_attempts,
                    task.source_task_id,
                ),
            )
            conn.commit()
        if task.status in {"done", "error", "cancelled"} and previous_status != task.status:
            labels = {
                "done": ("Task completed", "success"),
                "error": ("Task failed", "error"),
                "cancelled": ("Task cancelled", "warning"),
            }
            title, severity = labels[task.status]
            store.create_inbox_event(
                getattr(task, "owner_id", "admin"),
                f"task_{task.status}",
                title,
                task.objective[:240],
                severity=severity,
                task_id=task.id,
                action_type="open_task",
                action_payload={"taskId": task.id},
            )

    async def emit(self, task):
        self._persist_task(task)
        data = {"task": self.snapshot_task(task)}
        dead = []
        owner_id = getattr(task, "owner_id", "admin")
        for q, listener_owner in list(self.listeners.items()):
            if listener_owner != owner_id:
                continue
            try:
                await q.put(data)
            except Exception:
                dead.append(q)
        for q in dead:
            self.listeners.pop(q, None)

    def snapshot_task(self, task):
        return {
            "id": task.id,
            "sessionId": task.session_id,
            "objective": task.objective,
            "model": task.model,
            "skill": task.skill,
            "mode": task.mode,
            "reasoning": getattr(task, "reasoning", "auto"),
            "subagents": getattr(task, "subagents", 0),
            "priority": getattr(task, "priority", 0),
            "queueOrder": getattr(task, "queue_order", task.created_at),
            "scheduledFor": getattr(task, "scheduled_for", None),
            "startedAt": getattr(task, "started_at", None),
            "completedAt": getattr(task, "completed_at", None),
            "attemptCount": getattr(task, "attempt_count", 0),
            "maxAttempts": getattr(task, "max_attempts", 1),
            "sourceTaskId": getattr(task, "source_task_id", None),
            "status": task.status,
            "progress": task.progress,
            "logs": task.logs[-80:],
            "result": task.result,
            "sources": task.sources,
            "graph": task.graph,
            "outputs": task.outputs,
            "trace": task.trace[-80:],
            "streamText": task.stream_text[-4000:],
            "steps": task.steps[-40:],
            "permissionSnapshot": task.permission_snapshot,
            "workspace": task.workspace,
            "parentId": task.parent_id,
            "paused": task.paused_requested or task.status == "paused",
            "createdAt": task.created_at,
            "ownerId": getattr(task, "owner_id", "admin"),
        }

    def _snapshot_from_db(self, row, include_details=True):
        task = dict(row)
        base = {
            "id": task["id"],
            "sessionId": task["session_id"],
            "objective": task["objective"],
            "model": task["model"],
            "skill": task["skill"],
            "mode": task["mode"],
            "status": task["status"],
            "progress": task["progress"],
            "logs": [],
            "result": task["result"],
            "sources": [],
            "graph": [],
            "outputs": [],
            "trace": [],
            "streamText": "",
            "steps": [],
            "permissionSnapshot": store._loads(task["permission_snapshot"], {}),
            "workspace": task["workspace"],
            "parentId": task["parent_id"],
            "paused": bool(task["paused"]),
            "createdAt": task["created_at"],
            "ownerId": task.get("owner_id") or "admin",
            "reasoning": task.get("reasoning") or "auto",
            "subagents": task.get("subagents") or 0,
            "priority": task.get("priority") or 0,
            "queueOrder": task.get("queue_order") or task["created_at"],
            "scheduledFor": task.get("scheduled_for"),
            "startedAt": task.get("started_at"),
            "completedAt": task.get("completed_at"),
            "attemptCount": task.get("attempt_count") or 0,
            "maxAttempts": task.get("max_attempts") or 1,
            "sourceTaskId": task.get("source_task_id"),
        }
        if not include_details:
            return base
        with store._lock, store.connect() as conn:
            events = conn.execute(
                "SELECT kind,detail,created_at FROM task_events WHERE task_id=? ORDER BY id DESC LIMIT 80",
                (task["id"],),
            ).fetchall()
            outputs = conn.execute(
                "SELECT kind,title,content,created_at FROM outputs WHERE task_id=? ORDER BY created_at DESC LIMIT 40",
                (task["id"],),
            ).fetchall()
            traces = conn.execute(
                "SELECT kind,detail,created_at FROM agent_traces WHERE task_id=? ORDER BY id DESC LIMIT 80",
                (task["id"],),
            ).fetchall()
        logs = []
        for event in reversed(events):
            detail = store._loads(event["detail"], {})
            if event["kind"] == "log":
                logs.append(detail.get("message", ""))
        base.update({
            "logs": logs,
            "outputs": [
                {"kind": a["kind"], "title": a["title"], "content": a["content"], "createdAt": a["created_at"]}
                for a in outputs
            ],
            "trace": [
                {"at": t["created_at"], "kind": t["kind"], "detail": store._loads(t["detail"], {})}
                for t in reversed(traces)
            ],
        })
        return base

    def all_tasks(self, limit=100, include_details=False, owner_id="admin"):
        store.init_db()
        limit = max(1, min(int(limit or 100), 500))
        with store._lock, store.connect() as conn:
            rows = conn.execute("SELECT * FROM tasks WHERE owner_id=? ORDER BY created_at DESC LIMIT ?", (owner_id, limit)).fetchall()
        return [self._snapshot_from_db(row, include_details=include_details) for row in rows]

    def get_task(self, task_id, owner_id="admin"):
        task = self.tasks.get(task_id)
        if task and (owner_id is None or getattr(task, "owner_id", "admin") == owner_id):
            return self.snapshot_task(task)
        with store._lock, store.connect() as conn:
            if owner_id is None:
                row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            else:
                row = conn.execute("SELECT * FROM tasks WHERE id=? AND owner_id=?", (task_id, owner_id)).fetchone()
        return self._snapshot_from_db(row) if row else None

    def task_detail(self, task_id, owner_id="admin"):
        task = self.get_task(task_id, owner_id)
        if not task:
            return None
        with store._lock, store.connect() as conn:
            session = conn.execute("SELECT * FROM sessions WHERE id=?", (task["sessionId"],)).fetchone()
            events = conn.execute(
                "SELECT kind,detail,created_at FROM task_events WHERE task_id=? ORDER BY id ASC LIMIT 500",
                (task_id,),
            ).fetchall()
            traces = conn.execute(
                "SELECT kind,detail,created_at FROM agent_traces WHERE task_id=? ORDER BY id ASC LIMIT 300",
                (task_id,),
            ).fetchall()
            outputs = conn.execute(
                "SELECT id,kind,title,content,created_at FROM outputs WHERE task_id=? ORDER BY created_at ASC LIMIT 100",
                (task_id,),
            ).fetchall()
            children = conn.execute(
                "SELECT * FROM tasks WHERE parent_id=? ORDER BY created_at ASC LIMIT 100",
                (task_id,),
            ).fetchall()
            approvals = conn.execute(
                "SELECT * FROM approvals WHERE task_id=? ORDER BY created_at DESC LIMIT 100",
                (task_id,),
            ).fetchall()
            tool_calls = conn.execute(
                "SELECT * FROM tool_calls WHERE task_id=? ORDER BY created_at DESC LIMIT 150",
                (task_id,),
            ).fetchall()
        return {
            "task": task,
            "session": dict(session) if session else None,
            "events": [
                {"kind": e["kind"], "detail": store._loads(e["detail"], {}), "createdAt": e["created_at"]}
                for e in events
            ],
            "trace": [
                {"kind": t["kind"], "detail": store._loads(t["detail"], {}), "createdAt": t["created_at"]}
                for t in traces
            ],
            "outputs": [
                {"id": a["id"], "kind": a["kind"], "title": a["title"], "content": a["content"], "createdAt": a["created_at"]}
                for a in outputs
            ],
            "children": [self._snapshot_from_db(row) for row in children],
            "approvals": [self._public_approval(row) for row in approvals],
            "toolCalls": [self._public_tool_call(row) for row in tool_calls],
        }

    def _public_approval(self, row):
        data = dict(row)
        data["redacted_detail"] = store._loads(data.get("redacted_detail"), {})
        return data

    def _public_tool_call(self, row):
        data = dict(row)
        data["args_redacted"] = store._loads(data.get("args_redacted"), {})
        data["result_redacted"] = store._loads(data.get("result_redacted"), {})
        return data

    def sessions(self, limit=100, owner_id="admin"):
        with store._lock, store.connect() as conn:
            rows = conn.execute(
                """
                SELECT s.*,
                       (SELECT COUNT(*) FROM messages m
                        WHERE m.session_id=s.id AND TRIM(COALESCE(m.content, ''))!='') AS message_count,
                       (SELECT COUNT(*) FROM tasks t WHERE t.session_id=s.id) AS task_count
                FROM sessions s
                WHERE s.owner_id=?
                ORDER BY s.updated_at DESC
                LIMIT ?
                """,
                (owner_id, max(1, min(int(limit), 500))),
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) AS count FROM sessions WHERE owner_id=?", (owner_id,)).fetchone()
            empty_total = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM sessions s
                WHERE s.owner_id=?
                  AND NOT EXISTS (
                    SELECT 1 FROM messages m
                    WHERE m.session_id=s.id AND TRIM(COALESCE(m.content, ''))!=''
                  )
                  AND NOT EXISTS (SELECT 1 FROM tasks t WHERE t.session_id=s.id)
                """,
                (owner_id,),
            ).fetchone()
        session_items = []
        for row in rows:
            item = dict(row)
            item["is_empty"] = int(item.get("message_count") or 0) == 0 and int(item.get("task_count") or 0) == 0
            session_items.append(item)
        return {
            "sessions": session_items,
            "total": int(total["count"] if total else len(rows)),
            "empty_total": int(empty_total["count"] if empty_total else 0),
        }

    def delete_empty_session(self, session_id, owner_id="admin"):
        with store._lock, store.connect() as conn:
            session = conn.execute(
                "SELECT id FROM sessions WHERE id=? AND owner_id=?",
                (session_id, owner_id),
            ).fetchone()
            if not session:
                raise ValueError("session missing")
            has_content = conn.execute(
                """
                SELECT
                  EXISTS(
                    SELECT 1 FROM messages
                    WHERE session_id=? AND TRIM(COALESCE(content, ''))!=''
                  ) AS has_messages,
                  EXISTS(SELECT 1 FROM tasks WHERE session_id=?) AS has_tasks
                """,
                (session_id, session_id),
            ).fetchone()
            if has_content and (has_content["has_messages"] or has_content["has_tasks"]):
                raise ValueError("Only empty chats can be removed.")
            conn.execute("DELETE FROM sessions WHERE id=? AND owner_id=?", (session_id, owner_id))
            conn.commit()
        return {"deleted": True, "session_id": session_id}

    def delete_session(self, session_id, owner_id="admin"):
        with store._lock, store.connect() as conn:
            session = conn.execute(
                "SELECT id,title FROM sessions WHERE id=? AND owner_id=?",
                (session_id, owner_id),
            ).fetchone()
            if not session:
                raise ValueError("session missing")
            conn.execute("DELETE FROM sessions WHERE id=? AND owner_id=?", (session_id, owner_id))
            conn.commit()
        return {"deleted": True, "session_id": session_id, "title": session["title"]}

    def cleanup_empty_sessions(self, owner_id="admin"):
        with store._lock, store.connect() as conn:
            rows = conn.execute(
                """
                SELECT s.id
                FROM sessions s
                WHERE s.owner_id=?
                  AND NOT EXISTS (
                    SELECT 1 FROM messages m
                    WHERE m.session_id=s.id AND TRIM(COALESCE(m.content, ''))!=''
                  )
                  AND NOT EXISTS (SELECT 1 FROM tasks t WHERE t.session_id=s.id)
                """,
                (owner_id,),
            ).fetchall()
            session_ids = [row["id"] for row in rows]
            if session_ids:
                conn.executemany(
                    "DELETE FROM sessions WHERE id=? AND owner_id=?",
                    [(session_id, owner_id) for session_id in session_ids],
                )
                conn.commit()
        return {"deleted_count": len(session_ids), "session_ids": session_ids}

    def session(self, session_id, owner_id="admin"):
        with store._lock, store.connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id=? AND owner_id=?", (session_id, owner_id)).fetchone()
            if not row:
                raise ValueError("session missing")
            messages = conn.execute(
                "SELECT role,content,created_at,task_id FROM messages WHERE session_id=? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
            tasks = conn.execute("SELECT * FROM tasks WHERE session_id=? ORDER BY created_at ASC", (session_id,)).fetchall()
        return {"session": dict(row), "messages": [dict(m) for m in messages], "tasks": [self._snapshot_from_db(t) for t in tasks]}

    def create_session(self, title="New chat", workspace=".", model="dry-run", mode="chat", skill="general", folder="", owner_id="admin"):
        stamp = store.now()
        session_id = store.new_id("sess")
        clean_title = str(title or "New chat").strip()[:140] or "New chat"
        with store._lock, store.connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions(id,title,status,workspace,model,mode,skill,summary,created_at,updated_at,folder,owner_id)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    session_id,
                    clean_title,
                    "active",
                    workspace or ".",
                    model or "dry-run",
                    mode or "chat",
                    skill or "general",
                    "",
                    stamp,
                    stamp,
                    self._clean_folder_name(folder),
                    owner_id,
                ),
            )
            conn.commit()
        return self.session(session_id, owner_id)

    def chat_folders(self, owner_id="admin"):
        registry = store.get_kv(f"chat_folder_registry:{owner_id}", [])
        if not isinstance(registry, list):
            registry = []
        with store._lock, store.connect() as conn:
            rows = conn.execute(
                "SELECT folder, COUNT(*) AS session_count FROM sessions WHERE owner_id=? AND folder IS NOT NULL AND folder!='' GROUP BY folder",
                (owner_id,),
            ).fetchall()
            unfiled = conn.execute(
                "SELECT COUNT(*) AS count FROM sessions WHERE owner_id=? AND (folder IS NULL OR folder='')",
                (owner_id,),
            ).fetchone()
        counts = {str(row["folder"]): int(row["session_count"]) for row in rows}
        names = []
        seen = set()
        for name in registry + list(counts.keys()):
            cleaned = self._clean_folder_name(name)
            key = cleaned.casefold()
            if cleaned and key not in seen:
                names.append(cleaned)
                seen.add(key)
        return {
            "folders": [
                {"id": name, "name": name, "session_count": counts.get(name, 0)}
                for name in sorted(names, key=str.casefold)
            ],
            "unfiled_count": int(unfiled["count"] if unfiled else 0),
        }

    def _clean_folder_name(self, name):
        return " ".join(str(name or "").split())[:80]

    def create_chat_folder(self, name, color="", owner_id="admin"):
        cleaned = self._clean_folder_name(name)
        if not cleaned:
            raise ValueError("folder name is required")
        registry_key = f"chat_folder_registry:{owner_id}"
        registry = store.get_kv(registry_key, [])
        if not isinstance(registry, list):
            registry = []
        if cleaned.casefold() not in {str(item).casefold() for item in registry}:
            registry.append(cleaned)
            store.set_kv(registry_key, registry)
        return self.chat_folders(owner_id)

    def assign_session_folder(self, session_id, folder=None, owner_id="admin"):
        target_folder = self._clean_folder_name(folder)
        if target_folder.lower() in {"all", "unfiled"}:
            target_folder = ""
        with store._lock, store.connect() as conn:
            session = conn.execute("SELECT id FROM sessions WHERE id=? AND owner_id=?", (session_id, owner_id)).fetchone()
            if not session:
                raise ValueError("session missing")
            conn.execute(
                "UPDATE sessions SET folder=?, updated_at=? WHERE id=?",
                (target_folder, store.now(), session_id),
            )
            conn.commit()
        if target_folder:
            self.create_chat_folder(target_folder, owner_id=owner_id)
        return self.session(session_id, owner_id)

    def recent_messages(self, session_id, limit=10):
        with store._lock, store.connect() as conn:
            rows = conn.execute(
                "SELECT role,content,task_id,created_at FROM messages WHERE session_id=? AND evicted=0 ORDER BY created_at DESC LIMIT ?",
                (session_id, max(1, min(int(limit), 30))),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    async def subscribe(self, owner_id="admin"):
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        q = asyncio.Queue()
        self.listeners[q] = owner_id
        return q

    def start(
        self,
        objective,
        model="dry-run",
        skill="general",
        subagents=0,
        workspace_path=None,
        mode="chat",
        session_id=None,
        reasoning="auto",
        owner_id="admin",
        priority=0,
        scheduled_for=None,
        max_attempts=1,
        source_task_id=None,
    ):
        if session_id:
            self.session(session_id, owner_id)
        requested_mode = mode
        selected = model_registry.get_model(model)
        if mode != "chat" and selected and not model_providers.supports_agentic_tools(selected):
            mode = "chat"
        task = AgentTask(
            objective,
            model,
            skill,
            workspace_path=workspace_path,
            mode=mode,
            session_id=session_id,
            reasoning=reasoning,
            priority=priority,
            scheduled_for=scheduled_for,
            subagents=subagents,
            max_attempts=max_attempts,
            source_task_id=source_task_id,
        )
        if mode != requested_mode:
            task.log("Selected model does not support tool execution; switched to Chat mode before starting.")
            task.seen("tool_mode_fallback", {"model": model, "requestedMode": requested_mode, "resolvedMode": "chat"})
        task.owner_id = owner_id
        self._wire(task)
        self.tasks[task.id] = task
        self._persist_task(task)
        self._add_message(task.session_id, task.id, "user", objective)
        self._schedule_queued_task(task)
        return task

    async def run_tool_test(self, tool_id, args=None):
        definition = tool_relay.require_definition(tool_id)
        display = definition.get("display_name") or definition.get("displayName") or tool_id
        task = AgentTask(
            f"Test external tool: {display}",
            "dry-run",
            "tool-relay-test",
            workspace_path=workspace.get_active()["active_path"],
            mode="analyze",
        )
        self._wire(task)
        self.tasks[task.id] = task
        self._persist_task(task)
        self._add_message(task.session_id, task.id, "user", task.objective)
        task.status = "running"
        task.progress = 20
        task.log("tool test started")
        task.seen("tool_relay_test", {
            "toolId": tool_id,
            "toolName": display,
            "risk": definition.get("risk"),
            "permission": definition.get("permission_flag") or definition.get("permissionFlag") or "",
        })
        await self.emit(task)
        try:
            call_args = dict(args or {})
            call_args["_task_id"] = task.id
            result = await self.mcp.call_tool(tool_id, call_args)
            summary = tool_relay.summarize_result(tool_id, result)
            task.result = json.dumps(summary, indent=2)
            task.output("json", "Tool test result", task.result)
            self._add_message(task.session_id, task.id, "assistant", task.result)
            task.progress = 100
            task.status = "done"
            task.log("tool test done")
        except Exception as exc:
            task.status = "error"
            task.progress = 100
            task.result = str(exc)
            task.log(f"tool test failed: {exc}")
        finally:
            await self.emit(task)
        return self.task_detail(task.id)

    async def cancel(self, task_id):
        task = self.tasks.get(task_id)
        if not task:
            snapshot = self.get_task(task_id)
            if not snapshot:
                raise ValueError("task missing")
            with store._lock, store.connect() as conn:
                stamp = store.now()
                conn.execute(
                    "UPDATE tasks SET status='cancelled', completed_at=?, updated_at=? WHERE id=?",
                    (stamp, stamp, task_id),
                )
                conn.commit()
            store.create_inbox_event(
                snapshot.get("ownerId", "admin"),
                "task_cancelled",
                "Task cancelled",
                snapshot.get("objective", "")[:240],
                severity="warning",
                task_id=task_id,
                action_type="open_task",
                action_payload={"taskId": task_id},
            )
            return self.get_task(task_id)
        task.cancel_requested = True
        if task.status in {"queued", "running", "paused"}:
            task.status = "cancelled"
            task.completed_at = store.now()
            task.progress = min(task.progress, 99)
            task.log("cancel requested")
            await self.emit(task)
        return self.snapshot_task(task)

    async def pause(self, task_id):
        task = self.tasks.get(task_id)
        if task:
            task.paused_requested = True
            task.status = "paused"
            task.log("paused")
            await self.emit(task)
            return self.snapshot_task(task)
        with store._lock, store.connect() as conn:
            conn.execute("UPDATE tasks SET paused=1, status='paused', updated_at=? WHERE id=?", (store.now(), task_id))
            conn.commit()
        return self.get_task(task_id)

    async def resume(self, task_id):
        task = self.tasks.get(task_id)
        if task:
            task.paused_requested = False
            task.status = "running" if task.started_at else "queued"
            task.log("resumed")
            await self.emit(task)
            if task.status == "queued":
                self._schedule_queued_task(task)
            return self.snapshot_task(task)
        with store._lock, store.connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            raise ValueError("task missing")
        if row["status"] in {"done", "error", "cancelled"}:
            return self._snapshot_from_db(row)
        task = self._task_from_row(row)
        task.paused_requested = False
        task.status = "queued"
        self.tasks[task.id] = task
        await self.emit(task)
        self._schedule_queued_task(task)
        return self.snapshot_task(task)

    async def retry(self, task_id, owner_id="admin"):
        original = self.get_task(task_id, owner_id)
        if not original:
            raise ValueError("task missing")
        if original["status"] not in {"done", "error", "cancelled"}:
            raise ValueError("only completed tasks can be retried")
        return self.start(
            original["objective"],
            original["model"],
            original["skill"],
            original.get("subagents", 0),
            original["workspace"],
            original["mode"],
            original["sessionId"],
            reasoning=original.get("reasoning", "auto"),
            owner_id=owner_id,
            priority=original.get("priority", 0),
            max_attempts=original.get("maxAttempts", 1),
            source_task_id=task_id,
        )

    async def set_priority(self, task_id, priority, owner_id="admin"):
        task = self.tasks.get(task_id)
        if task and getattr(task, "owner_id", "admin") == owner_id:
            if task.status != "queued":
                raise ValueError("priority can only be changed while queued")
            task.priority = max(-10, min(int(priority or 0), 10))
            task.log(f"priority changed to {task.priority}")
            await self.emit(task)
            return self.snapshot_task(task)
        with store._lock, store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id=? AND owner_id=?",
                (task_id, owner_id),
            ).fetchone()
            if not row:
                raise ValueError("task missing")
            if row["status"] != "queued":
                raise ValueError("priority can only be changed while queued")
            value = max(-10, min(int(priority or 0), 10))
            conn.execute("UPDATE tasks SET priority=?, updated_at=? WHERE id=?", (value, store.now(), task_id))
            conn.commit()
        return self.get_task(task_id, owner_id)

    async def checkpoint(self, task):
        if task.cancel_requested or task.status == "cancelled":
            raise asyncio.CancelledError()
        while task.paused_requested:
            task.status = "paused"
            await self.emit(task)
            await asyncio.sleep(0.5)
            if task.cancel_requested:
                raise asyncio.CancelledError()
        if task.status == "paused":
            task.status = "running"
            await self.emit(task)

    async def run_task(self, task, subagents=0):
        task.started_at = task.started_at or store.now()
        task.attempt_count += 1
        task.status = "running"
        task.log("started")
        await self.emit(task)
        try:
            direct_chat = task.mode == "chat" and (not task.skill or task.skill == "general") and not subagents
            if direct_chat:
                task.progress = 18
                reply = await self.chat_reply(task)
                await self.checkpoint(task)
                reply = self.ground_chat_response(task, reply)
                task.result = reply
                task.output("markdown", "Chat reply", reply)
                task.progress = 100
                task.status = "done"
                memory.remember("session", {"objective": task.objective, "result": reply, "model": task.model}, task.owner_id)
                memory.suggest_from_task(task.id, task.objective, reply, task.workspace, task.owner_id)
                self._add_message(task.session_id, task.id, "assistant", reply)
                await self.compact_session(task)
                task.log("done")
            else:
                task.progress = 8
                plan = await self.plan(task)
                await self.checkpoint(task)
                task.seen("tool_plan", {"mode": task.mode, "skill": task.skill, "subagents": subagents})
                task.log("plan made")
                await self.emit(task)

                if subagents:
                    await self.spawn_subagents(task, plan, subagents)

                task.progress = 35
                work = await self.execute(task, plan)
                await self.checkpoint(task)
                task.log("executed")
                await self.emit(task)

                task.progress = 78
                reflection = await self.reflect(task, plan, work)
                await self.checkpoint(task)
                task.result = reflection
                task.output("markdown", "Task summary", reflection)
                task.progress = 100
                task.status = "done"
                memory.remember("session", {"objective": task.objective, "result": reflection, "model": task.model}, task.owner_id)
                memory.suggest_from_task(task.id, task.objective, reflection, task.workspace, task.owner_id)
                self._add_message(task.session_id, task.id, "assistant", reflection)
                await self.compact_session(task)
                task.log("done")
        except asyncio.CancelledError:
            task.status = "cancelled"
            task.result = "Cancelled."
            task.log("cancelled")
        except Exception as exc:
            task.status = "error"
            task.result = str(exc)
            task.log(f"error: {exc}")
        task.completed_at = store.now()
        await self.emit(task)

    def _tool_loop_budget(self, task):
        if task.mode == "code":
            return {"max_attempts": 80, "max_seconds": 900}
        return {"max_attempts": 15, "max_seconds": 180}

    def _test_loop_budget(self, task):
        # How many edit -> test -> fix reopens to attempt before giving up.
        # Distinct from _tool_loop_budget's tool-call ceiling; the reopens run
        # inside the same governed_chat loop, so they share its wall-clock budget
        # (they never get a fresh one) -- this is what keeps the test loop
        # "within Stage 4 budget".
        return 3

    def _parse_test_result(self, result):
        # Exit code is the reliable pass/fail signal (no fragile output scraping);
        # the trailing output is what the model gets to fix on the next attempt.
        if not isinstance(result, dict):
            return False, "The test command did not return a result."
        if result.get("timed_out"):
            return False, "The test command timed out.\n" + (result.get("output") or "")[-2000:]
        exit_code = result.get("exit_code")
        output = (result.get("output") or "")[-3000:]
        return exit_code == 0, f"exit code: {exit_code}\n{output}"

    async def _run_workspace_test(self, task, test_cmd):
        # Runs the workspace's configured test command via shell_exec (same
        # trust / allow_shell_execution gating as any shell tool). Returns
        # (passed, summary), or None when it couldn't run -- logged + traced so
        # "why didn't my tests run" is inspectable, never silent.
        try:
            result = await self.mcp.call_tool(
                "shell_exec",
                {"command": test_cmd, "workspace_path": task.workspace, "_task_id": task.id},
                on_log=task.log,
            )
        except PermissionError:
            task.log("test command configured but shell execution is not permitted here; skipping test loop")
            task.seen("test_skipped", {"reason": "shell_not_permitted"})
            return None
        except Exception as exc:
            task.log(f"test command failed to launch: {exc}")
            task.seen("test_skipped", {"reason": "launch_error"})
            return None
        passed, summary = self._parse_test_result(result)
        task.seen("test_run", {"passed": passed, "command": test_cmd})
        task.log(f"workspace tests {'passed' if passed else 'failed'}")
        return passed, summary

    def _bound_tool_loop_messages(self, task, model_key, messages, keep_recent=6, min_archive_chars=500):
        total_tokens = sum(context_governor.estimate_tokens(m.get("content")) for m in messages)
        if not context_governor.needs_compaction(model_key, total_tokens):
            return messages
        archived = 0
        boundary = max(0, len(messages) - keep_recent)
        for i in range(boundary):
            message = messages[i]
            if message.get("role") != "tool":
                continue
            content_str = str(message.get("content") or "")
            if len(content_str) < min_archive_chars:
                continue
            archive_id = store.new_id("arc")
            try:
                with store._lock, store.connect() as conn:
                    conn.execute(
                        "INSERT INTO eviction_log(id, session_id, kind, content, created_at) VALUES(?, ?, ?, ?, ?)",
                        (archive_id, task.session_id, "tool_result_archive", content_str, store.now()),
                    )
                    conn.commit()
            except Exception as exc:
                # Compaction is a token-budget optimization, not a correctness requirement -
                # skip this message rather than aborting an otherwise-working tool loop.
                task.log(f"context: could not archive tool result: {exc}")
                continue
            messages[i] = {
                **message,
                "content": (
                    f"[Tool result from '{message.get('name')}' archived to save context "
                    f"({len(content_str)} chars). Use archive_expand with archive_id '{archive_id}' "
                    "if the full output is needed again.]"
                ),
            }
            archived += 1
        if archived:
            task.log(f"context: archived {archived} older tool result(s) to stay within budget")
        return messages

    def _add_step(self, task, kind, name, status="running"):
        step = {"kind": kind, "name": name, "status": status, "at": time.time()}
        task.steps.append(step)
        task.steps = task.steps[-60:]
        self._trigger_broadcast(task.id)
        return step

    def _finish_step(self, task, step, status):
        step["status"] = status
        self._trigger_broadcast(task.id)

    def _stream_delta_handler(self, task):
        """Delta consumer handed to the provider layer. Invoked from the
        provider's worker thread — it only does GIL-safe field appends and
        _trigger_broadcast (which already marshals onto the event loop via
        call_soon_threadsafe). Broadcasts are throttled so token spray
        doesn't flood the SSE listeners with a snapshot per token."""
        state = {"last": 0.0}

        def on_delta(event):
            kind = event.get("type")
            if kind == "text":
                task.stream_text += event.get("text") or ""
            now = time.time()
            if kind == "tool_call" or now - state["last"] >= 0.15:
                state["last"] = now
                self._trigger_broadcast(task.id)

        return on_delta

    async def governed_chat(self, task, phase, role, sections, tools=None):
        model_key = self.phase_model(task, role)
        model = model_registry.get_model(model_key) or {}
        minimal_inference = phase == "chat" and model_compatibility.default_profile(model) == "minimal"
        if minimal_inference:
            # A reachable model that failed richer certification still gets a
            # useful escape hatch. No retrieved/untrusted data is present in
            # this profile, so wrap only the operator's text in a short direct-
            # answer instruction. Buffer until exposed thinking is cleaned.
            minimal_prompt = (
                "Answer the question directly. Output only the final answer. "
                "Do not show analysis, planning, brainstorming, or hidden reasoning.\n\n"
                f"Question: {task.objective}"
            )
            sections = [context_governor.section(
                "current_user_message", "", minimal_prompt, required=True, priority=0,
            )]
            task.seen("minimal_inference", {"model": model_key, "retrievalSkipped": True, "toolsAttached": False})
            task.log("minimal inference fallback selected; sending a direct-answer prompt without injected context")
            tools = None
        else:
            # Prepended here (not by each phase's own section list) so the
            # policy is present whenever retrieved content may be included.
            sections = [
                context_governor.section(
                    "untrusted_content_policy",
                    "Data-handling policy",
                    prompt_security.UNTRUSTED_CONTEXT_POLICY,
                    required=True,
                    priority=0,
                ),
                *sections,
            ]
        bundle = context_governor.compose_prompt(model_key, phase, sections)
        trace = bundle["trace"]
        task.seen("context_budget", trace)
        if trace.get("trimmed"):
            task.log(f"context trimmed: {', '.join(trace['trimmed'])}")
        if trace.get("omitted"):
            task.log(f"context omitted: {', '.join(trace['omitted'])}")

        messages = [{"role": "user", "content": bundle["prompt"]}]

        budget = self._tool_loop_budget(task)
        max_attempts = budget["max_attempts"]
        max_seconds = budget["max_seconds"]
        started_at = time.time()

        on_delta = None if minimal_inference else self._stream_delta_handler(task)
        phase_step = self._add_step(task, "phase", phase)

        # Stage 6 test loop: after the model finishes editing in a code-mode
        # execution phase, run the workspace's configured test command; on
        # failure feed the output back and reopen for a fix -- all inside this
        # same loop so the reopens share the one wall-clock budget rather than
        # each getting a fresh one. Bounded separately from the tool-call ceiling.
        test_cmd = None
        if phase == "execution" and task.mode == "code":
            test_cmd = (workspace.get_workspace_commands(task.workspace) or {}).get("test")
        test_edited = False
        test_reopens = 0
        test_budget = self._test_loop_budget(task)
        echo_retried = False

        try:
            for attempt in range(max_attempts):
                if time.time() - started_at > max_seconds:
                    task.log(f"tool loop stopped: {max_seconds}s time budget exceeded after {attempt} iteration(s)")
                    self._finish_step(task, phase_step, "error")
                    return f"Error: Tool loop time budget ({max_seconds}s) exceeded after {attempt} iteration(s)."

                messages = self._bound_tool_loop_messages(task, model_key, messages)
                task.stream_text = ""
                text, tool_calls = await _chat(model_key, messages, tools=tools, on_delta=on_delta, reasoning=getattr(task, "reasoning", "auto"))

                if minimal_inference and not tool_calls:
                    text = model_compatibility.clean_minimal_response(text)

                if (
                    phase == "chat"
                    and not tool_calls
                    and not echo_retried
                    and model_compatibility.looks_like_prompt_echo(text, messages[-1].get("content", ""))
                ):
                    echo_retried = True
                    task.stream_text = ""
                    task.seen("prompt_echo_recovery", {"model": model_key, "profile": "light"})
                    task.log("prompt echo detected; retrying once with lightweight context")
                    try:
                        model_registry.record_prompt_echo(model_key)
                    except Exception as exc:
                        task.log(f"prompt echo downgrade could not be saved: {exc}")
                    messages = [{
                        "role": "user",
                        "content": (
                            "You are Rasputin, a helpful local assistant. Answer the operator's request "
                            "directly. Do not repeat or describe this instruction.\n\n"
                            f"Operator request: {task.objective}"
                        ),
                    }]
                    tools = None
                    continue

                if text or tool_calls:
                    messages.append({
                        "role": "assistant",
                        "content": text,
                        "tool_calls": tool_calls
                    })

                if not tool_calls:
                    # Local chat runtimes may reject a tools-bearing request;
                    # providers.chat_sync deliberately retries without tools so
                    # ordinary conversation still works. In an execution phase,
                    # however, accepting the resulting prose as "done" is a
                    # dangerous silent no-op: no requested tool could have run.
                    # Fail the task visibly and preserve an inspectable trace.
                    if phase == "execution" and tools and model_providers.tools_unavailable(model_key):
                        message = (
                            f"Tools are unavailable for model '{model_key}'. Its local runtime rejected "
                            "tool definitions, so this agentic task stopped instead of treating a plain "
                            "chat response as completed work. Redeploy the model with its matching tool-call "
                            "parser or choose a tool-capable model."
                        )
                        task.seen("tools_unavailable", {"model": model_key, "phase": phase})
                        task.log(message)
                        self._finish_step(task, phase_step, "error")
                        raise RuntimeError(message)
                    if test_cmd and test_edited and test_reopens < test_budget:
                        outcome = await self._run_workspace_test(task, test_cmd)
                        if outcome is not None and not outcome[0]:
                            test_reopens += 1
                            test_edited = False
                            messages.append({
                                "role": "user",
                                "content": (
                                    "The workspace test command is still failing after your changes "
                                    f"(fix attempt {test_reopens}/{test_budget}). Fix the code so the "
                                    "tests pass, then stop.\n\n" + outcome[1]
                                ),
                            })
                            task.log(f"tests failing — reopening execution to fix (attempt {test_reopens}/{test_budget})")
                            continue
                    self._finish_step(task, phase_step, "done")
                    return text

                for tc in tool_calls:
                    task.log(f"tool: {tc['name']}")
                    step = self._add_step(task, "tool", tc["name"])
                    try:
                        args = tc.get("args", {})
                        args["_task_id"] = task.id
                        result = await self.mcp.call_tool(tc["name"], args, on_log=task.log)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "name": tc["name"],
                            "content": prompt_security.untrusted_context_message(
                                f"tool result: {tc['name']}",
                                json.dumps(result, ensure_ascii=False),
                            )
                        })
                        self._finish_step(task, step, "done")
                        if tc["name"] in FILE_MUTATING_TOOLS and not (
                            isinstance(result, dict) and result.get("approval_id")
                        ):
                            test_edited = True
                    except Exception as exc:
                        task.log(f"tool error: {exc}")
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "name": tc["name"],
                            "content": f"Error executing {tc['name']}: {exc}"
                        })
                        self._finish_step(task, step, "error")

            self._finish_step(task, phase_step, "error")
            return f"Error: Maximum tool loop iterations ({max_attempts}) exceeded."
        finally:
            task.stream_text = ""

    async def chat_reply(self, task):
        try:
            session_data = self.session(task.session_id).get("session", {})
        except ValueError:
            session_data = {}
        session_summary = session_data.get("summary", "")
        model_key = self.phase_model(task, "main")
        model = model_registry.get_model(model_key) or {}
        prompt_profile = model_compatibility.default_profile(model)
        light_context = prompt_profile in {"light", "minimal"}
        previous_messages = self.recent_messages(task.session_id, 4 if light_context else 10)
        if light_context:
            recall = {"items": []}
            context = {"hits": []}
            graph = {"edges": []}
            workspace_context = {"tree": None, "searches": [], "snippets": []}
            task.seen("adaptive_context", {"model": model_key, "profile": "light", "retrievalSkipped": True})
            task.log("lightweight Chat context selected from the model compatibility profile")
        else:
            recall = memory.search(task.objective, 5)
            context = await self.mcp.call_tool("rag_search", {"query": task.objective, "limit": 3, "workspace_path": task.workspace, "_task_id": task.id})
            graph = await self.mcp.call_tool("graph_search", {"query": task.objective, "limit": 4, "_task_id": task.id})
            workspace_context = await self.workspace_context(task)
        task.sources = [{"source": h["source"], "score": h["score"], "chunk": h["chunk"]} for h in context.get("hits", [])]
        task.graph = self.compact_graph_edges(graph)
        task.seen("memory_recall", {"items": len(recall.get("items", []))})
        task.seen("rag_context", {"hits": len(context.get("hits", [])), "workspace": task.workspace})
        task.seen("graph_context", {"edges": len(graph.get("edges", []))})
        if task.sources:
            task.log(f"rag hits: {len(task.sources)}")
        if task.graph:
            task.log(f"graph hits: {len(task.graph)}")
        sections = [
            context_governor.section(
                "assistant_identity",
                "Assistant",
                "You are Rasputin, the user's local AI workbench assistant. Reply naturally and directly. Do not use a repeated greeting unless the user's message is only a greeting.",
                required=True,
                priority=0,
            ),
            context_governor.section("current_user_message", "Current user message", task.objective, required=True, priority=0, min_chars=500),
            context_governor.section("compacted_history", "Compacted earlier history", session_summary, priority=5, min_chars=180),
            context_governor.section("previous_conversation", "Previous conversation", self.format_conversation(previous_messages, task.id), priority=10, min_chars=220),
            context_governor.section("workspace", "Workspace", "" if light_context else task.workspace, required=not light_context, priority=0),
            context_governor.section("memory_recall", "Relevant memory recall", "" if light_context else self.format_memory(recall), priority=20, min_chars=180),
            context_governor.section("rag_sources", "Actual local RAG context", "" if light_context else self.format_context(context), priority=25, min_chars=240),
            context_governor.section("graph_evidence", "Actual local graph context", "" if light_context else self.format_graph(graph), priority=30, min_chars=180),
            context_governor.section("file_snippets", "Approved workspace file snippets", "" if light_context else self.format_workspace_snippets(workspace_context), priority=35, min_chars=260),
            context_governor.section("workspace_tree", "Approved workspace file listing", "" if light_context else self.format_workspace_tree(workspace_context), priority=70, min_chars=180),
            context_governor.section(
                "rules",
                "Rules",
                "- Do not claim you browsed the web, searched social media, emailed, called, scheduled meetings, contacted people, edited files, or used external tools unless the context above proves that happened.\n"
                "- If workspace file context includes file paths or snippets, use those local paths as evidence. If a file is listed but not included as a snippet, say you can see the path but have not read its contents.\n"
                "- If there are no local matches, do not invent file sources. You can still answer from general model knowledge.\n"
                "- If the user asks for an action that requires a tool or permission not shown here, say what is missing instead of pretending it happened.\n"
                "- Keep the reply useful and conversational. Do not write an internal plan unless the user asked for one.",
                required=True,
                priority=0,
            ),
        ]
        # Plain Chat never needs tool schemas. Agentic modes attach them in
        # their planning/execution phases after capability routing approves the
        # model, avoiding wasted context and a failed retry on chat-only GGUFs.
        return await self.governed_chat(task, "chat", "main", sections, tools=None)

    def ground_chat_response(self, task, text):
        if task.sources or task.graph:
            return text
        lowered = (text or "").lower()
        suspect = [
            "sources used included", "the sources used", "i searched", "i researched", "i reached out",
            "we reached out", "contacted potential", "scheduled meetings", "followed up with leads",
            "research and outreach efforts", "identified through the research",
        ]
        if not any(phrase in lowered for phrase in suspect):
            return text
        task.log("grounding guard blocked unproven tool claims")
        return (
            "I need to correct that: this run did not actually use web research, social media, "
            "email, calls, meetings, or external outreach. No local sources were retrieved either. "
            "I can help draft a plan or analyze approved local files, but I should not label that as completed work."
        )

    async def plan(self, task):
        recall = memory.search(task.objective, 5)
        context = await self.mcp.call_tool("rag_search", {"query": task.objective, "limit": 3, "workspace_path": task.workspace, "_task_id": task.id})
        graph = await self.mcp.call_tool("graph_search", {"query": task.objective, "limit": 4, "_task_id": task.id})
        task.sources = [{"source": h["source"], "score": h["score"], "chunk": h["chunk"]} for h in context.get("hits", [])]
        task.graph = self.compact_graph_edges(graph)
        task.seen("memory_recall", {"items": len(recall.get("items", []))})
        task.seen("rag_context", {"hits": len(context.get("hits", [])), "workspace": task.workspace})
        task.seen("graph_context", {"edges": len(graph.get("edges", []))})
        sections = [
            context_governor.section("planner_instruction", "Instruction", "Plan this task in 3-6 steps.", required=True, priority=0),
            context_governor.section("mode", "Mode", task.mode, required=True, priority=0),
            context_governor.section("current_user_message", "Task", task.objective, required=True, priority=0, min_chars=500),
            context_governor.section("workspace", "Workspace", task.workspace, required=True, priority=0),
            context_governor.section("memory_recall", "Relevant memory recall", self.format_memory(recall), priority=20, min_chars=180),
            context_governor.section("rag_sources", "Local RAG context", self.format_context(context), priority=25, min_chars=240),
            context_governor.section("graph_evidence", "Local graph context", self.format_graph(graph), priority=30, min_chars=180),
            context_governor.section(
                "rules",
                "Rules",
                "- Available evidence is only the memory, local RAG, and graph context above.\n"
                "- Do not claim web research, outreach, email, phone calls, social media, or file changes were completed.\n"
                "- If the task needs unavailable tools or approvals, include that as a step.",
                required=True,
                priority=0,
            ),
        ]
        return await self.governed_chat(task, "planning", "planner", sections, tools=tool_relay.TOOL_DEFINITIONS)

    async def execute(self, task, plan):
        if task.skill and task.skill != "general":
            task.log(f"skill: {task.skill}")
            try:
                from backend.core.sandbox import run_skill_in_sandbox
                from backend.mcp.skills import get_skill
                skill_data = get_skill(task.skill)
                if skill_data and skill_data.get("content"):
                    return await run_skill_in_sandbox(task.skill, skill_data["content"], task.objective, json.dumps(plan), task.log)
                else:
                    task.log("skill code missing, using model")
            except Exception as e:
                task.log(f"skill missing or failed: {str(e)}, using model")

        sections = [
            context_governor.section("executor_instruction", "Instruction", "Execute this plan. Use tools to gather information and make changes as needed. Use concise output.", required=True, priority=0),
            context_governor.section("mode", "Mode", task.mode, required=True, priority=0),
            context_governor.section("current_user_message", "Task", task.objective, required=True, priority=0, min_chars=500),
            context_governor.section("workspace", "Workspace", task.workspace, required=True, priority=0),
            context_governor.section("plan", "Plan", plan, priority=15, min_chars=260),
            context_governor.section(
                "rules",
                "Rules",
                "- Do not pretend to browse, contact people, schedule meetings, or mutate files.\n"
                "- Use only the local context shown here and the plan above.\n"
                "- If a real-world action cannot be completed from the available tools, say so plainly.",
                required=True,
                priority=0,
            ),
        ]
        return await self.governed_chat(task, "execution", self.execution_role(task), sections, tools=tool_relay.TOOL_DEFINITIONS)

    async def reflect(self, task, plan, work):
        work_str = str(work)
        if len(work_str) > 4096:
            archive_id = store.new_id("arc")
            with store._lock, store.connect() as conn:
                conn.execute(
                    "INSERT INTO eviction_log(id, session_id, kind, content, created_at) VALUES(?, ?, ?, ?, ?)",
                    (archive_id, task.session_id, "tool_archive", work_str, store.now())
                )
                conn.commit()
            work_str = f"{work_str[:1500]}...\n\n[Full result archived ({len(work_str)} chars). Use 'archive_expand' with archive_id '{archive_id}' to retrieve.]"

        sections = [
            context_governor.section("reflection_instruction", "Instruction", "Write the final user-facing answer for this task.", required=True, priority=0),
            context_governor.section("current_user_message", "Task", task.objective, required=True, priority=0, min_chars=500),
            context_governor.section("rag_sources", "Actual local sources", self.format_task_sources(task.sources), priority=20, min_chars=180),
            context_governor.section("graph_evidence", "Actual graph evidence", self.format_task_graph(task.graph), priority=25, min_chars=180),
            context_governor.section("work", "Work", work_str, priority=30, min_chars=300),
            context_governor.section("plan", "Plan", plan, priority=50, min_chars=220),
            context_governor.section(
                "rules",
                "Rules",
                "- Do not list generic source categories like forums, social media, databases, emails, or contacts unless they appear in actual local sources or graph evidence.\n"
                "- Do not claim outreach, meetings, web research, file edits, or other external actions were completed unless the work explicitly proves it.\n"
                "- If there were no actual local sources, say that no local sources were used only when source usage matters to the answer.\n"
                "- Be direct and useful; avoid fake completion summaries.",
                required=True,
                priority=0,
            ),
        ]
        return await self.governed_chat(task, "reflection", "summarizer", sections)

    def phase_model(self, task, role):
        if task.model == "dry-run":
            return "dry-run"
        return model_registry.key_for_task(role, task.model)

    def execution_role(self, task):
        if task.mode == "code":
            return "coder"
        if task.mode == "research":
            return "researcher"
        return "executor"

    async def compact_session(self, task):
        with store._lock, store.connect() as conn:
            rows = conn.execute(
                "SELECT id, role, content FROM messages WHERE session_id=? AND evicted=0 ORDER BY created_at ASC",
                (task.session_id,),
            ).fetchall()
        messages = [dict(row) for row in rows]
        if len(messages) <= 6:
            return None
            
        total_tokens = sum(context_governor.estimate_tokens(m["content"]) for m in messages)
        if not context_governor.needs_compaction(task.model, total_tokens):
            return None
            
        older = messages[:-4]
        evicted_ids = [m["id"] for m in older]
        
        prompt_text = "Please summarize the following conversation history into a dense, informative checkpoint. Capture all key decisions, code snippets, tool outputs, and facts so the AI does not lose context.\n\n"
        for m in older:
            prompt_text += f"{m['role'].upper()}: {m['content']}\n\n"
            
        model_key = self.phase_model(task, "summarizer")
        try:
            summary = await _chat(model_key, [{"role": "user", "content": prompt_text}])
        except Exception as e:
            task.log(f"compaction summary failed: {e}")
            return None
            
        with store._lock, store.connect() as conn:
            session = conn.execute("SELECT summary FROM sessions WHERE id=?", (task.session_id,)).fetchone()
            existing_summary = session["summary"] if session else ""
            
            archive_pointers = []
            for m in older:
                conn.execute(
                    "INSERT INTO eviction_log(id, session_id, kind, content, created_at) VALUES(?, ?, ?, ?, ?)",
                    (m["id"], task.session_id, "message_archive", m["content"], store.now())
                )
                archive_pointers.append(f"{m['role']}: '{m['id']}'")
                
            pointers_str = ", ".join(archive_pointers)
            new_summary = f"{existing_summary}\n\n[Checkpoint]: {summary}\n[Archived exact messages: {pointers_str}. Use 'archive_expand' with archive_id to retrieve full text.]".strip()
            
            conn.execute("UPDATE sessions SET summary=?, updated_at=? WHERE id=?", (new_summary, store.now(), task.session_id))
            placeholders = ",".join("?" * len(evicted_ids))
            conn.execute(f"UPDATE messages SET evicted=1 WHERE id IN ({placeholders})", evicted_ids)
            conn.commit()
            
        asyncio.create_task(memory.consolidate_long_term_memory(task.session_id, older))
            
        task.log(f"compacted {len(evicted_ids)} messages to save tokens")
        return new_summary

    def needs_workspace_context(self, task):
        text = str(task.objective or "").lower()
        if task.mode in {"analyze", "code", "organize"}:
            return True
        return any(term in text for term in WORKSPACE_CONTEXT_TERMS)

    def needs_file_snippets(self, task):
        text = str(task.objective or "").lower()
        return task.mode in {"analyze", "code"} or any(term in text for term in FILE_SNIPPET_TERMS)

    def workspace_search_terms(self, task):
        text = str(task.objective or "")
        candidates = []
        candidates.extend(re.findall(r"[\w.-]+\.[A-Za-z0-9]{1,8}", text))
        candidates.extend(re.findall(r"['\"]([^'\"]{3,80})['\"]", text))
        if task.mode in {"analyze", "code", "organize"}:
            candidates.extend(re.findall(r"\b[A-Za-z][A-Za-z0-9_-]{5,}\b", text)[:3])
        seen = set()
        terms = []
        for candidate in candidates:
            clean = " ".join(str(candidate or "").split())[:80]
            key = clean.casefold()
            if clean and key not in seen:
                terms.append(clean)
                seen.add(key)
        return terms[:5]

    async def workspace_context(self, task):
        if not self.needs_workspace_context(task):
            return {"tree": None, "searches": [], "snippets": []}
        try:
            tree = await self.mcp.call_tool("fs_tree", {
                "path": ".",
                "workspace_path": task.workspace,
                "max_items": 90,
                "max_depth": 3,
                "_task_id": task.id,
            })
            items = tree.get("items", [])
            task.seen("workspace_tree", {
                "workspace": task.workspace,
                "items": len(items),
                "truncated": bool(tree.get("truncated")),
            })
            task.log(f"workspace files visible: {len(items)}")
            searches = []
            for term in self.workspace_search_terms(task):
                try:
                    found = await self.mcp.call_tool("fs_search", {
                        "query": term,
                        "workspace_path": task.workspace,
                        "max_results": 12,
                        "_task_id": task.id,
                    })
                    searches.append(found)
                    task.seen("workspace_search", {
                        "query": term,
                        "matches": len(found.get("matches") or []),
                        "truncated": bool(found.get("truncated")),
                    })
                except Exception as exc:
                    searches.append({"query": term, "matches": [], "error": str(exc)})
            if searches:
                task.log(f"workspace searches: {len(searches)}")
            snippets = []
            if self.needs_file_snippets(task):
                matched_files = []
                for search in searches:
                    matched_files.extend([
                        item for item in search.get("matches", [])
                        if item.get("kind") == "file"
                        and Path(str(item.get("path") or "")).suffix.lower() in TEXT_FILE_EXTENSIONS
                        and int(item.get("size_bytes") or item.get("sizeBytes") or 0) <= 50000
                    ])
                files = [
                    item for item in items
                    if item.get("kind") == "file"
                    and Path(str(item.get("path") or "")).suffix.lower() in TEXT_FILE_EXTENSIONS
                    and int(item.get("bytes") or 0) <= 50000
                ]
                seen_paths = set()
                ordered_files = []
                for item in matched_files + files:
                    path = item.get("path")
                    if path and path not in seen_paths:
                        ordered_files.append(item)
                        seen_paths.add(path)
                for item in ordered_files[:5]:
                    try:
                        read = await self.mcp.call_tool("fs_read", {
                            "path": item.get("path"),
                            "workspace_path": task.workspace,
                            "max_chars": 2500,
                            "_task_id": task.id,
                        })
                        snippets.append({
                            "path": read.get("relativePath") or item.get("path"),
                            "content": read.get("content", ""),
                            "truncated": bool(read.get("truncated")),
                        })
                    except Exception as exc:
                        snippets.append({"path": item.get("path"), "error": str(exc)})
                if snippets:
                    task.log(f"workspace files read: {len(snippets)}")
            return {"tree": tree, "searches": searches, "snippets": snippets}
        except Exception as exc:
            task.seen("workspace_context_error", {"workspace": task.workspace, "error": str(exc)})
            task.log(f"workspace context unavailable: {exc}")
            return {"tree": None, "searches": [], "snippets": [], "error": str(exc)}

    def format_conversation(self, messages, current_task_id=None):
        lines = []
        for message in messages:
            if message.get("task_id") == current_task_id and message.get("role") == "user":
                continue
            content = " ".join(str(message.get("content") or "").split())
            if not content:
                continue
            if len(content) > 420:
                content = content[:420].rstrip() + "..."
            role = "User" if message.get("role") == "user" else "Rasputin"
            lines.append(f"{role}: {content}")
        return "\n".join(lines[-8:]) if lines else "No previous messages in this chat."

    def format_workspace_context(self, context):
        tree = self.format_workspace_tree(context)
        search = self.format_workspace_search(context)
        snippets = self.format_workspace_snippets(context)
        if tree.startswith("Workspace context unavailable"):
            return tree
        if tree.startswith("No workspace") and search.startswith("No workspace") and snippets.startswith("No workspace"):
            return "No workspace file inspection was requested or available."
        return "\n\n".join(part for part in [search, tree, snippets] if not part.startswith("No workspace"))

    def format_workspace_tree(self, context):
        if context.get("error"):
            return f"Workspace context unavailable: {context['error']}"
        tree = context.get("tree") or {}
        items = tree.get("items") or []
        if not items:
            return "No workspace file listing was requested or available."
        lines = []
        lines.append("Visible files and folders:")
        for item in items[:55]:
            prefix = "  " * min(int(item.get("depth") or 0), 4)
            kind = "folder" if item.get("kind") == "dir" else "file"
            size = f" ({item.get('bytes')} bytes)" if kind == "file" else ""
            lines.append(f"- {prefix}{kind}: {item.get('path')}{size}")
        if tree.get("truncated"):
            lines.append("- [listing truncated]")
        return "\n".join(lines)

    def format_workspace_search(self, context):
        searches = context.get("searches") or []
        if not searches:
            return "No workspace file search was requested or available."
        lines = ["Workspace file search:"]
        for search in searches[:5]:
            query = search.get("query") or ""
            if search.get("error"):
                lines.append(f"- {query}: search failed: {search['error']}")
                continue
            matches = search.get("matches") or []
            if not matches:
                lines.append(f"- {query}: no matches")
                continue
            lines.append(f"- {query}: {len(matches)} match(es)")
            for match in matches[:6]:
                lines.append(f"  - {match.get('kind')}: {match.get('path')} ({match.get('match_type')}, score {match.get('score')})")
        return "\n".join(lines)

    def format_workspace_snippets(self, context):
        if context.get("error"):
            return f"Workspace context unavailable: {context['error']}"
        snippets = context.get("snippets") or []
        if not snippets:
            return "No workspace file snippets were requested or available."
        lines = ["Read snippets:"]
        for snippet in snippets[:5]:
            path = snippet.get("path") or "unknown"
            if snippet.get("error"):
                lines.append(f"[{path}] read failed: {snippet['error']}")
                continue
            content = str(snippet.get("content") or "")[:900]
            marker = " [truncated]" if snippet.get("truncated") else ""
            lines.append(f"[{path}{marker}]\n{content}")
        return prompt_security.untrusted_context_message("workspace file contents", "\n".join(lines))

    def format_context(self, context, max_items=3, max_chars=450):
        hits = context.get("hits", [])
        if not hits:
            return "No local matches."
        lines = []
        for h in hits[:max_items]:
            lines.append(f"[{h['source']}#{h['chunk']} score={h['score']}]\n{h['text'][:max_chars]}")
        return prompt_security.untrusted_context_message("local RAG search results", "\n\n".join(lines))

    def format_graph(self, graph):
        edges = graph.get("edges", [])
        if not edges:
            return "No graph matches."
        lines = []
        for edge in edges[:10]:
            suffix = f" ({edge.get('why')})" if edge.get("why") else ""
            lines.append(f"{edge['source']} --{edge['relation']}--> {edge['target']}{suffix}")
        return prompt_security.untrusted_context_message("workspace knowledge graph", "\n".join(lines))

    def format_memory(self, recall):
        items = recall.get("items", [])
        if not items:
            return "No relevant saved memory."
        lines = []
        for item in items[:4]:
            content = str(item.get("content"))[:420]
            lines.append(f"- {item.get('kind')}: {content}")
        return prompt_security.untrusted_context_message("saved memory", "\n".join(lines))

    def format_task_sources(self, sources):
        if not sources:
            return "No local RAG sources were retrieved."
        return "\n".join(f"{source.get('source')}#{source.get('chunk')} score={source.get('score')}" for source in sources[:10])

    def format_task_graph(self, graph):
        if not graph:
            return "No graph evidence was retrieved."
        lines = []
        for edge in graph[:10]:
            suffix = f" ({edge.get('why')})" if edge.get("why") else ""
            lines.append(f"{edge.get('source')} --{edge.get('relation')}--> {edge.get('target')}{suffix}")
        return prompt_security.untrusted_context_message("workspace knowledge graph", "\n".join(lines))

    def compact_graph_edges(self, graph):
        out = []
        for edge in graph.get("edges", [])[:8]:
            out.append({
                "source": edge.get("source"),
                "sourceKind": edge.get("source_kind") or edge.get("sourceKind"),
                "relation": edge.get("relation"),
                "target": edge.get("target"),
                "targetKind": edge.get("target_kind") or edge.get("targetKind"),
                "confidence": edge.get("confidence"),
                "why": edge.get("why"),
                "evidence": self.compact_graph_evidence(edge.get("evidence")),
            })
        return out

    def compact_graph_evidence(self, evidence):
        out = []
        for item in (evidence or [])[:2]:
            citation = item.get("citation") or {}
            out.append({
                "source": item.get("source"),
                "path": item.get("path") or citation.get("path"),
                "chunk": item.get("chunk") if item.get("chunk") is not None else citation.get("chunk"),
                "citation": citation,
                "snippet": str(item.get("snippet") or "")[:260],
            })
        return out

    async def spawn_subagents(self, parent, plan, count):
        parent.log(f"spawning {count} sub-agent(s)")
        for i in range(count):
            child = AgentTask(
                f"Subtask {i + 1} for: {parent.objective}",
                parent.model,
                parent.skill,
                parent.id,
                parent.workspace,
                parent.mode,
            )
            self._wire(child)
            self.tasks[child.id] = child
            self._persist_task(child)
            self._add_message(child.session_id, child.id, "user", child.objective)
            asyncio.create_task(self.run_task(child, subagents=0))
        await asyncio.sleep(0.1)
