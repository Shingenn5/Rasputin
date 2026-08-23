"""Normalized, evidence-aware hardware and runtime capability profiles.

The profile is intentionally separate from model placement. It describes what
Rasputin observed (and what remains unknown) so a later broker can make an
admission decision without treating aggregate memory as a single device.
"""

from __future__ import annotations

import os
import platform
import time
from typing import Any


SCHEMA_VERSION = 1
_KNOWN_BACKENDS = ("cpu", "cuda", "rocm", "metal", "mlx", "coreml", "openvino", "directml", "vulkan")


def _number(value: Any, default: float | None = None) -> float | None:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value: Any, default: int | None = None) -> int | None:
    number = _number(value)
    return default if number is None else int(number)


def _first(mapping: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        value = mapping.get(name)
        if value not in (None, ""):
            return value
    return default


def _vendor_for(name: str, explicit: Any = None) -> str:
    value = str(explicit or "").strip().lower()
    if value:
        return value
    lowered = str(name or "").lower()
    if any(token in lowered for token in ("nvidia", "geforce", "rtx", "quadro", "tesla")):
        return "nvidia"
    if any(token in lowered for token in ("amd", "radeon", "instinct")):
        return "amd"
    if any(token in lowered for token in ("intel", "arc", "uhd", "iris")):
        return "intel"
    if any(token in lowered for token in ("apple", "metal")):
        return "apple"
    return "unknown"


def _backend_hints(vendor: str, host_os: str) -> list[str]:
    if vendor == "nvidia":
        return ["cuda", "vulkan"]
    if vendor == "amd":
        return ["rocm", "vulkan"]
    if vendor == "intel":
        return ["openvino", "vulkan"]
    if vendor == "apple" or host_os == "Darwin":
        return ["metal", "mlx", "coreml"]
    return ["cpu"]


def _status(status: str, evidence: list[str] | None = None, note: str = "") -> dict[str, Any]:
    return {
        "status": status,
        "evidence": list(evidence or []),
        "note": note,
    }


def _host_memory() -> dict[str, int | None]:
    """Read host memory defensively; profile generation must never fail on it."""

    try:
        import psutil

        memory = psutil.virtual_memory()
        return {
            "totalMb": int(memory.total / (1024 * 1024)),
            "availableMb": int(memory.available / (1024 * 1024)),
            "usedMb": int(memory.used / (1024 * 1024)),
        }
    except Exception:
        return {"totalMb": None, "availableMb": None, "usedMb": None}


def _normalize_device(raw: dict[str, Any], index: int, host_os: str, observed_at: float) -> dict[str, Any]:
    device_index = _integer(_first(raw, "index", default=index), index)
    name = str(_first(raw, "name", "model", default=f"GPU {device_index}") or f"GPU {device_index}")
    vendor = _vendor_for(name, _first(raw, "vendor", "manufacturer"))
    total_mb = _integer(_first(raw, "memoryTotalMb", "memory_total_mb", "memoryTotal", default=None))
    used_mb = _number(_first(raw, "memoryUsedMb", "memory_used_mb", "memoryUsed", default=None))
    free_mb = _number(_first(raw, "memoryFreeMb", "memory_free_mb", "memoryFree", default=None))
    if free_mb is None and total_mb is not None and used_mb is not None:
        free_mb = max(0.0, total_mb - used_mb)
    if used_mb is None and total_mb is not None and free_mb is not None:
        used_mb = max(0.0, total_mb - free_mb)

    return {
        "deviceId": f"gpu:{device_index}",
        "kind": "gpu",
        "static": {
            "index": device_index,
            "name": name,
            "vendor": vendor,
            "backendHints": _backend_hints(vendor, host_os),
            "memoryTotalMb": total_mb,
        },
        "volatile": {
            "memoryUsedMb": round(used_mb, 2) if used_mb is not None else None,
            "memoryFreeMb": round(free_mb, 2) if free_mb is not None else None,
            "utilizationPct": _number(_first(raw, "utilizationPct", "utilization", "utilization_gpu", default=None)),
            "temperatureC": _number(_first(raw, "temperatureC", "temperature", "temperature_gpu", default=None)),
            "observedAt": observed_at,
        },
    }


def build_capability_profile(
    detected_hardware: dict[str, Any] | None = None,
    *,
    host_memory: dict[str, Any] | None = None,
    generated_at: float | None = None,
) -> dict[str, Any]:
    """Build a stable profile from hardware probe evidence.

    ``detected_hardware`` is intentionally permissive because it is assembled
    by native and Docker probes with slightly different field names. Unknown
    values remain ``None`` or ``unknown`` instead of being guessed. Static
    device facts and volatile capacity are kept in separate objects so a
    future broker can refresh capacity without changing device identity.
    """

    detected = dict(detected_hardware or {})
    now = float(generated_at if generated_at is not None else time.time())
    host_os = str(detected.get("os") or platform.system() or "unknown")
    runtime = str(detected.get("runtime") or os.environ.get("WRAPPER_RUNTIME") or "native")
    inside_docker = bool(detected.get("insideDocker", runtime == "docker"))
    memory = dict(host_memory or _host_memory())
    raw_gpus = detected.get("gpus") or []
    devices = [
        _normalize_device(item if isinstance(item, dict) else {}, index, host_os, now)
        for index, item in enumerate(raw_gpus)
    ]

    evidence: dict[str, list[str]] = {backend: [] for backend in _KNOWN_BACKENDS}
    evidence["cpu"].append("python-runtime")
    backends: dict[str, dict[str, Any]] = {
        "cpu": _status("available", evidence["cpu"], "CPU execution is always the safe baseline."),
    }
    probe_source = str(detected.get("gpuProbeSource") or "").strip().lower()
    docker_runtimes = {str(item).lower() for item in (detected.get("dockerRuntimes") or [])}
    has_nvidia = any(device["static"]["vendor"] == "nvidia" for device in devices)
    has_amd = any(device["static"]["vendor"] == "amd" for device in devices)
    has_intel = any(device["static"]["vendor"] == "intel" for device in devices)

    if has_nvidia:
        evidence["cuda"].append("nvidia-device-observed")
    if probe_source in {"nvidia-smi", "docker-nvidia-smi"}:
        evidence["cuda"].append(probe_source)
    if "nvidia" in docker_runtimes:
        evidence["cuda"].append("docker:nvidia-runtime")
    if has_amd:
        evidence["rocm"].append("amd-device-observed")
    if has_intel:
        evidence["openvino"].append("intel-device-observed")
    if host_os == "Darwin":
        for backend in ("metal", "mlx", "coreml"):
            evidence[backend].append("darwin-host-observed")

    for backend in _KNOWN_BACKENDS:
        if backend == "cpu":
            continue
        if evidence[backend]:
            backends[backend] = _status(
                "observed",
                evidence[backend],
                "Observed capability still requires a runtime/model compatibility probe before launch.",
            )
        else:
            backends[backend] = _status(
                "unknown",
                [],
                "No evidence was collected in this hardware probe; do not claim support yet.",
            )

    total_vram = sum(int(device["static"].get("memoryTotalMb") or 0) for device in devices)
    known_free = [device["volatile"].get("memoryFreeMb") for device in devices]
    free_values = [float(value) for value in known_free if value is not None]
    vendors = {device["static"].get("vendor") for device in devices}
    summary = {
        "hardwareClass": (
            "cpu-only" if not devices else
            "mixed-vendor" if len(vendors) > 1 else
            f"{next(iter(vendors))}-multi-gpu" if len(devices) > 1 else
            f"{devices[0]['static'].get('vendor', 'unknown')}-single-gpu"
        ),
        "deviceCount": len(devices),
        "gpuCount": len(devices),
        "installedVramMb": total_vram,
        "knownFreeVramMb": round(sum(free_values), 2) if free_values else None,
        "placementDefault": "all_compatible_gpus_first",
        "combinedVramRequiresExplicitRuntime": True,
    }
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": now,
        "volatileRefreshedAt": now,
        "host": {
            "os": host_os,
            "platform": str(detected.get("platform") or platform.platform()),
            "architecture": str(detected.get("architecture") or platform.machine() or "unknown"),
            "runtime": runtime,
            "insideDocker": inside_docker,
        },
        "cpu": {
            "processor": platform.processor() or "unknown",
            "logicalCores": os.cpu_count(),
            "memoryTotalMb": _integer(_first(memory, "totalMb", "total_mb", "memoryTotalMb", default=None)),
            "memoryAvailableMb": _integer(_first(memory, "availableMb", "available_mb", "memoryAvailableMb", default=None)),
            "memoryUsedMb": _integer(_first(memory, "usedMb", "used_mb", "memoryUsedMb", default=None)),
        },
        "devices": devices,
        "backends": backends,
        "summary": summary,
    }


__all__ = ["SCHEMA_VERSION", "build_capability_profile"]
