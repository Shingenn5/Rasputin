import asyncio
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
import shutil

from backend.rag import vector as rag
from backend.rag import graph as graphify
from backend.core import workspace
from backend.core import audit as audit
from backend.core import security as security
from backend.core import leak_guard as leak_guard
from backend.core import approvals as approvals
from backend.rag import memory as memory
from backend.models import registry as model_registry
from backend.mcp import tools as tool_relay
from backend.mcp import relay as mcp_relay
from backend.core import runtime_store as store
from backend.core.response import AppError

ROOT = Path(__file__).resolve().parents[1]
SAFE_ROOT = ROOT
EXCLUDED_TREE_DIRS = {".git", ".pytest_cache", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}

TOOL_SPECS = tool_relay.TOOL_SPECS

MAX_SHELL_OUTPUT_CHARS = 20000
SAFE_SHELL_ENV_KEYS = {
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP",
    "HOME", "USERPROFILE", "COMSPEC", "LANG", "LC_ALL", "PYTHONIOENCODING", "NODE_ENV",
}
# Soft backstop against obviously catastrophic commands. Trusted Dev Mode grants
# full local user-level shell execution by design; this is not a security boundary.
SHELL_DENY_PATTERNS = [
    re.compile(r"rm\s+-rf\s+(/|~|\$HOME)(\s|$)", re.IGNORECASE),
    re.compile(r"rm\s+-rf\s+(\.|\./|\*)\s*$", re.IGNORECASE),
    re.compile(r"format\s+[a-z]:", re.IGNORECASE),
    re.compile(r"rd\s+/s\s+/q\s+[a-z]:\\?\s*$", re.IGNORECASE),
    re.compile(r"remove-item\b.*-recurse\b.*-force\b.*[a-z]:\\?\s*$", re.IGNORECASE),
    re.compile(r":\(\)\s*\{\s*:\|\s*:\s*&\s*\}\s*;\s*:", re.IGNORECASE),
]


def _safe_shell_env():
    return {key: os.environ[key] for key in SAFE_SHELL_ENV_KEYS if key in os.environ}


def _parse_git_status_porcelain(text):
    entries = []
    for line in (text or "").splitlines():
        if not line or line.startswith("##") or len(line) < 4:
            continue
        entries.append({"status": line[:2].strip(), "path": line[3:]})
    return entries


_LOG_FIELD_SEP = "\x1f"


def _parse_git_log(text):
    commits = []
    for line in (text or "").splitlines():
        parts = line.split(_LOG_FIELD_SEP)
        if len(parts) != 4:
            continue
        commits.append({"hash": parts[0], "author": parts[1], "date": parts[2], "subject": parts[3]})
    return commits


_HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _parse_unified_diff(text):
    files = []
    current_file = None
    current_hunk = None
    for line in (text or "").splitlines():
        if line.startswith("diff --git"):
            current_file = {"header": line, "old_path": None, "new_path": None, "hunks": []}
            files.append(current_file)
            current_hunk = None
        elif line.startswith("--- ") and current_file is not None:
            current_file["old_path"] = line[4:].strip()
        elif line.startswith("+++ ") and current_file is not None:
            current_file["new_path"] = line[4:].strip()
        elif line.startswith("@@"):
            match = _HUNK_HEADER_RE.match(line)
            current_hunk = {
                "header": line,
                "old_start": int(match.group(1)) if match else None,
                "old_lines": int(match.group(2) or 1) if match else None,
                "new_start": int(match.group(3)) if match else None,
                "new_lines": int(match.group(4) or 1) if match else None,
                "lines": [],
            }
            if current_file is not None:
                current_file["hunks"].append(current_hunk)
        elif current_hunk is not None and line[:1] in ("+", "-", " "):
            current_hunk["lines"].append(line)
    return files


