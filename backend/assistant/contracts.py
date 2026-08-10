"""Stable contracts for the Rasputin personal-assistant direction.

These helpers keep the first implementation slice deterministic and safe to
call from an API request.  They normalize user-authored plans, validate the
delegation graph, and describe the local-control boundary; they do not run
workers or perform host I/O.
"""

from __future__ import annotations

import copy
import re
from typing import Any


MODEL_PACK_ROLES = {
    "main",
    "planner",
    "executor",
    "coder",
    "researcher",
    "summarizer",
    "memory",
    "embeddings",
    "helper",
    "test",
    "speech_to_text",
    "text_to_speech",
}

AGENT_MODES = {"chat", "plan", "research", "code", "test"}

VOICE_ROLES = {"speech_to_text", "text_to_speech"}

PERSONA_TONES = {"direct", "warm", "dry"}
SARCASM_LEVELS = {"off", "light", "moderate"}

# The personal-assistant surface and the coding surface are intentionally
# separate entrypoints.  They share Rasputin's identity, context authority,
# model registry, and safety broker, but each can be opened and used on its
# own without requiring the other workflow to be active.
WORKFLOW_DEFINITIONS = (
    {
        "id": "assistant",
        "label": "Assistant",
        "mode": "chat",
        "role": "main",
        "description": "Conversation, context recall, planning, and local assistant guidance.",
        "capabilities": ["conversation", "context", "planning", "voice"],
    },
    {
        "id": "coding",
        "label": "Coding",
        "mode": "code",
        "role": "coder",
        "description": "Repository analysis, edits, tests, repair, and review in a coding task.",
        "capabilities": ["workspace", "patch", "tests", "review"],
    },
)

VOICE_LOOP_STAGES = (
    {
        "id": "transcribe",
        "role": "speech_to_text",
        "capability": "audio.transcribe",
        "label": "Speech to text",
    },
    {
        "id": "reason",
        "role": "main",
        "capability": "chat.reason",
        "label": "Rasputin reasoning",
    },
    {
        "id": "synthesize",
        "role": "text_to_speech",
        "capability": "audio.synthesize",
        "label": "Text to speech",
    },
)

DEFAULT_PROFILE = {
    "assistant_id": "rasputin",
    "display_name": "Rasputin",
    "contract_version": "0.1",
    "persona": {
        "summary": "A dryly sarcastic, respectful local systems partner that keeps the user's intent and context coherent.",
        "traits": ["dryly sarcastic", "context-aware", "transparent", "privacy-first"],
        "style": {"tone": "dry", "sarcasm": "light", "respectful": True},
    },
    "mission": "Coordinate local models and agents as one dependable workstation assistant.",
    "context_authority": {
        "scope": "owner",
        "cross_workspace": True,
        "source_priority": ["explicit_request", "selected_session", "saved_memory", "owner_history"],
        "sensitive_by_default": False,
    },
    "agent_policy": {
        "delegated_by": "rasputin",
        "workers_are_replaceable": True,
        "model_containers_are_workers": True,
        "max_preview_agents": 16,
    },
    "local_control_policy": {
        "broker_only": True,
        "requires_approval_for_host_actions": True,
        "model_containers_have_host_access": False,
        "execution_default": "preview_only",
    },
    "voice_policy": {
        "input_role": "speech_to_text",
        "output_role": "text_to_speech",
        "conversation_loop": ["transcribe", "reason", "synthesize"],
        "models_are_replaceable": True,
    },
}

PROFILE_MUTABLE_FIELDS = {"display_name", "persona", "mission", "voice_policy"}

DEFAULT_MODEL_PACK = {
    "pack_id": "rasputin-core",
    "version": "0.1",
    "entries": [
        {
            "id": "conversation",
            "role": "main",
            "model_key": "main-vllm",
            "required": True,
            "capabilities": ["chat", "reasoning"],
        },
        {
            "id": "planner",
            "role": "planner",
            "required": False,
            "capabilities": ["planning", "delegation"],
        },
        {
            "id": "speech-input",
            "role": "speech_to_text",
            "required": False,
            "capabilities": ["audio.transcribe"],
        },
        {
            "id": "speech-output",
            "role": "text_to_speech",
            "required": False,
            "capabilities": ["audio.synthesize"],
        },
    ],
}

