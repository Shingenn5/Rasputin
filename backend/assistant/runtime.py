"""Rasputin orchestration preview and approval-aware broker boundary.

The preview is deliberately a contract boundary: it can inspect owner-scoped
context and the registered model fleet, but it never starts a task, container,
process, microphone, or speaker.  Broker preparation validates the approved
request and records a durable, side-effect-free envelope; dispatch then invokes
only the concrete allowlisted adapter selected by the approved operation.
"""

from __future__ import annotations

import json
from typing import Any

from backend.assistant.contracts import (
    CONTROL_OPERATIONS,
    DEFAULT_PROFILE,
    MODEL_PACK_ROLES,
    WORKFLOW_DEFINITIONS,
    VOICE_LOOP_STAGES,
    VOICE_ROLES,
    merge_profile,
    normalize_agents,
    normalize_model_pack,
    normalize_operations,
    sanitize_profile,
)
from backend.assistant import broker
from backend.assistant import voice as voice_adapter
from backend.core import audit
from backend.core import approvals
from backend.core import runtime_store as store
from backend.core.response import AppError
from backend.core import security
from backend.core import workspace
from backend.models import providers as model_providers
from backend.models import registry as model_registry
from backend.rag import memory as memory_store


PROFILE_KEY_PREFIX = "assistant_profile:"
BROKER_CONTRACT_VERSION = "0.1"
COMMAND_ROUTER_CONTRACT_VERSION = "0.1"

# Natural-language routing is deterministic and allowlisted. It produces a
# preview; it never turns user text into a shell command or starts a host
# process. New aliases must map to an existing CONTROL_OPERATIONS entry and
# receive a regression test before they become routable.
COMMAND_ALIASES = {
    "docker_status": (
        "docker status",
        "check docker status",
        "show docker status",
        "inspect docker status",
    ),
    "open_vscode": (
        "open vscode",
        "open vs code",
        "open visual studio code",
        "launch vscode",
        "launch vs code",
    ),
    "start_coding_task": (
        "start coding task",
        "begin coding task",
        "start a coding task",
        "begin a coding task",
    ),
    "run_test": (
        "run test",
        "run tests",
        "run the tests",
        "execute tests",
        "test the project",
    ),
    "run_build": (
        "run build",
        "run the build",
        "build the project",
        "build project",
    ),
    "transcribe": (
        "transcribe",
        "transcribe audio",
        "speech to text",
    ),
    "synthesize": (
        "synthesize speech",
        "text to speech",
        "read this aloud",
        "speak the response",
    ),
}
COMMAND_ROUTER_PREFIXES = ("please ", "can you ", "could you ", "would you ")
COMMAND_ROUTER_UNSAFE_MARKERS = ("&&", "||", ";", "|", ">", "<")


def _owner(owner_id: str | None) -> str:
    return str(owner_id or "admin").strip() or "admin"


def get_profile(owner_id: str = "admin") -> dict[str, Any]:
    owner = _owner(owner_id)
    saved = store.get_kv(f"{PROFILE_KEY_PREFIX}{owner}")
    return sanitize_profile(saved, owner)


