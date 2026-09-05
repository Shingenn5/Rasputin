function normalizedModelReference(value) {
  let reference = String(value || "").trim().replace(/\\/g, "/");
  reference = reference.replace(/^https?:\/\/(?:www\.)?huggingface\.co\//i, "");
  reference = reference.replace(/\/(?:tree|resolve|blob)\/[^/]+.*$/i, "");
  return reference.replace(/^\/+|\/+$/g, "").toLowerCase();
}

function modelReferences(value) {
  const artifact = value?.artifact || value?.artifactMetadata || value?.artifact_metadata || {};
  return new Set([
    value?.repository,
    value?.modelId,
    value?.model_id,
    value?.id,
    value?.warsatModelRef,
    artifact?.repository,
  ].map(normalizedModelReference).filter((reference) => reference.includes("/")));
}

/** Link a Discover repository to the durable native artifact shown in My Models. */
export function findInstalledCatalogModel(item, models, variant = null) {
  const wanted = modelReferences(item);
  if (!wanted.size) return null;
  const candidates = (models || []).filter((model) => {
    if (model?.runtime !== "native-llamacpp") return false;
    const artifactAvailable = model.artifactAvailable ?? model.artifact_available;
    if (artifactAvailable === false) return false;
    if (variant) {
      const artifact = model.artifact || model.artifactMetadata || model.artifact_metadata || {};
      const variantId = model.variantId || model.variant_id || artifact.variantId || artifact.variant_id;
      // An explicit selection must never fall back to another quantization.
      if (!variant.id || variantId !== variant.id) return false;
      const revision = model.revision || artifact.revision;
      if (variant.revision && revision !== variant.revision) return false;
    }
    return [...modelReferences(model)].some((reference) => wanted.has(reference));
  });
  return candidates.find((model) => ["running", "reachable", "healthy"].includes(
    String(model?.runtimeStatus || model?.containerStatus || model?.container_status || model?.status || "").toLowerCase(),
  )) || candidates[0] || null;
}

function hardwareDevices(hardware) {
  const capability = hardware?.capabilityProfile || hardware?.capability_profile || {};
  const detected = hardware?.detectedHardware || hardware?.detected_hardware || {};
  return hardware?.devices || hardware?.gpus || capability?.devices || detected?.gpus || [];
}

function freeMemoryMb(device) {
  const volatile = device?.volatile || {};
  const value = device?.freeMb ?? device?.free_mb ?? device?.freeMemoryMb ?? device?.memoryFreeMb
    ?? device?.freeVramMb ?? volatile?.freeMb ?? volatile?.free_mb ?? volatile?.freeMemoryMb
    ?? volatile?.memoryFreeMb ?? volatile?.freeVramMb;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.max(0, parsed) : null;
}

/**
 * A first-load preview cannot prove layer splitting until the runtime exists.
 * Permit that one provisional case only when the current GPUs have enough
 * aggregate free memory; the actual start installs, probes, and replans before
 * launching a process.
 */
export function firstLoadCanResolvePlacement(preview, runtimeStatus, hardware, profile = {}) {
  if (String(runtimeStatus?.state || "").toLowerCase() !== "install_required") return false;
  if (!["auto", "layer"].includes(profile.splitMode || "auto")) return false;
  if (profile.mainGpu != null && profile.mainGpu !== "") return false;
  if (profile.tensorSplit || profile.memoryMode === "cpu_only" || profile.gpuLayers === 0) return false;
  const reasons = preview?.blockReasons || preview?.block_reasons || [];
  if (!reasons.length || !reasons.every((reason) => String(reason).toLowerCase().includes("no permitted gpu allocation fits"))) return false;
  const required = Number(preview?.resolvedSettings?.requiredMemoryMb ?? preview?.resolved_settings?.required_memory_mb);
  if (!Number.isFinite(required) || required <= 0) return false;
  const safety = Math.max(0, Number(hardware?.safetyMarginMb ?? hardware?.safety_margin_mb ?? 512) || 0);
  const usable = hardwareDevices(hardware)
    .map(freeMemoryMb)
    .filter((value) => value != null)
    .map((value) => Math.max(0, value - safety));
  return usable.length >= 2 && Math.max(...usable) < required && usable.reduce((sum, value) => sum + value, 0) >= required;
}