CONTROL_OPERATIONS = {
    "open_vscode": {
        "label": "Open VS Code",
        "category": "desktop",
        "security_flag": "allow_shell_execution",
        "risk": "moderate",
        "requires_approval": True,
    },
    "run_test": {
        "label": "Run tests",
        "category": "developer",
        "security_flag": "allow_shell_execution",
        "risk": "high",
        "requires_approval": True,
    },
    "run_build": {
        "label": "Run a build",
        "category": "developer",
        "security_flag": "allow_shell_execution",
        "risk": "high",
        "requires_approval": True,
    },
    "start_coding_task": {
        "label": "Start a governed coding task",
        "category": "developer",
        "security_flag": None,
        "risk": "high",
        "requires_approval": True,
    },
    "docker_status": {
        "label": "Inspect Docker status",
        "category": "container",
        "security_flag": "allow_docker_control",
        "risk": "moderate",
        "requires_approval": True,
    },
    "docker_start_model": {
        "label": "Start a model container",
        "category": "container",
        "security_flag": "allow_docker_control",
        "risk": "high",
        "requires_approval": True,
    },
    "transcribe": {
        "label": "Transcribe audio",
        "category": "voice",
        "security_flag": None,
        "risk": "low",
        "requires_approval": False,
    },
    "synthesize": {
        "label": "Synthesize speech",
        "category": "voice",
        "security_flag": None,
        "risk": "low",
        "requires_approval": False,
    },
}


def _text(value: Any, default: str = "", limit: int = 500) -> str:
    value = str(value if value is not None else default).strip()
    return value[:limit]


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "-", _text(value, limit=80).lower()).strip("-")


def _list_of_text(value: Any, limit: int = 20, item_limit: int = 100) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    result = []
    for item in value[:limit]:
        text = _text(item, limit=item_limit)
        if text:
            result.append(text)
    return result


def default_profile(owner_id: str = "admin") -> dict[str, Any]:
    profile = copy.deepcopy(DEFAULT_PROFILE)
    profile["owner_id"] = _text(owner_id, "admin", 120) or "admin"
    return profile


def sanitize_profile(value: Any, owner_id: str = "admin") -> dict[str, Any]:
    """Return a bounded profile while preserving immutable safety policies."""

    profile = default_profile(owner_id)
    if not isinstance(value, dict):
        return profile
    if _text(value.get("assistant_id"), limit=80) == profile["assistant_id"]:
        profile["assistant_id"] = "rasputin"
    if value.get("display_name") is not None:
        profile["display_name"] = _text(value.get("display_name"), profile["display_name"], 80) or "Rasputin"
    if value.get("mission") is not None:
        profile["mission"] = _text(value.get("mission"), profile["mission"], 500)
    persona = value.get("persona")
    if isinstance(persona, dict):
        profile["persona"]["summary"] = _text(persona.get("summary"), profile["persona"]["summary"], 500)
        traits = _list_of_text(persona.get("traits"), limit=12, item_limit=60)
        if traits:
            profile["persona"]["traits"] = traits
        style = persona.get("style")
        if isinstance(style, dict):
            tone = _key(style.get("tone"))
            sarcasm = _key(style.get("sarcasm"))
            if tone in PERSONA_TONES:
                profile["persona"]["style"]["tone"] = tone
            if sarcasm in SARCASM_LEVELS:
                profile["persona"]["style"]["sarcasm"] = sarcasm
            # Respect is a safety invariant, not a user-toggleable personality
            # setting. Sarcasm must stay subordinate to it.
            profile["persona"]["style"]["respectful"] = True
    voice = value.get("voice_policy")
    if isinstance(voice, dict):
        input_role = _key(voice.get("input_role"))
        output_role = _key(voice.get("output_role"))
        if input_role in VOICE_ROLES:
            profile["voice_policy"]["input_role"] = input_role
        if output_role in VOICE_ROLES:
            profile["voice_policy"]["output_role"] = output_role
    profile["owner_id"] = _text(owner_id, "admin", 120) or "admin"
    return profile


def merge_profile(current: Any, updates: Any, owner_id: str = "admin") -> dict[str, Any]:
    """Merge only personality/presentation fields; safety policies stay fixed."""

    base = sanitize_profile(current, owner_id)
    if not isinstance(updates, dict):
        return base
    for field in PROFILE_MUTABLE_FIELDS:
        if field in updates:
            if field in {"persona", "voice_policy"} and isinstance(updates[field], dict):
                base[field] = {**base[field], **updates[field]}
                if field == "persona" and isinstance(updates[field].get("style"), dict):
                    base[field]["style"] = {**base[field].get("style", {}), **updates[field]["style"]}
            else:
                base[field] = updates[field]
    return sanitize_profile(base, owner_id)


