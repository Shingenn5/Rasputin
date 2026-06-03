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

ROOT = Path(__file__).resolve().parents[1]
SAFE_ROOT = ROOT


class McpLayer:
    def __init__(self, safe_root=SAFE_ROOT):
        self.safe_root = Path(safe_root).resolve()
        self.tools = {
            "fs_read": self.fs_read,
            "fs_write": self.fs_write,
            "fs_list": self.fs_list,
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
        return await self.tools[name](**args)

    async def fs_read(self, path, workspace_path=None):
        security.require("allow_file_read")
        target = self._safe(path, workspace_path)
        audit.log("fs_read", {"path": str(target)})
        return {"path": str(target), "content": target.read_text(encoding="utf-8")}

    async def fs_write(self, path, content, workspace_path=None, approved=False):
        security.require("allow_file_write")
        target = self._safe(path, workspace_path)
        cfg = security.load()
        if cfg.get("approval_required_file_write", True) and not approved:
            return approvals.mutation_preview("fs_write", {
                "path": str(target),
                "bytes": len(str(content).encode("utf-8")),
                "workspace": workspace_path or workspace.get_active()["active_path"],
            })
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        audit.log("fs_write", {"path": str(target), "bytes": len(content.encode("utf-8"))})
        return {"path": str(target), "bytes": len(content.encode("utf-8"))}

    async def fs_list(self, path=".", workspace_path=None):
        target = self._safe(path, workspace_path)
        items = []
        for p in target.iterdir():
            items.append({"name": p.name, "kind": "dir" if p.is_dir() else "file", "bytes": p.stat().st_size if p.is_file() else 0})
        return {"path": str(target), "items": items}

    async def fs_mkdir(self, path, workspace_path=None, approved=False):
        security.require("allow_file_reorganize")
        target = self._safe(path, workspace_path)
        cfg = security.load()
        if cfg.get("approval_required_file_move", True) and not approved:
            return approvals.mutation_preview("fs_mkdir", {
                "path": str(target),
                "workspace": workspace_path or workspace.get_active()["active_path"],
            })
        target.mkdir(parents=True, exist_ok=True)
        audit.log("fs_mkdir", {"path": str(target)})
        return {"path": str(target)}

    async def fs_move(self, source, target, workspace_path=None, approved=False):
        security.require("allow_file_reorganize")
        src = self._safe(source, workspace_path)
        dst = self._safe(target, workspace_path)
        if not src.exists():
            raise ValueError("source missing")
        if dst.exists():
            raise ValueError("target already exists")
        cfg = security.load()
        if cfg.get("approval_required_file_move", True) and not approved:
            return approvals.mutation_preview("fs_move", {
                "source": str(src),
                "target": str(dst),
                "workspace": workspace_path or workspace.get_active()["active_path"],
                "rollback": str(src),
            })
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        audit.log("fs_move", {"source": str(src), "target": str(dst)})
        return {"source": str(src), "target": str(dst)}

    async def web_search(self, query, max_results=5):
        security.require("allow_web_search")
        cfg = security.load()
        safe_query = leak_guard.validate_web_query(query, int(cfg.get("web_search_max_chars", 180)))
        if cfg.get("approval_required_web_search", False):
            return approvals.mutation_preview("web_search", {"query": safe_query, "max_results": max_results})
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

    async def rag_search(self, query, limit=6, workspace_path=None):
        return await asyncio.to_thread(rag.search, query, limit, workspace_path or workspace.get_active()["active_path"])

    async def graph_search(self, query, limit=12):
        return await asyncio.to_thread(graphify.search, query, limit)


async def demo_tool_call():
    mcp = McpLayer()
    return await mcp.call_tool("fs_list", {"path": "."})
