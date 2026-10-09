import { normalizeHardwareSnapshot } from "./hardwareSnapshot.js";

export const advisorProfileSlots = [
  { key: "fast", backendProfile: "fast", label: "Fast", goal: "Prioritizes low latency and quick responses." },
  { key: "balanced", backendProfile: "balanced", label: "Balanced", goal: "Balances quality, speed, and hardware fit." },
  { key: "maximumQuality", backendProfile: "maximum_quality", label: "Maximum Quality", goal: "Prioritizes quality and can accept heavier placement." },
];

export const ADVISOR_REQUEST_TIMEOUT_MS = 10000;

function advisorNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

export function advisorModelId(item) {
  return String(item?.modelId || item?.id || item?.name || "");
}

function advisorEvidenceRank(profile) {
  const evidence = profile?.benchmarkEvidence || profile?.benchmark || profile?.evidence?.benchmark || profile?.evidence || {};
  if (evidence.exact === true || evidence.status === "exact" || evidence.basis === "measured-exact") return 2;
  if (evidence.basis === "catalog-estimate" || profile?.evidence?.estimated || profile?.estimated) return 1;
  return 0;
}

function advisorProfileScore(profile) {
  return advisorNumber(profile?.profileScore ?? profile?.profile_score ?? profile?.score, -Infinity);
}

function advisorBlocked(profile) {
  return profile?.status === "blocked"
    || (Array.isArray(profile?.blockers) && profile.blockers.length > 0)
    || (Array.isArray(profile?.blockedReasons) && profile.blockedReasons.length > 0)
    || profile?.raw?.status === "blocked";
}

function advisorDecodeTps(profile) {
  const metrics = profile?.benchmarkEvidence?.metrics || profile?.benchmark?.metrics || profile?.metrics || {};
  const value = metrics.decodeTokensPerSecond ?? metrics.tokensPerSecond ?? metrics.tps ?? metrics.throughputTokensPerSecond;
  return advisorNumber(value?.p50 ?? value, -Infinity);
}

function advisorTtft(profile) {
  const metrics = profile?.benchmarkEvidence?.metrics || profile?.benchmark?.metrics || profile?.metrics || {};
  const value = metrics.ttftMs ?? metrics.timeToFirstTokenMs ?? metrics.ttft;
  return advisorNumber(value?.p50 ?? value, Infinity);
}

export function withAdvisorTimeout(requestFactory, timeoutMs = ADVISOR_REQUEST_TIMEOUT_MS, onTimeout) {
  return new Promise((resolve, reject) => {
    let settled = false;
    let timer;
    const finish = (callback, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      callback(value);
    };
    timer = setTimeout(() => {
      onTimeout?.();
      const error = new Error("Advisor request timed out after " + Math.round(timeoutMs / 1000) + "s.");
      error.name = "TimeoutError";
      finish(reject, error);
    }, timeoutMs);
    Promise.resolve()
      .then(requestFactory)
      .then((value) => finish(resolve, value), (error) => finish(reject, error));
  });
}