def normalize_model_pack(value: Any) -> dict[str, Any]:
    raw = copy.deepcopy(value) if isinstance(value, dict) else copy.deepcopy(DEFAULT_MODEL_PACK)
    pack_id = _key(raw.get("pack_id") or raw.get("packId") or "rasputin-core") or "rasputin-core"
    version = _text(raw.get("version"), "0.1", 40) or "0.1"
    raw_entries = raw.get("entries") if raw.get("entries") is not None else raw.get("models")
    if raw_entries is None:
        raw_entries = DEFAULT_MODEL_PACK["entries"]
    if not isinstance(raw_entries, list):
        raise ValueError("model_pack.entries must be a list")
    entries = []
    seen = set()
    for index, item in enumerate(raw_entries[:32]):
        if not isinstance(item, dict):
            raise ValueError(f"model_pack.entries[{index}] must be an object")
        entry_id = _key(item.get("id") or item.get("name") or f"model-{index + 1}") or f"model-{index + 1}"
        if entry_id in seen:
            raise ValueError(f"duplicate model pack entry: {entry_id}")
        seen.add(entry_id)
        role = _key(item.get("role") or "helper")
        if role not in MODEL_PACK_ROLES:
            raise ValueError(f"unsupported model pack role: {role}")
        entries.append(
            {
                "id": entry_id,
                "role": role,
                "model_key": _key(item.get("model_key") or item.get("modelKey")),
                "required": _bool(item.get("required"), False),
                "capabilities": _list_of_text(item.get("capabilities"), limit=16, item_limit=80),
                "placement": _text(item.get("placement"), "automatic", 80) or "automatic",
            }
        )
    if not entries:
        raise ValueError("model_pack.entries must contain at least one entry")
    return {"pack_id": pack_id, "version": version, "entries": entries}


def normalize_agents(value: Any, objective: str) -> list[dict[str, Any]]:
    raw_agents = value if isinstance(value, list) and value else [
        {"id": "primary", "role": "main", "objective": objective}
    ]
    if len(raw_agents) > 16:
        raise ValueError("agents may contain at most 16 entries")
    agents = []
    seen = set()
    for index, item in enumerate(raw_agents):
        if not isinstance(item, dict):
            raise ValueError(f"agents[{index}] must be an object")
        agent_id = _key(item.get("id") or f"agent-{index + 1}") or f"agent-{index + 1}"
        if agent_id in seen:
            raise ValueError(f"duplicate agent id: {agent_id}")
        seen.add(agent_id)
        role = _key(item.get("role") or "executor")
        if role not in MODEL_PACK_ROLES:
            raise ValueError(f"unsupported agent role: {role}")
        dependencies = [_key(dep) for dep in _list_of_text(item.get("depends_on") or item.get("dependsOn"), 16, 80)]
        dependencies = [dep for dep in dependencies if dep]
        agents.append(
            {
                "id": agent_id,
                "role": role,
                "objective": _text(item.get("objective"), objective, 1200) or objective,
                "model_key": _key(item.get("model_key") or item.get("modelKey")),
                "depends_on": dependencies,
                "mode": _key(item.get("mode") or "chat") or "chat",
            }
        )
        if agents[-1]["mode"] not in AGENT_MODES:
            raise ValueError(f"unsupported agent mode: {agents[-1]['mode']}")
    ids = {agent["id"] for agent in agents}
    for agent in agents:
        missing = [dep for dep in agent["depends_on"] if dep not in ids]
        if missing:
            raise ValueError(f"agent {agent['id']} depends on unknown agent(s): {', '.join(missing)}")
    _assert_acyclic(agents)
    return agents


def _assert_acyclic(agents: list[dict[str, Any]]) -> None:
    graph = {agent["id"]: agent["depends_on"] for agent in agents}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ValueError("agent dependencies must form an acyclic graph")
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph.get(node, []):
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def normalize_operations(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("requested_operations must be a list")
    operations = []
    seen = set()
    for raw in value[:32]:
        if isinstance(raw, dict):
            raw = raw.get("operation") or raw.get("name")
        operation = _key(raw).replace("-", "_")
        if not operation or operation in seen:
            continue
        seen.add(operation)
        operations.append(operation)
    return operations
