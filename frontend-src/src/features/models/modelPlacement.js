import { hardwarePlacementCapacity, systemMemoryCapacity } from "./hardwareSnapshot.js";

export function runtimeEnvelopeForItem(item) {
  return item?.resourceManifest?.runtimeEnvelope || item?.resource_manifest?.runtimeEnvelope || item?.resource_manifest?.runtime_envelope || {};
}

export function catalogVramEstimateGb(item) {
  const envelope = runtimeEnvelopeForItem(item);
  const parsed = Number(envelope?.estimatedVramGb ?? envelope?.estimateGb ?? envelope?.estimate ?? item?.vramEstimateGb);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function catalogSystemRamEstimateGb(item) {
  const envelope = runtimeEnvelopeForItem(item);
  const parsed = Number(
    envelope?.estimatedSystemRamGb
    ?? envelope?.estimated_system_ram_gb
    ?? item?.systemRamEstimateGb
    ?? item?.system_ram_estimate_gb
  );
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function withSystemRamAssessment(gpuAssessment, item, hardware) {
  const estimate = catalogSystemRamEstimateGb(item);
  const liveCapacity = systemMemoryCapacity(hardware);
  const backendCapacity = item?.fitCapacity || {};
  const backendTotal = Number(backendCapacity.installedSystemRamGb);
  const backendSafeAvailable = Number(backendCapacity.safeAvailableSystemRamGb);
  const total = liveCapacity.totalGb ?? (Number.isFinite(backendTotal) && backendTotal > 0 ? backendTotal : null);
  const safeAvailable = liveCapacity.safeAvailableGb ?? (Number.isFinite(backendSafeAvailable) && backendSafeAvailable >= 0 ? backendSafeAvailable : null);
  const result = {
    ...gpuAssessment,
    vramStatus: gpuAssessment.status,
    systemRamEstimateGb: estimate,
    installedSystemRamGb: total,
    safeAvailableSystemRamGb: safeAvailable,
    reasons: [...(gpuAssessment.reasons || [])],
  };
  if (!estimate) {
    if (gpuAssessment.status !== "blocked") {
      result.kind = result.status = "unknown";
      result.label = "Fit unknown";
      result.canDeploy = false;
      result.willFit = null;
      result.canRunNow = false;
    }
    result.reasons.push("System RAM demand is unknown, so overall fit cannot be determined.");
    return result;
  }
  if (total == null) {
    if (gpuAssessment.status !== "blocked") {
      result.kind = result.status = "unknown";
      result.label = "Fit unknown";
      result.canDeploy = false;
      result.willFit = null;
      result.canRunNow = false;
    }
    result.reasons.push("Installed system RAM is unavailable; refresh the hardware check.");
    return result;
  }
  if (estimate > total) {
    result.kind = result.status = "blocked";
    result.label = "Will not fit";
    result.canDeploy = false;
    result.willFit = false;
    result.canRunNow = false;
    result.reasons.push("Estimated " + estimate + " GB system RAM exceeds installed RAM (" + total.toFixed(1) + " GB).");
    return result;
  }
  if (safeAvailable == null) {
    if (gpuAssessment.status !== "blocked" && gpuAssessment.status !== "queued") {
      result.kind = result.status = "capacity-fit";
      result.label = "Will fit (availability unknown)";
      result.canDeploy = true;
      result.willFit = true;
      result.canRunNow = false;
    }
    result.reasons.push("Estimated " + estimate + " GB system RAM fits installed RAM, but current available RAM was not reported.");
    return result;
  }
  if (estimate > safeAvailable) {
    if (gpuAssessment.status !== "blocked") {
      result.kind = result.status = "queued";
      result.label = "Fits when memory is free";
      result.canDeploy = true;
      result.willFit = true;
      result.canRunNow = false;
    }
    result.reasons.push("Estimated " + estimate + " GB system RAM fits installed RAM, but only " + safeAvailable.toFixed(1) + " GB is safely available now.");
    return result;
  }
  result.reasons.push("Estimated " + estimate + " GB system RAM fits " + safeAvailable.toFixed(1) + " GB safely available now.");
  if (gpuAssessment.status === "queued") result.label = "Fits when memory is free";
  return result;
}

export function catalogPlacementAssessment(item, hardware, measuredEvidence = null) {
  const capacity = hardwarePlacementCapacity(hardware);
  const estimate = catalogVramEstimateGb(item);
  const evidence = measuredEvidence || item?.benchmarkEvidence || item?.benchmark || item?.resourceManifest?.benchmarkEvidence || {};
  const placement = evidence?.placement || {};
  const protocol = String(evidence?.protocolId || evidence?.protocol || evidence?.runtime || item?.recommendedProtocol || "").toLowerCase();
  const exact = evidence?.exact === true || evidence?.status === "exact" || evidence?.basis === "measured-exact";
  const multiGpu = placement?.mode === "multi-gpu" || placement?.mode === "multi_gpu" || evidence?.placementMode === "multi-gpu" || evidence?.placement_mode === "multi-gpu";
  const measuredLayerSharding = exact && multiGpu && (protocol.includes("llama") || protocol.includes("gguf"));
  const llamaLayerSharding = protocol.includes("llama") || protocol.includes("gguf");
  const matchingVllmTensorParallel = protocol.includes("vllm") && capacity.matchingGpuSet;
  const combinedPlacement = measuredLayerSharding || llamaLayerSharding || matchingVllmTensorParallel;
  const largest = capacity.largestSingleGpuGb;
  const installedCapacity = combinedPlacement ? capacity.aggregateVramGb : largest;
  const safeAvailable = combinedPlacement ? capacity.aggregateSafeFreeVramGb : capacity.largestSafeFreeGpuGb;
  const hasEstimate = Number.isFinite(estimate) && estimate > 0;
  const backendStatus = String(item?.fitStatus || item?.resourceManifest?.fit?.status || "").toLowerCase();
  const backendCapacity = item?.fitCapacity || {};
  const backendNumber = (value) => value == null || value === "" ? null : Number.isFinite(Number(value)) ? Number(value) : null;
  if ((!capacity.gpus.length || !hasEstimate) && backendStatus) {
    const backendWillFit = item?.fitWillFit ?? ["ready", "queued", "capacity-fit"].includes(backendStatus);
    const backendCanRunNow = item?.fitCanRunNow ?? backendStatus === "ready";
    return {
      kind: backendStatus,
      status: backendStatus,
      label: item?.fitLabel || (backendWillFit ? "Will fit" : backendStatus === "blocked" ? "Will not fit" : "Fit unknown"),
      canDeploy: Boolean(backendWillFit),
      willFit: backendWillFit,
      canRunNow: backendCanRunNow,
      largestSingleGpuGb: largest,
      aggregateVramGb: capacity.aggregateVramGb,
      safeAvailableVramGb: backendNumber(backendCapacity.safeAvailableVramGb),
      systemRamEstimateGb: catalogSystemRamEstimateGb(item) ?? backendNumber(backendCapacity.estimatedSystemRamGb),
      installedSystemRamGb: backendNumber(backendCapacity.installedSystemRamGb),
      safeAvailableSystemRamGb: backendNumber(backendCapacity.safeAvailableSystemRamGb),
      reasons: Array.isArray(item?.fitReasons) && item.fitReasons.length ? item.fitReasons : ["Hardware fit was calculated by the latest server-side probe."],
    };
  }
  if (!capacity.gpus.length || !hasEstimate) {
    return withSystemRamAssessment({
      kind: "unknown",
      status: "unknown",
      label: !hasEstimate ? "Choose variant to check fit" : "Check hardware",
      canDeploy: false,
      willFit: null,
      canRunNow: false,
      largestSingleGpuGb: largest,
      aggregateVramGb: capacity.aggregateVramGb,
      safeAvailableVramGb: safeAvailable,
      reasons: [!capacity.gpus.length
        ? "GPU capacity is unavailable; refresh the hardware check."
        : "Model VRAM demand is unknown, so fit cannot be determined."],
    }, item, hardware);
  }
  const placementLabel = measuredLayerSharding
    ? "measured llama.cpp/GGUF layer sharding"
    : llamaLayerSharding
      ? "llama.cpp/GGUF layer sharding"
      : matchingVllmTensorParallel
        ? "matching vLLM tensor-parallel GPUs"
        : "the largest single GPU";
  if (installedCapacity == null || estimate > installedCapacity) {
    return withSystemRamAssessment({
      kind: "blocked",
      status: "blocked",
      label: "Will not fit",
      canDeploy: false,
      willFit: false,
      canRunNow: false,
      largestSingleGpuGb: largest,
      aggregateVramGb: capacity.aggregateVramGb,
      safeAvailableVramGb: safeAvailable,
      reasons: ["Estimated " + estimate + " GB exceeds " + placementLabel + " capacity (" + (installedCapacity || 0).toFixed(1) + " GB)."],
    }, item, hardware);
  }
  if (safeAvailable == null) {
    return withSystemRamAssessment({
      kind: "capacity-fit",
      status: "capacity-fit",
      label: "Will fit (availability unknown)",
      canDeploy: true,
      willFit: true,
      canRunNow: false,
      largestSingleGpuGb: largest,
      aggregateVramGb: capacity.aggregateVramGb,
      safeAvailableVramGb: null,
      reasons: ["Estimated " + estimate + " GB fits " + placementLabel + " (" + installedCapacity.toFixed(1) + " GB), but current free VRAM was not reported."],
    }, item, hardware);
  }
  if (estimate <= safeAvailable) {
    return withSystemRamAssessment({
      kind: combinedPlacement ? "combined-ready" : "single-gpu-ready",
      status: "ready",
      label: "Will fit",
      canDeploy: true,
      willFit: true,
      canRunNow: true,
      largestSingleGpuGb: largest,
      aggregateVramGb: capacity.aggregateVramGb,
      safeAvailableVramGb: safeAvailable,
      reasons: ["Estimated " + estimate + " GB fits the current safe-free capacity for " + placementLabel + " (" + safeAvailable.toFixed(1) + " GB after headroom)."],
    }, item, hardware);
  }
  return withSystemRamAssessment({
    kind: "queued",
    status: "queued",
    label: "Fits when VRAM is free",
    canDeploy: true,
    willFit: true,
    canRunNow: false,
    largestSingleGpuGb: largest,
    aggregateVramGb: capacity.aggregateVramGb,
    safeAvailableVramGb: safeAvailable,
    reasons: [
      "Estimated " + estimate + " GB fits " + placementLabel + " (" + installedCapacity.toFixed(1) + " GB), but only " + safeAvailable.toFixed(1) + " GB is safely free now.",
      "Stop another GPU workload or wait for VRAM to become available before loading.",
    ],
  }, item, hardware);
}