def update_profile(owner_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    owner = _owner(owner_id)
    profile = merge_profile(get_profile(owner), updates, owner)
    store.set_kv(f"{PROFILE_KEY_PREFIX}{owner}", profile)
    audit.log(
        "assistant_profile_updated",
        {"owner_id": owner, "fields": sorted(str(key) for key in (updates or {}) if str(key) in {"display_name", "persona", "mission", "voice_policy"})},
        actor=owner,
    )
    return profile


def capabilities() -> dict[str, Any]:
    cfg = security.load()
    return {
        "contract_version": DEFAULT_PROFILE["contract_version"],
        "identity": {"assistant_id": "rasputin", "display_name": "Rasputin"},
        "model_roles": sorted(MODEL_PACK_ROLES),
        "voice_roles": sorted(VOICE_ROLES),
        "voice": voice_adapter.capabilities(),
        "workflows": [dict(workflow) for workflow in WORKFLOW_DEFINITIONS],
        "model_pack_storage": "owner_scoped",
        "context_capsules": {
            "supported": True,
            "storage": "owner_scoped_sqlite",
            "approval_required": True,
            "default_ttl_seconds": 3600,
            "max_ttl_seconds": 604800,
        },
        "control_operations": {
            name: {
                "operation": name,
                "label": definition["label"],
                "category": definition["category"],
                "risk": definition["risk"],
                "requires_approval": definition["requires_approval"],
                "security_flag": definition["security_flag"],
            }
            for name, definition in CONTROL_OPERATIONS.items()
        },
        "security": {
            "privacy_lock": bool(cfg.get("privacy_lock", True)),
            "allow_shell_execution": bool(cfg.get("allow_shell_execution", False)),
            "allow_docker_control": bool(cfg.get("allow_docker_control", False)),
            "model_containers_have_host_access": False,
            "broker_only": True,
        },
        "broker": {
            "contract_version": BROKER_CONTRACT_VERSION,
            "preparation_supported": True,
            "execution_enabled": bool(broker.supported_operations()),
            "dispatch_supported_operations": broker.supported_operations(),
            "dispatch_operation_metadata": [
                {"operation": name, **metadata}
                for name, metadata in broker.operation_metadata().items()
            ],
        },
        "command_router": {
            "contract_version": COMMAND_ROUTER_CONTRACT_VERSION,
            "preview_endpoint": "/api/assistant/command-preview",
            "execution_mode": "preview_only",
            "approval_before_handoff": True,
            "supported_operations": broker.supported_operations(),
            "aliases": {operation: list(aliases) for operation, aliases in COMMAND_ALIASES.items()},
        },
    }


def _session_reference(owner_id: str, session_id: str | None) -> dict[str, Any] | None:
    if not session_id:
        return None
    store.init_db()
    with store._lock, store.connect() as conn:
        row = conn.execute(
            "SELECT id,title,status,workspace,model,mode,updated_at FROM sessions WHERE id=? AND owner_id=?",
            (str(session_id), owner_id),
        ).fetchone()
    if not row:
        raise ValueError("session missing")
    return dict(row)


def _selected_session_context(owner_id: str, session_id: str | None, limit: int = 12) -> dict[str, Any] | None:
    """Return a small, owner-validated excerpt for an explicitly selected session."""
    session = _session_reference(owner_id, session_id)
    if not session:
        return None
    cap = max(1, min(int(limit or 12), 20))
    store.init_db()
    with store._lock, store.connect() as conn:
        total_row = conn.execute(
            "SELECT COUNT(*) AS count FROM messages WHERE session_id=? AND evicted=0",
            (session["id"],),
        ).fetchone()
        rows = conn.execute(
            """
            SELECT id,role,content,task_id,created_at
            FROM messages
            WHERE session_id=? AND evicted=0
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session["id"], cap),
        ).fetchall()
    messages = [
        {
            "id": row["id"],
            "role": row["role"],
            "content": str(row["content"] or "")[:1200],
            "task_id": row["task_id"],
            "created_at": row["created_at"],
        }
        for row in reversed(rows)
    ]
    total = int(total_row["count"] if total_row else 0)
    return {
        **session,
        "messages": messages,
        "message_count": total,
        "messages_truncated": total > len(messages),
    }


def _safe_context_item(item: dict[str, Any], include_sensitive: bool) -> dict[str, Any] | None:
    if bool(item.get("sensitive")) and not include_sensitive:
        return None
    content = item.get("content")
    if isinstance(content, str):
        content = content[:1200]
    elif isinstance(content, (dict, list)):
        try:
            content = json.loads(json.dumps(content))
        except Exception:
            content = str(content)[:1200]
    else:
        content = str(content or "")[:1200]
    return {
        "id": item.get("id"),
        "kind": item.get("kind"),
        "scope": item.get("scope"),
        "workspace_id": item.get("workspace_id"),
        "content": content,
        "sensitive": bool(item.get("sensitive")),
        "updated_at": item.get("updated_at"),
        "retention": item.get("retention") or "persistent",
        "expires_at": item.get("expires_at"),
        "source_task_id": item.get("source_task_id"),
        "source_session_id": item.get("source_session_id"),
        "source_message_ids": item.get("source_message_ids") or [],
        "confidence": item.get("confidence"),
        "importance": item.get("importance"),
    }


def build_context_preview(
    owner_id: str,
    objective: str,
    workspace_ref: str,
    session_id: str | None = None,
    context_query: str | None = None,
    include_sensitive: bool = False,
) -> dict[str, Any]:
    owner = _owner(owner_id)
    query = str(context_query or objective or "").strip()[:500]
    session = _selected_session_context(owner, session_id)
    memory_result = memory_store.search(query, limit=12, owner_id=owner, workspace_id=workspace_ref) if query else {"items": []}
    memory_items = []
    excluded_sensitive = 0
    for item in memory_result.get("items", []):
        safe_item = _safe_context_item(item, include_sensitive)
        if safe_item is None:
            excluded_sensitive += 1
        else:
            memory_items.append(safe_item)
    history = store.universal_search(owner, query, limit=18) if query else {"query": "", "results": [], "count": 0}
    return {
        "query": query,
        "workspace_ref": workspace_ref,
        "selected_session": session,
        "memory": {
            "items": memory_items,
            "matched": len(memory_result.get("items", [])),
            "sensitive_excluded": excluded_sensitive,
        },
        "owner_history": {
            "results": history.get("results", []),
            "matched": history.get("count", 0),
        },
        "provenance": {
            "source_session_id": session.get("id") if session else None,
            "source_session_mode": session.get("mode") if session else None,
            "workspace_ref": workspace_ref,
            "query": query,
            "memory_item_ids": [item.get("id") for item in memory_items if item.get("id")],
            "history_result_ids": [item.get("id") for item in history.get("results", []) if item.get("id")],
        },
        "policy": {
            "owner_scoped": True,
            "cross_workspace": True,
            "sensitive_included": bool(include_sensitive),
            "no_unscoped_database_reads": True,
        },
    }


def create_context_capsule(
    owner_id: str,
    objective: str,
    workspace_ref: str,
    session_id: str | None = None,
    context_query: str | None = None,
    include_sensitive: bool = False,
    expires_in_seconds: int = 3600,
) -> dict[str, Any]:
    context = build_context_preview(
        owner_id=owner_id,
        objective=objective,
        workspace_ref=workspace_ref,
        session_id=session_id,
        context_query=context_query,
        include_sensitive=include_sensitive,
    )
    record = store.create_assistant_context_capsule(
        owner_id=owner_id,
        objective=objective,
        workspace_ref=workspace_ref,
        context=context,
        provenance=context.get("provenance"),
        expires_in_seconds=expires_in_seconds,
    )
    audit.log(
        "assistant_context_capsule_created",
        {
            "capsule_id": record["id"],
            "source_session_id": context.get("provenance", {}).get("source_session_id"),
            "expires_at": record.get("expires_at"),
        },
        actor=_owner(owner_id),
    )
    return record


def get_context_capsule(owner_id: str, capsule_id: str) -> dict[str, Any] | None:
    return store.get_assistant_context_capsule(_owner(owner_id), capsule_id)


def list_context_capsules(owner_id: str, limit: int = 50) -> list[dict[str, Any]]:
    return store.list_assistant_context_capsules(_owner(owner_id), limit)


def review_context_capsule(owner_id: str, capsule_id: str, status: str, note: str = "") -> dict[str, Any]:
    owner = _owner(owner_id)
    current = store.get_assistant_context_capsule(owner, capsule_id)
    if not current:
        raise ValueError("assistant context capsule missing")
    updated = store.transition_assistant_context_capsule(owner, capsule_id, status, actor=owner, review_note=note)
    if not updated:
        raise ValueError("assistant context capsule missing")
    audit.log(
        "assistant_context_capsule_reviewed",
        {"capsule_id": capsule_id, "status": status},
        actor=owner,
    )
    return updated


def _approved_context_capsule(owner_id: str, capsule_id: str) -> dict[str, Any]:
    capsule = store.get_assistant_context_capsule(_owner(owner_id), capsule_id)
    if not capsule:
        raise ValueError("assistant context capsule missing")
    if capsule.get("status") == "expired":
        raise AppError("assistant_context_capsule_expired", "The context capsule has expired.", 409)
    if capsule.get("status") != "approved":
        raise AppError("assistant_context_capsule_not_approved", "Approve the context capsule before using it in a plan.", 409)
    context = dict(capsule.get("context") or {})
    context["capsule"] = {
        "id": capsule["id"],
        "status": capsule["status"],
        "approved_at": capsule.get("approved_at"),
        "approved_by": capsule.get("approved_by"),
        "expires_at": capsule.get("expires_at"),
        "provenance": capsule.get("provenance") or {},
    }
    return context


def _model_lookup() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    models = [dict(model) for model in model_registry.all_models()]
    return models, {str(model.get("key")): model for model in models if model.get("key")}


def _model_for_entry(entry: dict[str, Any], models: list[dict[str, Any]], by_key: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    requested_key = entry.get("model_key")
    if requested_key and requested_key in by_key:
        return by_key[requested_key]
    role = entry.get("role")
    candidates = [model for model in models if model.get("role") == role and model.get("enabled", True)]
    return candidates[0] if candidates else None


def _model_status(entry: dict[str, Any], model: dict[str, Any] | None, security_cfg: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if not model:
        blockers.append("model_not_registered")
        return {
            "entry_id": entry["id"],
            "model_key": entry.get("model_key") or None,
            "role": entry["role"],
            "required": entry["required"],
            "status": "missing",
            "next_action": "register_model",
            "blocked_reasons": blockers,
            "warnings": warnings,
            "runtime_status": "missing",
            "host_control_required": False,
        }
    runtime_status = str(model.get("runtime_status") or "unknown")
    if not model.get("enabled", True):
        blockers.append("model_disabled")
    if runtime_status in {"unhealthy", "stopped", "unreachable", "error"}:
        blockers.append(f"runtime_{runtime_status}")
    if runtime_status == "unknown":
        warnings.append("runtime_health_unknown")
    managed = bool(model.get("managed"))
    if managed and not security_cfg.get("allow_docker_control", False):
        blockers.append("docker_control_disabled")
    status = "blocked" if blockers else ("needs_health_check" if warnings else "ready")
    return {
        "entry_id": entry["id"],
        "model_key": model.get("key"),
        "role": entry["role"],
        "required": entry["required"],
        "status": status,
        "next_action": "start_or_health_check" if managed else "health_check" if warnings else "use_registered_model",
        "blocked_reasons": blockers,
        "warnings": warnings,
        "runtime_status": runtime_status,
        "provider": model.get("provider"),
        "managed": managed,
        "host_control_required": managed,
        "capabilities": entry.get("capabilities", []),
    }


def build_model_pack_preview(pack: Any) -> dict[str, Any]:
    normalized = normalize_model_pack(pack)
    models, by_key = _model_lookup()
    cfg = security.load()
    entries = [_model_status(entry, _model_for_entry(entry, models, by_key), cfg) for entry in normalized["entries"]]
    return {
        **normalized,
        "entries": entries,
        "placement_policy": {
            "default": "largest_fitting_single_gpu_first",
            "combined_vram": "explicit_backend_only",
            "vllm_tensor_parallel": "not_assumed",
            "capacity_status": "not_evaluated_without_runtime_inventory",
        },
        "launch_policy": {
            "mode": "broker_only",
            "started": False,
            "side_effects": False,
            "model_containers_receive_scoped_requests_only": True,
        },
    }


def save_model_pack(owner_id: str, pack: Any) -> dict[str, Any]:
    normalized = normalize_model_pack(pack)
    record = store.upsert_assistant_model_pack(
        _owner(owner_id),
        normalized["pack_id"],
        normalized["version"],
        normalized,
    )
    audit.log(
        "assistant_model_pack_saved",
        {"pack_id": normalized["pack_id"], "entry_count": len(normalized["entries"])},
        actor=_owner(owner_id),
    )
    return {
        **record,
        "preview": build_model_pack_preview(normalized),
        "launch_policy": {"started": False, "side_effects": False, "broker_only": True},
    }


def get_model_pack(owner_id: str, pack_id: str, include_preview: bool = True) -> dict[str, Any] | None:
    record = store.get_assistant_model_pack(_owner(owner_id), pack_id)
    if not record:
        return None
    if include_preview:
        record = {
            **record,
            "preview": build_model_pack_preview(record.get("pack") or {}),
            "launch_policy": {"started": False, "side_effects": False, "broker_only": True},
        }
    return record


def list_model_packs(owner_id: str, limit: int = 50) -> list[dict[str, Any]]:
    return [
        {
            **record,
            "launch_policy": {"started": False, "side_effects": False, "broker_only": True},
        }
        for record in store.list_assistant_model_packs(_owner(owner_id), limit)
    ]


def delete_model_pack(owner_id: str, pack_id: str) -> dict[str, Any]:
    deleted = store.delete_assistant_model_pack(_owner(owner_id), pack_id)
    if not deleted:
        raise ValueError("model pack missing")
    audit.log("assistant_model_pack_deleted", {"pack_id": pack_id}, actor=_owner(owner_id))
    return {"deleted": True, "pack_id": pack_id}


def build_voice_loop_preview(
    owner_id: str,
    model_pack: Any = None,
    model_pack_id: str | None = None,
    input_model_key: str | None = None,
    main_model_key: str | None = None,
    output_model_key: str | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Resolve the local voice turn contract without touching audio devices."""

    pack_source = "inline"
    if model_pack_id:
        saved_pack = get_model_pack(owner_id, model_pack_id, include_preview=False)
        if not saved_pack:
            raise ValueError("model pack missing")
        if model_pack is not None:
            raise ValueError("choose either model_pack or model_pack_id")
        model_pack = saved_pack.get("pack")
        pack_source = "saved"
    normalized_pack = normalize_model_pack(model_pack)
    models, by_key = _model_lookup()
    overrides = {
        "speech_to_text": str(input_model_key or "").strip(),
        "main": str(main_model_key or "").strip(),
        "text_to_speech": str(output_model_key or "").strip(),
    }
    stages = []
    blockers = []
    for stage in VOICE_LOOP_STAGES:
        role = stage["role"]
        pack_entry = next((entry for entry in normalized_pack["entries"] if entry.get("role") == role), None)
        selected_key = overrides.get(role) or (pack_entry or {}).get("model_key")
        entry = {
            "id": (pack_entry or {}).get("id") or stage["id"],
            "role": role,
            "model_key": selected_key,
            "required": True,
            "capabilities": [stage["capability"]],
        }
        model = None if selected_key and selected_key not in by_key else _model_for_entry(entry, models, by_key)
        status = _model_status(entry, model, security.load())
        if model and str(model.get("role") or "") != role:
            status.update(
                {
                    "status": "blocked",
                    "next_action": "select_role_compatible_model",
                    "blocked_reasons": ["model_role_mismatch"],
                }
            )
        status.update(
            {
                "stage": stage["id"],
                "label": stage["label"],
                "capability": stage["capability"],
                "selected_from": "override" if overrides.get(role) else "model_pack" if pack_entry else "registry_role",
            }
        )
        stages.append(status)
        if status.get("status") in {"blocked", "missing"}:
            blockers.extend(f"voice:{stage['id']}:{reason}" for reason in status.get("blocked_reasons", []))

    ready = not blockers
    return {
        "adapter": voice_adapter.capabilities(),
        "model_pack_source": pack_source,
        "model_pack_id": normalized_pack["pack_id"],
        "conversation_id": str(conversation_id or "").strip()[:120] or None,
        "loop": [stage["id"] for stage in VOICE_LOOP_STAGES],
        "stages": stages,
        "ready": ready,
        "blockers": sorted(set(blockers)),
        "next_actions": [
            "Register reachable speech-to-text, main, and text-to-speech models before starting a voice turn." if not ready else "Review the voice loop and explicitly start an approved audio adapter when one is available.",
            "Keep microphone and speaker access behind a local adapter; this preview starts no audio I/O.",
        ],
        "execution": {
            "mode": "preview_only",
            "started": False,
            "models_started": False,
            "transcription_started": False,
            "synthesis_started": False,
            "audio_io_started": False,
            "side_effects": False,
        },
        "policy": {
            "owner_scoped": True,
            "local_only": True,
            "broker_only": True,
            "direct_model_host_access": False,
            "microphone_access": "not_started",
            "speaker_access": "not_started",
        },
    }


def _resolve_agent_model(agent: dict[str, Any], model_pack: dict[str, Any], models: list[dict[str, Any]]) -> str | None:
    if agent.get("model_key"):
        return agent["model_key"]
    for entry in model_pack.get("entries", []):
        if entry.get("role") == agent.get("role") and entry.get("model_key"):
            return entry.get("model_key")
    for model in models:
        if model.get("role") == agent.get("role") and model.get("enabled", True):
            return model.get("key")
    return None


def build_agent_preview(objective: str, raw_agents: Any, model_pack: dict[str, Any]) -> dict[str, Any]:
    agents = normalize_agents(raw_agents, objective)
    models, _ = _model_lookup()
    steps = []
    for agent in agents:
        steps.append(
            {
                **agent,
                "resolved_model_key": _resolve_agent_model(agent, model_pack, models),
                "owner": "rasputin",
                "execution_state": "preview_only",
                "side_effects": False,
                "host_access": "none",
            }
        )
    return {
        "strategy": "rasputin_plans_then_delegates",
        "agents": steps,
        "dependency_edges": [
            {"from": dependency, "to": agent["id"]}
            for agent in agents
            for dependency in agent["depends_on"]
        ],
        "execution": {"started": False, "side_effects": False, "requires_broker": True},
    }


def _normalize_command_text(value: Any) -> str:
    text = " ".join(str(value or "").strip().lower().split())
    return text.strip(" .!?\t\r\n")[:500]


def _match_command_alias(normalized: str) -> tuple[str | None, str | None]:
    for operation, aliases in COMMAND_ALIASES.items():
        for alias in aliases:
            if normalized == alias:
                return operation, alias
            for prefix in COMMAND_ROUTER_PREFIXES:
                if normalized == f"{prefix}{alias}":
                    return operation, alias
    return None, None


def route_command_preview(command: Any, workspace_ref: str | None = None) -> dict[str, Any]:
    """Map one explicit assistant command to a side-effect-free broker preview.

    This is intentionally a small deterministic router. It accepts only known
    aliases, never accepts arbitrary command text, and does not create an
    approval or handoff. The existing plan/handoff endpoints remain the only
    path from this preview to execution.
    """

    raw_command = str(command or "").strip()[:500]
    normalized = _normalize_command_text(raw_command)
    base = {
        "contract_version": COMMAND_ROUTER_CONTRACT_VERSION,
        "command": raw_command,
        "normalized_command": normalized,
        "execution": {
            "mode": "preview_only",
            "started": False,
            "side_effects": False,
            "host_actions_started": False,
        },
        "policy": {
            "broker_only": True,
            "direct_model_host_access": False,
            "approval_before_handoff": True,
        },
    }
    if not normalized:
        return {
            **base,
            "route": {
                "status": "needs_clarification",
                "operation": None,
                "matched_alias": None,
                "reason": "command is empty",
            },
            "approval": {"required": False, "state": "not_requested"},
            "operation_preview": None,
        }
    if any(marker in normalized or marker in raw_command for marker in COMMAND_ROUTER_UNSAFE_MARKERS) or chr(96) in raw_command:
        return {
            **base,
            "route": {
                "status": "rejected",
                "operation": None,
                "matched_alias": None,
                "reason": "shell-like command syntax is not accepted by the assistant router",
            },
            "approval": {"required": False, "state": "blocked"},
            "operation_preview": None,
        }

    operation, alias = _match_command_alias(normalized)
    if not operation:
        return {
            **base,
            "route": {
                "status": "needs_clarification",
                "operation": None,
                "matched_alias": None,
                "reason": "no allowlisted assistant operation matched",
                "suggested_operations": sorted(COMMAND_ALIASES),
            },
            "approval": {"required": False, "state": "not_requested"},
            "operation_preview": None,
        }

    preview = build_control_preview([operation], workspace_ref=workspace_ref)
    planned = (preview.get("operations") or [None])[0]
    supported = bool((planned or {}).get("dispatch", {}).get("supported"))
    blocked = bool((planned or {}).get("blocked_reasons")) or not supported
    blocked_reasons = list((planned or {}).get("blocked_reasons") or [])
    if not supported and "operation_not_supported_by_broker" not in blocked_reasons:
        blocked_reasons.append("operation_not_supported_by_broker")
    route_status = "blocked" if blocked else "recognized"
    approval_required = bool((planned or {}).get("requires_approval", False))
    approval_state = "blocked" if blocked else "review_required" if approval_required else "not_required"
    return {
        **base,
        "route": {
            "status": route_status,
            "operation": operation,
            "matched_alias": alias,
            "reason": "allowlisted operation matched" if not blocked else "operation cannot proceed under current broker or security policy",
            "supported_by_broker": supported,
            "blocked_reasons": blocked_reasons,
        },
        "approval": {
            "required": approval_required,
            "state": approval_state,
            "created": False,
        },
        "operation_preview": planned,
    }


def build_control_preview(requested_operations: Any, workspace_ref: str | None = None) -> dict[str, Any]:
    operations = normalize_operations(requested_operations)
    cfg = security.load()
    adapter_metadata = broker.operation_metadata()
    planned = []
    for operation in operations:
        definition = CONTROL_OPERATIONS.get(operation)
        if not definition:
            planned.append(
                {
                    "operation": operation,
                    "status": "blocked",
                    "blocked_reasons": ["operation_not_supported_by_broker"],
                    "execution_state": "not_started",
                    "broker_only": True,
                }
            )
            continue
        required_flag = definition.get("security_flag")
        enabled = required_flag is None or bool(cfg.get(required_flag, False))
        blocked_reasons = [] if enabled else [f"security_flag_disabled:{required_flag}"]
        adapter = adapter_metadata.get(operation, {})
        if adapter.get("requires_workspace"):
            if not workspace_ref:
                blocked_reasons.append("workspace_required")
            else:
                try:
                    target = workspace.resolve_path(workspace_ref)
                    if not target.exists() or not target.is_dir():
                        blocked_reasons.append("workspace_missing")
                    elif adapter.get("requires_host_shell", True) and not workspace.is_host_shell_allowed(target):
                        blocked_reasons.append("workspace_host_shell_disabled")
                except (OSError, ValueError):
                    blocked_reasons.append("workspace_not_approved")
        planned.append(
            {
                "operation": operation,
                "label": definition["label"],
                "category": definition["category"],
                "risk": definition["risk"],
                "requires_approval": definition["requires_approval"],
                "security_flag": required_flag,
                "status": "planned" if not blocked_reasons else "blocked",
                "blocked_reasons": blocked_reasons,
                "execution_state": "not_started",
                "broker_only": True,
                "direct_model_host_access": False,
                "dispatch": {
                    "supported": operation in adapter_metadata,
                    "adapter": adapter.get("adapter"),
                    "action_kind": adapter.get("action_kind"),
                    "requires_workspace": bool(adapter.get("requires_workspace")),
                    "side_effects": bool(adapter.get("side_effects")),
                    "host_mutation": bool(adapter.get("host_mutation")),
                },
            }
        )
    return {
        "operations": planned,
        "policy": {
            "broker_only": True,
            "approval_before_execution": True,
            "direct_model_host_access": False,
            "started": False,
            "side_effects": False,
        },
    }


def _resolve_coding_model(model_pack: dict[str, Any], agent_preview: dict[str, Any]) -> tuple[str | None, str | None]:
    """Choose the model a brokered Code task will use, without guessing at dispatch time.

    Explicit Code agents win, followed by a coder/executor/main model-pack entry.  A
    plan is blocked when no registered tool-capable model can satisfy the handoff;
    this keeps the Assistant preview honest instead of queueing a silent Chat fallback.
    """

    candidates: list[str] = []
    for item in agent_preview.get("agents", []):
        if item.get("mode") == "code" or item.get("role") in {"coder", "executor"}:
            key = str(item.get("resolved_model_key") or item.get("model_key") or "").strip()
            if key:
                candidates.append(key)
    for entry in model_pack.get("entries", []):
        if entry.get("role") in {"coder", "executor", "main"}:
            key = str(entry.get("model_key") or "").strip()
            if key:
                candidates.append(key)
            else:
                models, by_key = _model_lookup()
                inferred = _model_for_entry(entry, models, by_key)
                if inferred and inferred.get("key"):
                    candidates.append(str(inferred["key"]))

    seen: set[str] = set()
    for key in candidates:
        if key in seen:
            continue
        seen.add(key)
        model = model_registry.get_model(key)
        if not model:
            continue
        if not model.get("enabled", True):
            return None, "coding_model_disabled"
        if str(model.get("runtime_status") or "").lower() in {"unhealthy", "stopped", "unreachable", "error"}:
            return None, f"coding_model_runtime_{str(model.get('runtime_status')).lower()}"
        if not model_providers.supports_agentic_tools(model):
            return None, "coding_model_not_tool_capable"
        return key, None
    return None, "coding_model_missing"


def build_plan_preview(
    owner_id: str,
    objective: str,
    workspace_ref: str,
    session_id: str | None = None,
    context_query: str | None = None,
    model_pack: Any = None,
    model_pack_id: str | None = None,
    agents: Any = None,
    requested_operations: Any = None,
    include_sensitive: bool = False,
    context_capsule_id: str | None = None,
) -> dict[str, Any]:
    clean_objective = str(objective or "").strip()[:1200]
    if not clean_objective:
        raise ValueError("objective is required")
    pack_source = "inline"
    if model_pack_id:
        saved_pack = get_model_pack(owner_id, model_pack_id, include_preview=False)
        if not saved_pack:
            raise ValueError("model pack missing")
        if model_pack is not None:
            raise ValueError("choose either model_pack or model_pack_id")
        model_pack = saved_pack.get("pack")
        pack_source = "saved"
    normalized_pack = normalize_model_pack(model_pack)
    if context_capsule_id:
        if session_id or context_query:
            raise ValueError("choose either context capsule or live context selection")
        context = _approved_context_capsule(owner_id, context_capsule_id)
        context_source = "approved_capsule"
    else:
        context = build_context_preview(owner_id, clean_objective, workspace_ref, session_id, context_query, include_sensitive)
        context_source = "live_preview"
    model_preview = build_model_pack_preview(normalized_pack)
    agent_preview = build_agent_preview(clean_objective, agents, normalized_pack)
    control_preview = build_control_preview(requested_operations, workspace_ref=workspace_ref)
    coding_model_key = None
    coding_model_blocker = None
    if any(item.get("operation") == "start_coding_task" for item in control_preview["operations"]):
        coding_model_key, coding_model_blocker = _resolve_coding_model(normalized_pack, agent_preview)
        if coding_model_blocker:
            for item in control_preview["operations"]:
                if item.get("operation") == "start_coding_task":
                    item["status"] = "blocked"
                    item.setdefault("blocked_reasons", []).append(coding_model_blocker)
    blockers = []
    for entry in model_preview["entries"]:
        if entry.get("status") == "blocked" or (entry.get("required") and entry.get("status") == "missing"):
            blockers.extend(f"model:{entry['entry_id']}:{reason}" for reason in entry.get("blocked_reasons", []))
    blockers.extend(
        f"control:{item['operation']}:{reason}"
        for item in control_preview["operations"]
        for reason in item.get("blocked_reasons", [])
    )
    next_actions = [
        "Review this preview and approve the model pack before launching workers.",
        "Keep host actions behind the local-control broker and existing approval gates.",
    ]
    if blockers:
        next_actions.insert(0, "Resolve the listed blockers before execution.")
    return {
        "assistant": get_profile(owner_id),
        "objective": clean_objective,
        "workspace_ref": workspace_ref,
        "model_pack_source": pack_source,
        "context_source": context_source,
        "context_capsule_id": ((context.get("capsule") or {}).get("id") if isinstance(context, dict) else None),
        "context": context,
        "model_pack": model_preview,
        "delegation": agent_preview,
        "local_control": control_preview,
        "execution": {
            "mode": "preview_only",
            "started": False,
            "side_effects": False,
            "host_actions_started": False,
            "models_started": False,
            "coding": {
                "mode": "code",
                "model_key": coding_model_key,
                "context_capsule_id": ((context.get("capsule") or {}).get("id") if isinstance(context, dict) else None),
                "ready": bool(coding_model_key) and not coding_model_blocker,
            } if any(item.get("operation") == "start_coding_task" for item in control_preview["operations"]) else None,
        },
        "blockers": sorted(set(blockers)),
        "next_actions": next_actions,
    }


def _public_plan(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if not record:
        return None
    item = dict(record)
    status = str(item.get("status") or "preview")
    item["handoff"] = {
        "status": "awaiting_broker" if status == "approved" else "reviewed_rejected" if status == "rejected" else "review_required",
        "broker_request_created": False,
        "execution_started": False,
        "side_effects": False,
    }
    return item


def create_persisted_plan(
    owner_id: str,
    objective: str,
    workspace_ref: str,
    session_id: str | None = None,
    context_query: str | None = None,
    model_pack: Any = None,
    model_pack_id: str | None = None,
    agents: Any = None,
    requested_operations: Any = None,
    include_sensitive: bool = False,
    context_capsule_id: str | None = None,
) -> dict[str, Any]:
    plan = build_plan_preview(
        owner_id=owner_id,
        objective=objective,
        workspace_ref=workspace_ref,
        session_id=session_id,
        context_query=context_query,
        model_pack=model_pack,
        model_pack_id=model_pack_id,
        agents=agents,
        requested_operations=requested_operations,
        include_sensitive=include_sensitive,
        context_capsule_id=context_capsule_id,
    )
    record = store.create_assistant_plan(owner_id, plan)
    audit.log(
        "assistant_plan_created",
        {"plan_id": record["id"], "blocker_count": len(plan.get("blockers", []))},
        actor=_owner(owner_id),
    )
    return _public_plan(record)


def get_persisted_plan(owner_id: str, plan_id: str) -> dict[str, Any] | None:
    return _public_plan(store.get_assistant_plan(_owner(owner_id), plan_id))


def list_persisted_plans(owner_id: str, limit: int = 50) -> list[dict[str, Any]]:
    return [_public_plan(item) for item in store.list_assistant_plans(_owner(owner_id), limit)]


def review_persisted_plan(owner_id: str, plan_id: str, status: str, note: str = "") -> dict[str, Any]:
    owner = _owner(owner_id)
    current = store.get_assistant_plan(owner, plan_id)
    if not current:
        raise ValueError("assistant plan missing")
    if status == "approved" and current.get("plan", {}).get("blockers"):
        blockers = ", ".join(current["plan"].get("blockers", [])[:5])
        raise AppError(
            "assistant_plan_blocked",
            f"Resolve plan blockers before approval: {blockers}",
            409,
        )
    updated = store.transition_assistant_plan(owner, plan_id, status, actor=owner, review_note=note)
    if not updated:
        raise ValueError("assistant plan missing")
    audit.log(
        "assistant_plan_reviewed",
        {"plan_id": plan_id, "status": status},
        actor=owner,
    )
    return _public_plan(updated)


def _public_handoff(owner_id: str, record: dict[str, Any] | None) -> dict[str, Any] | None:
    if not record:
        return None
    item = dict(record)
    approval = approvals.get(item.get("approval_id")) if item.get("approval_id") else None
    if item.get("status") == "completed":
        broker_status = "completed"
    elif item.get("status") == "failed":
        broker_status = "failed"
    elif item.get("status") == "ready_for_broker":
        broker_status = "ready_for_broker"
    elif approval:
        approval_status = str(approval.get("status") or "pending")
        broker_status = {
            "pending": "awaiting_approval",
            "approved": "approved_for_broker",
            "denied": "denied",
            "expired": "expired",
            "executed": "execution_recorded",
        }.get(approval_status, approval_status)
    else:
        broker_status = "ready_for_broker" if item.get("status") == "ready_for_broker" else item.get("status")
    request = item.get("request") or {}
    if item.get("status") == "completed":
        action_state = "completed"
    elif item.get("status") == "failed":
        action_state = "failed"
    elif item.get("status") == "ready_for_broker":
        action_state = "prepared"
    elif approval and str(approval.get("status") or "pending") == "approved":
        action_state = "approved"
    else:
        action_state = str(request.get("action_state") or "available")
    item["approval"] = approval
    item["broker_status"] = broker_status
    item["action_state"] = action_state
    item["policy"] = {
        "broker_only": True,
        "direct_model_host_access": False,
        "execution_started": bool(request.get("execution_started", False)),
        "side_effects": bool(request.get("side_effects", False)),
        "host_mutation": bool(request.get("host_mutation", False)),
        "planned_side_effects": bool(request.get("planned_side_effects", False)),
        "planned_host_mutation": bool(request.get("planned_host_mutation", False)),
    }
    return item


def _dispatch_start_coding_task(owner_id: str, handoff_id: str, plan_record: dict[str, Any], is_admin: bool = False) -> dict[str, Any]:
    """Start exactly one approved Code task through the existing AgentHub.

    The broker owns the allowlist and approval boundary; AgentHub remains the
    only component allowed to create and schedule an agent task.  The result is
    deliberately a receipt (task id, model, workspace, and capsule id), never
    the capsule's raw context or an arbitrary command string.
    """

    plan = plan_record.get("plan") or {}
    execution = plan.get("execution") or {}
    coding = execution.get("coding") or {}
    model_key = str(coding.get("model_key") or "").strip()
    model = model_registry.get_model(model_key) if model_key else None
    if not model or not model_providers.supports_agentic_tools(model):
        raise AppError(
            "assistant_coding_model_unavailable",
            "The approved plan does not have a reachable tool-capable Code model.",
            409,
        )

    workspace_ref = str(plan.get("workspace_ref") or ".").strip() or "."
    try:
        workspace.require_user_access(workspace_ref, owner_id, "contributor", is_admin)
        target_workspace = workspace.resolve_path(workspace_ref)
    except (OSError, ValueError, PermissionError) as exc:
        raise AppError(
            "assistant_coding_workspace_unavailable",
            "The approved plan no longer has contributor access to its workspace.",
            409,
        ) from exc

    capsule_id = str(
        plan.get("context_capsule_id")
        or coding.get("context_capsule_id")
        or ((plan.get("context") or {}).get("capsule") or {}).get("id")
        or ""
    ).strip() or None
    if capsule_id:
        capsule = store.get_assistant_context_capsule(owner_id, capsule_id)
        if not capsule:
            raise AppError("assistant_context_capsule_missing", "The approved context capsule is missing.", 409)
        if capsule.get("status") == "expired":
            raise AppError("assistant_context_capsule_expired", "The approved context capsule has expired.", 409)
        if capsule.get("status") != "approved":
            raise AppError("assistant_context_capsule_not_approved", "Approve the context capsule before starting the Code task.", 409)
        try:
            capsule_workspace = workspace.resolve_path(capsule.get("workspace_ref") or ".")
        except (OSError, ValueError) as exc:
            raise AppError("assistant_context_capsule_workspace_mismatch", "The context capsule workspace is no longer valid.", 409) from exc
        if str(target_workspace.resolve()).casefold() != str(capsule_workspace.resolve()).casefold():
            raise AppError("assistant_context_capsule_workspace_mismatch", "The approved context capsule belongs to a different workspace.", 409)

    # Import lazily to keep the assistant contract module independent from the
    # API router's singleton during startup and unit-test imports.
    from backend.api.core import hub

    task = hub.start(
        objective=str(plan.get("objective") or "Complete the approved coding task"),
        model=model_key,
        skill="general",
        subagents=0,
        workspace_path=workspace_ref,
        mode="code",
        reasoning="auto",
        owner_id=owner_id,
        context_capsule_id=capsule_id,
    )
    task.seen("assistant_handoff_started", {
        "handoffId": handoff_id,
        "planId": plan_record.get("id"),
        "operation": "start_coding_task",
        "model": model_key,
        "contextCapsuleId": capsule_id,
    })
    task.log("governed Code task started from an approved Assistant handoff")
    return {
        "contract_version": BROKER_CONTRACT_VERSION,
        "operation": "start_coding_task",
        "adapter": broker.operation_metadata()["start_coding_task"]["adapter"],
        "result": {
            "task_id": task.id,
            "status": task.status,
            "mode": task.mode,
            "model": task.model,
            "workspace": task.workspace,
            "context_capsule_id": capsule_id,
        },
        "action_state": "started",
        "side_effects": True,
        "host_mutation": True,
        "execution_started": True,
    }


def dispatch_handoff(owner_id: str, handoff_id: str, is_admin: bool = False) -> dict[str, Any]:
    """Consume an approved handoff through one allowlisted broker adapter."""

    owner = _owner(owner_id)
    handoff = store.get_assistant_handoff(owner, handoff_id)
    if not handoff:
        raise ValueError("assistant handoff missing")
    if handoff.get("status") == "completed":
        return _public_handoff(owner, handoff)
    if handoff.get("status") != "ready_for_broker":
        raise AppError("assistant_handoff_not_ready", "Prepare the broker handoff before dispatching it.", 409)

    plan_record = store.get_assistant_plan(owner, handoff.get("plan_id"))
    if not plan_record or plan_record.get("status") != "approved":
        raise AppError("assistant_plan_not_approved", "The assistant plan is no longer approved.", 409)
    operation = normalize_operations([handoff.get("operation")])
    if not operation or operation[0] not in broker.supported_operations():
        raise AppError("assistant_broker_adapter_unavailable", "No executable adapter is registered for that operation.", 409)
    operation = operation[0]
    plan = plan_record.get("plan") or {}
    workspace_ref = plan.get("workspace_ref") or "."
    current = build_control_preview([operation], workspace_ref=workspace_ref)["operations"]
    planned = current[0] if current else None
    if not planned or planned.get("status") == "blocked":
        reasons = ", ".join((planned or {}).get("blocked_reasons", ["operation_not_supported_by_broker"])[:4])
        raise AppError("assistant_operation_blocked", f"Resolve the operation blocker before dispatch: {reasons}", 409)

    approval = approvals.get(handoff.get("approval_id")) if handoff.get("approval_id") else None
    if planned.get("requires_approval") and not approval:
        raise AppError("assistant_approval_required", "This broker operation requires an approval record.", 409)
    if approval:
        try:
            approvals.require_approved(handoff.get("approval_id"), "assistant_broker_operation")
        except PermissionError as exc:
            raise AppError("assistant_approval_unavailable", str(exc), 409) from exc

    try:
        if operation == "start_coding_task":
            adapter_result = _dispatch_start_coding_task(owner, handoff_id, plan_record, is_admin=is_admin)
        else:
            adapter_result = broker.dispatch(
                operation,
                workspace_path=workspace.resolve_path(workspace_ref) if broker.operation_metadata().get(operation, {}).get("requires_workspace") else None,
            )
    except Exception as exc:
        request = dict(handoff.get("request") or {})
        request.update(
            {
                "dispatch_status": "failed",
                "action_state": "failed",
                "dispatch_error": str(exc)[:300],
                "side_effects": False,
                "host_mutation": False,
                "execution_started": False,
            }
        )
        store.transition_assistant_handoff(owner, handoff_id, "failed", request)
        audit.log("assistant_broker_handoff_failed", {"handoff_id": handoff_id, "operation": operation}, actor=owner)
        raise

    request = dict(handoff.get("request") or {})
    request.update(
        {
            "dispatch_status": "completed",
            "dispatch_contract_version": adapter_result.get("contract_version"),
            "adapter": adapter_result.get("adapter"),
            "result": adapter_result.get("result"),
            "action_state": adapter_result.get("action_state") or "completed",
            "side_effects": bool(adapter_result.get("side_effects", False)),
            "host_mutation": bool(adapter_result.get("host_mutation", False)),
            "execution_started": bool(adapter_result.get("execution_started", False)),
            "completed_at": store.now(),
        }
    )
    completed = store.transition_assistant_handoff(owner, handoff_id, "completed", request)
    if not completed:
        raise ValueError("assistant handoff missing")
    audit.log(
        "assistant_broker_handoff_completed",
        {
            "handoff_id": handoff_id,
            "operation": operation,
            "adapter": adapter_result.get("adapter"),
            "side_effects": bool(adapter_result.get("side_effects", False)),
        },
        actor=owner,
    )
    return _public_handoff(owner, completed)


def prepare_handoff(owner_id: str, handoff_id: str) -> dict[str, Any]:
    """Validate an approved handoff and mark it ready for a future broker.

    This is intentionally the last safe step before host execution.  It
    rechecks the current security policy, plan approval, and approval record so
    a stale approval cannot bypass a newly disabled capability.  No approval
    is consumed and no process, container, file, microphone, or speaker is
    started here.
    """

    owner = _owner(owner_id)
    handoff = store.get_assistant_handoff(owner, handoff_id)
    if not handoff:
        raise ValueError("assistant handoff missing")
    if handoff.get("status") == "ready_for_broker":
        return _public_handoff(owner, handoff)
    if handoff.get("status") in {"denied", "expired"}:
        raise AppError("assistant_handoff_closed", "That broker handoff is no longer active.", 409)

    plan_record = store.get_assistant_plan(owner, handoff.get("plan_id"))
    if not plan_record or plan_record.get("status") != "approved":
        raise AppError("assistant_plan_not_approved", "Approve the assistant plan before preparing a broker handoff.", 409)

    operation = normalize_operations([handoff.get("operation")])
    if not operation:
        raise ValueError("assistant handoff operation is invalid")
    operation = operation[0]
    plan = plan_record.get("plan") or {}
    workspace_ref = plan.get("workspace_ref") or "."
    current = build_control_preview([operation], workspace_ref=workspace_ref)["operations"]
    planned = current[0] if current else None
    if not planned or planned.get("status") == "blocked":
        reasons = ", ".join((planned or {}).get("blocked_reasons", ["operation_not_supported_by_broker"])[:4])
        raise AppError("assistant_operation_blocked", f"Resolve the operation blocker before broker preparation: {reasons}", 409)

    approval = approvals.get(handoff.get("approval_id")) if handoff.get("approval_id") else None
    if planned.get("requires_approval") and not approval:
        raise AppError("assistant_approval_required", "This broker operation requires an approval record.", 409)
    if approval and approval.get("status") != "approved":
        status = str(approval.get("status") or "pending")
        code = "assistant_approval_required" if status == "pending" else "assistant_approval_unavailable"
        message = "Approve the broker operation before preparation." if status == "pending" else f"The broker approval is {status}."
        raise AppError(code, message, 409)

    adapter = broker.operation_metadata().get(operation, {})
    request = dict(handoff.get("request") or {})
    request.update(
        {
            "contract_version": BROKER_CONTRACT_VERSION,
            "operation": operation,
            "plan_id": plan_record["id"],
            "workspace": workspace_ref,
            "approval_id": approval.get("id") if approval else None,
            "execution_mode": "broker_only",
            "execution_started": False,
            "side_effects": False,
            "host_mutation": False,
            "planned_side_effects": bool(adapter.get("side_effects", False)),
            "planned_host_mutation": bool(adapter.get("host_mutation", False)),
            "action_state": "prepared",
            "direct_model_host_access": False,
            "prepared_at": store.now(),
        }
    )
    prepared = store.transition_assistant_handoff(owner, handoff_id, "ready_for_broker", request)
    if not prepared:
        raise ValueError("assistant handoff missing")
    audit.log(
        "assistant_broker_handoff_prepared",
        {
            "handoff_id": handoff_id,
            "plan_id": plan_record["id"],
            "operation": operation,
            "approval_id": approval.get("id") if approval else None,
            "execution_started": False,
        },
        actor=owner,
    )
    return _public_handoff(owner, prepared)


def request_handoff(owner_id: str, plan_id: str, operation: str) -> dict[str, Any]:
    owner = _owner(owner_id)
    plan_record = store.get_assistant_plan(owner, plan_id)
    if not plan_record:
        raise ValueError("assistant plan missing")
    if plan_record.get("status") != "approved":
        raise AppError("assistant_plan_not_approved", "Approve the assistant plan before requesting a broker handoff.", 409)
    normalized = normalize_operations([operation])
    if not normalized:
        raise ValueError("operation is required")
    clean_operation = normalized[0]
    plan = plan_record.get("plan") or {}
    planned = next(
        (item for item in (plan.get("local_control", {}).get("operations", []) or []) if item.get("operation") == clean_operation),
        None,
    )
    if not planned:
        raise AppError("assistant_operation_not_planned", "That operation was not included in the approved plan.", 409)
    if planned.get("status") == "blocked":
        reasons = ", ".join(planned.get("blocked_reasons", [])[:4])
        raise AppError("assistant_operation_blocked", f"Resolve the operation blocker before handoff: {reasons}", 409)
    existing = store.find_assistant_handoff(owner, plan_id, clean_operation)
    if existing:
        return _public_handoff(owner, existing)
    requires_approval = bool(planned.get("requires_approval", True))
    approval = None
    if requires_approval:
        approval = approvals.create(
            "assistant_broker_operation",
            {
                "plan_id": plan_id,
                "operation": clean_operation,
                "workspace": plan.get("workspace_ref") or ".",
                "broker_only": True,
                "direct_model_host_access": False,
            },
            risk_level=planned.get("risk") or "approval_required",
            workspace=plan.get("workspace_ref") or ".",
            owner_id=owner,
        )
    handoff = store.create_assistant_handoff(
        owner,
        plan_id,
        clean_operation,
        approval["id"] if approval else None,
        {
            "plan_id": plan_id,
            "operation": clean_operation,
            "requires_approval": requires_approval,
            "broker_only": True,
            "direct_model_host_access": False,
            "action_state": "available",
            "planned_side_effects": bool((planned.get("dispatch") or {}).get("side_effects", False)),
            "planned_host_mutation": bool((planned.get("dispatch") or {}).get("host_mutation", False)),
        },
        status="pending_approval" if approval else "ready_for_broker",
    )
    audit.log(
        "assistant_broker_handoff_requested",
        {"handoff_id": handoff["id"], "plan_id": plan_id, "operation": clean_operation, "approval_id": approval["id"] if approval else None},
        actor=owner,
    )
    return _public_handoff(owner, handoff)


def get_handoff(owner_id: str, handoff_id: str) -> dict[str, Any] | None:
    return _public_handoff(_owner(owner_id), store.get_assistant_handoff(_owner(owner_id), handoff_id))


def list_handoffs(owner_id: str, limit: int = 50) -> list[dict[str, Any]]:
    owner = _owner(owner_id)
    return [_public_handoff(owner, item) for item in store.list_assistant_handoffs(owner, limit)]
