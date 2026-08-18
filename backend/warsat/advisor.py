"""Deterministic WarSat model-fit advice.

This is Rasputin-native code informed by the product lesson of Odysseus's
Cookbook. It does not launch anything and cannot bypass WarSat approval.
"""

from __future__ import annotations

from backend.models import catalog
from backend.warsat import benchmarks

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



PROFILE_ALIASES = {
    "fast": "fast", "responsive": "fast", "balanced": "balanced",
    "maximum": "maximum_quality", "maximum-quality": "maximum_quality",
    "maximum_quality": "maximum_quality", "maximumquality": "maximum_quality",
    "quality": "maximum_quality",
}


def _profile_name(value):
    return PROFILE_ALIASES.get(str(value or "balanced").strip().lower().replace(" ", "_"), "balanced")


def _model_id(model):
    return str(model.get("modelId") or model.get("model_id") or model.get("id") or "")


def _model_field(model, *names, default=""):
    for name in names:
        if model.get(name) not in (None, ""):
            return model.get(name)
    return default


def _runtime_for(model, protocol):
    value = _model_field(model, "runtime", "runtimeId", "runtime_id")
    return str(value) if value else {
        "vllmCudaOpenai": "vllm",
        "llamaCppGgufServer": "llama.cpp",
        "ollamaOpenaiServer": "ollama",
    }.get(protocol, "")


def _target(model, protocol, devices, context, placement_mode, concurrency=None):
    return {
        "modelId": _model_id(model),
        "modelRevision": _model_field(model, "modelRevision", "model_revision", "revision", "checksum", "sha"),
        "runtime": _runtime_for(model, protocol),
        "protocolId": protocol,
        "deviceIds": [str(gpu["index"]) for gpu in devices],
        "contextWindow": context,
        "concurrency": int(_number(concurrency if concurrency is not None else _model_field(model, "concurrency", default=1), 1)),
        "quantization": _model_field(model, "quantization", "quantizationType"),
        "placementMode": placement_mode,
    }


def _summary(certificate, key):
    return ((certificate or {}).get("summary") or {}).get(key) or {}


def _evidence(certificate, match, requested_id=""):
    result = {
        "status": match.get("status", "unavailable"),
        "certificateId": match.get("certificateId") or requested_id or None,
        "exact": bool(match.get("exact")),
        "fresh": bool(match.get("fresh")),
        "valid": bool(match.get("valid")),
        "mismatches": dict(match.get("mismatches") or {}),
        "mismatchFields": list(match.get("mismatchFields") or []),
        "basis": "measured-exact" if match.get("exact") else "catalog-estimate",
    }
    if certificate and match.get("exact"):
        result["metrics"] = {
            "ttftMs": _summary(certificate, "ttftMs"),
            "totalLatencyMs": _summary(certificate, "totalLatencyMs"),
            "decodeTokensPerSecond": _summary(certificate, "decodeTokensPerSecond"),
        }
    return result


def _select_certificate(certificates, target):
    """Choose exact fresh evidence first, then the best explanatory record."""
    records = []
    for certificate in certificates or []:
        match = benchmarks.match_certificate(certificate, target)
        records.append((certificate, match))
    if not records:
        return None, benchmarks.match_certificate(None, target)
    status_order = {"exact": 0, "mismatch": 1, "partial": 2, "stale": 3, "invalid": 4, "unavailable": 5}
    records.sort(key=lambda item: (
        not item[1].get("exact"),
        not item[1].get("fresh"),
        status_order.get(item[1].get("status"), 9),
        -_number(item[0].get("createdAt")),
        str(item[0].get("certificateId") or ""),
    ))
    return records[0]


def _placement(facts, devices, mode):
    return {
        "mode": mode,
        "deviceIds": [str(gpu["index"]) for gpu in devices],
        "largestSingleGpuGb": max((gpu["vramGb"] for gpu in facts["gpus"]), default=None),
        "aggregateVramGb": facts["aggregateVramGb"],
    }


def _score(profile, estimate, largest, aggregate, placement, match, certificate):
    capacity = aggregate if placement["mode"] == "multi-gpu" else largest
    score = 35
    if estimate and capacity is not None:
        score += min(35, max(-30, int((capacity - estimate) * 3)))
    if match.get("exact"):
        score += 35
        decode = _summary(certificate, "decodeTokensPerSecond").get("p50")
        if decode:
            score += min(15, int(float(decode) / 20))
    elif match.get("status") in {"stale", "mismatch", "partial", "invalid"}:
        score -= 5
    if profile == "fast":
        score += 5 if placement["mode"] == "single-gpu" else -20
    elif profile == "maximum_quality" and placement["mode"] == "multi-gpu":
        score += 5
    return max(0, min(100, int(score)))


