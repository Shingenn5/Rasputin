import asyncio
import json
import urllib.parse
import urllib.request
from pathlib import Path
import shutil

from . import rag
from . import graphify
from . import workspace
from . import audit
from . import security
from . import leak_guard
from . import approvals
from . import runtime_store as store

ROOT = Path(__file__).resolve().parents[1]
SAFE_ROOT = ROOT
EXCLUDED_TREE_DIRS = {".git", ".pytest_cache", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}

TOOL_SPECS = {
    "fs_read": {"risk": "safe", "permission": "allow_file_read"},
    "fs_write": {"risk": "approval_required", "permission": "allow_file_write"},
    "fs_list": {"risk": "safe", "permission": "allow_file_read"},
    "fs_tree": {"risk": "safe", "permission": "allow_file_read"},
    "fs_mkdir": {"risk": "approval_required", "permission": "allow_file_reorganize"},
    "fs_move": {"risk": "approval_required", "permission": "allow_file_reorganize"},
    "web_search": {"risk": "approval_required", "permission": "allow_web_search"},
    "rag_search": {"risk": "safe", "permission": "allow_file_read"},
    "graph_search": {"risk": "safe", "permission": "allow_file_read"},
}


class McpLayer:
    def __init__(self, safe_root=SAFE_ROOT):
        self.safe_root = Path(safe_root).resolve()
        self.tools = {
            "fs_read": self.fs_read,
            "fs_write": self.fs_write,
            "fs_list": self.fs_list,
            "fs_tree": self.fs_tree,
            "fs_mkdir": self.fs_mkdir,
            "fs_move": self.fs_move,
            "web_search": self.web_search,
            "rag_search": self.rag_search,
            "graph_search": self.graph_search,
        }

    def _safe(self, path, workspace_path=None):
        base = workspace.resolve_path(workspace_path or workspace.get_active()["active_path"])
        target = (base / path).resolve()
        if base not in target.parents and target != base:
            raise ValueError("path outside safe root")
        return target

    async def call_tool(self, name, args):
        if name not in self.tools:
            raise ValueError(f"missing tool {name}")
        args = dict(args or {})
        task_id = args.pop("_task_id", None)
        tool_call_id = args.pop("_tool_call_id", None) or store.new_id("tool")
        spec = TOOL_SPECS.get(name, {"risk": "safe"})
        self._record_tool(tool_call_id, task_id, name, spec.get("risk", "safe"), "running", args)
        try:
            result = await self.tools[name](**args, _task_id=task_id, _tool_call_id=tool_call_id)
            status = "pending_approval" if isinstance(result, dict) and result.get("approval_id") else "done"
            self._finish_tool(tool_call_id, status, result, result.get("approval_id") if isinstance(result, dict) else None)
            return result
        except Exception as exc:
            self._finish_tool(tool_call_id, "error", {"error": str(exc)})
            raise

    def _record_tool(self, tool_call_id, task_id, name, risk, status, args):
        store.init_db()
        with store._lock, store.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tool_calls(id,task_id,name,risk,status,args_redacted,result_redacted,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (tool_call_id, task_id, name, risk, status, json.dumps(approvals._redact(args)), "{}", store.now(), store.now()),
            )
            conn.commit()

    def _finish_tool(self, tool_call_id, status, result, approval_id=None):
        store.init_db()
        with store._lock, store.connect() as conn:
            conn.execute(
                "UPDATE tool_calls SET status=?, result_redacted=?, approval_id=?, updated_at=? WHERE id=?",
                (status, json.dumps(approvals._redact(result)), approval_id, store.now(), tool_call_id),
            )
            conn.commit()

    async def _wait_for_approval(self, preview, action_type, task_id=None):
        approval_id = preview.get("approval_id")
        if not approval_id or not task_id:
            return False
        while True:
            approval = approvals.get(approval_id)
            if not approval:
                raise PermissionError("approval missing")
            if approval["status"] == "approved":
                approvals.require_approved(approval_id, action_type)
                return True
            if approval["status"] in {"denied", "expired", "executed"}:
                raise PermissionError(f"approval {approval['status']}")
            await asyncio.sleep(2)

    def _relative(self, path, base):
        try:
            rel = path.relative_to(base)
            return "." if str(rel) == "." else rel.as_posix()
        except ValueError:
            return path.name

    async def fs_read(self, path, workspace_path=None, max_chars=12000, _task_id=None, _tool_call_id=None):
        security.require("allow_file_read")
        base = workspace.resolve_path(workspace_path or workspace.get_active()["active_path"])
        target = self._safe(path, workspace_path)
        workspace.require_path_permission(target, "read")
        audit.log("fs_read", {"path": str(target)})
        content = target.read_text(encoding="utf-8", errors="replace")
        limit = max(1000, min(int(max_chars or 12000), 24000))
        truncated = len(content) > limit
        return {"path": str(target), "relativePath": self._relative(target, base), "content": content[:limit], "truncated": truncated}

    async def fs_write(self, path, content, workspace_path=None, approved=False, approval_id=None, _task_id=None, _tool_call_id=None):
        security.require("allow_file_write")
        target = self._safe(path, workspace_path)
        workspace.require_path_permission(target, "write")
        cfg = security.load()
        if cfg.get("approval_required_file_write", True) and approval_id:
            approvals.require_approved(approval_id, "fs_write")
            approved = True
        if cfg.get("approval_required_file_write", True) and not approved:
            preview = approvals.mutation_preview("fs_write", {
                "path": str(target),
                "bytes": len(str(content).encode("utf-8")),
                "workspace": workspace_path or workspace.get_active()["active_path"],
            }, task_id=_task_id, tool_call_id=_tool_call_id)
            approved = await self._wait_for_approval(preview, "fs_write", _task_id)
            if not approved:
                return preview
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        audit.log("fs_write", {"path": str(target), "bytes": len(content.encode("utf-8"))})
        return {"path": str(target), "bytes": len(content.encode("utf-8"))}

    async def fs_list(self, path=".", workspace_path=None, _task_id=None, _tool_call_id=None):
        security.require("allow_file_read")
        base = workspace.resolve_path(workspace_path or workspace.get_active()["active_path"])
        target = self._safe(path, workspace_path)
        workspace.require_path_permission(target, "read")
        items = []
        for p in target.iterdir():
            items.append({
                "name": p.name,
                "path": self._relative(p, base),
                "kind": "dir" if p.is_dir() else "file",
                "bytes": p.stat().st_size if p.is_file() else 0,
            })
        return {"path": str(target), "items": items}

    async def fs_tree(self, path=".", workspace_path=None, max_items=120, max_depth=3, _task_id=None, _tool_call_id=None):
        security.require("allow_file_read")
        base = workspace.resolve_path(workspace_path or workspace.get_active()["active_path"])
        target = self._safe(path, workspace_path)
        workspace.require_path_permission(target, "read")
        items = []
        truncated = False
        limit = max(10, min(int(max_items or 120), 300))
        depth_limit = max(0, min(int(max_depth or 3), 6))

        def add_entry(p, depth):
            try:
                stat = p.stat()
            except OSError:
                stat = None
            items.append({
                "name": p.name,
                "path": self._relative(p, base),
                "kind": "dir" if p.is_dir() else "file",
                "bytes": stat.st_size if stat and p.is_file() else 0,
                "depth": depth,
            })

        def walk(current, depth):
            nonlocal truncated
            if len(items) >= limit:
                truncated = True
                return
            try:
                children = sorted(current.iterdir(), key=lambda item: (0 if item.is_dir() else 1, item.name.lower()))
            except OSError:
                return
            for child in children:
                if len(items) >= limit:
                    truncated = True
                    return
                if child.is_dir() and child.name in EXCLUDED_TREE_DIRS:
                    continue
                add_entry(child, depth)
                if child.is_dir() and depth < depth_limit:
                    walk(child, depth + 1)

        walk(target, 0)
        return {
            "workspace": workspace_path or workspace.get_active()["active_path"],
            "path": str(target),
            "items": items,
            "truncated": truncated,
        }

    async def fs_mkdir(self, path, workspace_path=None, approved=False, approval_id=None, _task_id=None, _tool_call_id=None):
        security.require("allow_file_reorganize")
        target = self._safe(path, workspace_path)
        workspace.require_path_permission(target, "reorganize")
        cfg = security.load()
        if cfg.get("approval_required_file_move", True) and approval_id:
            approvals.require_approved(approval_id, "fs_mkdir")
            approved = True
        if cfg.get("approval_required_file_move", True) and not approved:
            preview = approvals.mutation_preview("fs_mkdir", {
                "path": str(target),
                "workspace": workspace_path or workspace.get_active()["active_path"],
            }, task_id=_task_id, tool_call_id=_tool_call_id)
            approved = await self._wait_for_approval(preview, "fs_mkdir", _task_id)
            if not approved:
                return preview
        target.mkdir(parents=True, exist_ok=True)
        audit.log("fs_mkdir", {"path": str(target)})
        return {"path": str(target)}

    async def fs_move(self, source, target, workspace_path=None, approved=False, approval_id=None, _task_id=None, _tool_call_id=None):
        security.require("allow_file_reorganize")
        src = self._safe(source, workspace_path)
        dst = self._safe(target, workspace_path)
        workspace.require_path_permission(src, "reorganize")
        workspace.require_path_permission(dst, "reorganize")
        if not src.exists():
            raise ValueError("source missing")
        if dst.exists():
            raise ValueError("target already exists")
        cfg = security.load()
        if cfg.get("approval_required_file_move", True) and approval_id:
            approvals.require_approved(approval_id, "fs_move")
            approved = True
        if cfg.get("approval_required_file_move", True) and not approved:
            preview = approvals.mutation_preview("fs_move", {
                "source": str(src),
                "target": str(dst),
                "workspace": workspace_path or workspace.get_active()["active_path"],
                "rollback": str(src),
            }, task_id=_task_id, tool_call_id=_tool_call_id)
            approved = await self._wait_for_approval(preview, "fs_move", _task_id)
            if not approved:
                return preview
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        audit.log("fs_move", {"source": str(src), "target": str(dst)})
        return {"source": str(src), "target": str(dst)}

    async def web_search(self, query, max_results=5, approved=False, approval_id=None, _task_id=None, _tool_call_id=None):
        security.require("allow_web_search")
        cfg = security.load()
        safe_query = leak_guard.validate_web_query(query, int(cfg.get("web_search_max_chars", 180)))
        if cfg.get("approval_required_web_search", False) and approval_id:
            approvals.require_approved(approval_id, "web_search")
            approved = True
        if cfg.get("approval_required_web_search", False) and not approved:
            preview = approvals.mutation_preview("web_search", {"query": safe_query, "max_results": max_results}, task_id=_task_id, tool_call_id=_tool_call_id)
            approved = await self._wait_for_approval(preview, "web_search", _task_id)
            if not approved:
                return preview
        audit.log("web_search", {"query": safe_query, "max_results": max_results})
        # cheap search
        encoded = urllib.parse.quote_plus(safe_query)
        url = f"https://duckduckgo.com/html/?q={encoded}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "local-ai-wrapper/0.1"})
            text = await asyncio.to_thread(lambda: urllib.request.urlopen(req, timeout=12).read().decode("utf-8", "ignore"))
        except Exception as exc:
            return {"query": safe_query, "error": str(exc), "results": []}
        chunks = []
        for bit in text.split('class="result__a"')[1:max_results + 1]:
            title = bit.split(">")[-1].split("</a")[0]
            title = " ".join(title.replace("&amp;", "&").split())
            chunks.append({"title": title, "source": "duckduckgo-lite"})
        return {"query": safe_query, "results": chunks}

    async def rag_search(self, query, limit=6, workspace_path=None, _task_id=None, _tool_call_id=None):
        if not security.load().get("allow_file_read", False):
            return {"query": query, "hits": [], "blocked": True}
        return await asyncio.to_thread(rag.search, query, limit, workspace_path or workspace.get_active()["active_path"])

    async def graph_search(self, query, limit=12, _task_id=None, _tool_call_id=None):
        if not security.load().get("allow_file_read", False):
            return {"query": query, "nodes": [], "edges": [], "blocked": True}
        return await asyncio.to_thread(graphify.search, query, limit)


async def demo_tool_call():
    mcp = McpLayer()
    return await mcp.call_tool("fs_list", {"path": "."})