class McpLayer:
    def __init__(self, safe_root=SAFE_ROOT):
        self.safe_root = Path(safe_root).resolve()
        self.tools = {
            "fs_read": self.fs_read,
            "fs_write": self.fs_write,
            "fs_patch": self.fs_patch,
            "fs_list": self.fs_list,
            "fs_tree": self.fs_tree,
            "fs_search": self.fs_search,
            "fs_mkdir": self.fs_mkdir,
            "fs_move": self.fs_move,
            "web_search": self.web_search,
            "rag_search": self.rag_search,
            "graph_search": self.graph_search,
            "graph_relations": self.graph_relations,
            "workspace_browse": self.workspace_browse,
            "file_preview": self.file_preview,
            "workspace_mutation_preview": self.workspace_mutation_preview,
            "memory_search": self.memory_search,
            "archive_expand": self.archive_expand,
            "model_health": self.model_health,
            "shell_exec": self.shell_exec,
            "git_status": self.git_status,
            "git_diff": self.git_diff,
            "git_log": self.git_log,
            "git_add": self.git_add,
            "git_commit": self.git_commit,
        }

    def _safe(self, path, workspace_path=None):
        base = workspace.resolve_path(workspace_path or workspace.get_active()["active_path"])
        target = (base / path).resolve()
        if base not in target.parents and target != base:
            raise ValueError("path outside safe root")
        return target

    async def call_tool(self, name, args, on_log=None):
        definition = tool_relay.require_definition(name)
        external = mcp_relay.is_external_tool(name)
        if name not in self.tools and not external:
            raise AppError("tool_unavailable", f"Tool '{name}' is not executable in this MCP layer.", 501)
        args = dict(args or {})
        task_id = args.pop("_task_id", None)
        tool_call_id = args.pop("_tool_call_id", None) or store.new_id("tool")
        self._record_tool(tool_call_id, task_id, name, definition.get("risk", "safe"), "running", args)
        try:
            if not tool_relay.permission_allowed(definition):
                flag = definition.get("permission_flag") or "tool"
                raise PermissionError(f"{flag} is disabled")
            if external:
                result = await mcp_relay.call_tool(name, args, task_id=task_id, tool_call_id=tool_call_id)
            elif name == "shell_exec":
                result = await self.tools[name](**args, _task_id=task_id, _tool_call_id=tool_call_id, _on_log=on_log)
            else:
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
                (tool_call_id, task_id, name, risk, status, json.dumps(tool_relay.redact_args(name, args)), "{}", store.now(), store.now()),
            )
            conn.commit()

    def _finish_tool(self, tool_call_id, status, result, approval_id=None):
        store.init_db()
        with store._lock, store.connect() as conn:
            conn.execute(
                "UPDATE tool_calls SET status=?, result_redacted=?, approval_id=?, updated_at=? WHERE id=?",
                (status, json.dumps(tool_relay.summarize_result(self._tool_name(tool_call_id), result)), approval_id, store.now(), tool_call_id),
            )
            conn.commit()

    def _tool_name(self, tool_call_id):
        with store._lock, store.connect() as conn:
            row = conn.execute("SELECT name FROM tool_calls WHERE id=?", (tool_call_id,)).fetchone()
        return row["name"] if row else ""

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
        item = workspace.require_path_permission(target, "write")
        trusted = bool(item.get("trusted"))
        cfg = security.load()
        if cfg.get("approval_required_file_write", True) and not trusted and approval_id:
            approvals.require_approved(approval_id, "fs_write")
            approved = True
        if cfg.get("approval_required_file_write", True) and not trusted and not approved:
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
        audit.log("fs_write", {"path": str(target), "bytes": len(content.encode("utf-8")), "trusted": trusted})
        return {"path": str(target), "bytes": len(content.encode("utf-8"))}

    async def fs_patch(self, path, old_string, new_string, workspace_path=None, replace_all=False, approved=False, approval_id=None, _task_id=None, _tool_call_id=None):
        security.require("allow_file_write")
        target = self._safe(path, workspace_path)
        item = workspace.require_path_permission(target, "write")
        trusted = bool(item.get("trusted"))
        if not target.exists() or not target.is_file():
            raise ValueError("file does not exist; use fs_write to create a new file")
        old_string = str(old_string or "")
        new_string = str(new_string or "")
        if not old_string:
            raise ValueError("old_string is required and cannot be empty")
        if old_string == new_string:
            raise ValueError("old_string and new_string are identical; nothing to patch")
        original = target.read_text(encoding="utf-8")
        match_count = original.count(old_string)
        if match_count == 0:
            raise ValueError("old_string was not found in the file")
        if match_count > 1 and not replace_all:
            raise ValueError(f"old_string matches {match_count} locations; add more surrounding context to make it unique, or set replace_all=true")
        cfg = security.load()
        if cfg.get("approval_required_file_write", True) and not trusted and approval_id:
            approvals.require_approved(approval_id, "fs_patch")
            approved = True
        if cfg.get("approval_required_file_write", True) and not trusted and not approved:
            preview = approvals.mutation_preview("fs_patch", {
                "path": str(target),
                "matches": match_count,
                "replace_all": bool(replace_all),
                "old_string": old_string[:200],
                "new_string": new_string[:200],
                "workspace": workspace_path or workspace.get_active()["active_path"],
            }, task_id=_task_id, tool_call_id=_tool_call_id)
            approved = await self._wait_for_approval(preview, "fs_patch", _task_id)
            if not approved:
                return preview
        replacements = match_count if replace_all else 1
        updated = original.replace(old_string, new_string, -1 if replace_all else 1)
        target.write_text(updated, encoding="utf-8")
        audit.log("fs_patch", {"path": str(target), "replacements": replacements, "trusted": trusted})
        return {"path": str(target), "replacements": replacements, "bytes": len(updated.encode("utf-8"))}

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

    async def fs_search(self, query, path=".", workspace_path=None, max_results=40, include_content=False, _task_id=None, _tool_call_id=None):
        security.require("allow_file_read")
        workspace_ref = workspace_path or workspace.get_active()["active_path"]
        base = workspace.resolve_path(workspace_ref)
        target = self._safe(path or ".", workspace_ref)
        workspace.require_path_permission(target, "read")
        return await asyncio.to_thread(
            workspace.search_files,
            None,
            workspace.rel_path(target if target != base else base),
            query,
            max_results,
            include_content,
        )

    async def fs_mkdir(self, path, workspace_path=None, approved=False, approval_id=None, _task_id=None, _tool_call_id=None):
        security.require("allow_file_reorganize")
        target = self._safe(path, workspace_path)
        item = workspace.require_path_permission(target, "reorganize")
        trusted = bool(item.get("trusted"))
        cfg = security.load()
        if cfg.get("approval_required_file_move", True) and not trusted and approval_id:
            approvals.require_approved(approval_id, "fs_mkdir")
            approved = True
        if cfg.get("approval_required_file_move", True) and not trusted and not approved:
            preview = approvals.mutation_preview("fs_mkdir", {
                "path": str(target),
                "workspace": workspace_path or workspace.get_active()["active_path"],
            }, task_id=_task_id, tool_call_id=_tool_call_id)
            approved = await self._wait_for_approval(preview, "fs_mkdir", _task_id)
            if not approved:
                return preview
        target.mkdir(parents=True, exist_ok=True)
        audit.log("fs_mkdir", {"path": str(target), "trusted": trusted})
        return {"path": str(target)}

    async def fs_move(self, source, target, workspace_path=None, approved=False, approval_id=None, _task_id=None, _tool_call_id=None):
        security.require("allow_file_reorganize")
        src = self._safe(source, workspace_path)
        dst = self._safe(target, workspace_path)
        src_item = workspace.require_path_permission(src, "reorganize")
        dst_item = workspace.require_path_permission(dst, "reorganize")
        trusted = bool(src_item.get("trusted")) and bool(dst_item.get("trusted"))
        if not src.exists():
            raise ValueError("source missing")
        if dst.exists():
            raise ValueError("target already exists")
        cfg = security.load()
        if cfg.get("approval_required_file_move", True) and not trusted and approval_id:
            approvals.require_approved(approval_id, "fs_move")
            approved = True
        if cfg.get("approval_required_file_move", True) and not trusted and not approved:
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
        audit.log("fs_move", {"source": str(src), "target": str(dst), "trusted": trusted})
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

    async def graph_relations(self, entity, relation=None, direction="both", limit=25, _task_id=None, _tool_call_id=None):
        if not security.load().get("allow_file_read", False):
            return {"entity": entity, "relation": relation or "any", "direction": direction,
                    "matched_nodes": [], "edges": [], "count": 0, "blocked": True}
        return await asyncio.to_thread(graphify.query_relations, entity, relation, direction, limit)

    async def archive_expand(self, archive_id, _task_id=None, _tool_call_id=None):
        with store._lock, store.connect() as conn:
            row = conn.execute("SELECT content FROM eviction_log WHERE id=?", (archive_id,)).fetchone()
        if not row:
            raise AppError("not_found", f"Archive ID {archive_id} not found.", 404)
        return {"archive_id": archive_id, "content": row["content"]}

    async def workspace_browse(self, root_id=None, path=None, _task_id=None, _tool_call_id=None):
        security.require("allow_file_read")
        return await asyncio.to_thread(workspace.browse, root_id, path)

    async def file_preview(self, root_id=None, path=None, max_bytes=131072, _task_id=None, _tool_call_id=None):
        security.require("allow_file_read")
        return await asyncio.to_thread(workspace.preview_file, root_id, path, max_bytes)

    async def workspace_mutation_preview(self, kind, workspace_path=None, path=None, source=None, target=None, content=None, max_items=40, _task_id=None, _tool_call_id=None):
        security.require("allow_file_read")
        plan = await asyncio.to_thread(workspace.mutation_preview, kind, workspace_path or workspace.get_active()["active_path"], path, source, target, content, max_items)
        audit.log("workspace_mutation_preview", {
            "kind": plan.get("kind"),
            "workspace": plan.get("workspace"),
            "affected_paths": len(plan.get("affected_paths") or []),
            "task_id": _task_id,
            "will_mutate": False,
        })
        return plan

    async def memory_search(self, query, limit=10, _task_id=None, _tool_call_id=None):
        return await asyncio.to_thread(memory.search, query, limit)

    async def model_health(self, key="dry-run", _task_id=None, _tool_call_id=None):
        return await asyncio.to_thread(model_registry.test_model, key)

    async def shell_exec(self, command, workspace_path=None, timeout_seconds=120, _task_id=None, _tool_call_id=None, _on_log=None):
        security.require("allow_shell_execution")
        command = str(command or "").strip()
        if not command:
            raise ValueError("command is required")
        base = workspace.resolve_path(workspace_path or workspace.get_active()["active_path"])
        item = workspace.workspace_for_path(base)
        if not item or not item.get("trusted"):
            raise PermissionError("shell execution requires Trusted Dev Mode to be enabled for this workspace")
        for pattern in SHELL_DENY_PATTERNS:
            if pattern.search(command):
                raise PermissionError("command blocked by shell safety guardrail")
        timeout = max(5, min(int(timeout_seconds or 120), 600))
        audit.log("shell_exec", {"command": command, "cwd": str(base), "timeout": timeout})

        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=str(base),
            env=_safe_shell_env(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        lines = []
        total_chars = 0
        truncated = False

        async def pump(stream, label):
            nonlocal total_chars, truncated
            while True:
                raw_line = await stream.readline()
                if not raw_line:
                    break
                text = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if not truncated:
                    if total_chars + len(text) > MAX_SHELL_OUTPUT_CHARS:
                        truncated = True
                        lines.append(f"[output truncated at {MAX_SHELL_OUTPUT_CHARS} chars]")
                    else:
                        lines.append(text)
                        total_chars += len(text)
                if _on_log:
                    try:
                        _on_log(f"shell {label}: {text}"[:400])
                    except Exception:
                        pass

        timed_out = False
        exit_code = None
        try:
            await asyncio.wait_for(
                asyncio.gather(pump(proc.stdout, "out"), pump(proc.stderr, "err")),
                timeout=timeout,
            )
            exit_code = await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            timed_out = True
            proc.kill()
            await proc.wait()

        output = "\n".join(lines)
        audit.log("shell_exec_done", {"command": command, "exit_code": exit_code, "timed_out": timed_out, "truncated": truncated})
        return {
            "command": command,
            "cwd": str(base),
            "exit_code": exit_code,
            "timed_out": timed_out,
            "output": output,
            "truncated": truncated,
        }

    async def _run_git(self, base, args, timeout=20):
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=str(base),
            env=_safe_shell_env(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            raw_stdout, raw_stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {
                "exit_code": proc.returncode,
                "timed_out": False,
                "stdout": raw_stdout.decode("utf-8", errors="replace")[:MAX_SHELL_OUTPUT_CHARS],
                "stderr": raw_stderr.decode("utf-8", errors="replace")[:2000],
            }
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {"exit_code": None, "timed_out": True, "stdout": "", "stderr": "git command timed out"}

    async def git_status(self, workspace_path=None, _task_id=None, _tool_call_id=None):
        security.require("allow_file_read")
        base = workspace.resolve_path(workspace_path or workspace.get_active()["active_path"])
        workspace.require_path_permission(base, "read")
        result = await self._run_git(base, ["status", "--porcelain=v1", "-b"])
        audit.log("git_status", {"cwd": str(base)})
        return {"cwd": str(base), **result, "entries": _parse_git_status_porcelain(result.get("stdout", ""))}

    async def git_diff(self, workspace_path=None, path=None, staged=False, _task_id=None, _tool_call_id=None):
        security.require("allow_file_read")
        base = workspace.resolve_path(workspace_path or workspace.get_active()["active_path"])
        workspace.require_path_permission(base, "read")
        args = ["diff"]
        if staged:
            args.append("--staged")
        if path:
            target = self._safe(path, workspace_path)
            args += ["--", str(target.relative_to(base)) if target != base else "."]
        result = await self._run_git(base, args)
        audit.log("git_diff", {"cwd": str(base), "path": path, "staged": bool(staged)})
        return {
            "cwd": str(base),
            "path": path,
            "staged": bool(staged),
            **result,
            "hunks": _parse_unified_diff(result.get("stdout", "")),
        }

    async def git_log(self, workspace_path=None, limit=20, path=None, _task_id=None, _tool_call_id=None):
        security.require("allow_file_read")
        base = workspace.resolve_path(workspace_path or workspace.get_active()["active_path"])
        workspace.require_path_permission(base, "read")
        limit = max(1, min(int(limit or 20), 100))
        args = ["log", f"-{limit}", f"--pretty=format:%H{_LOG_FIELD_SEP}%an{_LOG_FIELD_SEP}%ad{_LOG_FIELD_SEP}%s", "--date=iso-strict"]
        if path:
            target = self._safe(path, workspace_path)
            args += ["--", str(target.relative_to(base)) if target != base else "."]
        result = await self._run_git(base, args)
        audit.log("git_log", {"cwd": str(base), "limit": limit, "path": path})
        return {"cwd": str(base), **result, "commits": _parse_git_log(result.get("stdout", ""))}

    async def git_add(self, paths, workspace_path=None, approved=False, approval_id=None, _task_id=None, _tool_call_id=None):
        security.require("allow_file_write")
        base = workspace.resolve_path(workspace_path or workspace.get_active()["active_path"])
        item = workspace.require_path_permission(base, "write")
        trusted = bool(item.get("trusted"))
        raw_paths = paths if isinstance(paths, list) else [paths]
        raw_paths = [str(p).strip() for p in raw_paths if str(p or "").strip()]
        if not raw_paths:
            raise ValueError("at least one path is required")
        rel_paths = []
        for p in raw_paths:
            target = self._safe(p, workspace_path)
            rel_paths.append(str(target.relative_to(base)) if target != base else ".")
        cfg = security.load()
        if cfg.get("approval_required_file_write", True) and not trusted and approval_id:
            approvals.require_approved(approval_id, "git_add")
            approved = True
        if cfg.get("approval_required_file_write", True) and not trusted and not approved:
            preview = approvals.mutation_preview("git_add", {
                "paths": rel_paths,
                "workspace": workspace_path or workspace.get_active()["active_path"],
            }, task_id=_task_id, tool_call_id=_tool_call_id)
            approved = await self._wait_for_approval(preview, "git_add", _task_id)
            if not approved:
                return preview
        result = await self._run_git(base, ["add", "--"] + rel_paths)
        audit.log("git_add", {"cwd": str(base), "paths": rel_paths, "trusted": trusted})
        return {"cwd": str(base), "paths": rel_paths, **result}

    async def git_commit(self, message, workspace_path=None, approved=False, approval_id=None, _task_id=None, _tool_call_id=None):
        security.require("allow_file_write")
        message = str(message or "").strip()
        if not message:
            raise ValueError("commit message is required")
        base = workspace.resolve_path(workspace_path or workspace.get_active()["active_path"])
        item = workspace.require_path_permission(base, "write")
        trusted = bool(item.get("trusted"))
        cfg = security.load()
        if cfg.get("approval_required_file_write", True) and not trusted and approval_id:
            approvals.require_approved(approval_id, "git_commit")
            approved = True
        if cfg.get("approval_required_file_write", True) and not trusted and not approved:
            preview = approvals.mutation_preview("git_commit", {
                "message": message,
                "workspace": workspace_path or workspace.get_active()["active_path"],
            }, task_id=_task_id, tool_call_id=_tool_call_id)
            approved = await self._wait_for_approval(preview, "git_commit", _task_id)
            if not approved:
                return preview
        result = await self._run_git(base, ["commit", "-m", message])
        audit.log("git_commit", {"cwd": str(base), "message_length": len(message), "trusted": trusted})
        return {"cwd": str(base), "message": message, **result}


async def demo_tool_call():
    mcp = McpLayer()
    return await mcp.call_tool("fs_list", {"path": "."})
