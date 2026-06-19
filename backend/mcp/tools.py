from copy import deepcopy

from backend.core import security as security

SENSITIVE_KEYS = {
    "content",
    "diff",
    "prompt",
    "model_output",
    "raw_output",
    "file_text",
    "text",
    "snippet",
    "body",
    "secret",
    "token",
    "api_key",
    "apiKey",
}


TOOL_DEFINITIONS = [
    {
        "id": "rag_search",
        "display_name": "RAG Search",
        "description": "Searches the local workspace index and returns cited local matches.",
        "category": "Knowledge",
        "risk": "safe",
        "permission_flag": "allow_file_read",
        "enabled": True,
        "implemented": True,
        "approval_behavior": "not_required",
        "timeout_seconds": 20,
        "output_summary_policy": "citations_only_no_chunk_text",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                "workspace_path": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    {
        "id": "graph_search",
        "display_name": "Graphify Search",
        "description": "Searches the local knowledge graph for related nodes and evidence-backed edges.",
        "category": "Knowledge",
        "risk": "safe",
        "permission_flag": "allow_file_read",
        "enabled": True,
        "implemented": True,
        "approval_behavior": "not_required",
        "timeout_seconds": 20,
        "output_summary_policy": "relationship_metadata_only",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": ["query"],
        },
    },
    {
        "id": "workspace_browse",
        "display_name": "Workspace Browse",
        "description": "Lists safe file and folder metadata inside an approved workspace root.",
        "category": "Workspace",
        "risk": "safe",
        "permission_flag": "allow_file_read",
        "enabled": True,
        "implemented": True,
        "approval_behavior": "not_required",
        "timeout_seconds": 15,
        "output_summary_policy": "metadata_only",
        "input_schema": {
            "type": "object",
            "properties": {
                "root_id": {"type": "string"},
                "path": {"type": "string"},
            },
        },
    },
    {
        "id": "file_preview",
        "display_name": "File Preview",
        "description": "Reads a small safe text preview from an approved workspace file.",
        "category": "Workspace",
        "risk": "safe",
        "permission_flag": "allow_file_read",
        "enabled": True,
        "implemented": True,
        "approval_behavior": "not_required",
        "timeout_seconds": 15,
        "output_summary_policy": "content_redacted_length_only",
        "input_schema": {
            "type": "object",
            "properties": {
                "root_id": {"type": "string"},
                "path": {"type": "string"},
                "max_bytes": {"type": "integer", "minimum": 1, "maximum": 131072},
            },
            "required": ["path"],
        },
    },
    {
        "id": "fs_list",
        "display_name": "File List",
        "description": "Lists direct children in an approved workspace folder.",
        "category": "Workspace",
        "risk": "safe",
        "permission_flag": "allow_file_read",
        "enabled": True,
        "implemented": True,
        "approval_behavior": "not_required",
        "timeout_seconds": 15,
        "output_summary_policy": "metadata_only",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "workspace_path": {"type": "string"},
            },
        },
    },
    {
        "id": "fs_tree",
        "display_name": "File Tree",
        "description": "Builds a bounded metadata tree inside an approved workspace.",
        "category": "Workspace",
        "risk": "safe",
        "permission_flag": "allow_file_read",
        "enabled": True,
        "implemented": True,
        "approval_behavior": "not_required",
        "timeout_seconds": 20,
        "output_summary_policy": "metadata_only",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "workspace_path": {"type": "string"},
                "max_items": {"type": "integer", "minimum": 1, "maximum": 300},
                "max_depth": {"type": "integer", "minimum": 0, "maximum": 6},
            },
        },
    },
    {
        "id": "fs_read",
        "display_name": "File Read",
        "description": "Reads bounded text content from an approved workspace file for local model context.",
        "category": "Workspace",
        "risk": "safe",
        "permission_flag": "allow_file_read",
        "enabled": True,
        "implemented": True,
        "approval_behavior": "not_required",
        "timeout_seconds": 20,
        "output_summary_policy": "content_redacted_length_only",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "workspace_path": {"type": "string"},
                "max_chars": {"type": "integer", "minimum": 1000, "maximum": 24000},
            },
            "required": ["path"],
        },
    },
    {
        "id": "fs_search",
        "display_name": "File Search",
        "description": "Searches file and folder names, with optional bounded text matching, inside an approved workspace.",
        "category": "Workspace",
        "risk": "safe",
        "permission_flag": "allow_file_read",
        "enabled": True,
        "implemented": True,
        "approval_behavior": "not_required",
        "timeout_seconds": 20,
        "output_summary_policy": "metadata_only",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "path": {"type": "string"},
                "workspace_path": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
                "include_content": {"type": "boolean"},
            },
            "required": ["query"],
        },
    },
    {
        "id": "workspace_mutation_preview",
        "display_name": "Workspace Mutation Preview",
        "description": "Builds a dry-run plan for future writes, folder creation, moves, renames, or organization without changing files.",
        "category": "Workspace",
        "risk": "guarded",
        "permission_flag": "allow_file_read",
        "enabled": True,
        "implemented": True,
        "approval_behavior": "preview_only",
        "timeout_seconds": 20,
        "output_summary_policy": "paths_and_actions_only",
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["write", "mkdir", "move", "rename", "organize"]},
                "workspace_path": {"type": "string"},
                "path": {"type": "string"},
                "source": {"type": "string"},
                "target": {"type": "string"},
                "content": {"type": "string"},
                "max_items": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["kind"],
        },
    },
    {
        "id": "archive_expand",
        "display_name": "Archive Expand",
        "description": "Fetches the full text of an archived message or tool result from the eviction log.",
        "category": "Knowledge",
        "risk": "safe",
        "permission_flag": None,
        "enabled": True,
        "implemented": True,
        "approval_behavior": "not_required",
        "timeout_seconds": 15,
        "output_summary_policy": "content_redacted_length_only",
        "input_schema": {
            "type": "object",
            "properties": {
                "archive_id": {"type": "string"},
            },
            "required": ["archive_id"],
        },
    },
    {
        "id": "memory_search",
        "display_name": "Memory Search",
        "description": "Searches local saved memory and session recall metadata.",
        "category": "Memory",
        "risk": "safe",
        "permission_flag": None,
        "enabled": True,
        "implemented": True,
        "approval_behavior": "not_required",
        "timeout_seconds": 15,
        "output_summary_policy": "memory_metadata_only",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": ["query"],
        },
    },
    {
        "id": "model_health",
        "display_name": "Model Health Test",
        "description": "Runs a small local health check against a registered model endpoint.",
        "category": "Models",
        "risk": "guarded",
        "permission_flag": "allow_model_tests",
        "enabled": True,
        "implemented": True,
        "approval_behavior": "not_required",
        "timeout_seconds": 30,
        "output_summary_policy": "status_latency_error_only",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
            },
            "required": ["key"],
        },
    },
    {
        "id": "fs_write",
        "display_name": "File Write",
        "description": "Previews a local workspace write and requires approval before mutation.",
        "category": "Workspace",
        "risk": "approval_required",
        "permission_flag": "allow_file_write",
        "enabled": True,
        "implemented": True,
        "approval_behavior": "one_time_approval",
        "timeout_seconds": 60,
        "output_summary_policy": "paths_and_byte_counts_only",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "workspace_path": {"type": "string"},
                "approval_id": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "id": "fs_mkdir",
        "display_name": "Folder Create",
        "description": "Previews local folder creation and requires approval before mutation.",
        "category": "Workspace",
        "risk": "approval_required",
        "permission_flag": "allow_file_reorganize",
        "enabled": True,
        "implemented": True,
        "approval_behavior": "one_time_approval",
        "timeout_seconds": 60,
        "output_summary_policy": "paths_only",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "workspace_path": {"type": "string"},
                "approval_id": {"type": "string"},
            },
            "required": ["path"],
        },
    },
    {
        "id": "fs_move",
        "display_name": "File Move",
        "description": "Previews local file or folder moves and requires approval before mutation.",
        "category": "Workspace",
        "risk": "approval_required",
        "permission_flag": "allow_file_reorganize",
        "enabled": True,
        "implemented": True,
        "approval_behavior": "one_time_approval",
        "timeout_seconds": 60,
        "output_summary_policy": "paths_only",
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "target": {"type": "string"},
                "workspace_path": {"type": "string"},
                "approval_id": {"type": "string"},
            },
            "required": ["source", "target"],
        },
    },
    {
        "id": "web_search",
        "display_name": "Web Search Broker",
        "description": "Runs brokered web search after leak checks and approval policy.",
        "category": "Web",
        "risk": "approval_required",
        "permission_flag": "allow_web_search",
        "enabled": True,
        "implemented": True,
        "approval_behavior": "policy_or_one_time_approval",
        "timeout_seconds": 30,
        "output_summary_policy": "titles_and_sources_only",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 10},
                "approval_id": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    {
        "id": "shell_exec",
        "display_name": "Shell Execution",
        "description": "Policy stub for future shell execution. Execution is not implemented in Tool Relay V1.",
        "category": "System",
        "risk": "approval_required",
        "permission_flag": "allow_shell_execution",
        "enabled": False,
        "implemented": False,
        "approval_behavior": "disabled_in_v1",
        "timeout_seconds": 0,
        "output_summary_policy": "not_available",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "id": "docker_control",
        "display_name": "Docker Control",
        "description": "Policy stub for future Docker actions. Warsat keeps its existing approval path.",
        "category": "System",
        "risk": "approval_required",
        "permission_flag": "allow_docker_control",
        "enabled": False,
        "implemented": False,
        "approval_behavior": "disabled_in_v1",
        "timeout_seconds": 0,
        "output_summary_policy": "not_available",
        "input_schema": {"type": "object", "properties": {}},
    },
]