def recommend(model, hardware, mission="chat", protocol_id="", context_window=None,
              tool_call_parser="", profile=None, benchmark_certificate=None,
              benchmark_certificate_id="", concurrency=None, benchmark_certificates=None):
    """Return legacy advice plus a strict hardware/profile recommendation.

    A missing profile preserves the historical direct-call aggregate-fit behavior;
    the API supplies its balanced default explicitly.
    """
    model = dict(model or {})
    facts = _hardware_facts(hardware)
    protocol = str(protocol_id or model.get("recommendedProtocol") or "")
    parser = str(tool_call_parser or model.get("toolCallParserHint") or "").strip().lower()
    context = int(context_window or model.get("contextWindow") or 8192)
    profile_name = _profile_name(profile)
    strict = profile is not None
    estimate = _number(model.get("vramEstimateGb"))
    aggregate_margin = round(facts["aggregateVramGb"] - estimate, 2) if estimate and facts["aggregateVramGb"] else None
    largest = min(facts["gpus"], key=lambda item: (-item["vramGb"], item["index"])) if facts["gpus"] else None
    largest_vram = largest["vramGb"] if largest else None
    blockers, warnings, assumptions = [], [], []

    if protocol not in SUPPORTED_PARSERS:
        blockers.append(f"Runtime {protocol or '(missing)'} is not a managed WarSat deployment protocol.")
    if not model.get("deployable", True) or protocol == "apiOnly":
        blockers.append("This catalog entry has no managed local deployment path.")
    if parser and parser not in SUPPORTED_PARSERS.get(protocol, set()):
        blockers.append(f"Tool-call parser {parser} is not supported by {protocol}.")
    if estimate and aggregate_margin is not None and aggregate_margin < 0:
        blockers.append(f"Estimated model demand exceeds aggregate VRAM by {abs(aggregate_margin):.2f} GB.")
    elif estimate and aggregate_margin is not None and aggregate_margin < 4:
        warnings.append(f"Only {aggregate_margin:.2f} GB of estimated VRAM headroom remains.")
    if not facts["gpus"]:
        warnings.append("No GPU memory was observed; accelerator fit is unproven.")
    if not estimate:
        warnings.append("Model VRAM demand is unknown; fit remains unproven.")
    if context > 32768:
        assumptions.append("VRAM estimate may not include the full KV-cache cost of the requested context.")
    if len(facts["gpus"]) > 1:
        assumptions.append("Aggregate VRAM is not assumed: default placement uses the largest fitting single GPU. Multi-GPU sharding requires an explicit runtime certificate for the selected devices.")
    purpose = str(model.get("purpose") or "chat")
    if mission not in {purpose, "chat"} and mission not in (model.get("capabilities") or []):
        warnings.append(f"The catalog does not certify this model for the {mission} mission.")

    single_devices = [largest] if largest else []
    single_target = _target(model, protocol, single_devices, context, "single-gpu", concurrency)
    if benchmark_certificates is not None:
        single_certificate, single_match = _select_certificate(benchmark_certificates, single_target)
    else:
        single_certificate = benchmark_certificate
        single_match = benchmarks.match_certificate(benchmark_certificate, single_target)
    selected_devices, placement_mode, evidence_match = single_devices, "single-gpu", single_match
    evidence_certificate = single_certificate
    can_combine = (
        profile_name == "maximum_quality" and protocol == "llamaCppGgufServer"
        and len(facts["gpus"]) > 1 and estimate and largest_vram is not None
        and estimate > largest_vram
    )
    combined_target = _target(model, protocol, facts["gpus"], context, "multi-gpu", concurrency)
    if benchmark_certificates is not None:
        combined_certificate, combined_match = _select_certificate(benchmark_certificates, combined_target)
    else:
        combined_certificate = benchmark_certificate
        combined_match = benchmarks.match_certificate(benchmark_certificate, combined_target)
    if can_combine and combined_match.get("exact"):
        selected_devices, placement_mode, evidence_match = list(facts["gpus"]), "multi-gpu", combined_match
        evidence_certificate = combined_certificate
    elif can_combine:
        # A single-GPU certificate is not evidence for a Maximum Quality
        # candidate that requires combined llama.cpp placement.
        evidence_match, evidence_certificate = combined_match, combined_certificate
    elif strict and profile_name in {"fast", "balanced"} and estimate and largest_vram is not None and estimate > largest_vram:
        blockers.append(f"Estimated model demand exceeds the largest single GPU by {estimate - largest_vram:.2f} GB for the {profile_name} profile.")
    elif strict and profile_name == "maximum_quality" and estimate and largest_vram is not None and estimate > largest_vram:
        blockers.append("Maximum Quality requires an exact fresh measured llama.cpp/GGUF multi-GPU certificate; aggregate VRAM alone cannot authorize placement.")
    has_evidence = benchmark_certificate is not None or bool(benchmark_certificates)
    if strict and has_evidence and evidence_match.get("status") == "mismatch":
        warnings.append("Benchmark evidence is present but does not match the requested placement tuple.")
    if strict and can_combine and has_evidence and not combined_match.get("exact"):
        warnings.append("Combined placement evidence is stale, partial, invalid, or mismatched.")

    fit = catalog._fit_item(model, hardware)
    placement = _placement(facts, selected_devices, placement_mode)
    evidence = _evidence(evidence_certificate, evidence_match, benchmark_certificate_id)
    if strict and estimate and largest_vram is not None and estimate <= largest_vram:
        assumptions.append(f"{profile_name.title()} uses the largest single GPU by default.")
    if placement_mode == "multi-gpu":
        assumptions.append("Combined placement is allowed only by an exact fresh measured llama.cpp/GGUF certificate.")
    if evidence_match.get("exact"):
        assumptions.append("Fresh exact benchmark evidence outranks catalog-only estimates for this tuple.")
    status = "blocked" if blockers else "ready_with_warnings" if warnings else "ready_with_assumptions" if assumptions else "ready"
    confidence = "high" if evidence_match.get("exact") else "medium" if estimate or facts["gpus"] else "low"
    result = {
        "status": status, "mission": mission, "profile": profile_name,
        "placement": placement,
        "profileScore": _score(profile_name, estimate, largest_vram, facts["aggregateVramGb"], placement, evidence_match, evidence_certificate),
        "benchmarkEvidence": evidence, "benchmark": evidence,
        "recommendation": {"modelRef": _model_id(model), "protocolId": protocol, "contextWindow": context, "toolCallParser": parser, "multiGpu": placement_mode == "multi-gpu"},
        "planSeed": {"protocolId": protocol, "modelRef": _model_id(model), "contextWindow": context, "toolCallParser": parser or None, "multiGpu": placement_mode == "multi-gpu"},
        "evidence": {
            "observed": facts,
            "estimated": {"modelVramGb": estimate or None, "vramMarginGb": aggregate_margin, "catalogFitScore": fit.get("fitScore"), "catalogFitLabel": fit.get("fitLabel")},
            "confidence": confidence, "unproven": warnings, "benchmark": evidence,
        },
        "blockers": blockers, "warnings": warnings, "assumptions": assumptions, "approvalBypassed": False,
    }
    return result


