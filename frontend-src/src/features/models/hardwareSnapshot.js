

export function hardwarePlacementCapacity(hardware) {
  const detected = hardware?.detectedHardware || hardware?.detected_hardware || hardware || {};
  const profile = hardware?.capabilityProfile || hardware?.capability_profile || {};
  const detectedGpus = Array.isArray(detected?.gpus) ? detected.gpus : [];
  const profileDevices = Array.isArray(profile?.devices) ? profile.devices : [];
  const gpus = detectedGpus.length ? detectedGpus : profileDevices;
  const capacities = gpus
    .map((gpu, index) => {
      const staticFacts = gpu?.static && typeof gpu.static === "object" ? gpu.static : gpu;
      const volatileFacts = gpu?.volatile && typeof gpu.volatile === "object" ? gpu.volatile : gpu;
      const memoryMb = staticFacts?.memoryTotalMb ?? staticFacts?.memory_total_mb;
      const memoryGb = staticFacts?.memoryGb ?? staticFacts?.memory_gb;
      const freeMb = volatileFacts?.memoryFreeMb ?? volatileFacts?.memory_free_mb;
      const freeGb = volatileFacts?.memoryFreeGb ?? volatileFacts?.memory_free_gb;
      const usedMb = volatileFacts?.memoryUsedMb ?? volatileFacts?.memory_used_mb;
      const total = memoryMb != null ? Number(memoryMb) / 1024 : Number(memoryGb);
      let free = freeMb != null ? Number(freeMb) / 1024 : Number(freeGb);
      if (!Number.isFinite(free) && Number.isFinite(total) && usedMb != null) {
        free = Math.max(0, total - (Number(usedMb) / 1024));
      }
      const safeFree = Number.isFinite(free) && Number.isFinite(total)
        ? Math.max(0, free - Math.max(0.5, total * 0.10))
        : null;
      return {
        index,
        name: staticFacts?.name || staticFacts?.model || "GPU " + index,
        memoryGb: total,
        freeGb: Number.isFinite(free) ? free : null,
        safeFreeGb: Number.isFinite(safeFree) ? safeFree : null,
      };
    })
    .filter((gpu) => Number.isFinite(gpu.memoryGb) && gpu.memoryGb > 0);
  const safeValues = capacities.map((gpu) => gpu.safeFreeGb);
  const hasLiveFree = capacities.length > 0 && safeValues.every((value) => Number.isFinite(value));
  const names = new Set(capacities.map((gpu) => String(gpu.name || "").trim().toLowerCase()));
  const totals = capacities.map((gpu) => gpu.memoryGb);
  const matchingGpuSet = capacities.length > 1
    && names.size === 1
    && !names.has("")
    && Math.max(...totals) - Math.min(...totals) <= Math.max(0.25, Math.min(...totals) * 0.02);
  return {
    gpus: capacities,
    largestSingleGpuGb: capacities.reduce((largest, gpu) => Math.max(largest, gpu.memoryGb), 0) || null,
    aggregateVramGb: capacities.reduce((total, gpu) => total + gpu.memoryGb, 0) || null,
    largestSafeFreeGpuGb: hasLiveFree ? capacities.reduce((largest, gpu) => Math.max(largest, gpu.safeFreeGb), 0) : null,
    aggregateSafeFreeVramGb: hasLiveFree ? capacities.reduce((total, gpu) => total + gpu.safeFreeGb, 0) : null,
    hasLiveFree,
    matchingGpuSet,
  };
}

export function shouldProbeHardware(view, hasHardware, attempt, refreshToken) {
  return ["discover", "models"].includes(view) && !hasHardware && attempt !== refreshToken;
}

function hardwareStrings(value) {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry) => {
    if (typeof entry === "string") return [entry];
    if (!entry || typeof entry !== "object") return [];
    return [entry.message, entry.detail, entry.reason, entry.text]
      .filter((text) => typeof text === "string" && text.trim())
      .map((text) => text.trim());
  });
}