_DEFINITIONS = {item["id"]: item for item in TOOL_DEFINITIONS}
TOOL_SPECS = {
    item["id"]: {
        "risk": item["risk"],
        "permission": item.get("permission_flag"),
        "approval_behavior": item.get("approval_behavior"),
    }
    for item in TOOL_DEFINITIONS
}


def get(tool_id):
    definition = _DEFINITIONS.get(tool_id)
    if definition:
        return definition
    if str(tool_id or "").startswith("mcp:"):
        from . import relay as mcp_relay
        return mcp_relay.get_tool_definition(tool_id)
    return None


def require_definition(tool_id):
    definition = get(tool_id)
    if not definition:
        from backend.core.response import AppError
        raise AppError("tool_missing", f"Tool '{tool_id}' is not registered.", 404)
    if not definition.get("implemented", False):
        from backend.core.response import AppError
        raise AppError("tool_unavailable", f"Tool '{tool_id}' is not available in Tool Relay V1.", 501)
    return definition


def permission_allowed(definition, cfg=None):
    flag = definition.get("permission_flag")
    if not flag:
        return True
    return bool((cfg or security.load()).get(flag))


def disabled_reason(definition, cfg=None):
    if not definition.get("implemented", False):
        return "Not implemented in Tool Relay V1."
    if not definition.get("enabled", True):
        return "Disabled by Tool Relay policy."
    flag = definition.get("permission_flag")
    if flag and not permission_allowed(definition, cfg):
        return f"{flag} is disabled."
    return ""