export function normalizeHuggingFaceSearchInput(value) {
  const input = String(value || "").trim();
  if (!input) return "";
  try {
    const candidate = /^https?:\/\//i.test(input) ? new URL(input) : null;
    if (candidate && /(^|\.)huggingface\.co$/i.test(candidate.hostname)) {
      const segments = candidate.pathname.split("/").filter(Boolean);
      return segments.slice(0, 2).join("/").replace(/\.git$/i, "");
    }
  } catch {
    // Keep ordinary search terms intact when the input only resembles a URL.
  }
  return input.replace(/^huggingface\.co\//i, "").replace(/\.git$/i, "");
}

export function advisorStateForInputs({
  catalogLoading = false,
  hardwareProbeStatus = "idle",
  hardwareError = "",
  hasHardware = false,
  hardwareSnapshot = normalizeHardwareSnapshot(null),
  catalogCount = 0,
  candidateCount = 0,
}) {
  if (catalogLoading) return { status: "catalog-loading", reason: "The local model catalog is still loading." };
  if (hardwareProbeStatus === "error") {
    return { status: "hardware-error", reason: hardwareError || "GPU detection failed, so placement is unproven." };
  }
  if (!hasHardware || !hardwareSnapshot.received) {
    return { status: "hardware-loading", reason: "Waiting for a hardware snapshot before requesting recommendations." };
  }
  if (hardwareSnapshot.blocked) {
    return {
      status: "hardware-blocked",
      reason: "Hardware snapshot received, but deployment is blocked.",
      hardwareReasons: hardwareSnapshot.blockedReasons,
      hardwareRecommendations: hardwareSnapshot.recommendations,
      hardwareChecks: hardwareSnapshot.checkMessages,
    };
  }
  if (!catalogCount) return { status: "catalog-empty", reason: "The hardware snapshot is ready, but the local model catalog is empty." };
  if (!candidateCount) return { status: "no-deployable-candidates", reason: "No deployable, unblocked catalog candidates are available." };
  return null;
}

export function shortlistAdvisorModels(items, limit = 12) {
  return (Array.isArray(items) ? items : [])
    .filter((item) => {
      const blockedReasons = Array.isArray(item?.blockedReasons) ? item.blockedReasons : [];
      return item?.deployable === true && item?.apiOnly !== true && blockedReasons.length === 0 && advisorModelId(item);
    })
    .sort((a, b) => (
      advisorNumber(b.fitScore, -Infinity) - advisorNumber(a.fitScore, -Infinity)
      || advisorNumber(b.downloads, 0) - advisorNumber(a.downloads, 0)
      || advisorNumber(b.likes, 0) - advisorNumber(a.likes, 0)
      || advisorModelId(a).localeCompare(advisorModelId(b))
    ))
    .slice(0, Math.max(0, Math.min(12, Number(limit) || 12)));
}

export function selectAdvisorWinner(candidates, profileKey = "balanced") {
  return (Array.isArray(candidates) ? candidates : [])
    .filter((candidate) => candidate?.profile)
    .sort((a, b) => {
      const blockedDifference = Number(advisorBlocked(a.profile)) - Number(advisorBlocked(b.profile));
      if (blockedDifference) return blockedDifference;
      const evidenceDifference = advisorEvidenceRank(b.profile) - advisorEvidenceRank(a.profile);
      if (evidenceDifference) return evidenceDifference;
      const scoreDifference = advisorProfileScore(b.profile) - advisorProfileScore(a.profile);
      if (scoreDifference) return scoreDifference;
      if (profileKey === "fast") {
        const ttftDifference = advisorTtft(a.profile) - advisorTtft(b.profile);
        if (ttftDifference) return ttftDifference;
        const tpsDifference = advisorDecodeTps(b.profile) - advisorDecodeTps(a.profile);
        if (tpsDifference) return tpsDifference;
      }
      return advisorModelId(a.item).localeCompare(advisorModelId(b.item));
    })[0] || null;
}

export function advisorProfileFromPayload(payload, slotKey) {
  const profiles = payload?.profiles || payload?.results || payload?.recommendations || payload?.data?.profiles || payload || {};
  const aliases = {
    fast: ["fast", "responsive", "speed"],
    balanced: ["balanced", "default"],
    maximumQuality: ["maximumQuality", "maximum_quality", "maximum-quality", "quality"],
  }[slotKey] || [slotKey];
  for (const key of aliases) {
    if (profiles?.[key] && typeof profiles[key] === "object") return profiles[key];
  }
  return null;
}

function advisorArray(value) {
  return Array.isArray(value) ? value.filter(Boolean).map(String) : [];
}

function advisorMetricValue(metrics, keys, fallback = null) {
  for (const key of keys) {
    const raw = metrics?.[key];
    const value = raw?.p50 ?? raw?.median ?? raw?.value ?? raw;
    if (Number.isFinite(Number(value))) return Number(value);
  }
  return fallback;
}

export function normalizeAdvisorProfile(profile, item, slot, settings, hardwareSnapshot) {
  const recommendation = profile?.recommendation || profile?.planSeed || profile?.plan || {};
  const placement = profile?.placement || profile?.gpuPlacement || profile?.gpu_placement || {};
  const evidence = profile?.benchmarkEvidence || profile?.benchmark || profile?.evidence?.benchmark || {};
  const metrics = evidence?.metrics || profile?.metrics || {};
  const exact = evidence.exact === true || evidence.status === "exact" || evidence.basis === "measured-exact";
  const estimated = !exact && (evidence.basis === "catalog-estimate" || profile?.evidence?.estimated || item?.vramEstimateGb);
  const blockers = advisorArray(profile?.blockers || profile?.blockedReasons || profile?.blockerReasons);
  if (!hardwareSnapshot && !exact) blockers.push("Hardware capacity is unavailable; placement is unproven.");
  const multiGpu = recommendation.multiGpu === true || placement.mode === "multi-gpu" || placement.mode === "multi_gpu";
  if (multiGpu && settings?.allowMultiGpu === false) blockers.push("Multi-GPU placement is disabled in Model Settings.");
  const deviceIds = placement.deviceIds || placement.device_ids || placement.gpuDeviceIds || placement.gpu_device_ids || placement.devices || [];
  return {
    item,
    slot,
    raw: profile,
    recommendation,
    planSeed: profile?.planSeed || recommendation,
    placement,
    evidence,
    evidenceLabel: exact ? "Measured" : estimated ? "Estimated" : "Unverified",
    exact,
    blockers: [...new Set(blockers)],
    warnings: advisorArray(profile?.warnings),
    modelRef: recommendation.modelRef || recommendation.model_ref || advisorModelId(item),
    protocolId: recommendation.protocolId || recommendation.protocol_id || item?.recommendedProtocol || item?.runtimeOptions?.[0]?.protocolId || "",
    contextWindow: recommendation.contextWindow || recommendation.context_window || item?.contextWindow || null,
    toolCallParser: recommendation.toolCallParser || recommendation.tool_call_parser || item?.toolCallParserHint || "",
    placementMode: placement.mode || (multiGpu ? "multi-gpu" : "single-gpu"),
    deviceIds: Array.isArray(deviceIds) ? deviceIds.map(String) : [],
    profileScore: advisorProfileScore(profile),
    measuredTps: exact ? advisorMetricValue(metrics, ["decodeTokensPerSecond", "tokensPerSecond", "tps", "throughputTokensPerSecond"]) : null,
    measuredTtft: exact ? advisorMetricValue(metrics, ["ttftMs", "timeToFirstTokenMs", "ttft"]) : null,
  };
}
