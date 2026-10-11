"""Hardware capacity and model fit calculations."""

import os

from backend.models import resource_manifest
from backend.models.catalog_metadata import _tool_call_parser_hint


def _hardware_vram_values(hardware=None):
    return [gpu["totalGb"] for gpu in _hardware_gpu_capacities(hardware) if gpu.get("totalGb")]


def _hardware_gpu_capacities(hardware=None):
    """Return installed and safely usable VRAM from the live hardware probe.

    The hardware probe reports raw free VRAM. Match the resource broker's
    launch-time policy by retaining ten percent (at least 512 MiB) as safety
    headroom instead of presenting all currently free memory as deployable.
    """

    source = hardware or {}
    detected = source.get("detected_hardware") or source.get("detectedHardware") or {}
    raw_gpus = detected.get("gpus") or []
    if not raw_gpus:
        profile = source.get("capability_profile") or source.get("capabilityProfile") or {}
        raw_gpus = profile.get("devices") or []
    capacities = []
    for index, gpu in enumerate(raw_gpus):
        if not isinstance(gpu, dict):
            continue
        static = gpu.get("static") if isinstance(gpu.get("static"), dict) else gpu
        volatile = gpu.get("volatile") if isinstance(gpu.get("volatile"), dict) else gpu
        total_mb = static.get("memory_total_mb")
        if total_mb in (None, ""):
            total_mb = static.get("memoryTotalMb")
        free_mb = volatile.get("memory_free_mb")
        if free_mb in (None, ""):
            free_mb = volatile.get("memoryFreeMb")
        used_mb = volatile.get("memory_used_mb")
        if used_mb in (None, ""):
            used_mb = volatile.get("memoryUsedMb")
        try:
            total_mb = float(total_mb) if total_mb not in (None, "") else None
            free_mb = float(free_mb) if free_mb not in (None, "") else None
            used_mb = float(used_mb) if used_mb not in (None, "") else None
        except (TypeError, ValueError):
            continue
        if free_mb is None and total_mb is not None and used_mb is not None:
            free_mb = max(0.0, total_mb - used_mb)
        if total_mb is None or total_mb <= 0:
            continue
        headroom_mb = max(512.0, total_mb * 0.10)
        safe_free_mb = max(0.0, free_mb - headroom_mb) if free_mb is not None else None
        capacities.append({
            "index": index,
            "name": str(static.get("name") or gpu.get("name") or f"GPU {index}").strip(),
            "totalGb": total_mb / 1024,
            "freeGb": free_mb / 1024 if free_mb is not None else None,
            "safeFreeGb": safe_free_mb / 1024 if safe_free_mb is not None else None,
        })
    return capacities


def _matching_gpu_set(hardware=None):
    gpus = _hardware_gpu_capacities(hardware)
    if len(gpus) < 2:
        return False
    names = {str(gpu.get("name") or "").strip().lower() for gpu in gpus}
    values = [gpu["totalGb"] for gpu in gpus]
    return bool(
        len(values) == len(gpus)
        and names and "" not in names and len(names) == 1
        and max(values) - min(values) <= max(0.25, min(values) * 0.02)
    )


def _hardware_vram_gb(hardware=None):
    env_vram = os.environ.get("WARSAT_AVAILABLE_VRAM_GB")
    if env_vram:
        try:
            return float(env_vram)
        except ValueError:
            pass
    # Retain the aggregate helper for llama.cpp and legacy callers.
    values = _hardware_vram_values(hardware)
    return sum(values) if values else None