def public_definition(definition, cfg=None):
    cfg = cfg or security.load()
    item = deepcopy(definition)
    reason = disabled_reason(item, cfg)
    item["available"] = not bool(reason)
    item["disabled_reason"] = reason
    return item


def catalog(include_external=True):
    cfg = security.load()
    tools = [public_definition(item, cfg) for item in TOOL_DEFINITIONS]
    if include_external:
        try:
            from . import relay as mcp_relay
            tools.extend(mcp_relay.external_tool_definitions())
        except Exception:
            pass
    categories = []
    for item in tools:
        if item["category"] not in categories:
            categories.append(item["category"])
    return {
        "tools": tools,
        "groups": [
            {
                "category": category,
                "tools": [item for item in tools if item["category"] == category],
            }
            for category in categories
        ],
    }


def _short_text(value, max_len=160):
    text = str(value or "")
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _redacted_blob(value):
    text = "" if value is None else str(value)
    return {"redacted": True, "chars": len(text)}


def _safe_value(key, value, tool_id=None):
    key_text = str(key or "")
    lower = key_text.lower()
    if key_text in SENSITIVE_KEYS or lower in SENSITIVE_KEYS:
        return _redacted_blob(value)
    if any(marker in lower for marker in ["secret", "token", "api_key", "apikey", "password"]):
        return "[redacted]"
    if lower == "query":
        if tool_id == "web_search":
            return _redacted_blob(value)
        text = str(value or "")
        if "\n" in text or len(text) > 180:
            return _redacted_blob(value)
        return _short_text(text, 160)
    if isinstance(value, dict):
        return {k: _safe_value(k, v, tool_id) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_value(key, item, tool_id) for item in value[:20]]
    if isinstance(value, str):
        if "path" in lower or lower in {"source", "target", "workspace", "relative_path", "relativePath"}:
            return _short_text(value, 180)
        if len(value) > 240:
            return _short_text(value, 240)
    return value


