"""Deny-by-default capability policy for unattended agent runs.

Prompt instructions are not a security boundary. When the appliance is
explicitly placed in unattended mode, this module constrains the tool surface
before any implementation receives model-authored arguments.
"""

from backend.core import security
from backend.core import workspace


# This is an allowlist, not a denylist: newly registered tools are blocked in
# unattended mode until they receive an explicit safety review.
UNATTENDED_SAFE_TOOL_IDS = frozenset({
    "rag_search",
    "graph_search",
    "graph_relations",
    "workspace_browse",
    "file_preview",
    "fs_list",
    "fs_tree",
    "fs_read",
    "fs_search",
    "workspace_mutation_preview",
    "memory_search",
    "archive_expand",
    "model_health",
    "git_status",
    "git_diff",
    "git_log",
    # File edits remain bounded by approved workspace containment and the
    # existing Trusted Dev/approval policy. They are deliberately not shell.
    "fs_write",
    "fs_patch",
})


def _workspace_path(args):
    values = args if isinstance(args, dict) else {}
    return values.get("workspace_path") or workspace.get_active().get("active_path")


def disabled_reason(tool_id, cfg=None, external=False, args=None):
    """Return a stable user-facing reason, or an empty string when allowed."""

    if not security.unattended_enabled(cfg):
        return ""
    if external:
        return "unattended mode blocks external MCP tools"
    if tool_id not in UNATTENDED_SAFE_TOOL_IDS:
        return f"unattended mode blocks {tool_id} until it is explicitly allowlisted"
    if tool_id in {"fs_write", "fs_patch"}:
        try:
            if not workspace.is_trusted(_workspace_path(args)):
                return "unattended file edits require a Trusted Dev workspace"
        except Exception:
            return "unattended file edits require a resolvable approved workspace"
    return ""


def enforce(tool_id, args=None, cfg=None, external=False):
    reason = disabled_reason(tool_id, cfg=cfg, external=external, args=args)
    if reason:
        raise PermissionError(reason)
    return True


def filter_definitions(definitions, cfg=None):
    """Hide tools that cannot be used in unattended mode from model schemas."""

    if not security.unattended_enabled(cfg):
        return list(definitions)
    return [item for item in definitions if item.get("id") in UNATTENDED_SAFE_TOOL_IDS]
