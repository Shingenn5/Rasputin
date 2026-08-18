import React, { useState, useMemo, useEffect, useRef } from "react";
import {
  Activity,
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Cloud,
  Cpu,
  Database,
  Download,
  ExternalLink,
  Gauge,
  HardDrive,
  KeyRound,
  Layers,
  MonitorSpeaker,
  Package,
  Play,
  Power,
  RefreshCw,
  Search,
  Server,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Trash2,
  Users,
  Wrench,
  Zap,
} from "lucide-react";
import {
  discoveredModelIds,
  displayModelName,
  displayModelSecondary,
  isModelHealthy,
  labelize,
  modelMismatchLine,
  runtimeStatus,
} from "../../lib/display.js";
import { actionRegistry, useReliableAction } from "../../lib/actionRegistry.js";
import { api } from "../../api/client.js";
import { useSettingsStore } from "../settings/settingsStore.js";
import { SkeletonList } from "../../components/Skeleton.jsx";
import { Button } from "../../components/Button.jsx";
import { Button as UIButton } from "@/components/ui/button.jsx";
import { Badge } from "@/components/ui/badge.jsx";
import { Card } from "@/components/ui/card.jsx";

/* ── Tab config ── */
const modelsTabs = [
  { id: "library",    label: "Library",     icon: BookOpen },
  { id: "installed",  label: "Installed",   icon: Package },
  { id: "running",    label: "Running",     icon: Activity },
  { id: "settings",   label: "Settings",    icon: Settings },
];


/* ── Guided advisor helpers ── */
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

