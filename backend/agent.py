import asyncio
import importlib
import json
import re
import time
import uuid
from pathlib import Path

from .mcp_layer import McpLayer
from .models import chat
from . import context_governor
from . import memory
from . import model_registry
from . import runtime_store as store
from . import security
from . import tool_relay
from . import workspace

TEXT_FILE_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css",
    ".json", ".csv", ".yml", ".yaml", ".toml", ".ini", ".cfg",
}
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
    def __init__(self, objective, model, skill, parent_id=None, workspace_path=None, mode="chat", task_id=None, session_id=None):
        self.id = task_id or str(uuid.uuid4())[:8]
        self.session_id = session_id or store.new_id("sess")
        self.objective = objective
        self.model = model
        self.skill = skill or "general"
        self.mode = mode or "chat"
        self.parent_id = parent_id
        self.status = "queued"
        self.progress = 0
        self.logs = []
        self.result = ""
        self.sources = []
        self.graph = []
        self.outputs = []
        self.trace = []
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
        self.listeners = set()
        self.mcp = McpLayer()
        self._memory_export_task = None
        self._mark_interrupted()

    def _mark_interrupted(self):
        with store._lock, store.connect() as conn:
            conn.execute(
                "UPDATE tasks SET status='paused', paused=1, updated_at=? WHERE status IN ('queued','running')",
                (store.now(),),
            )
            conn.commit()

    def _wire(self, task):
        task.event_sink = self.record_event
        task.output_sink = self.record_output
        task.trace_sink = self.record_trace

    def record_event(self, task_id, kind, detail):
        with store._lock, store.connect() as conn:
            conn.execute(
                "INSERT INTO task_events(task_id,kind,detail,created_at) VALUES(?,?,?,?)",
                (task_id, kind, store._json(detail), store.now()),
            )
            conn.commit()

    def record_trace(self, task_id, kind, detail):
        with store._lock, store.connect() as conn:
            conn.execute(
                "INSERT INTO agent_traces(task_id,kind,detail,created_at) VALUES(?,?,?,?)",
                (task_id, kind, store._json(detail), store.now()),
            )
            conn.commit()

    def record_output(self, task_id, kind, title, content):
        with store._lock, store.connect() as conn:
            conn.execute(
                "INSERT INTO outputs(id,task_id,kind,title,content,created_at) VALUES(?,?,?,?,?,?)",
                (store.new_id("out"), task_id, kind, title, str(content or ""), store.now()),
            )
            conn.commit()

    def _persist_session(self, task):
        stamp = store.now()
        title = task.objective.strip().splitlines()[0][:140] or "Rasputin session"
        with store._lock, store.connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions(id,title,status,workspace,model,mode,skill,summary,created_at,updated_at,folder)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
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
                (task.session_id, title, "active", task.workspace, task.model, task.mode, task.skill, "", stamp, stamp, ""),
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
        with store._lock, store.connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks(id,session_id,parent_id,objective,model,skill,mode,status,progress,result,workspace,permission_snapshot,paused,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET status=excluded.status, progress=excluded.progress, result=excluded.result, paused=excluded.paused, updated_at=excluded.updated_at
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
                ),
            )
            conn.commit()

    async def emit(self, task):
        self._persist_task(task)
        data = self.snapshot_task(task)
        dead = []
        for q in self.listeners:
            try:
                await q.put(data)
            except Exception:
                dead.append(q)
        for q in dead:
            self.listeners.discard(q)

    def snapshot_task(self, task):
        return {
            "id": task.id,
            "sessionId": task.session_id,
            "objective": task.objective,
            "model": task.model,
            "skill": task.skill,
            "mode": task.mode,
            "status": task.status,
            "progress": task.progress,
            "logs": task.logs[-80:],
            "result": task.result,
            "sources": task.sources,
            "graph": task.graph,
            "outputs": task.outputs,
            "trace": task.trace[-80:],
            "permissionSnapshot": task.permission_snapshot,
            "workspace": task.workspace,
            "parentId": task.parent_id,
            "paused": task.paused_requested or task.status == "paused",
            "createdAt": task.created_at,
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
            "permissionSnapshot": store._loads(task["permission_snapshot"], {}),
            "workspace": task["workspace"],
            "parentId": task["parent_id"],
            "paused": bool(task["paused"]),
            "createdAt": task["created_at"],
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

    def all_tasks(self, limit=100, include_details=False):
        store.init_db()
        limit = max(1, min(int(limit or 100), 500))
        with store._lock, store.connect() as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._snapshot_from_db(row, include_details=include_details) for row in rows]

    def get_task(self, task_id):
        task = self.tasks.get(task_id)
        if task:
            return self.snapshot_task(task)
        with store._lock, store.connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return self._snapshot_from_db(row) if row else None

    def task_detail(self, task_id):
        task = self.get_task(task_id)
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

    def sessions(self, limit=100):
        with store._lock, store.connect() as conn:
            rows = conn.execute("SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (max(1, min(int(limit), 500)),)).fetchall()
        return {"sessions": [dict(row) for row in rows]}

    def session(self, session_id):
        with store._lock, store.connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            if not row:
                raise ValueError("session missing")
            messages = conn.execute(
                "SELECT role,content,created_at,task_id FROM messages WHERE session_id=? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
            tasks = conn.execute("SELECT * FROM tasks WHERE session_id=? ORDER BY created_at ASC", (session_id,)).fetchall()
        return {"session": dict(row), "messages": [dict(m) for m in messages], "tasks": [self._snapshot_from_db(t) for t in tasks]}

    def create_session(self, title="New chat", workspace=".", model="dry-run", mode="chat", skill="general", folder=""):
        stamp = store.now()
        session_id = store.new_id("sess")
        clean_title = str(title or "New chat").strip()[:140] or "New chat"
        with store._lock, store.connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions(id,title,status,workspace,model,mode,skill,summary,created_at,updated_at,folder)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
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
                ),
            )
            conn.commit()
        return self.session(session_id)

    def chat_folders(self):
        registry = store.get_kv("chat_folder_registry", [])
        if not isinstance(registry, list):
            registry = []
        with store._lock, store.connect() as conn:
            rows = conn.execute(
                "SELECT folder, COUNT(*) AS session_count FROM sessions WHERE folder IS NOT NULL AND folder!='' GROUP BY folder"
            ).fetchall()
            unfiled = conn.execute(
                "SELECT COUNT(*) AS count FROM sessions WHERE folder IS NULL OR folder=''"
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

    def create_chat_folder(self, name, color=""):
        cleaned = self._clean_folder_name(name)
        if not cleaned:
            raise ValueError("folder name is required")
        registry = store.get_kv("chat_folder_registry", [])
        if not isinstance(registry, list):
            registry = []
        if cleaned.casefold() not in {str(item).casefold() for item in registry}:
            registry.append(cleaned)
            store.set_kv("chat_folder_registry", registry)
        return self.chat_folders()

    def assign_session_folder(self, session_id, folder=None):
        target_folder = self._clean_folder_name(folder)
        if target_folder.lower() in {"all", "unfiled"}:
            target_folder = ""
        with store._lock, store.connect() as conn:
            session = conn.execute("SELECT id FROM sessions WHERE id=?", (session_id,)).fetchone()
            if not session:
                raise ValueError("session missing")
            conn.execute(
                "UPDATE sessions SET folder=?, updated_at=? WHERE id=?",
                (target_folder, store.now(), session_id),
            )
            conn.commit()
        if target_folder:
            self.create_chat_folder(target_folder)
        return self.session(session_id)

    def recent_messages(self, session_id, limit=10):
        with store._lock, store.connect() as conn:
            rows = conn.execute(
                "SELECT role,content,task_id,created_at FROM messages WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
                (session_id, max(1, min(int(limit), 30))),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    async def subscribe(self):
        q = asyncio.Queue()
        self.listeners.add(q)
        return q

    def start(self, objective, model="dry-run", skill="general", subagents=0, workspace_path=None, mode="chat", session_id=None):
        task = AgentTask(objective, model, skill, workspace_path=workspace_path, mode=mode, session_id=session_id)
        self._wire(task)
        self.tasks[task.id] = task
        self._persist_task(task)
        self._add_message(task.session_id, task.id, "user", objective)
        asyncio.create_task(self.run_task(task, subagents=subagents))
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
                conn.execute("UPDATE tasks SET status='cancelled', updated_at=? WHERE id=?", (store.now(), task_id))
                conn.commit()
            return self.get_task(task_id)
        task.cancel_requested = True
        if task.status in {"queued", "running", "paused"}:
            task.status = "cancelled"
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
            task.status = "running"
            task.log("resumed")
            await self.emit(task)
            return self.snapshot_task(task)
        with store._lock, store.connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            raise ValueError("task missing")
        if row["status"] in {"done", "error", "cancelled"}:
            return self._snapshot_from_db(row)
        task = AgentTask(
            row["objective"],
            row["model"],
            row["skill"],
            row["parent_id"],
            row["workspace"],
            row["mode"],
            task_id=row["id"],
            session_id=row["session_id"],
        )
        task.created_at = row["created_at"]
        task.progress = row["progress"]
        self._wire(task)
        self.tasks[task.id] = task
        asyncio.create_task(self.run_task(task, subagents=0))
        return self.snapshot_task(task)

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
                memory.remember("session", {"objective": task.objective, "result": reply, "model": task.model})
                memory.suggest_from_task(task.id, task.objective, reply, task.workspace)
                self._add_message(task.session_id, task.id, "assistant", reply)
                self.compact_session(task.session_id)
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
                memory.remember("session", {"objective": task.objective, "result": reflection, "model": task.model})
                memory.suggest_from_task(task.id, task.objective, reflection, task.workspace)
                self._add_message(task.session_id, task.id, "assistant", reflection)
                self.compact_session(task.session_id)
                task.log("done")
        except asyncio.CancelledError:
            task.status = "cancelled"
            task.result = "Cancelled."
            task.log("cancelled")
        except Exception as exc:
            task.status = "error"
            task.result = str(exc)
            task.log(f"error: {exc}")
        await self.emit(task)

    async def governed_chat(self, task, phase, role, sections):
        model_key = self.phase_model(task, role)
        bundle = context_governor.compose_prompt(model_key, phase, sections)
        trace = bundle["trace"]
        task.seen("context_budget", trace)
        if trace.get("trimmed"):
            task.log(f"context trimmed: {', '.join(trace['trimmed'])}")
        if trace.get("omitted"):
            task.log(f"context omitted: {', '.join(trace['omitted'])}")
        return await chat(model_key, [{"role": "user", "content": bundle["prompt"]}])

    async def chat_reply(self, task):
        previous_messages = self.recent_messages(task.session_id, 10)
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
            context_governor.section("previous_conversation", "Previous conversation", self.format_conversation(previous_messages, task.id), priority=10, min_chars=220),
            context_governor.section("workspace", "Workspace", task.workspace, required=True, priority=0),
            context_governor.section("memory_recall", "Relevant memory recall", self.format_memory(recall), priority=20, min_chars=180),
            context_governor.section("rag_sources", "Actual local RAG context", self.format_context(context), priority=25, min_chars=240),
            context_governor.section("graph_evidence", "Actual local graph context", self.format_graph(graph), priority=30, min_chars=180),
            context_governor.section("file_snippets", "Approved workspace file snippets", self.format_workspace_snippets(workspace_context), priority=35, min_chars=260),
            context_governor.section("workspace_tree", "Approved workspace file listing", self.format_workspace_tree(workspace_context), priority=70, min_chars=180),
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
        return await self.governed_chat(task, "chat", "main", sections)

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
        return await self.governed_chat(task, "planning", "planner", sections)

    async def execute(self, task, plan):
        if task.skill and task.skill != "general":
            task.log(f"skill: {task.skill}")
            try:
                mod = importlib.import_module(f"backend.skills.{task.skill}")
                return await mod.run(task.objective, plan, self.mcp, task.log)
            except ModuleNotFoundError:
                task.log("skill missing, using model")

        context = await self.mcp.call_tool("rag_search", {"query": task.objective + ' ' + plan[:600], "limit": 4, "workspace_path": task.workspace, "_task_id": task.id})
        graph = await self.mcp.call_tool("graph_search", {"query": task.objective + ' ' + plan[:600], "limit": 6, "_task_id": task.id})
        sections = [
            context_governor.section("executor_instruction", "Instruction", "Execute this plan. Use concise output.", required=True, priority=0),
            context_governor.section("mode", "Mode", task.mode, required=True, priority=0),
            context_governor.section("current_user_message", "Task", task.objective, required=True, priority=0, min_chars=500),
            context_governor.section("workspace", "Workspace", task.workspace, required=True, priority=0),
            context_governor.section("plan", "Plan", plan, priority=15, min_chars=260),
            context_governor.section("rag_sources", "Extra local context", self.format_context(context), priority=25, min_chars=240),
            context_governor.section("graph_evidence", "Extra graph context", self.format_graph(graph), priority=30, min_chars=180),
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
        return await self.governed_chat(task, "execution", self.execution_role(task), sections)

    async def reflect(self, task, plan, work):
        sections = [
            context_governor.section("reflection_instruction", "Instruction", "Write the final user-facing answer for this task.", required=True, priority=0),
            context_governor.section("current_user_message", "Task", task.objective, required=True, priority=0, min_chars=500),
            context_governor.section("rag_sources", "Actual local sources", self.format_task_sources(task.sources), priority=20, min_chars=180),
            context_governor.section("graph_evidence", "Actual graph evidence", self.format_task_graph(task.graph), priority=25, min_chars=180),
            context_governor.section("work", "Work", work, priority=30, min_chars=300),
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
        return model_registry.key_for_role(role, task.model)

    def execution_role(self, task):
        if task.mode == "code":
            return "coder"
        if task.mode == "research":
            return "researcher"
        return "executor"

    def compact_session(self, session_id):
        with store._lock, store.connect() as conn:
            messages = conn.execute(
                "SELECT role,content FROM messages WHERE session_id=? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
            if len(messages) <= 12:
                return None
            older = messages[:-8]
            summary = "Earlier context: " + " ".join(f"{m['role']}: {m['content'][:180]}" for m in older[:8])[:1800]
            conn.execute("UPDATE sessions SET summary=?, updated_at=? WHERE id=?", (summary, store.now(), session_id))
            conn.commit()
        return summary

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
        return "\n".join(lines)

    def format_context(self, context, max_items=3, max_chars=450):
        hits = context.get("hits", [])
        if not hits:
            return "No local matches."
        lines = []
        for h in hits[:max_items]:
            lines.append(f"[{h['source']}#{h['chunk']} score={h['score']}]\n{h['text'][:max_chars]}")
        return "\n\n".join(lines)

    def format_graph(self, graph):
        edges = graph.get("edges", [])
        if not edges:
            return "No graph matches."
        lines = []
        for edge in edges[:10]:
            suffix = f" ({edge.get('why')})" if edge.get("why") else ""
            lines.append(f"{edge['source']} --{edge['relation']}--> {edge['target']}{suffix}")
        return "\n".join(lines)

    def format_memory(self, recall):
        items = recall.get("items", [])
        if not items:
            return "No relevant saved memory."
        lines = []
        for item in items[:4]:
            content = str(item.get("content"))[:420]
            lines.append(f"- {item.get('kind')}: {content}")
        return "\n".join(lines)

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
        return "\n".join(lines)

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
