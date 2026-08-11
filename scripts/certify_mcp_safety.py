"""Certify the local MCP safety boundary without host or network actions.

The command runs a small deterministic exercise in an isolated data directory:
callable-only discovery, allowlisted assistant routing, a dry-run mutation
preview, a file-write approval preview, and redacted audit evidence. It never
starts an external MCP server, executes a host command, mutates the fixture
workspace, or contacts a remote endpoint.
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "rasputin.mcp-safety-certification.v1"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run(data_dir: Path) -> dict:
    os.environ["RASPUTIN_DATA_DIR"] = str(data_dir)
    from backend.assistant import runtime
    from backend.core import audit, workspace
    from backend.mcp import layer as mcp_layer
    from backend.mcp import tools as tool_relay

    policy = {
        "allow_file_read": True,
        "allow_file_write": True,
        "allow_file_move": True,
        "allow_shell_execution": False,
        "allow_web_search": False,
        "allow_docker_control": False,
        "approval_required_file_write": True,
        "approval_required_file_move": True,
        "approval_required_web_search": True,
    }

    with tempfile.TemporaryDirectory(prefix="rasputin-mcp-safety-workspace-") as workspace_dir:
        fixture = Path(workspace_dir)
        workspace_item = workspace.add(
            fixture,
            name="MCP safety certification fixture",
            permission_profile={"read": True, "write": True, "reorganize": False},
            owner_username="certification-owner",
        )
        with patch("backend.core.security.load", return_value=policy):
            catalog = tool_relay.catalog(include_external=False)
            callable_tools = list(catalog.get("callable_tools") or [])
            blocked_tools = [item for item in catalog.get("tools", []) if not item.get("callable")]
            schemas_valid = all(isinstance(item.get("input_schema"), dict) for item in callable_tools)
            no_disabled_tool_callable = not any(
                item.get("id") in {"docker_control", "shell_exec", "web_search"}
                for item in callable_tools
            )

            # The route preview may show an approval-ready read-only operation
            # when its policy flag is enabled, but it must never dispatch it.
            route_policy = {**policy, "allow_docker_control": True}
            with patch("backend.core.security.load", return_value=route_policy):
                read_only_route = runtime.route_command_preview("check docker status", workspace_ref=str(fixture))
                host_route = runtime.route_command_preview("open vscode", workspace_ref=str(fixture))
                unsafe_route = runtime.route_command_preview("docker status; rm -rf /", workspace_ref=str(fixture))

            layer = mcp_layer.McpLayer()
            dry_run = asyncio.run(layer.call_tool("workspace_mutation_preview", {
                "kind": "write",
                "workspace_path": str(fixture),
                "path": "would-be-created.txt",
                "content": "fixture content must never be written",
            }))
            write_preview = asyncio.run(layer.call_tool("fs_write", {
                "path": "approval-only.txt",
                "content": "private fixture content",
                "workspace_path": str(fixture),
            }))
            events = audit.recent(100)

        audit_actions = {str(item.get("action")) for item in events}
        blocked_ids = {str(item.get("id")) for item in blocked_tools}
        pass_checks = {
            "contract": catalog.get("contract", {}).get("name") == "rasputin.mcp.capabilities"
            and catalog.get("contract", {}).get("version") == "1.0"
            and catalog.get("contract", {}).get("discovery_mode") == "fail_closed",
            "callableSchemas": schemas_valid,
            "blockedHighRiskTools": no_disabled_tool_callable and "docker_control" in blocked_ids,
            "readOnlyRoute": read_only_route.get("route", {}).get("status") == "recognized"
            and read_only_route.get("route", {}).get("operation") == "docker_status"
            and not read_only_route.get("execution", {}).get("started"),
            "HostRouteRequiresGovernance": host_route.get("route", {}).get("status") in {"recognized", "blocked"}
            and not host_route.get("execution", {}).get("started")
            and host_route.get("approval", {}).get("state") in {"review_required", "blocked"},
            "UnsafeRouteRejected": unsafe_route.get("route", {}).get("status") == "rejected"
            and unsafe_route.get("approval", {}).get("state") == "blocked",
            "DryRunNoMutation": bool(dry_run.get("dry_run"))
            and dry_run.get("will_mutate") is False
            and not (fixture / "would-be-created.txt").exists(),
            "WriteApprovalNoMutation": bool(write_preview.get("preview"))
            and bool(write_preview.get("approval_id"))
            and not (fixture / "approval-only.txt").exists(),
            "AuditEvidence": {"approval_created", "approval_preview"}.issubset(audit_actions),
        }
    passed = all(pass_checks.values())
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "passed" if passed else "failed",
        "passed": passed,
        "checks": pass_checks,
        "evidence": {
            "toolCount": len(catalog.get("tools", [])),
            "callableToolCount": len(callable_tools),
            "blockedToolIds": sorted(blocked_ids),
            "workspaceId": workspace_item.get("id"),
            "auditActions": sorted(action for action in audit_actions if action in {"approval_created", "approval_preview"}),
        },
        "policy": {
            "isolatedDataDirectory": True,
            "externalMcpServersStarted": False,
            "hostCommandsStarted": False,
            "fixtureWorkspaceMutated": False,
            "remoteEndpointsContacted": False,
            "approvalBypassed": False,
        },
        "nextActions": [] if passed else ["Inspect the failed local MCP safety check and rerun in a fresh isolated data directory."],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        help="empty isolated directory to use; omitted means a temporary directory is removed after the run",
    )
    args = parser.parse_args(argv)
    try:
        if args.data_dir:
            data_dir = Path(args.data_dir).expanduser().resolve()
            if data_dir.exists() and any(data_dir.iterdir()):
                report = {
                    "schemaVersion": SCHEMA_VERSION,
                    "status": "blocked",
                    "passed": False,
                    "error": "refusing to write a non-empty data directory; use an isolated empty target",
                }
                print(json.dumps(report, indent=2, sort_keys=True))
                return 2
            data_dir.mkdir(parents=True, exist_ok=True)
            report = _run(data_dir)
        else:
            with tempfile.TemporaryDirectory(prefix="rasputin-mcp-safety-") as temp_dir:
                report = _run(Path(temp_dir))
                # sqlite3 connections used by the legacy runtime-store context
                # manager close on collection rather than on ``with`` exit.
                # Collect before TemporaryDirectory removes the isolated store
                # on Windows, where an open handle prevents cleanup.
                gc.collect()
    except (OSError, RuntimeError, ValueError) as exc:
        report = {
            "schemaVersion": SCHEMA_VERSION,
            "status": "failed",
            "passed": False,
            "error": str(exc)[:1000],
        }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
