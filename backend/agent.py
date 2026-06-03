import asyncio
import importlib
import time
import uuid

from .mcp_layer import McpLayer
from .memory import load_memory, remember
from .models import chat
from . import workspace
from . import security


class AgentTask:
    def __init__(self, objective, model, skill, parent_id=None, workspace_path=None, mode="chat"):
        self.id = str(uuid.uuid4())[:8]
        self.objective = objective
        self.model = model
        self.skill = skill
        self.mode = mode or "chat"
        self.parent_id = parent_id
        self.status = "queued"
        self.progress = 0
        self.logs = []
        self.result = ""
        self.sources = []
        self.graph = []
        self.artifacts = []
        self.trace = []
        self.cancel_requested = False
        self.workspace = workspace_path or workspace.get_active()["active_path"]
        self.permission_snapshot = security.load()
        self.created_at = time.time()

    def log(self, msg):
        stamp = time.strftime("%H:%M:%S")
        self.logs.append(f"[{stamp}] {msg}")
        self.logs = self.logs[-500:]

    def seen(self, kind, detail):
        self.trace.append({"at": time.time(), "kind": kind, "detail": detail})
        self.trace = self.trace[-120:]

    def artifact(self, kind, title, content):
        self.artifacts.append({"kind": kind, "title": title, "content": content, "created_at": time.time()})
        self.artifacts = self.artifacts[-40:]


class AgentHub:
    def __init__(self):
        self.tasks = {}
        self.listeners = set()
        self.mcp = McpLayer()

    async def emit(self, task):
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
            "artifacts": task.artifacts,
            "trace": task.trace[-80:],
            "permission_snapshot": task.permission_snapshot,
            "workspace": task.workspace,
            "parent_id": task.parent_id,
            "created_at": task.created_at,
        }

    def all_tasks(self):
        return [self.snapshot_task(t) for t in sorted(self.tasks.values(), key=lambda x: x.created_at, reverse=True)]

    def get_task(self, task_id):
        task = self.tasks.get(task_id)
        if not task:
            return None
        return self.snapshot_task(task)

    async def subscribe(self):
        q = asyncio.Queue()
        self.listeners.add(q)
        return q

    def start(self, objective, model="dry-run", skill="general", subagents=0, workspace_path=None, mode="chat"):
        task = AgentTask(objective, model, skill, workspace_path=workspace_path, mode=mode)
        self.tasks[task.id] = task
        asyncio.create_task(self.run_task(task, subagents=subagents))
        return task

    async def cancel(self, task_id):
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError("task missing")
        task.cancel_requested = True
        if task.status in {"queued", "running"}:
            task.status = "cancelled"
            task.progress = min(task.progress, 99)
            task.log("cancel requested")
            await self.emit(task)
        return self.snapshot_task(task)

    def checkpoint(self, task):
        if task.cancel_requested or task.status == "cancelled":
            raise asyncio.CancelledError()

    async def run_task(self, task, subagents=0):
        task.status = "running"
        task.log("started")
        await self.emit(task)
        try:
            task.progress = 8
            plan = await self.plan(task)
            self.checkpoint(task)
            task.log("plan made")
            await self.emit(task)

            if subagents:
                await self.spawn_subagents(task, plan, subagents)

            task.progress = 35
            work = await self.execute(task, plan)
            self.checkpoint(task)
            task.log("executed")
            await self.emit(task)

            task.progress = 78
            reflection = await self.reflect(task, plan, work)
            self.checkpoint(task)
            task.result = reflection
            task.artifact("markdown", "Task summary", reflection)
            task.progress = 100
            task.status = "done"
            remember("session", {"objective": task.objective, "result": reflection, "model": task.model})
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

    async def plan(self, task):
        mem = load_memory()
        context = await self.mcp.call_tool("rag_search", {"query": task.objective, "limit": 6, "workspace_path": task.workspace})
        graph = await self.mcp.call_tool("graph_search", {"query": task.objective, "limit": 8})
        task.sources = [{"source": h["source"], "score": h["score"], "chunk": h["chunk"]} for h in context.get("hits", [])]
        task.graph = [{"source": e["source"], "relation": e["relation"], "target": e["target"]} for e in graph.get("edges", [])[:8]]
        task.seen("rag_context", {"hits": len(context.get("hits", [])), "workspace": task.workspace})
        task.seen("graph_context", {"edges": len(graph.get("edges", []))})
        if task.sources:
            task.log(f"rag hits: {len(task.sources)}")
        if task.graph:
            task.log(f"graph hits: {len(task.graph)}")
        prompt = f"""Plan this task in 3-6 steps.
Mode: {task.mode}
Task: {task.objective}
Workspace: {task.workspace}
Memory: {mem}
Local RAG context:
{self.format_context(context)}
Local graph context:
{self.format_graph(graph)}
"""
        return await chat(task.model, [{"role": "user", "content": prompt}])

    async def execute(self, task, plan):
        if task.skill and task.skill != "general":
            task.log(f"skill: {task.skill}")
            try:
                mod = importlib.import_module(f"backend.skills.{task.skill}")
                return await mod.run(task.objective, plan, self.mcp, task.log)
            except ModuleNotFoundError:
                task.log("skill missing, using model")

        context = await self.mcp.call_tool("rag_search", {"query": task.objective + ' ' + plan[:600], "limit": 4, "workspace_path": task.workspace})
        graph = await self.mcp.call_tool("graph_search", {"query": task.objective + ' ' + plan[:600], "limit": 6})
        prompt = f"""Execute this plan. Use concise output.
Mode: {task.mode}
Task: {task.objective}
Workspace: {task.workspace}
Plan: {plan}
Extra local context:
{self.format_context(context)}
Extra graph context:
{self.format_graph(graph)}
"""
        return await chat(task.model, [{"role": "user", "content": prompt}])

    async def reflect(self, task, plan, work):
        prompt = f"""Reflect on the result. Say what was done, sources used, and next useful step.
Task:{task.objective}
Sources:{task.sources}
Graph:{task.graph}
Plan:{plan}
Work:{work}
"""
        return await chat(task.model, [{"role": "user", "content": prompt}])

    def format_context(self, context):
        hits = context.get("hits", [])
        if not hits:
            return "No local matches."
        lines = []
        for h in hits:
            lines.append(f"[{h['source']}#{h['chunk']} score={h['score']}]\n{h['text'][:1200]}")
        return "\n\n".join(lines)

    def format_graph(self, graph):
        edges = graph.get("edges", [])
        if not edges:
            return "No graph matches."
        lines = []
        for e in edges[:10]:
            lines.append(f"{e['source']} --{e['relation']}--> {e['target']}")
        return "\n".join(lines)

    async def spawn_subagents(self, parent, plan, count):
        parent.log(f"spawning {count} sub-agent(s)")
        for i in range(count):
            child = AgentTask(f"Subtask {i + 1} for: {parent.objective}", parent.model, parent.skill, parent.id, parent.workspace, parent.mode)
            self.tasks[child.id] = child
            asyncio.create_task(self.run_task(child, subagents=0))
        await asyncio.sleep(0.1)