def _ranking_key(item, profile):
    evidence, metrics = item.get("benchmarkEvidence") or {}, (item.get("benchmarkEvidence") or {}).get("metrics") or {}
    ttft = (metrics.get("ttftMs") or {}).get("p50")
    latency = (metrics.get("totalLatencyMs") or {}).get("p50")
    decode = (metrics.get("decodeTokensPerSecond") or {}).get("p50")
    ref = item["recommendation"]["modelRef"]
    blocked = item.get("status") == "blocked"
    profile = _profile_name(profile)
    if profile == "fast":
        return (blocked, not evidence.get("exact"), -float(decode or 0), float(ttft or 10**9), float(latency or 10**9), -float(item.get("profileScore") or 0), ref)
    if profile == "maximum_quality":
        return (blocked, not evidence.get("exact"), (item.get("placement") or {}).get("mode") != "multi-gpu", -float(item.get("profileScore") or 0), ref)
    return (blocked, not evidence.get("exact"), -float(item.get("profileScore") or 0), -float(decode or 0), float(latency or 10**9), ref)


def rank_recommendations(models, hardware, mission="chat", profile="balanced", **kwargs):
    results = [recommend(item, hardware, mission=mission, profile=profile, **kwargs) for item in (models or [])]
    results.sort(key=lambda item: _ranking_key(item, profile))
    return results


rank_models = rank_recommendations
