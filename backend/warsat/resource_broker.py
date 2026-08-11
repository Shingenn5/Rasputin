"""Safe, side-effect-bounded resource admission for local model packs.

The broker owns reservations, not inference.  It only accounts for resources
that are explicitly requested and observed.  Unknown capacity remains
unknown, aggregate VRAM is never treated as one device, and every reservation
has an owner scope plus an expiry heartbeat.
"""

from __future__ import annotations

import re
import time
import uuid
from threading import RLock
from typing import Any

from backend.core import runtime_store as store


LEASES_KEY = "warsat_resource_leases"
LEASE_SCHEMA_VERSION = 1
DEFAULT_TTL_SECONDS = 120
MIN_TTL_SECONDS = 15
MAX_TTL_SECONDS = 3600
HEADROOM_FRACTION = 0.10
MIN_HEADROOM_MB = 512
COMBINED_RUNTIME_HINTS = {
    "gguf",
    "llama.cpp",
    "llama_cpp",
    "llamacpp",
    "llamacppggufserver",
}
_LOCK = RLock()


def _text(value: Any, default: str = "", limit: int = 160) -> str:
    text = str(value if value is not None else default).strip()
    return text[:limit]


def _key(value: Any, default: str = "") -> str:
    return re.sub(r"[^a-zA-Z0-9_.:-]+", "-", _text(value, default, 160)).strip("-").lower()


def _number(value: Any, default: float | None = None) -> float | None:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value: Any, default: int | None = None) -> int | None:
    number = _number(value)
    return default if number is None else max(0, int(number))


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _now(value: float | None = None) -> float:
    return float(value if value is not None else time.time())


def _ttl(value: Any) -> int:
    parsed = _integer(value, DEFAULT_TTL_SECONDS) or DEFAULT_TTL_SECONDS
    return max(MIN_TTL_SECONDS, min(MAX_TTL_SECONDS, parsed))


def _device_capacity(device: dict[str, Any]) -> dict[str, Any]:
    static = device.get("static") if isinstance(device.get("static"), dict) else device
    volatile = device.get("volatile") if isinstance(device.get("volatile"), dict) else device
    device_id = _key(device.get("deviceId") or static.get("deviceId"))
    if not device_id:
        index = _integer(static.get("index"), 0) or 0
        device_id = f"gpu:{index}"
    total = _number(static.get("memoryTotalMb") or static.get("memory_total_mb"))
    free = _number(volatile.get("memoryFreeMb") or volatile.get("memory_free_mb"))
    if free is None and total is not None:
        used = _number(volatile.get("memoryUsedMb") or volatile.get("memory_used_mb"))
        if used is not None:
            free = max(0.0, total - used)
    safe_free = None
    if free is not None:
        headroom = max(MIN_HEADROOM_MB, (total or free) * HEADROOM_FRACTION)
        safe_free = max(0.0, free - headroom)
    return {
        "deviceId": device_id,
        "name": _text(static.get("name"), device_id, 120),
        "vendor": _key(static.get("vendor"), "unknown") or "unknown",
        "totalMb": int(total) if total is not None else None,
        "freeMb": round(free, 2) if free is not None else None,
        "safeFreeMb": round(safe_free, 2) if safe_free is not None else None,
    }


def _normalize_profile(profile: dict[str, Any] | None) -> list[dict[str, Any]]:
    value = profile or {}
    if isinstance(value.get("capabilityProfile"), dict):
        value = value["capabilityProfile"]
    devices = value.get("devices") if isinstance(value, dict) else []
    if not isinstance(devices, list):
        return []
    return [_device_capacity(item) for item in devices if isinstance(item, dict)]


