import asyncio
import importlib
import json
import time
import uuid

from .mcp_layer import McpLayer
from .models import chat
from . import memory
from . import model_registry
from . import runtime_store as store
from . import security
from . import workspace


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
                INSERT INTO sessions(id,title,status,workspace,model,mode,skill,summary,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET status=excluded.status, workspace=excluded.workspace, model=excluded.model, mode=excluded.mode, skill=excluded.skill, updated_at=excluded.updated_at
                """,
                (task.session_id, title, "active", task.workspace, task.model, task.mode, task.skill, "", stamp, stamp),
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
        try:
            memory.export_master_context()
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

    def _snapshot_from_db(self, row):
        task = dict(row)
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
        return {
            "id": task["id"],
            "sessionId": task["session_id"],
            "objective": task["objective"],
            "model": task["model"],
            "skill": task["skill"],
            "mode": task["mode"],
            "status": task["status"],
            "progress": task["progress"],
            "logs": logs,
            "result": task["result"],
            "sources": [],
            "graph": [],
            "outputs": [
                {"kind": a["kind"], "title": a["title"], "content": a["content"], "createdAt": a["created_at"]}
                for a in outputs
            ],
            "trace": [
                {"at": t["created_at"], "kind": t["kind"], "detail": store._loads(t["detail"], {})}
                for t in reversed(traces)
            ],
            "permissionSnapshot": store._loads(task["permission_snapshot"], {}),
            "workspace": task["workspace"],
            "parentId": task["parent_id"],
            "paused": bool(task["paused"]),
            "createdAt": task["created_at"],
        }

    def all_tasks(self):
        store.init_db()
        with store._lock, store.connect() as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 250").fetchall()
        return [self._snapshot_from_db(row) for row in rows]

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

    async def subscribe(self):
        q = asyncio.Queue()
        self.listeners.add(q)
        return q

    def start(self, objective, model="dry-run", skill="general", subagents=0, workspace_path=None, mode="chat"):
        task = AgentTask(objective, model, skill, workspace_path=workspace_path, mode=mode)
        self._wire(task)
        self.tasks[task.id] = task
        self._persist_task(task)
        self._add_message(task.session_id, task.id, "user", objective)
        asyncio.create_task(self.run_task(task, subagents=subagents))
        return task

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

    async def chat_reply(self, task):
        recall = memory.search(task.objective, 5)
        context = await self.mcp.call_tool("rag_search", {"query": task.objective, "limit": 3, "workspace_path": task.workspace, "_task_id": task.id})
        graph = await self.mcp.call_tool("graph_search", {"query": task.objective, "limit": 4, "_task_id": task.id})
        task.sources = [{"source": h["source"], "score": h["score"], "chunk": h["chunk"]} for h in context.get("hits", [])]
        task.graph = [{"source": e["source"], "relation": e["relation"], "target": e["target"]} for e in graph.get("edges", [])[:8]]
        task.seen("memory_recall", {"items": len(recall.get("items", []))})
        task.seen("rag_context", {"hits": len(context.get("hits", [])), "workspace": task.workspace})
        task.seen("graph_context", {"edges": len(graph.get("edges", []))})
        if task.sources:
            task.log(f"rag hits: {len(task.sources)}")
        if task.graph:
            task.log(f"graph hits: {len(task.graph)}")
        prompt = f"""Answer the user directly as Rasputin.
Task: {task.objective}
Workspace: {task.workspace}
Relevant memory recall:
{self.format_memory(recall)}

Actual local RAG context:
{self.format_context(context)}

Actual local graph context:
{self.format_graph(graph)}

Rules:
- Do not claim you browsed the web, searched social media, emailed, called, scheduled meetings, contacted people, edited files, or used external tools unless the context above proves that happened.
- If there are no local matches, do not invent file sources. You can still answer from general model knowledge.
- If the user asks for an action that requires a tool or permission not shown here, say what is missing instead of pretending it happened.
- Keep the reply useful and conversational. Do not write an internal plan unless the user asked for one.
"""
        return await chat(self.phase_model(task, "main"), [{"role": "user", "content": prompt}])

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
        task.graph = [{"source": e["source"], "relation": e["relation"], "target": e["target"]} for e in graph.get("edges", [])[:8]]
        task.seen("memory_recall", {"items": len(recall.get("items", []))})
        task.seen("rag_context", {"hits": len(context.get("hits", [])), "workspace": task.workspace})
        task.seen("graph_context", {"edges": len(graph.get("edges", []))})
        prompt = f"""Plan this task in 3-6 steps.
Mode: {task.mode}
Task: {task.objective}
Workspace: {task.workspace}
Relevant memory recall:
{self.format_memory(recall)}
Local RAG context:
{self.format_context(context)}
Local graph context:
{self.format_graph(graph)}

Rules:
- Available evidence is only the memory, local RAG, and graph context above.
- Do not claim web research, outreach, email, phone calls, social media, or file changes were completed.
- If the task needs unavailable tools or approvals, include that as a step.
"""
        return await chat(self.phase_model(task, "planner"), [{"role": "user", "content": prompt}])

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
        prompt = f"""Execute this plan. Use concise output.
Mode: {task.mode}
Task: {task.objective}
Workspace: {task.workspace}
Plan: {plan}
Extra local context:
{self.format_context(context)}
Extra graph context:
{self.format_graph(graph)}

Rules:
- Do not pretend to browse, contact people, schedule meetings, or mutate files.
- Use only the local context shown here and the plan above.
- If a real-world action cannot be completed from the available tools, say so plainly.
"""
        return await chat(self.phase_model(task, self.execution_role(task)), [{"role": "user", "content": prompt}])

    async def reflect(self, task, plan, work):
        prompt = f"""Write the final user-facing answer for this task.
Task:{task.objective}
Actual local sources:{self.format_task_sources(task.sources)}
Actual graph evidence:{self.format_task_graph(task.graph)}
Plan:{plan}
Work:{work}

Rules:
- Do not list generic source categories like forums, social media, databases, emails, or contacts unless they appear in actual local sources or graph evidence.
- Do not claim outreach, meetings, web research, file edits, or other external actions were completed unless the work explicitly proves it.
- If there were no actual local sources, say that no local sources were used only when source usage matters to the answer.
- Be direct and useful; avoid fake completion summaries.
"""
        return await chat(self.phase_model(task, "summarizer"), [{"role": "user", "content": prompt}])

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
        return "\n".join(f"{e['source']} --{e['relation']}--> {e['target']}" for e in edges[:10])

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
        return "\n".join(f"{edge.get('source')} --{edge.get('relation')}--> {edge.get('target')}" for edge in graph[:10])

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
