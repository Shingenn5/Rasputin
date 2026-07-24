"""Deterministic WarSat model-fit advice.

This is Rasputin-native code informed by the product lesson of Odysseus's
Cookbook. It does not launch anything and cannot bypass WarSat approval.
"""

from __future__ import annotations

from backend.models import catalog

SUPPORTED_PARSERS = {
    "vllmCudaOpenai": {"hermes", "mistral", "llama3_json"},
    "llamaCppGgufServer": set(),
    "ollamaOpenaiServer": set(),
}


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _hardware_facts(hardware):
    detected = (hardware or {}).get("detectedHardware") or (hardware or {}).get("detected_hardware") or {}
    gpus = detected.get("gpus") or []
    devices = []
    for index, gpu in enumerate(gpus):
        total_mb = _number(gpu.get("memoryTotalMb") or gpu.get("memory_total_mb"))
        devices.append({
            "index": index,
            "name": str(gpu.get("name") or f"GPU {index}"),
            "vramGb": round(total_mb / 1024, 2),
        })
    ram_mb = _number(detected.get("memoryTotalMb") or detected.get("memory_total_mb"))
    return {
        "gpus": devices,
        "aggregateVramGb": round(sum(item["vramGb"] for item in devices), 2),
        "ramGb": round(ram_mb / 1024, 2) if ram_mb else None,
    }


def recommend(model, hardware, mission="chat", protocol_id="", context_window=None, tool_call_parser=""):
    model = dict(model or {})
    facts = _hardware_facts(hardware)
    protocol = str(protocol_id or model.get("recommendedProtocol") or "")
    parser = str(tool_call_parser or model.get("toolCallParserHint") or "").strip().lower()
    context = int(context_window or model.get("contextWindow") or 8192)
    estimate = _number(model.get("vramEstimateGb"))
    margin = round(facts["aggregateVramGb"] - estimate, 2) if estimate and facts["aggregateVramGb"] else None
    blockers = []
    warnings = []
    assumptions = []

    if protocol not in SUPPORTED_PARSERS:
        blockers.append(f"Runtime {protocol or '(missing)'} is not a managed WarSat deployment protocol.")
    if not model.get("deployable", True) or protocol == "apiOnly":
        blockers.append("This catalog entry has no managed local deployment path.")
    if parser and parser not in SUPPORTED_PARSERS.get(protocol, set()):
        blockers.append(f"Tool-call parser {parser} is not supported by {protocol}.")
    if estimate and margin is not None and margin < 0:
        blockers.append(f"Estimated model demand exceeds aggregate VRAM by {abs(margin):.2f} GB.")
    elif estimate and margin is not None and margin < 4:
        warnings.append(f"Only {margin:.2f} GB of estimated VRAM headroom remains.")
    if not facts["gpus"]:
        warnings.append("No GPU memory was observed; accelerator fit is unproven.")
    if not estimate:
        warnings.append("Model VRAM demand is unknown; fit remains unproven.")
    if context > 32768:
        assumptions.append("VRAM estimate may not include the full KV-cache cost of the requested context.")
    if len(facts["gpus"]) > 1:
        assumptions.append("Aggregate VRAM is usable only when the selected runtime can shard this model across the observed devices.")

    purpose = str(model.get("purpose") or "chat")
    if mission not in {purpose, "chat"} and mission not in (model.get("capabilities") or []):
        warnings.append(f"The catalog does not certify this model for the {mission} mission.")

    fit = catalog._fit_item(model, hardware)
    status = "blocked" if blockers else "ready_with_warnings" if warnings else "ready_with_assumptions" if assumptions else "ready"
    confidence = "high" if estimate and facts["gpus"] and not assumptions else "medium" if estimate or facts["gpus"] else "low"
    return {
        "status": status,
        "mission": mission,
        "recommendation": {
            "modelRef": model.get("modelId") or model.get("id") or "",
            "protocolId": protocol,
            "contextWindow": context,
            "toolCallParser": parser,
            "multiGpu": len(facts["gpus"]) > 1,
        },
        "planSeed": {
            "protocolId": protocol,
            "modelRef": model.get("modelId") or model.get("id") or "",
            "contextWindow": context,
            "toolCallParser": parser or None,
            "multiGpu": len(facts["gpus"]) > 1,
        },
        "evidence": {
            "observed": facts,
            "estimated": {
                "modelVramGb": estimate or None,
                "vramMarginGb": margin,
                "catalogFitScore": fit.get("fitScore"),
                "catalogFitLabel": fit.get("fitLabel"),
            },
            "confidence": confidence,
            "unproven": warnings,
        },
        "blockers": blockers,
        "warnings": warnings,
        "assumptions": assumptions,
        "approvalBypassed": False,
    }
