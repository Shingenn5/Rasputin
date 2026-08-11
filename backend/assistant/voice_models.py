"""Readiness contracts for locally registered speech models.

The voice adapters deliberately accept caller-supplied audio and never probe
microphones or speakers. This module provides the matching model-side
contract: it classifies registered speech-to-text and text-to-speech endpoints
without starting a model, making a network request, or exposing private
endpoint details.
"""

from __future__ import annotations

from typing import Any, Iterable

from backend.core import security
from backend.models import registry as model_registry


VOICE_MODEL_READINESS_CONTRACT_VERSION = "0.1"
VOICE_MODEL_ROLES = ("speech_to_text", "text_to_speech")
_DEAD_RUNTIME_STATUSES = frozenset({"unhealthy", "stopped", "unreachable", "error"})


def _text(value: Any, limit: int = 160) -> str:
    return str(value or "").strip()[:limit]


def _endpoint_state(model: dict[str, Any]) -> tuple[bool, bool]:
    """Return (configured, local) without returning the URL itself."""

    endpoint = _text(model.get("base_url") or model.get("baseUrl"), 500).rstrip("/")
    if not endpoint:
        return False, False
    return True, bool(security.is_local_url(endpoint))


def _model_status(model: dict[str, Any], role: str) -> dict[str, Any]:
    configured, local = _endpoint_state(model)
    runtime_status = _text(model.get("runtime_status") or model.get("runtimeStatus"), 40).lower() or "unknown"
    blockers: list[str] = []
    health_checks: list[str] = []

    if _text(model.get("role"), 80) != role:
        blockers.append("model_role_mismatch")
    if not bool(model.get("enabled", True)):
        blockers.append("model_disabled")
    if not configured:
        blockers.append("local_endpoint_missing")
    elif not local:
        blockers.append("remote_endpoint_blocked")
    if runtime_status in _DEAD_RUNTIME_STATUSES:
        blockers.append(f"runtime_{runtime_status}")
    elif runtime_status != "reachable":
        health_checks.append("runtime_reachability_unverified")

    if blockers:
        status = "blocked"
    elif health_checks:
        status = "needs_health_check"
    else:
        status = "ready"

    # Registry entries can contain provider-specific fields, secrets, and
    # endpoint URLs. The readiness surface intentionally returns only the
    # minimum operator-facing identity and evidence.
    return {
        "key": _text(model.get("key"), 120),
        "name": _text(model.get("name") or model.get("model") or model.get("key"), 160),
        "role": role,
        "provider": _text(model.get("provider"), 80),
        "runtime": _text(model.get("runtime"), 80),
        "runtime_status": runtime_status,
        "enabled": bool(model.get("enabled", True)),
        "endpoint": "local_configured" if configured and local else "missing" if not configured else "remote_blocked",
        "health_evidence": "reachable" if runtime_status == "reachable" else "unverified",
        "status": status,
        "blocked_reasons": sorted(set(blockers)),
        "health_checks": sorted(set(health_checks)),
    }


def _role_readiness(role: str, models: Iterable[dict[str, Any]]) -> dict[str, Any]:
    entries = [_model_status(model, role) for model in models if isinstance(model, dict)]
    entries.sort(key=lambda item: (0 if item["status"] == "ready" else 1 if item["status"] == "needs_health_check" else 2, item["key"]))
    selected = next((item for item in entries if item["status"] in {"ready", "needs_health_check"}), None)
    blocked_reasons = sorted({reason for item in entries for reason in item["blocked_reasons"]})
    health_checks = sorted({reason for item in entries for reason in item["health_checks"]})
    if not entries:
        status = "blocked"
        blocked_reasons = ["role_model_missing"]
    elif selected is None:
        status = "blocked"
    elif selected["status"] == "ready":
        status = "ready"
    else:
        status = "needs_health_check"
    return {
        "role": role,
        "required": True,
        "status": status,
        "selected_model_key": selected["key"] if selected else None,
        "models": entries,
        "blocked_reasons": blocked_reasons,
        "health_checks": health_checks,
        "next_action": (
            "Register an enabled local endpoint for this role."
            if "role_model_missing" in blocked_reasons
            else "Enable a local model and remove any unreachable runtime."
            if status == "blocked"
            else "Run the model health check before starting a voice turn."
            if status == "needs_health_check"
            else "No action required."
        ),
    }


def readiness(models: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Describe local STT/TTS registration without starting model or audio I/O."""

    source = list(models) if models is not None else model_registry.all_models()
    roles = {
        role: _role_readiness(role, (item for item in source if _text(item.get("role"), 80) == role))
        for role in VOICE_MODEL_ROLES
    }
    blockers = sorted({f"voice:{role}:{reason}" for role, data in roles.items() for reason in data["blocked_reasons"]})
    health_checks = sorted({f"voice:{role}:{reason}" for role, data in roles.items() for reason in data["health_checks"]})
    if blockers:
        status = "blocked"
    elif health_checks:
        status = "needs_health_check"
    else:
        status = "ready"
    return {
        "contract_version": VOICE_MODEL_READINESS_CONTRACT_VERSION,
        "local_only": True,
        "status": status,
        "ready": status == "ready",
        "roles": roles,
        "blockers": blockers,
        "health_checks": health_checks,
        "execution": {
            "models_started": False,
            "network_probe_started": False,
            "audio_io_started": False,
            "side_effects": False,
        },
        "policy": {
            "local_only": True,
            "endpoint_urls_exposed": False,
            "microphone_access": "caller_supplied_audio_only",
            "speaker_access": "response_stream_only",
        },
        "next_actions": (
            ["Register reachable local speech-to-text and text-to-speech endpoints."]
            if status == "blocked"
            else ["Run model health checks before starting a voice turn."]
            if status == "needs_health_check"
            else ["Voice model endpoints are reachable; verify browser permissions and audio hardware separately."]
        ),
    }


__all__ = ["VOICE_MODEL_READINESS_CONTRACT_VERSION", "VOICE_MODEL_ROLES", "readiness"]