def _fit_vram_capacity(item, hardware=None):
    env_vram = os.environ.get("WARSAT_AVAILABLE_VRAM_GB")
    if env_vram:
        try:
            configured = float(env_vram)
            return {
                "installedGb": configured,
                "safeAvailableGb": configured,
                "installedBasis": "configured VRAM capacity",
                "availableBasis": "configured available VRAM",
            }
        except ValueError:
            pass
    gpus = _hardware_gpu_capacities(hardware)
    if not gpus:
        return {
            "installedGb": None,
            "safeAvailableGb": None,
            "installedBasis": "detected VRAM",
            "availableBasis": "live safe-free VRAM",
        }
    totals = [gpu["totalGb"] for gpu in gpus]
    safe_values = [gpu.get("safeFreeGb") for gpu in gpus]
    has_live_free = all(value is not None for value in safe_values)
    protocol = str(item.get("recommendedProtocol") or "").lower()
    if protocol == "llamacppggufserver":
        return {
            "installedGb": sum(totals),
            "safeAvailableGb": sum(safe_values) if has_live_free else None,
            "installedBasis": "aggregate detected VRAM for llama.cpp layer sharding",
            "availableBasis": "aggregate live safe-free VRAM for llama.cpp layer sharding",
        }
    if protocol == "vllmcudaopenai" and _matching_gpu_set(hardware):
        return {
            "installedGb": sum(totals),
            "safeAvailableGb": sum(safe_values) if has_live_free else None,
            "installedBasis": "aggregate detected VRAM for matching vLLM tensor-parallel GPUs",
            "availableBasis": "aggregate live safe-free VRAM for matching vLLM tensor-parallel GPUs",
        }
    # vLLM tensor parallelism is not assumed on heterogeneous GPUs; it needs
    # exact runtime evidence before aggregate capacity is considered safe.
    return {
        "installedGb": max(totals),
        "safeAvailableGb": max(safe_values) if has_live_free else None,
        "installedBasis": "largest detected GPU (multi-GPU sharding unproven)",
        "availableBasis": "largest live safe-free GPU (10% headroom reserved)",
    }


def _fit_available_vram(item, hardware=None):
    """Compatibility wrapper returning current safe-free capacity and its basis."""

    capacity = _fit_vram_capacity(item, hardware)
    return capacity["safeAvailableGb"], capacity["availableBasis"]


def _hardware_ram_capacity(hardware=None):
    """Return installed and safely available system RAM from the live probe."""

    env_ram = os.environ.get("WARSAT_AVAILABLE_RAM_GB")
    if env_ram:
        try:
            configured = float(env_ram)
            return {
                "installedGb": configured,
                "availableGb": configured,
                "safeAvailableGb": configured,
                "headroomGb": 0.0,
                "basis": "configured available system RAM",
            }
        except ValueError:
            pass
    source = hardware or {}
    profile = source.get("capability_profile") or source.get("capabilityProfile") or {}
    memory = profile.get("cpu") if isinstance(profile.get("cpu"), dict) else None
    if not isinstance(memory, dict):
        detected = source.get("detected_hardware") or source.get("detectedHardware") or {}
        memory = detected.get("hostMemory") or detected.get("host_memory") or detected
    def first_present(*keys):
        for key in keys:
            if memory.get(key) is not None:
                return memory.get(key)
        return None

    total_mb = first_present("memoryTotalMb", "totalMb", "total_mb")
    available_mb = first_present("memoryAvailableMb", "availableMb", "available_mb")
    used_mb = first_present("memoryUsedMb", "usedMb", "used_mb")
    try:
        total_mb = float(total_mb) if total_mb not in (None, "") else None
        available_mb = float(available_mb) if available_mb not in (None, "") else None
        used_mb = float(used_mb) if used_mb not in (None, "") else None
    except (TypeError, ValueError):
        total_mb = available_mb = used_mb = None
    if available_mb is None and total_mb is not None and used_mb is not None:
        available_mb = max(0.0, total_mb - used_mb)
    headroom_mb = 2048.0
    safe_available_mb = max(0.0, available_mb - headroom_mb) if available_mb is not None else None
    return {
        "installedGb": total_mb / 1024 if total_mb is not None else None,
        "availableGb": available_mb / 1024 if available_mb is not None else None,
        "safeAvailableGb": safe_available_mb / 1024 if safe_available_mb is not None else None,
        "headroomGb": headroom_mb / 1024,
        "basis": "live available system RAM with 2 GB reserved for the operating system",
    }