export function normalizeHardwareSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== "object") {
    return {
      received: false,
      status: "missing",
      blocked: false,
      detectedHardware: null,
      capabilityProfile: null,
      blockedReasons: [],
      recommendations: [],
      checkMessages: [],
    };
  }
  const rawStatus = String(snapshot.status || "").toLowerCase();
  const checks = Array.isArray(snapshot.checks) ? snapshot.checks : [];
  const checkMessages = hardwareStrings(checks);
  const blockedReasons = [...new Set([
    ...hardwareStrings(snapshot.blockedReasons),
    ...hardwareStrings(snapshot.blocked_reasons),
    ...checks.flatMap((check) => {
      if (!check || typeof check !== "object") return [];
      const checkStatus = String(check.status || "").toLowerCase();
      return ["blocked", "failed", "error"].includes(checkStatus)
        ? hardwareStrings([check])
        : [];
    }),
  ])];
  const recommendations = [...new Set([
    ...hardwareStrings(snapshot.recommendations),
    ...hardwareStrings(snapshot.nextActions),
    ...hardwareStrings(snapshot.next_actions),
  ])];
  const blocked = snapshot.ok === false || rawStatus === "blocked" || blockedReasons.length > 0;
  return {
    received: true,
    status: blocked ? "blocked" : rawStatus || "ready",
    blocked,
    detectedHardware: snapshot.detectedHardware || snapshot.detected_hardware || {},
    capabilityProfile: snapshot.capabilityProfile || snapshot.capability_profile || null,
    generatedAt: snapshot.generatedAt || snapshot.generated_at || null,
    blockedReasons,
    recommendations,
    checkMessages,
    raw: snapshot,
  };
}

export function systemHardwareSummary(hardware) {
  const snapshot = normalizeHardwareSnapshot(hardware);
  const cpu = snapshot.capabilityProfile?.cpu || {};
  const detected = snapshot.detectedHardware || {};
  const gpus = Array.isArray(detected.gpus) ? detected.gpus : [];
  return {
    processor: String(cpu.processor || detected.processor || detected.cpu || "Unknown CPU"),
    logicalCores: Number(cpu.logicalCores ?? cpu.logical_cores ?? detected.logicalCores ?? detected.logical_cores) || null,
    memoryTotalGb: Number.isFinite(Number(cpu.memoryTotalMb ?? cpu.memory_total_mb))
      ? Number(cpu.memoryTotalMb ?? cpu.memory_total_mb) / 1024
      : null,
    memoryAvailableGb: Number.isFinite(Number(cpu.memoryAvailableMb ?? cpu.memory_available_mb))
      ? Number(cpu.memoryAvailableMb ?? cpu.memory_available_mb) / 1024
      : null,
    gpus,
  };
}

export function systemMemoryCapacity(hardware) {
  const snapshot = normalizeHardwareSnapshot(hardware);
  const detected = snapshot.detectedHardware || {};
  const profileCpu = snapshot.capabilityProfile?.cpu || {};
  const host = detected.hostMemory || detected.host_memory || detected;
  const totalMb = profileCpu.memoryTotalMb ?? profileCpu.memory_total_mb ?? host.memoryTotalMb ?? host.totalMb ?? host.total_mb;
  const availableMb = profileCpu.memoryAvailableMb ?? profileCpu.memory_available_mb ?? host.memoryAvailableMb ?? host.availableMb ?? host.available_mb;
  const usedMb = profileCpu.memoryUsedMb ?? profileCpu.memory_used_mb ?? host.memoryUsedMb ?? host.usedMb ?? host.used_mb;
  const totalGb = Number.isFinite(Number(totalMb)) ? Number(totalMb) / 1024 : null;
  let availableGb = Number.isFinite(Number(availableMb)) ? Number(availableMb) / 1024 : null;
  if (availableGb == null && totalGb != null && Number.isFinite(Number(usedMb))) {
    availableGb = Math.max(0, totalGb - (Number(usedMb) / 1024));
  }
  return {
    totalGb,
    availableGb,
    safeAvailableGb: availableGb == null ? null : Math.max(0, availableGb - 2),
    headroomGb: 2,
  };
}