function advisorModelId(item) {
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

export function hardwarePlacementCapacity(hardware) {
  const detected = hardware?.detectedHardware || hardware?.detected_hardware || hardware || {};
  const gpus = Array.isArray(detected?.gpus) ? detected.gpus : [];
  const capacities = gpus
    .map((gpu, index) => {
      const memoryMb = gpu?.memoryTotalMb ?? gpu?.memory_total_mb;
      const memoryGb = gpu?.memoryGb ?? gpu?.memory_gb;
      return {
        index,
        name: gpu?.name || gpu?.model || "GPU " + index,
        memoryGb: memoryMb != null ? Number(memoryMb) / 1024 : Number(memoryGb),
      };
    })
    .filter((gpu) => Number.isFinite(gpu.memoryGb) && gpu.memoryGb > 0);
  return {
    gpus: capacities,
    largestSingleGpuGb: capacities.reduce((largest, gpu) => Math.max(largest, gpu.memoryGb), 0) || null,
    aggregateVramGb: capacities.reduce((total, gpu) => total + gpu.memoryGb, 0) || null,
  };
}

export function shouldProbeHardware(view, hasHardware, attempt, refreshToken) {
  return view === "models" && !hasHardware && attempt !== refreshToken;
}

export function catalogPlacementAssessment(item, hardware, measuredEvidence = null) {
  const capacity = hardwarePlacementCapacity(hardware);
  const estimate = Number(item?.vramEstimateGb);
  const evidence = measuredEvidence || item?.benchmarkEvidence || item?.benchmark || item?.resourceManifest?.benchmarkEvidence || {};
  const placement = evidence?.placement || {};
  const protocol = String(evidence?.protocolId || evidence?.protocol || evidence?.runtime || item?.recommendedProtocol || "").toLowerCase();
  const exact = evidence?.exact === true || evidence?.status === "exact" || evidence?.basis === "measured-exact";
  const multiGpu = placement?.mode === "multi-gpu" || placement?.mode === "multi_gpu" || evidence?.placementMode === "multi-gpu" || evidence?.placement_mode === "multi-gpu";
  const measuredLayerSharding = exact && multiGpu && (protocol.includes("llama") || protocol.includes("gguf"));
  const largest = capacity.largestSingleGpuGb;
  const hasEstimate = Number.isFinite(estimate) && estimate > 0;
  if (measuredLayerSharding) {
    return {
      kind: "measured-multi-gpu",
      label: "Supported multi-GPU / layer sharding",
      canDeploy: true,
      largestSingleGpuGb: largest,
      aggregateVramGb: capacity.aggregateVramGb,
      reasons: ["Exact measured llama.cpp/GGUF evidence supports this device set."],
    };
  }
  if (hasEstimate && largest != null && estimate <= largest) {
    return {
      kind: "single-gpu-fit",
      label: "Single-GPU fit",
      canDeploy: true,
      largestSingleGpuGb: largest,
      aggregateVramGb: capacity.aggregateVramGb,
      reasons: ["Estimated " + estimate + " GB fits on the largest single GPU (" + largest.toFixed(1) + " GB)."],
    };
  }
  const reasons = [];
  if (!capacity.gpus.length) reasons.push("GPU capacity is unavailable, so placement is unproven.");
  else if (!hasEstimate) reasons.push("Model VRAM demand is unknown, so placement is unproven.");
  else if (largest != null && estimate > largest) reasons.push("Estimated " + estimate + " GB exceeds the largest single GPU (" + largest.toFixed(1) + " GB).");
  reasons.push("Combined VRAM is not treated as a vLLM fit without exact measured llama.cpp/GGUF evidence.");
  return {
    kind: "blocked-unproven",
    label: "Blocked / unproven",
    canDeploy: false,
    largestSingleGpuGb: largest,
    aggregateVramGb: capacity.aggregateVramGb,
    reasons,
  };
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

function advisorProfileFromPayload(payload, slotKey) {
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

function normalizeAdvisorProfile(profile, item, slot, settings, hardwareSnapshot) {
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

/* ── Helpers ── */
function contextWindowFor(m) {
  for (const k of ["contextWindow","context_window","maxModelLen","max_model_len"])
    if (Number.isFinite(Number(m?.[k])) && Number(m?.[k]) > 0) return Number(m[k]);
  return 0;
}

function statusColor(st) {
  if (["reachable","healthy","ready","running"].includes(st)) return "var(--ras-safe)";
  if (["unhealthy","error","failed","blocked"].includes(st)) return "var(--ras-danger)";
  if (["stopped","unknown","warning"].includes(st)) return "var(--ras-warn)";
  return "var(--cc-muted)";
}

function trustedDownloadProgress(download) {
  const downloaded = Number(download?.downloadedBytes);
  const total = Number(download?.totalBytes);
  const percent = Number(download?.progress);
  return Boolean(
    download?.progressTrusted === true
    && Number.isFinite(downloaded)
    && Number.isFinite(total)
    && total > 0
    && downloaded >= 0
    && downloaded <= total
    && Number.isFinite(percent)
    && percent >= 0
    && percent <= 100
  );
}

function ModelDownloadProgress({ download }) {
  const hasTrustedProgress = trustedDownloadProgress(download);
  const downloaded = Number(download?.downloadedBytes) || 0;
  const total = Number(download?.totalBytes) || 0;
  const percent = Number(download?.progress);
  return (
    <div className="w2-card" data-testid="model-download-progress" style={{ padding: "8px 12px", gap: "4px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8125rem" }}>
        <strong>{download?.modelId}</strong>
        <span style={{ color: "var(--cc-muted)" }}>{download?.status}</span>
      </div>
      {hasTrustedProgress && (
        <div
          role="progressbar"
          aria-label={`Download progress for ${download?.modelId}`}
          aria-valuemin="0"
          aria-valuemax="100"
          aria-valuenow={percent}
          style={{ height: "4px", background: "var(--cc-border)", borderRadius: "2px", overflow: "hidden" }}
        >
          <div style={{ height: "100%", width: `${percent}%`, background: "var(--ras-safe)", transition: "width 0.5s ease" }} />
        </div>
      )}
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.6875rem", color: "var(--cc-muted)" }}>
        <span>{(downloaded / 1024 / 1024 / 1024).toFixed(2)} GB / {total > 0 ? `${(total / 1024 / 1024 / 1024).toFixed(2)} GB` : "size unavailable"}</span>
        <span>{hasTrustedProgress ? `${percent.toFixed(1)}%` : "percentage unavailable"}</span>
      </div>
    </div>
  );
}

function CompatibilitySummary({ model }) {
  const profile = model?.compatibility;
  if (!profile) {
    return (
      <div data-testid="model-compatibility" className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
        Not certified yet. Run Test to verify chat, context retention, and tool calling automatically.
      </div>
    );
  }
  const legacyFallback = profile.status === "incompatible";
  const status = legacyFallback ? "limited" : (profile.status || "unknown");
  const tier = legacyFallback ? "basic-inference" : (profile.tier || "unknown");
  const modes = legacyFallback ? ["chat"] : (Array.isArray(profile.supportedModes) ? profile.supportedModes : []);
  const issues = Array.isArray(profile.issues) ? profile.issues : [];
  const tone = status === "certified" ? "text-emerald-400" : status === "incompatible" ? "text-red-400" : "text-amber-400";
  return (
    <div data-testid="model-compatibility" className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <strong className={tone}>{labelize(status)}</strong>
        <span className="text-muted-foreground">Tier: {labelize(tier)}</span>
        <span className="text-muted-foreground">Context profile: {labelize(legacyFallback ? "minimal" : (profile.promptProfile || "standard"))}</span>
      </div>
      <div className="mt-1 text-muted-foreground">
        Modes: {modes.length ? modes.map(labelize).join(", ") : "None"}
      </div>
      {issues[0] && <div className="mt-1 text-amber-400">{issues[0]}</div>}
    </div>
  );
}

/* ═══════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════ */
export function ModelsView({
  view,
  models,
  selectedModelObject,
  selectedModel,
  setSelectedModel,
  testingMode,
  updateTestingMode,
  runModelAction,
  loadModels,
  scanGguf,
  registerLocalModel,
  registerApiModel,
  modelProviders,
  modelCatalog,
  modelCatalogLoading,
  modelCatalogError,
  loadModelCatalog,
  prepareCatalogModelForWarsat,
  warsat,
  warsatHardware,
  warsatRuntimes,
  warsatPlan,
  security,
  openWarsat,
}) {
  const [activeTab, setActiveTab] = useState("library");
  const [uiState, setUiState] = useState({ status: "idle", message: "" });
  const executeAction = useReliableAction("ModelsView");

  /* catalog state */
  const [catalogSearch, setCatalogSearch] = useState("");
  const [catalogPurpose, setCatalogPurpose] = useState("all");
  const [catalogRuntime, setCatalogRuntime] = useState("all");
  const [catalogFit, setCatalogFit] = useState("all");
  const [searchMode, setSearchMode] = useState("catalog");
  const [hfQuery, setHfQuery] = useState("");
  const hfSearchInputRef = useRef(null);
  const [hfResults, setHfResults] = useState([]);
  const [hfLoading, setHfLoading] = useState(false);
  const [hfError, setHfError] = useState("");
  const [hfSort, setHfSort] = useState("popular");
  const [vramMinGb, setVramMinGb] = useState("");
  const [vramMaxGb, setVramMaxGb] = useState("");
  const [activeDownloads, setActiveDownloads] = useState([]);
  const [pageSize, setPageSize] = useState(20);
  const [page, setPage] = useState(1);
  const modelSettings = useSettingsStore((state) => state.models || {});
  const [showAllModels, setShowAllModels] = useState(false);
  const [advisorRefreshToken, setAdvisorRefreshToken] = useState(0);
  const [hardwareRefreshToken, setHardwareRefreshToken] = useState(0);
  const [localHardware, setLocalHardware] = useState(null);
  const [hardwareProbeState, setHardwareProbeState] = useState({ status: warsatHardware ? "ready" : "idle", error: "" });
  const [advisorState, setAdvisorState] = useState({ status: "idle", profiles: {}, errors: [] });
  const hardwareProbeAttempt = useRef(-1);


  // Back to page 1 whenever the visible set changes shape.
  useEffect(() => {
    setPage(1);
  }, [catalogSearch, catalogPurpose, catalogRuntime, catalogFit, searchMode, hfQuery, pageSize, vramMinGb, vramMaxGb]);

  const [downloadRefreshToken, setDownloadRefreshToken] = useState(0);

  useEffect(() => {
    if (view !== "models") return undefined;
    let disposed = false;
    let timer;
    const pollDownloads = async () => {
      try {
        const d = await api("/api/models/downloads/active");
        const active = Array.isArray(d) ? d : [];
        if (disposed) return;
        setActiveDownloads(active);
        // No background interval is kept when there is nothing to monitor.
        // Once a download exists, use a measured 3s cadence instead of a 1s
        // request storm, and stop again as soon as the list is empty.
        if (active.length > 0) timer = setTimeout(pollDownloads, 3000);
      } catch (e) {
        if (!disposed) timer = setTimeout(pollDownloads, 5000);
      }
    };
    pollDownloads();
    return () => {
      disposed = true;
      clearTimeout(timer);
    };
  }, [view, downloadRefreshToken]);

  /* derived */
  const catalogItems = modelCatalog?.items || [];
  const catalogCategories = modelCatalog?.categories || [];
  const catalogRuntimes = modelCatalog?.runtimes || [];
  const activeModel = selectedModelObject || models?.[0] || null;
  const healthy = isModelHealthy(activeModel);
  const status = runtimeStatus(activeModel);
  const effectiveHardware = warsatHardware || localHardware;
  const gpuCapacity = useMemo(() => hardwarePlacementCapacity(effectiveHardware), [effectiveHardware]);
  const totalVramGb = gpuCapacity.aggregateVramGb || 0;

  useEffect(() => {
    if (warsatHardware) {
      setHardwareProbeState({ status: "ready", error: "" });
      return undefined;
    }
    if (!shouldProbeHardware(view, Boolean(warsatHardware || localHardware), hardwareProbeAttempt.current, hardwareRefreshToken)) return undefined;
    hardwareProbeAttempt.current = hardwareRefreshToken;
    const controller = new AbortController();
    let disposed = false;
    setHardwareProbeState({ status: "loading", error: "" });
    withAdvisorTimeout(
      () => api("/api/warsat/hardware", { signal: controller.signal }),
      ADVISOR_REQUEST_TIMEOUT_MS,
      () => controller.abort("timeout"),
    ).then((hardware) => {
      if (disposed) return;
      setLocalHardware(hardware);
      setHardwareProbeState({ status: "ready", error: "" });
    }).catch((error) => {
      const superseded = controller.signal.aborted && controller.signal.reason === "superseded";
      if (disposed || superseded) return;
      setHardwareProbeState({ status: "error", error: error?.message || "Hardware detection failed." });
    });
    return () => {
      disposed = true;
      controller.abort("superseded");
    };
  }, [view, warsatHardware, hardwareRefreshToken]);

  const apiProviders = modelProviders?.length ? modelProviders : [
    { id: "openai", name: "OpenAI", defaultKeyEnv: "OPENAI_API_KEY" },
    { id: "anthropic", name: "Anthropic", defaultKeyEnv: "ANTHROPIC_API_KEY" },
    { id: "gemini", name: "Google Gemini", defaultKeyEnv: "GEMINI_API_KEY" },
    { id: "openai-compatible-remote", name: "Other OpenAI-compatible", defaultKeyEnv: "" },
  ];
  const remoteBlocked = security?.privacyLock || !security?.allowRemoteModels;

  const registeredModels = useMemo(() => (models || []).filter(m => (
    m.key !== "dry-run" && !["mock", "hash-vector"].includes(m.provider)
  )), [models]);
  const installedModels = registeredModels;
  const reachableModels = useMemo(() => registeredModels.filter(m => runtimeStatus(m) === "reachable"), [registeredModels]);
  const runningModels = useMemo(() => registeredModels.filter(m => (
    m.managed && String(m.container_status || "").toLowerCase() === "running"
  )), [registeredModels]);

  const filteredCatalog = useMemo(() => {
    const q = catalogSearch.trim().toLowerCase();
    return catalogItems.filter(item => {
      const text = [item.name, item.id, item.modelId, item.provider, item.purpose, ...(item.capabilities || [])].join(" ").toLowerCase();
      if (q && !text.includes(q)) return false;
      if (catalogPurpose !== "all" && item.purpose !== catalogPurpose) return false;
      if (catalogRuntime === "deployable" && !item.deployable && !item.containerBacked) return false;
      if (catalogRuntime !== "all" && catalogRuntime !== "deployable" && !(item.runtimeOptions || []).some(o => o.protocolId === catalogRuntime)) return false;
      return true;
    });
  }, [catalogItems, catalogSearch, catalogPurpose, catalogRuntime]);


  const advisorCandidates = useMemo(() => shortlistAdvisorModels(catalogItems), [catalogItems]);

  useEffect(() => {
    let disposed = false;
    if (view !== "models") return () => { disposed = true; };
    const hardwareUnavailable = hardwareProbeState.status === "error";
    if (!catalogItems.length || (!effectiveHardware && !hardwareUnavailable)) {
      setAdvisorState((previous) => previous.status === "waiting"
        ? previous
        : { status: "waiting", profiles: {}, errors: [], completed: 0, total: advisorCandidates.length });
      return () => { disposed = true; };
    }
    if (!advisorCandidates.length) {
      setAdvisorState((previous) => previous.status === "ready" ? previous : { status: "ready", profiles: {}, errors: [] });
      return () => { disposed = true; };
    }

    setAdvisorState({ status: "loading", profiles: {}, errors: [], completed: 0, total: advisorCandidates.length, timedOut: 0 });
    const maxContext = Number(modelSettings?.maxContextTokens);
    const contextWindow = Number.isFinite(maxContext) && maxContext > 0 ? maxContext : undefined;
    const controller = new AbortController();
    const profiles = {};
    const errors = [];
    let completed = 0;
    const summarize = (final = false) => {
      if (disposed) return;
      const winners = {};
      for (const slot of advisorProfileSlots) {
        const winner = selectAdvisorWinner(profiles[slot.key], slot.key);
        if (winner) winners[slot.key] = winner;
      }
      setAdvisorState({
        status: final ? (errors.length === advisorCandidates.length ? "error" : "ready") : "loading",
        profiles: winners,
        errors: [...errors],
        completed,
        total: advisorCandidates.length,
        timedOut: errors.filter((error) => error.includes("timed out")).length,
      });
    };
    const advisorRequest = (item) => {
      const requestController = new AbortController();
      const forwardAbort = () => requestController.abort(controller.signal.reason || "superseded");
      if (controller.signal.aborted) forwardAbort();
      else controller.signal.addEventListener("abort", forwardAbort, { once: true });
      return withAdvisorTimeout(() => api("/api/warsat/advisor/profiles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: requestController.signal,
        body: JSON.stringify({
          model: item,
          hardware: effectiveHardware || {},
          allProfiles: true,
          mission: item.purpose === "coding" ? "coding" : item.purpose === "research" ? "research" : "chat",
          protocolId: item.recommendedProtocol || item.runtimeOptions?.[0]?.protocolId || "",
          contextWindow: contextWindow || contextWindowFor(item) || undefined,
          toolCallParser: item.toolCallParserHint || "",
        }),
      }), ADVISOR_REQUEST_TIMEOUT_MS, () => requestController.abort("timeout"))
        .finally(() => controller.signal.removeEventListener("abort", forwardAbort));
    };
    advisorCandidates.forEach((item) => {
      advisorRequest(item)
        .then((result) => {
          for (const slot of advisorProfileSlots) {
            const rawProfile = advisorProfileFromPayload(result, slot.key);
            if (!rawProfile) continue;
            const normalized = normalizeAdvisorProfile(rawProfile, item, slot, modelSettings, effectiveHardware);
            profiles[slot.key] = [...(profiles[slot.key] || []), { item, profile: normalized }];
          }
        })
        .catch((error) => {
          if (disposed || error?.name === "AbortError" && controller.signal.aborted) return;
          errors.push((item.name || advisorModelId(item)) + ": " + (error?.message || "Advisor request failed"));
        })
        .finally(() => {
          if (disposed) return;
          completed += 1;
          summarize(completed === advisorCandidates.length);
        });
    });
    return () => {
      disposed = true;
      controller.abort("superseded");
    };
  }, [
    view,
    catalogItems,
    advisorCandidates,
    effectiveHardware,
    hardwareProbeState.status,
    modelSettings?.maxContextTokens,
    modelSettings?.allowMultiGpu,
    advisorRefreshToken,
  ]);

  /* HF search with debounce */
  useEffect(() => {
    if (searchMode !== "huggingface") return;
    // Neither fetch() nor the backend's own HF call had an upper bound the
    // UI could see, so a slow/dropped connection to huggingface.co left the
    // spinner running forever with no error and no way out. Bound it and
    // abort the previous request when a new one starts, so a stale slow
    // response can't land after a newer, faster one already resolved.
    const controller = new AbortController();
    const abortTimer = setTimeout(() => controller.abort(), 30000);
    const t = setTimeout(async () => {
      setHfLoading(true);
      setHfError("");
      try {
        // Fetch enough results to fill several pages at the chosen size.
        const hasVramRange = vramMinGb !== "" || vramMaxGb !== "";
        const hfLimit = String(hasVramRange ? 500 : Math.min(500, Math.max(100, pageSize * 5)));
        const p = new URLSearchParams({ q: hfQuery, sort: hfSort, limit: hfLimit, fit: "true" });
        if (vramMinGb !== "") p.set("min_vram_gb", vramMinGb);
        if (vramMaxGb !== "") p.set("max_vram_gb", vramMaxGb);
        if (catalogPurpose !== "all") {
          const pm = { chat: "text-generation", coding: "text-generation", vision: "image-to-text", embeddings: "feature-extraction", speech: "automatic-speech-recognition" };
          if (pm[catalogPurpose]) p.set("type", pm[catalogPurpose]);
        }
        const d = await api(`/api/model-catalog/search?${p.toString()}`, { signal: controller.signal });
        setHfResults(d.items || []);
        setHfError(d.error ? `Hugging Face search failed: ${d.error}` : "");
      } catch (err) {
        if (err.name === "AbortError") {
          // Either superseded by a newer search, or the 30s bound tripped.
          if (!controller.signal.reason || controller.signal.reason !== "superseded") {
            setHfResults([]);
            setHfError("Hugging Face search timed out after 30s. Check the container's network access to huggingface.co and try again.");
          }
        } else {
          console.error("HF Search Error:", err);
          setHfResults([]);
          setHfError(`Hugging Face search failed: ${err.message || "unknown error"}`);
        }
      }
      setHfLoading(false);
    }, 500);
    return () => {
      clearTimeout(t);
      clearTimeout(abortTimer);
      controller.abort("superseded");
    };
  }, [hfQuery, hfSort, catalogPurpose, searchMode, pageSize, vramMinGb, vramMaxGb]);

  const displayItems = useMemo(() => {
    const list = searchMode === "huggingface" ? hfResults : filteredCatalog;
    const hasMin = vramMinGb !== "" && Number.isFinite(Number(vramMinGb));
    const hasMax = vramMaxGb !== "" && Number.isFinite(Number(vramMaxGb));
    const minVram = hasMin ? Number(vramMinGb) : 0;
    const maxVram = hasMax ? Number(vramMaxGb) : Infinity;
    return list.filter(item => {
      if (!item.vramEstimateGb) return !hasMin && !hasMax;
      if (item.vramEstimateGb < minVram || item.vramEstimateGb > maxVram) return false;
      return catalogFit !== "fits" || catalogPlacementAssessment(item, effectiveHardware).canDeploy;
    });
  }, [searchMode, hfResults, filteredCatalog, catalogFit, effectiveHardware, vramMinGb, vramMaxGb]);

  const pageCount = Math.max(1, Math.ceil(displayItems.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const pagedItems = useMemo(
    () => displayItems.slice((currentPage - 1) * pageSize, currentPage * pageSize),
    [displayItems, currentPage, pageSize]
  );

  /* reliable actions */
  const handleRefresh = () => executeAction("RefreshRegistry", "system", async () => loadModels?.(), setUiState);
  const handleScanGguf = () => executeAction("ScanGGUF", "system", async () => scanGguf?.(), setUiState);
  const handleLoadCatalog = (remote) => executeAction("LoadCatalog", "system", async () => loadModelCatalog?.(remote), setUiState);
  const openSpecificHuggingFaceModel = () => {
    setShowAllModels(true);
    setSearchMode("huggingface");
    setCatalogPurpose("all");
    setCatalogFit("all");
    setPage(1);
    requestAnimationFrame(() => hfSearchInputRef.current?.focus());
  };
  const handleAdvisorRefresh = () => {
    setAdvisorRefreshToken((value) => value + 1);
    if (!warsatHardware) setHardwareRefreshToken((value) => value + 1);
  };
  const startDownload = async (modelId) => {
    try {
      await postJson("/api/models/download", { modelId });
      setDownloadRefreshToken((value) => value + 1);
      setUiState({ status: "success", message: `Started download of ${modelId}` });
    } catch (e) {
      setUiState({ status: "failed", message: `Failed to start download: ${e.message}` });
    }
  };

  /* stats */
  const totalModels = registeredModels.length;
  const healthyCount = reachableModels.length;

  return (
    <section className={`w2-layout app-view models-view tw ${view === "models" ? "active" : ""}`} id="modelsView" data-app-view="models">
      <div className="fx-rise mx-auto flex w-full min-w-0 max-w-[1500px] flex-col gap-5 p-7">

      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-5">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Models <span className="text-muted-foreground">Center</span></h1>
          <p className="mt-1.5 text-sm text-muted-foreground">Discover, deploy, and manage AI models.</p>
        </div>
        <div className="flex min-w-0 flex-wrap justify-end gap-3">
          {[
            { v: totalModels, l: "Registered", c: "text-foreground" },
            { v: healthyCount, l: "Reachable now", c: "text-primary" },
            { v: runningModels.length, l: "Running containers", c: "text-amber-400" },
            { v: catalogItems.length, l: "Cached locally", c: "text-sky-400" },
          ].map((s) => (
            <div key={s.l} className="glow-card rounded-xl border border-border bg-card px-4 py-2.5 text-center">
              <div className={`text-xl font-bold ${s.c}`}>{s.v}</div>
              <div className="text-[0.66rem] uppercase tracking-wide text-muted-foreground">{s.l}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Tab Bar ── */}
      <div className="flex items-center gap-2 overflow-x-auto" role="tablist" aria-label="Model management areas">
        {modelsTabs.map(t => {
          const Icon = t.icon;
          return (
            <UIButton
              key={t.id}
              id={`models-tab-${t.id}`}
              role="tab"
              aria-selected={activeTab === t.id}
              aria-controls={`models-panel-${t.id}`}
              variant={activeTab === t.id ? "default" : "outline"}
              size="sm"
              type="button"
              onClick={() => setActiveTab(t.id)}
            >
              <Icon size={15} /> {t.label}
            </UIButton>
          );
        })}
        <div className="flex-1" />
        {uiState.status !== "idle" && (
          <Badge variant={uiState.status === "failed" ? "down" : uiState.status === "success" ? "up" : "muted"}>
            {uiState.message}
          </Badge>
        )}
        <UIButton variant="outline" size="sm" type="button" onClick={handleRefresh}>
          <RefreshCw size={15} /> Refresh
        </UIButton>
      </div>

      {/* ── Content ── */}
      <div className="w2-main-grid">
        <div className="w2-column">

          {/* ═══ LIBRARY TAB ═══ */}
          {activeTab === "library" && (
            <div id="models-panel-library" role="tabpanel" aria-labelledby="models-tab-library" className="w2-section" style={{ flex: 1 }}>
              {!showAllModels ? (
                <GuidedRecommendations
                  advisorState={advisorState}
                  advisorCandidateCount={advisorCandidates.length}
                  modelCatalogLoading={modelCatalogLoading}
                  catalogError={modelCatalogError}
                  hardwareReady={Boolean(effectiveHardware)}
                   hardwareProbeState={hardwareProbeState}
                  performancePreference={modelSettings?.performancePreference || "balanced"}
                  automaticBenchmarking={modelSettings?.automaticBenchmarking !== false}
                  onRefresh={handleAdvisorRefresh}
                  onBrowseAll={() => setShowAllModels(true)}
                  onUseSpecificModel={openSpecificHuggingFaceModel}
                  prepareCatalogModelForWarsat={prepareCatalogModelForWarsat}
                />
              ) : (
                <>
                  <div className="mb-3 flex justify-end">
                    <UIButton variant="outline" size="sm" type="button" onClick={() => setShowAllModels(false)}>
                      <Gauge size={14} /> Back to recommendations
                    </UIButton>
                  </div>
              {/* Source toggle */}
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <button className={`w2-button ${searchMode === "catalog" ? "primary" : ""}`} type="button" onClick={() => setSearchMode("catalog")}>
                  <HardDrive size={14} /> Local cache
                </button>
                <button className={`w2-button ${searchMode === "huggingface" ? "primary" : ""}`} type="button" onClick={() => setSearchMode("huggingface")}>
                  <Cloud size={14} /> Hugging Face
                </button>
                <div style={{ flex: 1 }} />
                {searchMode === "catalog" && (
                  <>
                    <button className="w2-button" type="button" onClick={() => handleLoadCatalog(false)}>
                      <RefreshCw size={14} /> Refresh cache
                    </button>
                    <Button primary onClick={() => handleLoadCatalog(true)} loading={modelCatalogLoading} loadingLabel="Refreshing…" icon={<Cloud size={14} />}>
                      Refresh catalog
                    </Button>
                  </>
                )}
              </div>

              {/* Search + filters */}
              <div className="model-catalog-filters" style={{ display: "flex", flexWrap: "wrap", gap: "8px", alignItems: "center" }}>
                <Search size={16} color="var(--cc-muted)" />
                <input
                  ref={hfSearchInputRef}
                  className="w2-input model-catalog-search"
                  style={{ minWidth: "240px", flex: "1 1 320px" }}
                  aria-label={searchMode === "huggingface" ? "Hugging Face model ID, URL, or search terms" : "Search models"}
                  data-testid="model-specific-hf-input"
                  value={searchMode === "huggingface" ? hfQuery : catalogSearch}
                  onChange={e => searchMode === "huggingface" ? setHfQuery(e.target.value) : setCatalogSearch(e.target.value)}
                  placeholder={searchMode === "huggingface" ? "Paste org/model or a huggingface.co URL" : "Filter locally cached models by name..."}
                />
                {searchMode === "huggingface" && (
                  <span className="w-full text-xs text-muted-foreground" data-testid="model-specific-hf-help">
                    Enter an exact model ID or Hugging Face URL, or use ordinary search terms. Exact matches appear first and still require WarSat review.
                  </span>
                )}
                <select className="w2-input" style={{ width: "140px", flex: "none" }} value={catalogPurpose} onChange={e => setCatalogPurpose(e.target.value)}>
                  <option value="all">All types</option>
                  {catalogCategories.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
                </select>
                {searchMode === "huggingface" && (
                  <select className="w2-input" style={{ width: "130px", flex: "none" }} value={hfSort} onChange={e => setHfSort(e.target.value)}>
                    <option value="popular">Most popular</option>
                    <option value="downloads">Most downloaded</option>
                    <option value="likes">Most liked</option>
                    <option value="trending">Trending</option>
                    <option value="lastModified">Recent</option>
                    <option value="vram_desc">VRAM: largest first</option>
                  </select>
                )}
                {searchMode === "catalog" && (
                  <select className="w2-input" style={{ width: "130px", flex: "none" }} value={catalogRuntime} onChange={e => setCatalogRuntime(e.target.value)}>
                    <option value="deployable">Deployable</option>
                    <option value="all">All Runtimes</option>
                    {catalogRuntimes.map(r => <option key={r.id} value={r.id}>{r.label}</option>)}
                  </select>
                )}
                <select className="w2-input" style={{ width: "130px", flex: "none" }} value={catalogFit} onChange={e => setCatalogFit(e.target.value)}>
                  <option value="all">Any fit</option>
                  <option value="fits">Fits safely</option>
                </select>
              </div>

              <div className="model-vram-filter" data-testid="model-vram-filter">
                <span className="model-vram-filter__capacity" data-testid="model-placement-capacity">
                  Largest single GPU: <strong>{gpuCapacity.largestSingleGpuGb ? gpuCapacity.largestSingleGpuGb.toFixed(1) + " GB" : "unknown"}</strong>
                  {" · "}Optional combined layer-sharding pool: <strong>{totalVramGb > 0 ? totalVramGb.toFixed(1) + " GB" : "unknown"}</strong>
                </span>
                <label>
                  <span>VRAM from</span>
                  <input
                    className="w2-input"
                    aria-label="Minimum VRAM GB"
                    type="number"
                    min="0"
                    step="1"
                    value={vramMinGb}
                    onChange={e => setVramMinGb(e.target.value)}
                    placeholder="Any"
                  />
                </label>
                <label>
                  <span>to</span>
                  <input
                    className="w2-input"
                    aria-label="Maximum VRAM GB"
                    type="number"
                    min="1"
                    step="1"
                    value={vramMaxGb}
                    onChange={e => setVramMaxGb(e.target.value)}
                    placeholder={gpuCapacity.largestSingleGpuGb ? String(Math.max(1, Math.floor(gpuCapacity.largestSingleGpuGb - 2))) : "Any"}
                  />
                </label>
                <button
                  className="w2-button"
                  type="button"
                  disabled={!gpuCapacity.largestSingleGpuGb}
                  onClick={() => {
                    setVramMinGb(totalVramGb >= 24 ? "16" : "");
                    setVramMaxGb(String(Math.max(1, Math.floor((gpuCapacity.largestSingleGpuGb || totalVramGb) - 2))));
                    setHfSort("vram_desc");
                  }}
                >
                  Use my largest GPU
                </button>
                {(vramMinGb !== "" || vramMaxGb !== "") && (
                  <button className="w2-button" type="button" onClick={() => { setVramMinGb(""); setVramMaxGb(""); }}>
                    Clear VRAM range
                  </button>
                )}
              </div>

              {/* Status line */}
              <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
                {searchMode === "catalog"
                  ? `${displayItems.length} locally cached model${displayItems.length === 1 ? "" : "s"}`
                  : hfLoading ? "Searching Hugging Face..." : `${displayItems.length} matching results`}
              </div>

              {searchMode === "huggingface" && hfError && (
                <div style={{ fontSize: "0.8125rem", color: "var(--ras-danger)", backgroundColor: "color-mix(in srgb, var(--ras-danger) 10%, var(--cc-surface))", border: "1px solid var(--ras-danger)", borderRadius: "6px", padding: "8px 12px" }}>
                  {hfError}
                </div>
              )}

              {/* Active Downloads */}
              {activeDownloads.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "8px" }}>
                  {activeDownloads.map(dl => <ModelDownloadProgress key={dl.id} download={dl} />)}
                </div>
              )}

              {/* Model list */}
              {pagedItems.map(item => (
                <CatalogCard key={item.id} item={item} placementFit={catalogPlacementAssessment(item, effectiveHardware)} prepareCatalogModelForWarsat={prepareCatalogModelForWarsat} searchMode={searchMode} startDownload={startDownload} activeDownloads={activeDownloads} />
              ))}

              {/* Pagination */}
              {displayItems.length > 0 && (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "10px", padding: "6px 0" }}>
                  <button className="w2-button" type="button" disabled={currentPage <= 1} onClick={() => setPage(currentPage - 1)} style={{ fontSize: "0.75rem", padding: "4px 12px" }}>
                    Prev
                  </button>
                  <span style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
                    Page {currentPage} of {pageCount} · {displayItems.length} models
                  </span>
                  <button className="w2-button" type="button" disabled={currentPage >= pageCount} onClick={() => setPage(currentPage + 1)} style={{ fontSize: "0.75rem", padding: "4px 12px" }}>
                    Next
                  </button>
                  <select className="w2-input" style={{ width: "110px", flex: "none" }} value={pageSize} onChange={e => setPageSize(Number(e.target.value))}>
                    {[10, 20, 40, 80].map(n => <option key={n} value={n}>{n} / page</option>)}
                  </select>
                </div>
              )}

              {/* Loading skeletons while the catalog/search is in flight and nothing is shown yet */}
              {!displayItems.length && (modelCatalogLoading || hfLoading) && (
                <SkeletonList count={5} />
              )}

              {!displayItems.length && !modelCatalogLoading && !hfLoading && (
                <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>
                  {searchMode === "huggingface" ? "No models found. Try broadening your search or choosing a different category." : "No models match. Try different filters."}
                </div>
              )}
                </>
              )}
            </div>
          )}

          {/* ═══ INSTALLED TAB ═══ */}
          {activeTab === "installed" && (
            <div id="models-panel-installed" role="tabpanel" aria-labelledby="models-tab-installed" className="w2-section" style={{ flex: 1 }}>
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <h2 style={{ margin: 0, fontSize: "1rem" }}>Local Registry</h2>
                <div style={{ flex: 1 }} />
                <button className="w2-button" type="button" onClick={handleScanGguf}><HardDrive size={14} /> Scan GGUF</button>
                <button className="w2-button" type="button" onClick={handleRefresh}><RefreshCw size={14} /> Refresh</button>
              </div>

              {installedModels.map(model => (
                <InstalledCard key={model.key} model={model} allModels={models} runModelAction={runModelAction} executeAction={executeAction} setUiState={setUiState} />
              ))}

              {!installedModels.length && (
                <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>
                  No models registered. Use Library to discover, or Settings to connect endpoints.
                </div>
              )}
            </div>
          )}

          {/* ═══ RUNNING TAB ═══ */}
          {activeTab === "running" && (
            <div id="models-panel-running" role="tabpanel" aria-labelledby="models-tab-running" className="w2-section" style={{ flex: 1 }}>
              <ActiveModelCard
                model={activeModel}
                models={models}
                healthy={healthy}
                status={status}
                runModelAction={runModelAction}
                executeAction={executeAction}
                setUiState={setUiState}
                openWarsat={openWarsat}
              />

              {runningModels.length > 0 && (
                <div className="w2-card">
                  <h3 style={{ margin: 0, fontSize: "0.875rem" }}>Active Deployments ({runningModels.length})</h3>
                  {runningModels.map(m => (
                    <div key={m.key} className="w2-list-item">
                      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                        <Activity size={14} color="var(--ras-safe)" />
                        <div>
                          <strong style={{ fontSize: "0.8125rem" }}>{displayModelName(m, models)}</strong>
                          <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>{m.runtime || m.provider} · {labelize(m.role || "chat")}</div>
                        </div>
                      </div>
                      <span style={{ fontSize: "0.6875rem", color: "var(--ras-safe)", fontWeight: 600 }}>Online</span>
                    </div>
                  ))}
                </div>
              )}

              <InfraStatusCard warsatHardware={warsatHardware} warsatRuntimes={warsatRuntimes} warsat={warsat} />
            </div>
          )}

          {/* ═══ SETTINGS TAB ═══ */}
          {activeTab === "settings" && (
            <div id="models-panel-settings" role="tabpanel" aria-labelledby="models-tab-settings" className="w2-section" style={{ flex: 1 }}>
              {/* Testing Mode */}
              <div className="w2-card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <strong>Testing Mode</strong>
                    <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>Show dry-run model for local smoke tests.</div>
                  </div>
                  <button className={`w2-button ${testingMode ? "primary" : ""}`} type="button" onClick={() => updateTestingMode(!testingMode)}>
                    {testingMode ? "Disable" : "Enable"}
                  </button>
                </div>
              </div>

              {/* Connect Local */}
              <div className="w2-card">
                <h3 style={{ margin: 0, fontSize: "0.875rem" }}><HardDrive size={14} style={{ verticalAlign: "-2px" }} /> Connect Local Endpoint</h3>
                <form onSubmit={registerLocalModel} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                  <input className="w2-input" name="name" placeholder="Display Name" />
                  <input className="w2-input" name="model" placeholder="Model ID *" required />
                  <input className="w2-input" name="baseUrl" placeholder="http://127.0.0.1:1234/v1 *" required />
                  <select className="w2-input" name="role" defaultValue="helper">
                    <option value="main">Main</option><option value="coder">Coder</option><option value="researcher">Researcher</option><option value="helper">Helper</option><option value="planner">Planner</option><option value="summarizer">Summarizer</option>
                  </select>
                  <div style={{ gridColumn: "1 / -1" }}>
                    <button className="w2-button primary" type="submit" style={{ width: "100%" }}><CheckCircle2 size={14} /> Connect Model</button>
                  </div>
                </form>
              </div>

              {/* Connect API */}
              <div className="w2-card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <h3 style={{ margin: 0, fontSize: "0.875rem" }}><Cloud size={14} style={{ verticalAlign: "-2px" }} /> Connect API Provider</h3>
                  <span style={{ fontSize: "0.6875rem", padding: "2px 10px", borderRadius: "999px", background: remoteBlocked ? "color-mix(in srgb, var(--ras-danger) 15%, var(--cc-surface))" : "color-mix(in srgb, var(--ras-safe) 15%, var(--cc-surface))", color: remoteBlocked ? "var(--ras-danger)" : "var(--ras-safe)", fontWeight: 600 }}>
                    {remoteBlocked ? "Remote blocked" : "Remote allowed"}
                  </span>
                </div>
                <form onSubmit={registerApiModel} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                  <select className="w2-input" name="provider" defaultValue="openai">
                    {apiProviders.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                  <input className="w2-input" name="name" placeholder="Display Name" />
                  <input className="w2-input" name="model" placeholder="Model ID *" required />
                  <input className="w2-input" name="baseUrl" placeholder="Base URL (blank = default)" />
                  <select className="w2-input" name="role" defaultValue="helper">
                    <option value="main">Main</option><option value="coder">Coder</option><option value="researcher">Researcher</option><option value="helper">Helper</option>
                  </select>
                  <input className="w2-input" name="apiKey" type="password" autoComplete="off" placeholder="API Key (local secret)" />
                  <div style={{ gridColumn: "1 / -1" }}>
                    <button className="w2-button primary" type="submit" style={{ width: "100%" }}><KeyRound size={14} /> Register API Model</button>
                  </div>
                </form>
              </div>

              {/* Warsat */}
              <div className="w2-card">
                <h3 style={{ margin: 0, fontSize: "0.875rem" }}><Play size={14} style={{ verticalAlign: "-2px" }} /> Warsat Deployment</h3>
                <p style={{ fontSize: "0.75rem", color: "var(--cc-muted)", margin: 0 }}>Use Warsat to deploy local model endpoints via Docker.</p>
                <button className="w2-button primary" type="button" onClick={openWarsat} style={{ alignSelf: "flex-start" }}><Play size={14} /> Open Warsat</button>
              </div>

              {/* Full registry list */}
              <div className="w2-card">
                <h3 style={{ margin: 0, fontSize: "0.875rem" }}><SlidersHorizontal size={14} style={{ verticalAlign: "-2px" }} /> Full Registry</h3>
                {(models || []).map(m => (
                  <div key={m.key} className="w2-list-item" style={{ cursor: "default" }}>
                    <div>
                      <strong style={{ fontSize: "0.8125rem" }}>{displayModelName(m, models)}</strong>
                      <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>{labelize(m.role || "chat")} · {m.runtime || m.provider || "local"} · {runtimeStatus(m)}</div>
                    </div>
                    <span style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>{m.key}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>

        {/* ── Right Column (context) ── */}
        <div className="w2-column">
          <RightPanel
            activeTab={activeTab}
            activeModel={activeModel}
            models={models}
            healthy={healthy}
            status={status}
            warsatHardware={warsatHardware}
          />
        </div>
      </div>
      </div>
    </section>
  );
}



function AdvisorRecommendationCard({ slot, winner, prepareCatalogModelForWarsat, primary = false }) {
  const item = winner?.item;
  const profile = winner?.profile;
  const blockers = profile?.blockers || [];
  const blocked = !profile || blockers.length > 0 || profile?.raw?.status === "blocked";
  const modelName = item?.name || profile?.modelRef || "No model selected";
  const runtimeOption = item?.runtimeOptions?.find((option) => option?.protocolId === profile?.protocolId);
  const runtimeLabel = runtimeOption?.label || item?.runtime || "Warsat runtime";
  const deviceLabel = profile
    ? (profile.placement?.label || profile.placementMode || "Hardware placement")
      + (profile.deviceIds?.length ? " (" + profile.deviceIds.join(", ") + ")" : "")
    : "Waiting for advisor";
  const contextLabel = profile?.contextWindow ? Number(profile.contextWindow).toLocaleString() + " tokens" : "Automatic/default";
  const why = blocked
    ? "This profile is shown for transparency but cannot be deployed until its blockers are resolved."
    : profile.evidenceLabel === "Measured"
      ? "Fresh measured evidence supports this model and runtime on the available hardware."
      : profile.evidenceLabel === "Estimated"
        ? "This is a catalog-based fit estimate; benchmark it locally before relying on peak speed."
        : "No measured or catalog estimate is available yet, so treat this as exploratory.";
  return (
    <Card data-testid={"advisor-recommendation-" + slot.key} className={"flex h-full flex-col gap-3 p-4 " + (primary ? "border-primary/50 bg-primary/5" : "")}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-primary">{primary ? "Best match for your computer" : slot.label}</div>
          <h3 className="mt-1 text-base font-semibold">{modelName}</h3>
        </div>
        <Badge variant={blocked ? "down" : profile?.evidenceLabel === "Measured" ? "up" : "muted"}>
          {profile?.evidenceLabel || "Unverified"}
        </Badge>
      </div>
      <p className="m-0 text-xs text-muted-foreground">{slot.goal}</p>
      {!profile && (
        <div className="rounded-lg border border-border bg-muted/30 px-3 py-3 text-xs text-muted-foreground">
          No profile is available yet. The advisor will retry when a deployable, unblocked catalog candidate and hardware snapshot are ready.
        </div>
      )}
      {profile && (
        <>
          <details className="model-recommendation-details rounded-lg border border-border bg-muted/20 px-3 py-2">
            <summary className="cursor-pointer text-xs font-semibold text-foreground">Technical details</summary>
            <div className="mt-3 grid gap-2 text-xs text-muted-foreground">
            <div><strong className="text-foreground">Runtime / protocol:</strong> {runtimeLabel} · {profile.protocolId || "Unspecified"}</div>
            <div><strong className="text-foreground">GPU placement:</strong> {deviceLabel}</div>
            <div><strong className="text-foreground">Context:</strong> {contextLabel}</div>
            <div>
              <strong className="text-foreground">Measured TPS / TTFT:</strong>{" "}
              {profile.measuredTps == null ? "unavailable" : profile.measuredTps + " TPS"}
              {" · "}
              {profile.measuredTtft == null ? "unavailable" : profile.measuredTtft + " ms TTFT"}
            </div>
            </div>
          </details>
          <div className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            <strong className="text-foreground">Why this recommendation:</strong> {why}
            {Number.isFinite(profile.profileScore) && <span> Profile score: {profile.profileScore.toFixed(1)}.</span>}
          </div>
          {blockers.length > 0 && (
            <div className="rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
              <strong>Blocked:</strong> {blockers.join(" ")}
            </div>
          )}
          {profile.warnings?.length > 0 && (
            <div className="text-xs text-amber-400">{profile.warnings.join(" ")}</div>
          )}
        </>
      )}
      <div className="mt-auto flex items-center gap-2">
        <UIButton
          size="sm"
          type="button"
          disabled={blocked}
          title={blocked ? blockers.join(" ") || "This recommendation is not deployable." : undefined}
          onClick={() => {
            const planSeed = profile.planSeed || {};
            prepareCatalogModelForWarsat?.(item, {
              ...planSeed,
              strengthProfile: slot.backendProfile,
              protocolId: planSeed.protocolId || profile.protocolId,
              contextWindow: planSeed.contextWindow || profile.contextWindow || undefined,
              toolCallParser: planSeed.toolCallParser || profile.toolCallParser || undefined,
            });
          }}
        >
          <Play size={12} /> Review WarSat plan
        </UIButton>
        {blocked && <span className="text-[0.7rem] text-muted-foreground">Resolve blockers first</span>}
      </div>
    </Card>
  );
}

function GuidedRecommendations({
  advisorState,
  advisorCandidateCount,
  modelCatalogLoading,
  catalogError,
  hardwareProbeState,
  hardwareReady,
  performancePreference,
  automaticBenchmarking,
  onRefresh,
  onBrowseAll,
  onUseSpecificModel,
  prepareCatalogModelForWarsat,
}) {
  const loading = advisorState.status === "loading" || advisorState.status === "waiting" || modelCatalogLoading;
  const preferredSlotKey = performancePreference === "responsive"
    ? "fast"
    : performancePreference === "maximum_quality" ? "maximumQuality" : "balanced";
  const primarySlot = advisorProfileSlots.find((slot) => slot.key === preferredSlotKey) || advisorProfileSlots[1];
  const alternativeSlots = advisorProfileSlots.filter((slot) => slot.key !== primarySlot.key);
  const statusText = modelCatalogLoading
    ? "Loading the local catalog and hardware fit data…"
    : advisorState.status === "loading"
      ? "Analyzing up to " + advisorCandidateCount + " deployable candidates…"
      : advisorState.status === "waiting"
        ? "Waiting for a hardware snapshot before requesting recommendations…"
        : advisorState.status === "error"
          ? "The advisor could not complete any candidate request."
          : advisorCandidateCount
            ? "Recommendations are ready."
            : "No deployable, unblocked catalog candidates are available yet.";
  return (
    <section aria-labelledby="guided-recommendations-title" data-testid="guided-recommendations" className="mb-5">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Gauge size={18} className="text-primary" />
            <h2 id="guided-recommendations-title" className="m-0 text-xl font-semibold">Recommended for this computer</h2>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">Start with one best match, choose a specific Hugging Face model, or explore the full catalog.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <UIButton variant="outline" size="sm" type="button" onClick={onRefresh} disabled={loading} aria-label="Refresh model recommendations">
            <RefreshCw size={14} /> {loading ? "Analyzing…" : "Refresh recommendations"}
          </UIButton>
          <UIButton variant="outline" size="sm" type="button" onClick={onUseSpecificModel} data-testid="use-specific-hf-model">
            <Cloud size={14} /> Use a specific Hugging Face model
          </UIButton>
          <UIButton variant="default" size="sm" type="button" onClick={onBrowseAll}>
            <Database size={14} /> Browse full catalog
          </UIButton>
        </div>
      </div>
      <div aria-live="polite" role="status" className="mb-3 text-xs text-muted-foreground">
        {statusText}
        {advisorState.completed != null && advisorState.total ? " " + advisorState.completed + "/" + advisorState.total + " complete." : ""}
        {advisorState.errors?.length > 0 && " " + advisorState.errors.slice(0, 2).join(" ")}
      </div>
      {catalogError && (
        <div role="alert" className="mb-3 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
          Catalog warning: {catalogError}
        </div>
      )}
      {!hardwareReady && !modelCatalogLoading && (
        <div role="alert" className="mb-3 rounded-lg border border-amber-400/40 bg-amber-400/5 px-3 py-2 text-xs text-amber-300">
          {hardwareProbeState?.status === "loading"
            ? "Detecting GPU capacity locally before ranking recommendations…"
            : hardwareProbeState?.status === "error"
              ? "GPU detection failed, so placement is unproven. Use Refresh recommendations to retry; model cards will remain blocked until hardware or exact runtime evidence is available."
              : "GPU detection is not ready yet; recommendations will remain unverified or blocked."}
        </div>
      )}
      <div className="mb-3 text-xs text-muted-foreground">
        Default preference: <strong className="text-foreground">{performancePreference}</strong>
        {" · "}
        Automatic benchmarking: <strong className="text-foreground">{automaticBenchmarking ? "on" : "off"}</strong>
      </div>
      <div className="max-w-3xl" data-testid="primary-model-recommendation">
        <AdvisorRecommendationCard
          slot={primarySlot}
          winner={advisorState.profiles?.[primarySlot.key]}
          prepareCatalogModelForWarsat={prepareCatalogModelForWarsat}
          primary
        />
      </div>
      <details className="model-alternatives mt-4 rounded-xl border border-border bg-card p-4" data-testid="model-alternatives">
        <summary className="cursor-pointer text-sm font-semibold">Compare alternatives</summary>
        <p className="mt-2 text-xs text-muted-foreground">Fast, balanced, and maximum-quality options remain available when you want more control.</p>
        <div className="mt-3 grid gap-4 lg:grid-cols-2">
          {alternativeSlots.map((slot) => (
            <AdvisorRecommendationCard
              key={slot.key}
              slot={slot}
              winner={advisorState.profiles?.[slot.key]}
              prepareCatalogModelForWarsat={prepareCatalogModelForWarsat}
            />
          ))}
        </div>
      </details>
    </section>
  );
}

/* ═══════════════════════════════════════════
   CATALOG CARD
   ═══════════════════════════════════════════ */
function CatalogCard({ item, placementFit, prepareCatalogModelForWarsat, searchMode, startDownload, activeDownloads }) {
  const modelId = item.modelId || item.id;
  const downloadState = (activeDownloads || []).find(dl => dl.modelId === modelId);
  const isDownloading = downloadState && downloadState.status !== "failed" && downloadState.status !== "completed";
  const blockedReasons = Array.isArray(item.blockedReasons) ? item.blockedReasons : [];
  const fitReasons = Array.isArray(item.fitReasons) ? item.fitReasons : [];
  const placement = placementFit || catalogPlacementAssessment(item, null);
  const blocked = blockedReasons.length > 0 || !placement.canDeploy;
  const fmt = (n) => n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}K` : n;
  return (
    <div className="ras-list-item glow-card flex flex-col gap-3 rounded-2xl border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <strong className="text-sm">{item.name}</strong>
          <div className="truncate text-[0.7rem] text-muted-foreground">{item.modelId || item.id}</div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {item.deployable && <Zap size={13} className="text-primary" />}
          {item.containerBacked && <Badge variant="muted">Managed container</Badge>}
          <span className="text-[0.7rem] text-muted-foreground">{labelize(item.purpose || "chat")}</span>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {item.vramEstimateGb && <Badge variant="muted">~{item.vramEstimateGb} GB VRAM</Badge>}
        {item.downloads > 0 && <Badge variant="muted">↓ {fmt(item.downloads)}</Badge>}
        {item.likes > 0 && <Badge variant="muted">♥ {fmt(item.likes)}</Badge>}
        {item.license && <Badge variant="muted">{item.license}</Badge>}
        <Badge variant={placement.kind === "single-gpu-fit" || placement.kind === "measured-multi-gpu" ? "up" : "down"}>
          {placement.label}
        </Badge>
      </div>

      <div className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
        Largest single GPU: {placement.largestSingleGpuGb == null ? "unknown" : placement.largestSingleGpuGb.toFixed(1) + " GB"}
        {" · "}Optional combined pool: {placement.aggregateVramGb == null ? "unknown" : placement.aggregateVramGb.toFixed(1) + " GB"}
        {placement.reasons?.[0] && <div className="mt-1">{placement.reasons[0]}</div>}
      </div>
      {item.summary && <p className="text-xs text-muted-foreground">{item.summary.slice(0, 120)}</p>}

      {(blocked || fitReasons.length > 0) && (
        <div className={`rounded-lg border px-3 py-2 text-xs ${blocked ? "border-destructive/40 bg-destructive/5 text-destructive" : "border-border bg-muted/30 text-muted-foreground"}`}>
          <strong className="mr-1">{blocked ? "Deployment blocked:" : "Why it fits:"}</strong>
          {(blocked ? blockedReasons : fitReasons).join(" ")}
        </div>
      )}

      <div className="flex items-center gap-2">
        {item.deployable && (
          <UIButton size="sm" type="button" disabled={blocked} title={blocked ? [...blockedReasons, ...placement.reasons].join(" ") : undefined} onClick={() => prepareCatalogModelForWarsat?.(item)}>
            <Play size={12} /> Deploy via Warsat
          </UIButton>
        )}
        {(searchMode === "huggingface" || item.source === "huggingface") && (
          <UIButton variant={isDownloading ? "default" : "outline"} size="sm" type="button" disabled={isDownloading} onClick={() => startDownload(modelId)}>
            <Download size={12} /> {isDownloading ? "Downloading…" : "Download Weights"}
          </UIButton>
        )}
        {item.sourceUrl && item.source === "huggingface" && (
          <a href={item.sourceUrl} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-[0.7rem] text-sky-400 no-underline">
            <ExternalLink size={11} /> HF Page
          </a>
        )}
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════
   INSTALLED CARD
   ═══════════════════════════════════════════ */
function InstalledCard({ model, allModels, runModelAction, executeAction, setUiState }) {
  const name = displayModelName(model, allModels);
  const secondary = displayModelSecondary(model, allModels);
  const st = runtimeStatus(model);
  const isHealthy = isModelHealthy(model);
  const mismatch = modelMismatchLine(model);
  const ctx = contextWindowFor(model);

  const [busy, setBusy] = useState(null); // which action ("test"|"discover") is in flight
  const runAction = async (key, name, op) => {
    setBusy(key);
    try {
      await executeAction(name, model.key, async () => runModelAction?.(op, model.key), setUiState);
    } finally {
      setBusy(null);
    }
  };
  const handleTest = () => runAction("test", "TestHealth", "test");
  const handleDiscover = () => runAction("discover", "Discover", "discover");

  return (
    <div className="ras-list-item glow-card flex flex-col gap-3 rounded-2xl border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <Cpu size={18} style={{ color: statusColor(st) }} />
          <div>
            <strong className="text-sm">{name}</strong>
            {secondary && <div className="text-[0.7rem] text-muted-foreground">{secondary}</div>}
          </div>
        </div>
        <Badge variant={isHealthy ? "up" : "down"}>{isHealthy ? "Healthy" : labelize(st)}</Badge>
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span>Model: {model.model || "—"}</span>
        <span>Runtime: {model.runtime || model.provider || "local"}</span>
        <span>Role: {labelize(model.role || "chat")}</span>
        {ctx > 0 && <span>Context: {ctx.toLocaleString()}</span>}
      </div>

      {mismatch && (
        <div className="flex items-center gap-1.5 rounded-lg bg-amber-500/10 px-2.5 py-1.5 text-xs text-amber-400">
          <AlertTriangle size={13} /> {mismatch}
        </div>
      )}

      <CompatibilitySummary model={model} />

      <div className="flex gap-2">
        <Button onClick={handleTest} loading={busy === "test"} loadingLabel="Testing…" icon={<CheckCircle2 size={12} />} spinnerSize={12} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>Test</Button>
        <Button onClick={handleDiscover} loading={busy === "discover"} loadingLabel="Discovering…" icon={<Search size={12} />} spinnerSize={12} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>Discover</Button>
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════
   ACTIVE MODEL CARD
   ═══════════════════════════════════════════ */
function ActiveModelCard({ model, models, healthy, status, runModelAction, executeAction, setUiState, openWarsat }) {
  const name = displayModelName(model, models);
  const secondary = displayModelSecondary(model, models);
  const mismatch = modelMismatchLine(model);
  const ctx = contextWindowFor(model);

  const handleTest = () => executeAction("TestHealth", model?.key, async () => runModelAction?.("test", model?.key), setUiState);
  const handleDiscover = () => executeAction("Discover", model?.key, async () => runModelAction?.("discover", model?.key), setUiState);
  const handleRepair = () => executeAction("Repair", model?.key, async () => runModelAction?.("repair", model?.key), setUiState);

  return (
    <div className="w2-card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          <Cpu size={24} color={healthy ? "var(--ras-safe)" : "var(--ras-danger)"} />
          <div>
            <div style={{ fontSize: "0.6875rem", textTransform: "uppercase", letterSpacing: ".05em", color: "var(--cc-muted)", fontWeight: 600 }}>Active Chat Model</div>
            <h2 style={{ margin: "2px 0 0", fontSize: "1.125rem" }}>{name}</h2>
            {secondary && <p style={{ margin: 0, fontSize: "0.8125rem", color: "var(--cc-muted)" }}>{secondary}</p>}
          </div>
        </div>
        <span style={{ fontSize: "0.75rem", padding: "4px 12px", borderRadius: "999px", background: healthy ? "color-mix(in srgb, var(--ras-safe) 15%, var(--cc-surface))" : "color-mix(in srgb, var(--ras-danger) 15%, var(--cc-surface))", color: healthy ? "var(--ras-safe)" : "var(--ras-danger)", fontWeight: 600 }}>
          {healthy ? "Reachable" : labelize(status)}
        </span>
      </div>

      <div style={{ display: "flex", gap: "16px", fontSize: "0.75rem", color: "var(--cc-muted)", flexWrap: "wrap" }}>
        <span>Model: {model?.model || "Not configured"}</span>
        <span>Endpoint: {model?.url || model?.base_url || "Not set"}</span>
        <span>Runtime: {model?.runtime || model?.provider || "local"}</span>
        {ctx > 0 && <span>Context: {ctx.toLocaleString()}</span>}
      </div>

      {mismatch && (
        <div style={{ display: "flex", gap: "6px", alignItems: "center", fontSize: "0.75rem", color: "var(--ras-warn)", padding: "8px 10px", background: "color-mix(in srgb, var(--ras-warn) 8%, var(--cc-surface))", borderRadius: "6px" }}>
          <Wrench size={13} /> {mismatch}
        </div>
      )}


      <CompatibilitySummary model={model} />

      <div style={{ display: "flex", gap: "8px" }}>
        <button className="w2-button" type="button" onClick={handleTest}><CheckCircle2 size={14} /> Test</button>
        <button className="w2-button" type="button" onClick={handleDiscover}><Search size={14} /> Discover</button>
        <button className="w2-button" type="button" onClick={handleRepair}><Wrench size={14} /> Repair</button>
        <button className="w2-button primary" type="button" onClick={openWarsat}><Play size={14} /> Warsat</button>
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════
   INFRA STATUS
   ═══════════════════════════════════════════ */
function InfraStatusCard({ warsatHardware, warsatRuntimes, warsat }) {
  const runtimeCount = warsatRuntimes?.count ?? warsatRuntimes?.containers?.length ?? 0;
  return (
    <div className="w2-card">
      <h3 style={{ margin: 0, fontSize: "0.875rem" }}>Infrastructure</h3>
      <div className="w2-health-grid">
        <div className="w2-health-item"><Server size={16} color="var(--cc-muted)" /> Warsat: {warsatHardware ? labelize(warsatHardware.status || "unknown") : "Not checked"}</div>
        <div className="w2-health-item"><MonitorSpeaker size={16} color="var(--cc-muted)" /> Containers: {runtimeCount}</div>
        <div className="w2-health-item"><ShieldCheck size={16} color="var(--ras-safe)" /> Docker: {warsat?.dockerControlEnabled ? "Enabled" : "Off"}</div>
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════
   RIGHT PANEL
   ═══════════════════════════════════════════ */
function RightPanel({ activeTab, activeModel, models, healthy, status, warsatHardware }) {
  const name = displayModelName(activeModel, models);

  if (activeTab === "library") {
    return (
      <div className="w2-section">
        <h3 className="w2-section-title">Quick Start</h3>
        <div className="w2-card">
          <strong style={{ fontSize: "0.875rem" }}>How to add a model</strong>
          <ol style={{ margin: 0, paddingLeft: "18px", fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            <li>Browse or search for a model</li>
            <li>Click "Deploy via Warsat" on a deployable model</li>
            <li>Or use Settings to connect a running endpoint</li>
          </ol>
        </div>
        <div className="w2-card">
          <strong style={{ fontSize: "0.875rem" }}>Supported Runtimes</strong>
          <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)", display: "flex", flexDirection: "column", gap: "4px" }}>
            <span>• vLLM CUDA (Hugging Face models)</span>
            <span>• llama.cpp (GGUF files)</span>
            <span>• Ollama (quick experiments)</span>
            <span>• External local endpoints</span>
            <span>• Remote APIs (OpenAI, Anthropic, Gemini)</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="w2-section">
      <h3 className="w2-section-title">Active Model</h3>
      <div className="w2-card">
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <Cpu size={18} color={healthy ? "var(--ras-safe)" : "var(--ras-danger)"} />
          <strong style={{ fontSize: "0.875rem" }}>{name}</strong>
        </div>
        <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)", display: "flex", flexDirection: "column", gap: "4px" }}>
          <span>Status: {healthy ? "Reachable" : labelize(status)}</span>
          <span>Model: {activeModel?.model || "—"}</span>
          <span>Runtime: {activeModel?.runtime || activeModel?.provider || "—"}</span>
          <span>Role: {labelize(activeModel?.role || "main")}</span>
        </div>
      </div>

      {warsatHardware?.detectedHardware?.gpus?.length > 0 && (
        <>
          <h3 className="w2-section-title">GPU Hardware</h3>
          <div className="w2-card">
            {warsatHardware.detectedHardware.gpus.map((gpu, i) => {
              const vramMb = gpu.memoryTotalMb || gpu.memory_total_mb;
              return (
                <div key={i} style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
                  <strong style={{ color: "var(--cc-text)" }}>{gpu.name}</strong>
                  <div>{vramMb ? `${(vramMb / 1024).toFixed(1)} GB VRAM` : "Unknown VRAM"}</div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