def _system_ram_estimate(item, manifest=None):
    envelope = (manifest or {}).get("runtimeEnvelope") or {}
    for value in (
        envelope.get("estimatedSystemRamGb"),
        item.get("systemRamEstimateGb"),
        item.get("system_ram_estimate_gb"),
    ):
        try:
            if value not in (None, "") and float(value) > 0:
                return float(value)
        except (TypeError, ValueError):
            continue
    return resource_manifest.estimate_system_ram_demand(item).get("totalGb")


def _fit_item(item, hardware=None):
    item = dict(item)
    # Cached catalogs created before parser hints were introduced still pass
    # through fit scoring on every read, so enrich them here as well as during
    # normalization. This makes the API change effective without a forced
    # network refresh or cache migration.
    if "toolCallParserHint" not in item:
        item["toolCallParserHint"] = _tool_call_parser_hint(
            item.get("modelId") or item.get("id"),
            item.get("recommendedProtocol"),
        )
    blocked = []
    reasons = []
    score = 50
    manifest = item.get("resourceManifest") or resource_manifest.build_manifest(item)
    vram = item.get("vramEstimateGb")
    capacity = _fit_vram_capacity(item, hardware)
    installed = capacity["installedGb"]
    available = capacity["safeAvailableGb"]
    available_basis = capacity["availableBasis"]
    installed_basis = capacity["installedBasis"]
    fit_status = "unknown"
    will_fit = None
    can_run_now = False
    if not item.get("deployable"):
        blocked.append("No local Warsat runtime is known for this catalog entry.")
        score -= 45
        fit_status = "blocked"
        will_fit = False
    if vram:
        demand = float(vram)
        if installed is None:
            score += 10 if demand <= 12 else -5
            reasons.append(f"Estimated {vram} GB VRAM; refresh the hardware check for a device-specific result.")
        elif demand > installed:
            score -= 40
            fit_status = "blocked"
            will_fit = False
            blocked.append(f"Estimated {vram} GB VRAM exceeds {installed_basis} of {installed:.1f} GB.")
        elif available is None:
            score += 12
            if fit_status != "blocked":
                fit_status = "capacity-fit"
                will_fit = True
            reasons.append(f"Estimated {vram} GB VRAM fits {installed_basis} of {installed:.1f} GB; current free VRAM was not reported.")
        else:
            margin = available - demand
            if margin >= 0:
                can_run_now = fit_status != "blocked"
                if fit_status != "blocked":
                    fit_status = "ready"
                    will_fit = True
                if margin >= 4:
                    score += 35
                    reasons.append(f"Estimated {vram} GB VRAM fits {available_basis} of {available:.1f} GB.")
                else:
                    score += 18
                    reasons.append(f"Estimated {vram} GB VRAM fits {available_basis}, but headroom is tight.")
            else:
                score += 4
                if fit_status != "blocked":
                    fit_status = "queued"
                    will_fit = True
                reasons.append(
                    f"The model fits {installed_basis} ({installed:.1f} GB), but only {available:.1f} GB of safe VRAM is free now."
                )
                reasons.append("Stop another GPU workload or wait for VRAM to become available before loading.")
    else:
        reasons.append("VRAM estimate is unknown.")
    ram_estimate = _system_ram_estimate(item, manifest)
    ram_capacity = _hardware_ram_capacity(hardware)
    installed_ram = ram_capacity["installedGb"]
    available_ram = ram_capacity["safeAvailableGb"]
    ram_status = "unknown"
    if ram_estimate:
        item["systemRamEstimateGb"] = round(float(ram_estimate), 2)
        if installed_ram is None:
            score -= 5
            reasons.append(f"Estimated {ram_estimate:.2f} GB system RAM; refresh the hardware check for a host-memory result.")
        elif ram_estimate > installed_ram:
            score -= 35
            ram_status = "blocked"
            blocked.append(f"Estimated {ram_estimate:.2f} GB system RAM exceeds installed RAM of {installed_ram:.1f} GB.")
        elif available_ram is None:
            score += 4
            ram_status = "capacity-fit"
            reasons.append(
                f"Estimated {ram_estimate:.2f} GB system RAM fits {installed_ram:.1f} GB installed RAM; current available RAM was not reported."
            )
        elif ram_estimate <= available_ram:
            score += 10
            ram_status = "ready"
            reasons.append(
                f"Estimated {ram_estimate:.2f} GB system RAM fits {available_ram:.1f} GB safely available now."
            )
        else:
            ram_status = "queued"
            reasons.append(
                f"The model fits {installed_ram:.1f} GB installed RAM, but only {available_ram:.1f} GB is safely available now."
            )
            reasons.append("Close another memory-heavy workload or wait for system RAM to become available before loading.")
    else:
        reasons.append("System RAM demand is unknown.")

    if fit_status != "blocked":
        if ram_status == "blocked":
            fit_status = "blocked"
        elif fit_status == "unknown" or ram_status == "unknown":
            fit_status = "unknown"
        elif fit_status == "queued" or ram_status == "queued":
            fit_status = "queued"
        elif fit_status == "capacity-fit" or ram_status == "capacity-fit":
            fit_status = "capacity-fit"
        else:
            fit_status = "ready"
    will_fit = False if fit_status == "blocked" else None if fit_status == "unknown" else True
    can_run_now = fit_status == "ready"
    purpose = item.get("purpose")
    if purpose in {"coding", "reasoning", "research"}:
        score += 8
        reasons.append(f"Useful for {purpose} workflows.")
    if item.get("recommendedProtocol") == "ollamaOpenaiServer":
        score += 5
        reasons.append("Ollama target is useful for quick local experiments.")
    score = max(0, min(100, int(score)))
    if fit_status == "blocked":
        label = "Will not fit"
    elif fit_status == "ready":
        label = "Will fit"
    elif fit_status == "queued":
        label = "Fits when memory is free"
    elif fit_status == "capacity-fit":
        label = "Will fit (availability unknown)"
    else:
        label = "Fit unknown"
    item.update({
        "fitScore": score,
        "fitLabel": label,
        "fitStatus": fit_status,
        "fitWillFit": will_fit,
        "fitCanRunNow": can_run_now,
        "fitCapacity": {
            "installedVramGb": round(installed, 2) if installed is not None else None,
            "safeAvailableVramGb": round(available, 2) if available is not None else None,
            "estimatedSystemRamGb": round(ram_estimate, 2) if ram_estimate is not None else None,
            "installedSystemRamGb": round(installed_ram, 2) if installed_ram is not None else None,
            "availableSystemRamGb": round(ram_capacity["availableGb"], 2) if ram_capacity["availableGb"] is not None else None,
            "safeAvailableSystemRamGb": round(available_ram, 2) if available_ram is not None else None,
            "systemRamHeadroomGb": round(ram_capacity["headroomGb"], 2),
            "systemRamBasis": ram_capacity["basis"],
            "installedBasis": installed_basis,
            "availableBasis": available_basis,
        },
        "fitReasons": reasons[:6],
        "blockedReasons": blocked,
    })
    item["resourceManifest"] = resource_manifest.attach_fit(
        manifest,
        score=score,
        label=label,
        available_vram_gb=available,
        headroom_gb=(available - float(vram)) if available is not None and vram else None,
        available_system_ram_gb=available_ram,
        system_ram_headroom_gb=(available_ram - float(ram_estimate)) if available_ram is not None and ram_estimate else None,
        basis=(
            "live-safe-free-vram-and-system-ram"
            if available is not None and available_ram is not None
            else "installed-memory-capacity"
        ),
        blocked_reasons=blocked,
    )
    return item


def _apply_fit(items, hardware=None):
    fitted = [_fit_item(item, hardware) for item in items]
    fitted.sort(key=lambda item: (bool(item.get("blockedReasons")), -int(item.get("fitScore") or 0), item.get("name", "")))
    return fitted