def _normalize_placement(item: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    device_id = _key(item.get("deviceId") or item.get("device_id"))
    amount = _integer(item.get("vramMb") or item.get("vram_mb") or item.get("reservedVramMb"))
    if not device_id or amount is None:
        return None
    return {"deviceId": device_id, "vramMb": amount}


def normalize_lease(value: Any, *, now: float | None = None) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    lease_id = _key(value.get("leaseId") or value.get("lease_id"))
    owner_id = _key(value.get("ownerId") or value.get("owner_id"), "admin") or "admin"
    if not lease_id:
        return None
    stamp = _now(now)
    expires_at = _number(value.get("expiresAt") or value.get("expires_at"), stamp)
    state = _key(value.get("state"), "active") or "active"
    if state == "active" and expires_at is not None and expires_at <= stamp:
        state = "expired"
    placements = [
        placement
        for placement in (_normalize_placement(item) for item in (value.get("placements") or []))
        if placement
    ]
    return {
        "schemaVersion": LEASE_SCHEMA_VERSION,
        "leaseId": lease_id,
        "ownerId": owner_id,
        "workspaceRef": _text(value.get("workspaceRef") or value.get("workspace_ref"), "", 500),
        "taskId": _key(value.get("taskId") or value.get("task_id")),
        "packId": _key(value.get("packId") or value.get("pack_id"), "model-pack") or "model-pack",
        "runtime": _key(value.get("runtime"), "unknown") or "unknown",
        "state": state,
        "placements": placements,
        "reservedRamMb": _integer(value.get("reservedRamMb") or value.get("reserved_ram_mb"), 0) or 0,
        "createdAt": _number(value.get("createdAt") or value.get("created_at"), stamp),
        "heartbeatAt": _number(value.get("heartbeatAt") or value.get("heartbeat_at"), stamp),
        "expiresAt": expires_at,
        "preemptible": _bool(value.get("preemptible"), False),
    }


def active_leases(*, now: float | None = None) -> list[dict[str, Any]]:
    stamp = _now(now)
    raw = store.get_kv(LEASES_KEY, [])
    values = raw if isinstance(raw, list) else []
    normalized = [normalize_lease(item, now=stamp) for item in values]
    return [item for item in normalized if item and item["state"] == "active"]


def list_leases(owner_id: str | None = None, *, now: float | None = None) -> list[dict[str, Any]]:
    leases = active_leases(now=now)
    if owner_id is None:
        return leases
    owner = _key(owner_id, "admin") or "admin"
    return [lease for lease in leases if lease["ownerId"] == owner]


def _reserved_by_device(leases: list[dict[str, Any]]) -> dict[str, int]:
    reserved: dict[str, int] = {}
    for lease in leases:
        for placement in lease.get("placements") or []:
            device_id = placement["deviceId"]
            reserved[device_id] = reserved.get(device_id, 0) + int(placement["vramMb"])
    return reserved


def _request(value: dict[str, Any] | None) -> dict[str, Any]:
    raw = value or {}
    requested_vram = _integer(raw.get("requestedVramMb") or raw.get("requested_vram_mb"))
    requested_ram = _integer(raw.get("requestedRamMb") or raw.get("requested_ram_mb"), 0) or 0
    requested_devices = raw.get("deviceIds") or raw.get("device_ids") or []
    if isinstance(requested_devices, str):
        requested_devices = [requested_devices]
    device_ids = [_key(item) for item in requested_devices if _key(item)]
    explicit_device = _key(raw.get("deviceId") or raw.get("device_id"))
    if explicit_device and explicit_device not in device_ids:
        device_ids.append(explicit_device)
    return {
        "ownerId": _key(raw.get("ownerId") or raw.get("owner_id"), "admin") or "admin",
        "workspaceRef": _text(raw.get("workspaceRef") or raw.get("workspace_ref"), "", 500),
        "taskId": _key(raw.get("taskId") or raw.get("task_id")),
        "packId": _key(raw.get("packId") or raw.get("pack_id"), "model-pack") or "model-pack",
        "runtime": _key(raw.get("runtime"), "unknown") or "unknown",
        "requestedVramMb": requested_vram,
        "requestedRamMb": requested_ram,
        "deviceIds": device_ids,
        "allowCombined": _bool(raw.get("allowCombined") if "allowCombined" in raw else raw.get("allow_combined"), False),
        "allowCpuFallback": _bool(raw.get("allowCpuFallback") if "allowCpuFallback" in raw else raw.get("allow_cpu_fallback"), True),
        "preemptible": _bool(raw.get("preemptible"), False),
    }


def evaluate_admission(
    profile: dict[str, Any] | None,
    request: dict[str, Any] | None,
    leases: list[dict[str, Any]] | None = None,
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """Return a side-effect-free placement decision for one model pack."""

    normalized_request = _request(request)
    devices = _normalize_profile(profile)
    current_leases = [normalize_lease(item, now=now) for item in (leases if leases is not None else active_leases(now=now))]
    current_leases = [item for item in current_leases if item and item["state"] == "active"]
    reserved = _reserved_by_device(current_leases)
    requested_vram = normalized_request["requestedVramMb"]
    requested_devices = normalized_request["deviceIds"]
    runtime = normalized_request["runtime"]
    base = {
        "schemaVersion": LEASE_SCHEMA_VERSION,
        "status": "unmeasured",
        "ownerId": normalized_request["ownerId"],
        "packId": normalized_request["packId"],
        "runtime": runtime,
        "requested": {
            "vramMb": requested_vram,
            "ramMb": normalized_request["requestedRamMb"],
            "deviceIds": requested_devices,
        },
        "placements": [],
        "capacity": {
            "devices": devices,
            "reservedVramMbByDevice": reserved,
            "observedDeviceCount": len(devices),
        },
        "reasons": [],
        "leasesConsidered": len(current_leases),
    }
    if requested_vram is None and normalized_request["requestedRamMb"] <= 0:
        base["reasons"].append("resource_envelope_missing")
        return base
    if len(requested_devices) > 1:
        if not normalized_request["allowCombined"]:
            base["status"] = "blocked"
            base["reasons"].append("combined_vram_requires_explicit_opt_in")
            return base
        if runtime not in COMBINED_RUNTIME_HINTS:
            base["status"] = "blocked"
            base["reasons"].append("runtime_does_not_certify_combined_vram")
            return base

    if requested_vram is None:
        base["status"] = "ready"
        base["placements"] = [{"deviceId": "cpu", "vramMb": 0}]
        base["reasons"].append("cpu_ram_only_request")
        return base

    if not devices:
        if normalized_request["allowCpuFallback"]:
            base["status"] = "degraded"
            base["placements"] = [{"deviceId": "cpu", "vramMb": 0}]
            base["reasons"].append("no_accelerator_observed_cpu_fallback")
        else:
            base["status"] = "blocked"
            base["reasons"].append("no_accelerator_observed")
        return base

    candidates = []
    for device in devices:
        if requested_devices and device["deviceId"] not in requested_devices:
            continue
        total = device["totalMb"]
        safe_free = device["safeFreeMb"]
        reserved_mb = reserved.get(device["deviceId"], 0)
        available = max(0.0, (safe_free if safe_free is not None else 0.0) - reserved_mb)
        candidates.append({
            **device,
            "reservedMb": reserved_mb,
            "availableMb": round(available, 2),
            "totalCanFit": total is not None and requested_vram <= total,
            "safeCanFit": safe_free is not None and requested_vram <= available,
        })
    candidates.sort(key=lambda item: (item["safeCanFit"], item["availableMb"]), reverse=True)
    if len(requested_devices) > 1 and normalized_request["allowCombined"]:
        selected = [item for item in candidates if item["totalMb"] is not None]
        total_available = sum(item["availableMb"] for item in selected)
        if len(selected) == len(requested_devices) and requested_vram <= total_available:
            remaining = requested_vram
            placements = []
            for item in selected:
                amount = min(int(item["availableMb"]), remaining)
                if amount > 0:
                    placements.append({"deviceId": item["deviceId"], "vramMb": amount})
                    remaining -= amount
            if remaining <= 0:
                base["status"] = "ready"
                base["placements"] = placements
                base["reasons"].append("explicit_runtime_combined_vram_fit")
                return base
    elif candidates and candidates[0]["safeCanFit"]:
        selected = candidates[0]
        base["status"] = "ready"
        base["placements"] = [{"deviceId": selected["deviceId"], "vramMb": requested_vram}]
        base["reasons"].append("largest_fitting_single_gpu_first")
        return base

    if candidates and any(item["totalCanFit"] for item in candidates):
        base["status"] = "queued"
        base["reasons"].append("device_capacity_reserved_or_headroom_required")
    else:
        base["status"] = "blocked"
        base["reasons"].append("requested_vram_exceeds_observed_device_capacity")
    base["capacity"]["candidates"] = candidates
    return base


def _lease_from_decision(request: dict[str, Any], decision: dict[str, Any], *, now: float, ttl_seconds: Any) -> dict[str, Any]:
    stamp = _now(now)
    ttl = _ttl(ttl_seconds)
    return {
        "schemaVersion": LEASE_SCHEMA_VERSION,
        "leaseId": f"lease_{uuid.uuid4().hex[:16]}",
        "ownerId": request["ownerId"],
        "workspaceRef": request["workspaceRef"],
        "taskId": request["taskId"],
        "packId": request["packId"],
        "runtime": request["runtime"],
        "state": "active",
        "placements": list(decision.get("placements") or []),
        "reservedRamMb": request["requestedRamMb"],
        "createdAt": stamp,
        "heartbeatAt": stamp,
        "expiresAt": stamp + ttl,
        "preemptible": request["preemptible"],
    }


def reserve(
    profile: dict[str, Any] | None,
    request: dict[str, Any] | None,
    *,
    ttl_seconds: Any = DEFAULT_TTL_SECONDS,
    now: float | None = None,
) -> dict[str, Any]:
    """Atomically evaluate and persist one active lease in this process."""

    stamp = _now(now)
    normalized_request = _request(request)
    with _LOCK:
        leases = active_leases(now=stamp)
        decision = evaluate_admission(profile, normalized_request, leases, now=stamp)
        result = {"decision": decision, "lease": None}
        if decision["status"] not in {"ready", "degraded"}:
            return result
        lease = _lease_from_decision(normalized_request, decision, now=stamp, ttl_seconds=ttl_seconds)
        store.set_kv(LEASES_KEY, leases + [lease])
        result["lease"] = lease
        return result


def heartbeat(lease_id: str, owner_id: str, *, ttl_seconds: Any = DEFAULT_TTL_SECONDS, now: float | None = None) -> dict[str, Any] | None:
    stamp = _now(now)
    lease_key = _key(lease_id)
    owner = _key(owner_id, "admin") or "admin"
    with _LOCK:
        leases = active_leases(now=stamp)
        for lease in leases:
            if lease["leaseId"] == lease_key and lease["ownerId"] == owner:
                lease["heartbeatAt"] = stamp
                lease["expiresAt"] = stamp + _ttl(ttl_seconds)
                store.set_kv(LEASES_KEY, leases)
                return lease
    return None


def release(lease_id: str, owner_id: str, *, now: float | None = None) -> bool:
    stamp = _now(now)
    lease_key = _key(lease_id)
    owner = _key(owner_id, "admin") or "admin"
    with _LOCK:
        leases = active_leases(now=stamp)
        kept = [lease for lease in leases if not (lease["leaseId"] == lease_key and lease["ownerId"] == owner)]
        if len(kept) == len(leases):
            return False
        store.set_kv(LEASES_KEY, kept)
        return True


def clear_all() -> None:
    """Test/development reset; production callers should release by owner."""

    with _LOCK:
        store.set_kv(LEASES_KEY, [])


__all__ = [
    "DEFAULT_TTL_SECONDS",
    "HEADROOM_FRACTION",
    "LEASE_SCHEMA_VERSION",
    "active_leases",
    "clear_all",
    "evaluate_admission",
    "heartbeat",
    "list_leases",
    "normalize_lease",
    "release",
    "reserve",
]