def redact_args(tool_id, args):
    return _safe_value("", dict(args or {}), tool_id)


def _summarize_hits(hits):
    out = []
    for hit in (hits or [])[:10]:
        out.append({
            "score": hit.get("score"),
            "source": hit.get("source"),
            "path": hit.get("path"),
            "chunk": hit.get("chunk"),
            "line_start": hit.get("line_start"),
            "line_end": hit.get("line_end"),
            "citation": hit.get("citation"),
        })
    return out


def _summarize_memory(items):
    out = []
    for item in (items or [])[:10]:
        out.append({
            "id": item.get("id"),
            "kind": item.get("kind"),
            "scope": item.get("scope"),
            "workspace_id": item.get("workspace_id"),
            "sensitive": bool(item.get("sensitive")),
            "status": item.get("status"),
        })
    return out


def summarize_result(tool_id, result):
    if not isinstance(result, dict):
        return _safe_value("", result, tool_id)
    if tool_id == "rag_search":
        return {
            "query": _safe_value("query", result.get("query"), tool_id),
            "hit_count": len(result.get("hits") or []),
            "hits": _summarize_hits(result.get("hits")),
            "blocked": result.get("blocked", False),
        }
    if tool_id == "graph_search":
        return {
            "query": _safe_value("query", result.get("query"), tool_id),
            "node_count": len(result.get("nodes") or []),
            "edge_count": len(result.get("edges") or []),
            "nodes": _safe_value("nodes", result.get("nodes", [])[:10], tool_id),
            "edges": _safe_value("edges", result.get("edges", [])[:10], tool_id),
            "blocked": result.get("blocked", False),
        }
    if tool_id == "memory_search":
        return {
            "query": _safe_value("query", result.get("query"), tool_id),
            "item_count": len(result.get("items") or []),
            "items": _summarize_memory(result.get("items")),
        }
    if tool_id in {"fs_read", "file_preview"}:
        return {
            "path": result.get("path"),
            "relative_path": result.get("relativePath") or result.get("relative_path"),
            "content": _redacted_blob(result.get("content")),
            "truncated": result.get("truncated", False),
            "bytes": result.get("bytes"),
            "size": result.get("size"),
        }
    if tool_id in {"fs_list", "fs_tree", "workspace_browse"}:
        entries = result.get("entries") or result.get("items") or []
        return {
            "path": result.get("path"),
            "root_id": result.get("rootId") or result.get("root_id"),
            "entry_count": len(entries),
            "truncated": result.get("truncated", False),
            "entries": _safe_value("entries", entries[:30], tool_id),
        }
    if tool_id == "fs_search":
        matches = result.get("matches") or []
        return {
            "path": result.get("path"),
            "query": _safe_value("query", result.get("query"), tool_id),
            "match_count": len(matches),
            "searched": result.get("searched"),
            "truncated": result.get("truncated", False),
            "matches": [
                {
                    "path": item.get("path"),
                    "kind": item.get("kind"),
                    "extension": item.get("extension"),
                    "score": item.get("score"),
                    "match_type": item.get("match_type"),
                    "previewable": item.get("previewable"),
                }
                for item in matches[:30]
            ],
        }
    if tool_id == "workspace_mutation_preview":
        return {
            "kind": result.get("kind"),
            "dry_run": result.get("dry_run", True),
            "will_mutate": result.get("will_mutate", False),
            "workspace": result.get("workspace"),
            "affected_path_count": len(result.get("affected_paths") or []),
            "step_count": len(result.get("steps") or []),
            "warnings": _safe_value("warnings", result.get("warnings", [])[:10], tool_id),
            "affected_paths": _safe_value("affected_paths", result.get("affected_paths", [])[:20], tool_id),
            "steps": _safe_value("steps", result.get("steps", [])[:20], tool_id),
            "rollback_notes": _safe_value("rollback_notes", result.get("rollback_notes", [])[:5], tool_id),
        }
    if tool_id == "model_health":
        return {
            "ok": result.get("ok"),
            "status": result.get("status"),
            "latency_ms": result.get("latency_ms") or result.get("latencyMs"),
            "message": result.get("message"),
            "error": result.get("error"),
        }
    if tool_id == "web_search":
        return {
            "query": _safe_value("query", result.get("query"), tool_id),
            "result_count": len(result.get("results") or []),
            "results": _safe_value("results", result.get("results", [])[:10], tool_id),
            "error": result.get("error"),
        }
    return _safe_value("", result, tool_id)
