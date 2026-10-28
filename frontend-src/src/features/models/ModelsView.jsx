import { InstalledModelInspector } from "./InstalledModelInspector.jsx";
import { LocalModelSources } from "./LocalModelSources.jsx";
import { useModelActions } from "./useModelActions.js";
import { usesNativeModels } from "./nativeDeployment.js";
import { useState, useMemo, useEffect, useRef } from "react";
import { Activity, CheckCircle2, Cloud, Cpu, Database, Gauge, HardDrive, KeyRound, Package, PanelLeftClose, PanelLeftOpen, Play, RadioTower, RefreshCw, Search, Settings, SlidersHorizontal } from "lucide-react";
import { displayModelName, isModelHealthy, isManagedModelRunning, labelize, runtimeStatus } from "../../lib/display.js";
import { useReliableAction } from "../../lib/actionRegistry.js";
import { showsGlobalDownloadProgress } from "../../lib/modelDownloadVisibility.js";
import { api } from "../../api/client.js";
import { useSettingsStore } from "../settings/settingsStore.js";
import { SkeletonList } from "../../components/Skeleton.jsx";
import { Button } from "../../components/Button.jsx";
import { Button as UIButton } from "@/components/ui/button.jsx";
import { Badge } from "@/components/ui/badge.jsx";

import { ModelLoadDialog } from "./ModelLoadDialog.jsx";
import { ModelServingPanel } from "./ModelServingPanel.jsx";
import { catalogItemPassesFilters } from "./catalogFitFilter.js";
import { findInstalledCatalogModel } from "./modelEcosystem.js";
import "../../styles/models-workspace-v3.css";
import "./modelWorkspace.css";
import { downloadJobIdentity, downloadJobState, downloadJobsFromPayload } from "./downloadState.js";
import { hardwarePlacementCapacity, normalizeHardwareSnapshot, shouldProbeHardware, systemHardwareSummary } from "./hardwareSnapshot.js";
import { ADVISOR_REQUEST_TIMEOUT_MS, advisorModelId, advisorProfileFromPayload, advisorProfileSlots, advisorStateForInputs, normalizeAdvisorProfile, selectAdvisorWinner, shortlistAdvisorModels, withAdvisorTimeout } from "./advisorSelection.js";
import { contextWindowFor, installedModelCategory, modelOperationalSignal } from "./modelPresentation.js";
import { catalogPlacementAssessment, catalogVramEstimateGb } from "./modelPlacement.js";
import { GuidedRecommendations } from "./ModelAdvisor.jsx";
import { CatalogPagination, DiscoverCatalogRow, DiscoverInstalledSummary } from "./ModelCatalogRows.jsx";
import { ModelDownloadProgress } from "./ModelDownloadProgress.jsx";
import { DiscoverModelInspector } from "./DiscoverModelInspector.jsx";
import { CatalogCard } from "./CatalogCard.jsx";
import { InstalledCard } from "./InstalledModelRow.jsx";
import { ActiveModelCard, InfraStatusCard, RightPanel } from "./ModelRuntimePanel.jsx";
import { ModelStateSignal } from "./ModelStatus.jsx";
export { preferredDownloadVariant } from "./downloadState.js";

const modelsTabs = [
  { id: "library", label: "Discover", icon: Search },
  { id: "installed",  label: "Installed",   icon: Package },
  { id: "running",    label: "Running",     icon: Activity },
  { id: "serving",    label: "Serving",     icon: RadioTower },
  { id: "settings",   label: "Advanced",    icon: Settings },
];

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
  go,
}) {
  const [activeTab, setActiveTab] = useState(() => view === "discover" ? "library" : "installed");
  const [libraryStatus, setLibraryStatus] = useState("all");
  const [showModelSources, setShowModelSources] = useState(false);
  const [uiState, setUiState] = useState({ status: "idle", message: "" });
  const [modelsRailCollapsed, setModelsRailCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    try {
      return window.localStorage.getItem("rasputin-models-rail-collapsed") === "1";
    } catch {
      return false;
    }
  });
  const modelTabRefs = useRef({});
  const executeAction = useReliableAction("ModelsView");
  const modelsWorkspaceOpen = ["discover", "models"].includes(view);

  useEffect(() => {
    if (view === "discover") setActiveTab("library");
    if (view === "models") setActiveTab("installed");
  }, [view]);

  const focusModelTab = (tabId) => {
    requestAnimationFrame(() => modelTabRefs.current[tabId]?.focus());
  };

  const handleModelTabKeyDown = (event, tabId) => {
    const index = modelsTabs.findIndex((tab) => tab.id === tabId);
    if (index < 0) return;
    let nextIndex = index;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") nextIndex = (index + 1) % modelsTabs.length;
    else if (event.key === "ArrowLeft" || event.key === "ArrowUp") nextIndex = (index - 1 + modelsTabs.length) % modelsTabs.length;
    else if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = modelsTabs.length - 1;
    else return;
    event.preventDefault();
    const nextTab = modelsTabs[nextIndex].id;
    setActiveTab(nextTab);
    focusModelTab(nextTab);
  };

  /* catalog state */
  const [catalogSearch, setCatalogSearch] = useState("");
  const [catalogPurpose, setCatalogPurpose] = useState("chat");
  const [catalogRuntime, setCatalogRuntime] = useState("all");
  const [catalogFit, setCatalogFit] = useState("all");
  const [searchMode, setSearchMode] = useState(() => view === "discover" ? "browse" : "catalog");
  const [hfQuery, setHfQuery] = useState("");
  const [hfSearchDraft, setHfSearchDraft] = useState("");
  const hfSearchInputRef = useRef(null);
  const nativeRecoveryQueryRef = useRef("");
  const [hfResults, setHfResults] = useState([]);
  const [hfLoading, setHfLoading] = useState(false);
  const [hfError, setHfError] = useState("");
  const [hfSort, setHfSort] = useState("popular");
  const [vramMinGb, setVramMinGb] = useState("");
  const [vramMaxGb, setVramMaxGb] = useState("");
  const [activeDownloads, setActiveDownloads] = useState([]);
  const [downloadError, setDownloadError] = useState("");
  const [pageSize, setPageSize] = useState(20);
  const [page, setPage] = useState(1);
  const modelSettings = useSettingsStore((state) => state.models || {});
  const [showAllModels, setShowAllModels] = useState(() => view === "discover" || Boolean(security?.desktopOnly));
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
  const [loadingArtifact, setLoadingArtifact] = useState(null);
  const [selectedCatalogId, setSelectedCatalogId] = useState("");
  const [discoverInspectorTab, setDiscoverInspectorTab] = useState("info");
  const [installedSearch, setInstalledSearch] = useState("");
  const [installedCategory, setInstalledCategory] = useState("all");
  const [selectedInstalledKey, setSelectedInstalledKey] = useState("");
  const [installedInspectorTab, setInstalledInspectorTab] = useState("info");
  const [inspectorWidth, setInspectorWidth] = useState(() => {
    if (typeof window === "undefined") return 350;
    try {
      const stored = Number(window.localStorage.getItem("rasputin-model-inspector-width"));
      return Number.isFinite(stored) ? Math.min(480, Math.max(260, stored)) : 350;
    } catch {
      return 350;
    }
  });
  const inspectorResizeRef = useRef(null);
  const installedSearchInputRef = useRef(null);
  const [loadDialogModel, setLoadDialogModel] = useState(null);
  const completedRefreshJobs = useRef(new Set());

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem("rasputin-model-inspector-width", String(inspectorWidth));
    } catch {
      // Storage may be unavailable in a locked-down desktop session.
    }
  }, [inspectorWidth]);

  useEffect(() => () => {
    const resize = inspectorResizeRef.current;
    if (!resize) return;
    window.removeEventListener("pointermove", resize.move);
    window.removeEventListener("pointerup", resize.end);
  }, []);

  const startInspectorResize = (event) => {
    if (event.button !== 0) return;
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = inspectorWidth;
    const move = (moveEvent) => setInspectorWidth(Math.min(480, Math.max(260, startWidth - (moveEvent.clientX - startX))));
    const end = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", end);
      inspectorResizeRef.current = null;
    };
    inspectorResizeRef.current = { move, end };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end);
  };

  const handleInspectorResizeKeyDown = (event) => {
    if (event.key === "Home") setInspectorWidth(260);
    else if (event.key === "End") setInspectorWidth(480);
    else if (event.key === "ArrowLeft") setInspectorWidth((width) => Math.min(480, width + 16));
    else if (event.key === "ArrowRight") setInspectorWidth((width) => Math.max(260, width - 16));
    else return;
    event.preventDefault();
  };

  useEffect(() => {
    if (!modelsWorkspaceOpen || activeTab !== "library") return;
    setShowAllModels(true);
    const recoveryQuery = nativeRecoveryQueryRef.current;
    nativeRecoveryQueryRef.current = "";
    setSearchMode(recoveryQuery ? "huggingface" : "browse");
    if (recoveryQuery) {
      setHfSearchDraft(recoveryQuery);
      setHfQuery(recoveryQuery);
      requestAnimationFrame(() => hfSearchInputRef.current?.focus());
    }
    setPage(1);
  }, [view, activeTab]);

  useEffect(() => {
    if (!modelsWorkspaceOpen) return undefined;
    let disposed = false;
    let timer;
    const pollDownloads = async () => {
      try {
        let payload;
        try {
          payload = await api("/api/models/downloads");
        } catch (primaryError) {
          payload = await api("/api/models/downloads/active");
        }
        const jobs = downloadJobsFromPayload(payload);
        if (disposed) return;
        setDownloadError("");
        setActiveDownloads(jobs);
        const newlyCompleted = jobs.filter((job) => {
          const identity = downloadJobIdentity(job);
          return downloadJobState(job) === "completed" && identity && !completedRefreshJobs.current.has(identity);
        });
        newlyCompleted.forEach((job) => completedRefreshJobs.current.add(downloadJobIdentity(job)));
        if (newlyCompleted.length && loadModels) {
          try {
            await loadModels();
            setUiState({ status: "success", message: "Download complete. The exact GGUF artifact is registered and ready to load." });
          } catch (error) {
            setDownloadError("Download completed, but the model registry could not refresh: " + (error?.message || "unknown error"));
          }
        }
        const hasNonterminalJob = jobs.some((job) => !["completed", "failed", "cancelled"].includes(downloadJobState(job)));
        if (hasNonterminalJob) timer = setTimeout(pollDownloads, 3000);
      } catch (error) {
        if (!disposed) {
          setDownloadError("Unable to load model download status: " + (error?.message || "unknown error"));
          timer = setTimeout(pollDownloads, 5000);
        }
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
  const normalizedHardware = useMemo(() => normalizeHardwareSnapshot(effectiveHardware), [effectiveHardware]);
  const gpuCapacity = useMemo(() => hardwarePlacementCapacity(effectiveHardware), [effectiveHardware]);
  const systemHardware = useMemo(() => systemHardwareSummary(effectiveHardware), [effectiveHardware]);
  const totalVramGb = gpuCapacity.aggregateVramGb || 0;
  const downloadProgressJobs = useMemo(
    () => activeDownloads.filter((job) => showsGlobalDownloadProgress(downloadJobState(job))),
    [activeDownloads],
  );

  useEffect(() => {
    if (warsatHardware) {
      const snapshot = normalizeHardwareSnapshot(warsatHardware);
      setHardwareProbeState({ status: snapshot.blocked ? "blocked" : "ready", error: "", snapshot });
      return undefined;
    }
    if (security?.native == null && security?.desktopOnly == null) return undefined;
    if (!shouldProbeHardware(view, Boolean(warsatHardware || localHardware), hardwareProbeAttempt.current, hardwareRefreshToken)) return undefined;
    hardwareProbeAttempt.current = hardwareRefreshToken;
    const controller = new AbortController();
    let disposed = false;
    setHardwareProbeState({ status: "loading", error: "" });
    withAdvisorTimeout(
      () => api(usesNativeModels(security) ? "/api/warsat/hardware?native_models=true" : "/api/warsat/hardware", { signal: controller.signal }),
      ADVISOR_REQUEST_TIMEOUT_MS,
      () => controller.abort("timeout"),
    ).then((hardware) => {
      if (disposed) return;
      const snapshot = normalizeHardwareSnapshot(hardware);
      setLocalHardware(hardware);
      setHardwareProbeState({ status: snapshot.blocked ? "blocked" : "ready", error: "", snapshot });
    }).catch((error) => {
      const superseded = controller.signal.aborted && controller.signal.reason === "superseded";
      if (disposed || superseded) return;
      setHardwareProbeState({ status: "error", error: error?.message || "Hardware detection failed." });
    });
    return () => {
      disposed = true;
      controller.abort("superseded");
    };
  }, [view, warsatHardware, hardwareRefreshToken, security?.native, security?.desktopOnly]);

  const apiProviders = modelProviders?.length ? modelProviders : [
    { id: "openai", name: "OpenAI", defaultKeyEnv: "OPENAI_API_KEY" },
    { id: "anthropic", name: "Anthropic", defaultKeyEnv: "ANTHROPIC_API_KEY" },
    { id: "gemini", name: "Google Gemini", defaultKeyEnv: "GEMINI_API_KEY" },
    { id: "openai-compatible-remote", name: "Other OpenAI-compatible", defaultKeyEnv: "" },
  ];
  const remoteBlocked = security?.privacyLock || !security?.allowRemoteModels;
  const desktopOnly = Boolean(security?.desktopOnly);
  const nativeModels = usesNativeModels(security);

  useEffect(() => {
    if (!desktopOnly || typeof window === "undefined") return;
    try {
      window.localStorage.setItem("rasputin-models-rail-collapsed", modelsRailCollapsed ? "1" : "0");
    } catch {
      // Storage may be unavailable in a locked-down desktop session.
    }
  }, [desktopOnly, modelsRailCollapsed]);

  useEffect(() => {
    if (!nativeModels) return;
    setShowAllModels(true);
    setCatalogRuntime("llamaCppGgufServer");
  }, [nativeModels]);

  const registeredModels = useMemo(() => (models || []).filter(m => (
    m.key !== "dry-run" && !["mock", "hash-vector"].includes(m.provider)
  )), [models]);
  const installedModels = useMemo(() => {
    const rank = (model) => {
      const signal = modelOperationalSignal(model);
      return signal.key === "live" ? 0 : signal.label === "Not loaded" ? 1 : signal.key === "down" ? 3 : 2;
    };
    return [...registeredModels].sort((left, right) => rank(left) - rank(right));
  }, [registeredModels]);
  const discoverInstalledModels = useMemo(() => registeredModels.filter((model) => {
    const path = model.hostModelPath || model.host_model_path || model.modelPath || model.model_path;
    const artifactAvailable = model.artifactAvailable ?? model.artifact_available;
    const size = Number(model.sizeBytes ?? model.size_bytes);
    return model.runtime === "native-llamacpp" && artifactAvailable === true && Boolean(path) && Number.isFinite(size) && size > 0;
  }), [registeredModels]);
  const filteredInstalledModels = useMemo(() => {
    const query = installedSearch.trim().toLowerCase();
    return installedModels.filter((model) => {
      const signal = modelOperationalSignal(model);
      if (libraryStatus === "ready" && signal.key !== "live") return false;
      if (libraryStatus === "help" && signal.key !== "down") return false;
      if (libraryStatus === "idle" && signal.label !== "Not loaded") return false;
      if (installedCategory !== "all" && installedModelCategory(model) !== installedCategory) return false;
      if (!query) return true;
      const searchable = [
        model.key,
        model.name,
        model.model,
        model.provider,
        model.runtime,
        model.role,
        model.architecture,
        model.arch,
        model.quantization,
      ].filter(Boolean).join(" ").toLowerCase();
      return searchable.includes(query);
    });
  }, [installedModels, installedSearch, installedCategory, libraryStatus]);
  const selectedInstalledModel = filteredInstalledModels.find((model) => model.key === selectedInstalledKey)
    || filteredInstalledModels[0]
    || null;
  const reachableModels = useMemo(() => registeredModels.filter(m => runtimeStatus(m) === "reachable"), [registeredModels]);
  const runningModels = useMemo(() => registeredModels.filter(isManagedModelRunning), [registeredModels]);

  useEffect(() => {
    const nextKey = selectedInstalledModel?.key || "";
    if (nextKey !== selectedInstalledKey) setSelectedInstalledKey(nextKey);
  }, [selectedInstalledModel, selectedInstalledKey]);

  useEffect(() => {
    if (!modelsWorkspaceOpen || activeTab !== "installed") return undefined;
    const focusInstalledSearch = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "f") {
        event.preventDefault();
        installedSearchInputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", focusInstalledSearch);
    return () => window.removeEventListener("keydown", focusInstalledSearch);
  }, [view, activeTab]);

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
    if (!modelsWorkspaceOpen) return () => { disposed = true; };
    const terminalState = advisorStateForInputs({
      catalogLoading: modelCatalogLoading,
      hardwareProbeStatus: hardwareProbeState.status,
      hardwareError: hardwareProbeState.error,
      hasHardware: Boolean(effectiveHardware),
      hardwareSnapshot: normalizedHardware,
      catalogCount: catalogItems.length,
      candidateCount: advisorCandidates.length,
    });
    if (terminalState) {
      setAdvisorState((previous) => previous.status === terminalState.status && previous.reason === terminalState.reason
        ? previous
        : { ...terminalState, profiles: {}, errors: [], completed: 0, total: advisorCandidates.length });
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
    hardwareProbeState.error,
    normalizedHardware,
    modelCatalogLoading,
    modelSettings?.maxContextTokens,
    modelSettings?.allowMultiGpu,
    advisorRefreshToken,
  ]);

  /* Available-model browsing and exact Hugging Face search share one bounded request path. */
  useEffect(() => {
    if (!["browse", "huggingface"].includes(searchMode)) return;
    if (searchMode === "huggingface" && !hfQuery.trim()) {
      setHfResults([]);
      setHfLoading(false);
      return;
    }
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
        const p = new URLSearchParams({ q: searchMode === "browse" ? "" : hfQuery, sort: hfSort, limit: hfLimit, fit: "true" });
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
        const superseded = controller.signal.aborted && controller.signal.reason === "superseded";
        if (superseded) {
          return;
        }
        if (err.name === "AbortError") {
          // Either superseded by a newer search, or the 30s bound tripped.
          setHfResults([]);
          setHfError("Hugging Face search timed out after 30s. Check this runtime's network access to huggingface.co and try again.");
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
    const list = searchMode === "catalog" ? filteredCatalog : hfResults;
    return list.filter((item) => catalogItemPassesFilters(item, {
      catalogFit,
      vramMinGb,
      vramMaxGb,
      hardware: effectiveHardware,
      estimateVramGb: catalogVramEstimateGb,
      assessPlacement: catalogPlacementAssessment,
    }));
  }, [searchMode, hfResults, filteredCatalog, catalogFit, effectiveHardware, vramMinGb, vramMaxGb]);

  const pageCount = Math.max(1, Math.ceil(displayItems.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const pagedItems = useMemo(
    () => displayItems.slice((currentPage - 1) * pageSize, currentPage * pageSize),
    [displayItems, currentPage, pageSize]
  );

  const selectedCatalogItem = pagedItems.find((item) => (item.id || item.modelId) === selectedCatalogId) || pagedItems[0] || null;
  useEffect(() => {
    if (selectedCatalogItem && selectedCatalogId !== (selectedCatalogItem.id || selectedCatalogItem.modelId)) {
      setSelectedCatalogId(selectedCatalogItem.id || selectedCatalogItem.modelId);
    }
  }, [selectedCatalogItem, selectedCatalogId]);

  /* reliable actions */
  const {
    handleRefresh,
    handleScanGguf,
    handleLoadCatalog,
    openSpecificHuggingFaceModel,
    submitHfSearch,
    configureNativeLoad,
    handleAdvisorRefresh,
    startDownload,
    onDownloadAction,
    downloadCatalogItem,
    manageInstalledModel,
    loadCompletedArtifact,
  } = useModelActions({
    executeAction,
    loadModels,
    setUiState,
    scanGguf,
    loadModelCatalog,
    setShowAllModels,
    setSearchMode,
    setCatalogPurpose,
    setCatalogFit,
    setPage,
    hfSearchInputRef,
    hfSearchDraft,
    setHfResults,
    setHfError,
    setHfSearchDraft,
    setHfQuery,
    nativeModels,
    setLoadDialogModel,
    prepareCatalogModelForWarsat,
    nativeRecoveryQueryRef,
    go,
    setActiveTab,
    setAdvisorRefreshToken,
    warsatHardware,
    setHardwareRefreshToken,
    registeredModels,
    setDownloadRefreshToken,
    setDownloadError,
    activeDownloads,
    setSelectedCatalogId,
    setDiscoverInspectorTab,
    searchMode,
    setInstalledSearch,
    setInstalledCategory,
    setSelectedInstalledKey,
    setInstalledInspectorTab,
    setLoadingArtifact,
    models,
  });

  /* stats */
  const totalModels = registeredModels.length;
  const healthyCount = reachableModels.length;

  const modelsSurface = (
    <section
      className={`w2-layout app-view models-view models-workspace-v3 models-unified tw ${activeTab === "library" ? "is-discover-route" : ""} ${modelsWorkspaceOpen ? "active" : ""}`}
      id="modelsView"
      data-app-view={view === "discover" ? "discover" : "models"}
    >
      <div className="models-page-shell fx-rise mx-auto flex w-full min-w-0 max-w-[1600px] flex-col">

      {/* ── Header ── */}
      <div className="models-page-header models-v3-command-band">
        <div className="models-v3-command-copy">
          <h1>Model Hub</h1>
          <p>{view === "discover" ? "Find the right model, choose an exact variant, and download it." : "Import, configure, and run the models on your workstation."}</p>
        </div>
        {desktopOnly && (
          <div className="models-header-runtime" aria-label="Native runtime status">
            <span aria-hidden="true" /> Native · llama.cpp
          </div>
        )}
        <details className="models-v3-overview-disclosure">
          <summary>
            <span>Library Overview</span>
            <small>{totalModels} models · {runningModels.length} loaded</small>
          </summary>
          <div className="models-v3-runtime-metrics">
            {[
              { v: totalModels, l: "Registered", c: "text-foreground" },
              { v: healthyCount, l: "Reachable now", c: "text-primary" },
              { v: runningModels.length, l: nativeModels ? "Running models" : "Running containers", c: "text-amber-400" },
              { v: catalogItems.length, l: "Catalog entries", c: "text-sky-400" },
            ].map((s) => (
              <div key={s.l} className="models-v3-metric">
                <div className={`text-xl font-bold ${s.c}`}>{s.v}</div>
                <div className="text-[0.66rem] uppercase tracking-wide text-muted-foreground">{s.l}</div>
              </div>
            ))}
          </div>
        </details>
      </div>

      {/* ── Tab Bar ── */}
      {modelsWorkspaceOpen && <div className="models-page-rail">
        <div id="models-navigation" className="models-page-tabs" role="tablist" aria-orientation="horizontal" aria-label="Model management areas">
        {modelsTabs.map(t => {
          const Icon = t.icon;
          const desktopItem = {
            library: { label: "Discover", hint: "Find & download" },
            installed: { label: "My Models", hint: "Local and connected" },
            running: { label: "Loaded", hint: "Active runtime" },
            serving: { label: "Share models", hint: "Connect other tools" },
            settings: { label: "Advanced", hint: "Connections & diagnostics" },
          }[t.id];
          return (
            <UIButton
              key={t.id}
              id={`models-tab-${t.id}`}
              role="tab"
              aria-selected={activeTab === t.id}
              aria-controls={`models-panel-${t.id}`}
              tabIndex={activeTab === t.id ? 0 : -1}
              aria-label={desktopOnly && modelsRailCollapsed ? desktopItem.label : undefined}
              title={desktopOnly && modelsRailCollapsed ? desktopItem.label : undefined}
              variant={activeTab === t.id ? "default" : "outline"}
              size="sm"
              type="button"
              ref={(node) => { modelTabRefs.current[t.id] = node; }}
              onKeyDown={(event) => handleModelTabKeyDown(event, t.id)}
              onClick={() => setActiveTab(t.id)}
              className="models-v3-tab"
            >
              <span className="models-v3-tab-icon"><Icon size={15} /></span>
              <span>
                <strong>{desktopItem.label}</strong>
                {desktopOnly && <small>{desktopItem.hint}</small>}
              </span>
            </UIButton>
          );
        })}
        <div className="flex-1" />
        {uiState.status !== "idle" && (
          <Badge className="models-rail-status" role="status" title={uiState.message} variant={uiState.status === "failed" ? "down" : uiState.status === "success" ? "up" : "muted"}>
            {uiState.message}
          </Badge>
        )}

        </div>
        {desktopOnly && (
          <button
            type="button"
            className="models-rail-toggle"
            data-testid="models-rail-toggle"
            aria-expanded={!modelsRailCollapsed}
            aria-controls="models-navigation"
            aria-label={modelsRailCollapsed ? "Expand Models navigation" : "Collapse Models navigation to icons"}
            title={modelsRailCollapsed ? "Expand navigation" : "Collapse to icons"}
            onClick={() => setModelsRailCollapsed(value => !value)}
          >
            {modelsRailCollapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
            <span>{modelsRailCollapsed ? "Expand navigation" : "Collapse to icons"}</span>
          </button>
        )}
      </div>}

      {/* ── Content ── */}
      <div className={`${desktopOnly ? "models-page-content" : "w2-main-grid"} models-v3-content`}>
        <div className="w2-column">

          {/* ═══ LIBRARY TAB ═══ */}
          {activeTab === "library" && (
            <div id="models-panel-library" role="tabpanel" aria-labelledby="models-tab-library" className="w2-section models-v3-panel" style={{ flex: 1 }}>
              {!showAllModels ? (
                <GuidedRecommendations
                  advisorState={advisorState}
                  advisorCandidateCount={advisorCandidates.length}
                  modelCatalogLoading={modelCatalogLoading}
                  catalogError={modelCatalogError}
                  hardwareReady={Boolean(effectiveHardware)}
                  hardwareSnapshot={normalizedHardware}
                  hardwareProbeState={hardwareProbeState}
                  performancePreference={modelSettings?.performancePreference || "balanced"}
                  automaticBenchmarking={modelSettings?.automaticBenchmarking !== false}
                  onRefresh={handleAdvisorRefresh}
                  onBrowseAll={() => setShowAllModels(true)}
                  onUseSpecificModel={openSpecificHuggingFaceModel}
                  prepareCatalogModelForWarsat={prepareCatalogModelForWarsat}
                  desktopOnly={nativeModels}
                />
              ) : (
                <>
                  <div className={desktopOnly ? "hidden" : "mb-3 flex justify-end"}>
                    <UIButton variant="outline" size="sm" type="button" onClick={() => setShowAllModels(false)}>
                      <Gauge size={14} /> Back to recommendations
                    </UIButton>
                  </div>
              <div className="models-catalog-toolbar">
              <div className="models-source-switcher">
                {!desktopOnly && <button className={`w2-button ${searchMode === "catalog" ? "primary" : ""}`} type="button" onClick={() => setSearchMode("catalog")}>
                  <HardDrive size={14} /> Local Catalog
                </button>}
                <button className={`w2-button ${searchMode === "browse" ? "primary" : ""}`} data-testid="discover-browse-models" type="button" onClick={() => { setHfQuery(""); setHfSearchDraft(""); setHfError(""); setSearchMode("browse"); }}>
                  <Cloud size={14} /> Browse Catalog
                </button>
                <button className={`w2-button ${searchMode === "huggingface" ? "primary" : ""}`} data-testid="discover-search-models" type="button" onClick={openSpecificHuggingFaceModel}>
                  <Search size={14} /> Search Models
                </button>
                <div style={{ flex: 1 }} />
                {searchMode === "catalog" && (
                  <>
                    <Button onClick={() => handleLoadCatalog(true)} loading={modelCatalogLoading} loadingLabel="Refreshing…" icon={<RefreshCw size={14} />} aria-label="Refresh model catalog" title="Refresh model catalog">
                      Refresh
                    </Button>
                  </>
                )}
              </div>

              {/* Search + filters */}
              <div className="model-catalog-filters" style={{ display: "flex", flexWrap: "wrap", gap: "8px", alignItems: "center" }}>
                {searchMode !== "browse" && <Search size={16} color="var(--cc-muted)" />}
                {searchMode === "huggingface" ? (
                  <form className="models-catalog-search-form" role="search" onSubmit={submitHfSearch}>
                    <input
                      ref={hfSearchInputRef}
                      className="w2-input model-catalog-search"
                      aria-label="Hugging Face model ID, URL, or search terms"
                      data-testid="model-specific-hf-input"
                      value={hfSearchDraft}
                      onChange={(event) => setHfSearchDraft(event.target.value)}
                      placeholder="Model name, org/model, or Hugging Face URL…"
                    />
                    <button className="w2-button primary" type="submit" data-testid="model-specific-hf-submit">
                      <Search size={14} /> Search
                    </button>
                  </form>
                ) : searchMode !== "browse" ? (
                  <input
                    className="w2-input model-catalog-search"
                    style={{ minWidth: "240px", flex: "1 1 320px" }}
                    aria-label="Search models"
                    value={catalogSearch}
                    onChange={(event) => setCatalogSearch(event.target.value)}
                    placeholder="Filter locally cached models by name…"
                  />
                ) : null}
                {searchMode === "huggingface" && (
                  <span className="w-full text-xs text-muted-foreground" data-testid="model-specific-hf-help">
                    Enter a model name, exact org/model ID, or Hugging Face URL, then press Enter or Search. Exact matches appear first.
                  </span>
                )}
              </div>

              <details className="models-catalog-advanced">
                <summary>
                  <span><SlidersHorizontal size={15} /> Filters</span>
                  <small>{[catalogPurpose !== "all", catalogRuntime !== "all", catalogFit !== "all", hfSort !== "popular", vramMinGb !== "", vramMaxGb !== ""].filter(Boolean).length || "None"} active</small>
                </summary>
                <div className="models-catalog-secondary-filters">
                  <label><span>Type</span><select className="w2-input" value={catalogPurpose} onChange={e => setCatalogPurpose(e.target.value)}>
                    <option value="all">All types</option>
                    {catalogCategories.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
                  </select></label>
                  {searchMode !== "catalog" && (
                    <label><span>Sort</span><select className="w2-input" value={hfSort} onChange={e => setHfSort(e.target.value)}>
                      <option value="popular">Most popular</option>
                      <option value="downloads">Most downloaded</option>
                      <option value="likes">Most liked</option>
                      <option value="trending">Trending</option>
                      <option value="lastModified">Recent</option>
                      <option value="vram_desc">VRAM: largest first</option>
                    </select></label>
                  )}
                  {searchMode === "catalog" && !desktopOnly && (
                    <label><span>Runtime</span><select className="w2-input" value={catalogRuntime} onChange={e => setCatalogRuntime(e.target.value)}>
                      <option value="deployable">Deployable</option>
                      <option value="all">All runtimes</option>
                      {catalogRuntimes.map(r => <option key={r.id} value={r.id}>{r.label}</option>)}
                    </select></label>
                  )}
                  <label><span>Hardware fit</span><select className="w2-input" value={catalogFit} onChange={e => setCatalogFit(e.target.value)}>
                    <option value="all">Any fit</option>
                    <option value="fits">Fits safely</option>
                  </select></label>
                </div>
              </details>

              <details className="model-hardware-filters">
                <summary>
                  <span><SlidersHorizontal size={16} /><strong>Hardware</strong></span>
                  <small>CPU, system RAM & GPU capacity</small>
                </summary>
                <div className="model-vram-filter" data-testid="model-vram-filter">
                <div className="models-hardware-summary" data-testid="model-system-hardware">
                  <div className="models-hardware-fact"><Cpu size={17} /><span><small className="models-hardware-fact__label">Processor</small><strong>{systemHardware.processor}</strong><small>{systemHardware.logicalCores ? `${systemHardware.logicalCores} logical CPU threads` : "CPU thread count unavailable"}</small></span></div>
                  <div className="models-hardware-fact"><Database size={17} /><span><small className="models-hardware-fact__label">System memory</small><strong>{systemHardware.memoryTotalGb == null ? "System RAM unavailable" : `${systemHardware.memoryTotalGb.toFixed(1)} GB system RAM`}</strong><small>{systemHardware.memoryAvailableGb == null ? "Available RAM unavailable" : `${systemHardware.memoryAvailableGb.toFixed(1)} GB currently available`}</small></span></div>
                  {systemHardware.gpus.map((gpu, index) => {
                    const totalMb = Number(gpu.memoryTotalMb ?? gpu.memory_total_mb);
                    const freeMb = Number(gpu.memoryFreeMb ?? gpu.memory_free_mb);
                    return (
                      <div className="models-hardware-fact" key={`${gpu.name || "gpu"}-${index}`}><Gauge size={17} /><span><small className="models-hardware-fact__label">GPU {index + 1}</small><strong>{gpu.name || `GPU ${index + 1}`}</strong><small>{Number.isFinite(totalMb) ? `${(totalMb / 1024).toFixed(1)} GB VRAM` : "VRAM unavailable"}{Number.isFinite(freeMb) ? `, ${(freeMb / 1024).toFixed(1)} GB free` : ""}</small></span></div>
                    );
                  })}
                </div>
                <div className="model-vram-filter__capacity" data-testid="model-placement-capacity">
                  <span><small>Largest single GPU</small><strong>{gpuCapacity.largestSingleGpuGb ? gpuCapacity.largestSingleGpuGb.toFixed(1) + " GB" : "Unknown"}</strong></span>
                  <span title="Optional combined layer-sharding pool"><small>Combined layer pool</small><strong>{totalVramGb > 0 ? totalVramGb.toFixed(1) + " GB" : "Unknown"}</strong></span>
                </div>
                <label>
                  <span>Minimum VRAM</span>
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
                  <span>Maximum VRAM</span>
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
                  Use Largest GPU
                </button>
                {(vramMinGb !== "" || vramMaxGb !== "") && (
                  <button className="w2-button" type="button" onClick={() => { setVramMinGb(""); setVramMaxGb(""); }}>
                    Clear Range
                  </button>
                )}
                </div>
              </details>
              </div>

              {/* Status line */}
              <div className="models-catalog-summary" data-testid="discover-catalog-summary">
                <strong>{searchMode === "browse" ? "Available Models" : searchMode === "huggingface" ? "Search Results" : "Local Models"}</strong>
                <span>{searchMode === "catalog"
                  ? `${displayItems.length} local model${displayItems.length === 1 ? "" : "s"}`
                  : hfLoading ? "Loading available models…" : `${displayItems.length} model${displayItems.length === 1 ? "" : "s"} with hardware-fit information`}</span>
              </div>

              {searchMode !== "catalog" && hfError && (
                <div style={{ fontSize: "0.8125rem", color: "var(--ras-danger)", backgroundColor: "color-mix(in srgb, var(--ras-danger) 10%, var(--cc-surface))", border: "1px solid var(--ras-danger)", borderRadius: "6px", padding: "8px 12px" }}>
                  {hfError}
                </div>
              )}

              {downloadError && (
                <div role="alert" style={{ fontSize: "0.8125rem", color: "var(--ras-danger)", backgroundColor: "color-mix(in srgb, var(--ras-danger) 10%, var(--cc-surface))", border: "1px solid var(--ras-danger)", borderRadius: "6px", padding: "8px 12px" }} data-testid="model-download-error">
                  {downloadError}
                </div>
              )}

              {discoverInstalledModels.length > 0 && (
                <DiscoverInstalledSummary models={discoverInstalledModels} onManage={manageInstalledModel} />
              )}

              {/* Active downloads only. Completed and cancelled receipts remain out of this rail. */}
              {downloadProgressJobs.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "8px" }} data-testid="model-download-progress-rail">
                  {downloadProgressJobs.map((dl) => <ModelDownloadProgress key={downloadJobIdentity(dl) || dl.modelId || dl.repository} download={dl} onDownloadAction={onDownloadAction} onLoadArtifact={downloadJobState(dl) === "completed" ? loadCompletedArtifact : undefined} loadingArtifact={loadingArtifact === downloadJobIdentity(dl)} />)}
                </div>
              )}

              {/* Model catalog */}
              <div className="models-v3-catalog-stage" data-testid="discover-model-catalog">
                {desktopOnly && (
                  <div
                    className="models-inventory-workbench models-discover-workbench"
                    style={{ "--models-inspector-width": `${inspectorWidth}px` }}
                    data-testid="discover-model-workbench"
                  >
                    <section className="models-inventory-main" aria-labelledby="discover-catalog-title">
                      <h2 id="discover-catalog-title" className="sr-only">Available models</h2>
                      <div
                        className="models-discover-list models-inventory-table"
                        data-testid="discover-model-table"
                        data-table-kind="discover-model-table"
                        role="table"
                        aria-label="Available models"
                      >
                        <div className="models-discover-head" role="row">
                          <span role="columnheader">Model</span>
                          <span role="columnheader">Fit</span>
                          <span role="columnheader">Actions</span>
                        </div>
                        {pagedItems.map((item) => {
                          const itemId = item.id || item.modelId;
                          const installedModel = findInstalledCatalogModel(item, registeredModels);
                          return (
                            <DiscoverCatalogRow
                              key={itemId}
                              item={item}
                              selected={selectedCatalogItem === item}
                              placementFit={catalogPlacementAssessment(item, effectiveHardware)}
                              activeDownloads={activeDownloads}
                              installedModel={installedModel}
                              onSelect={() => setSelectedCatalogId(itemId)}
                              onDownload={() => {
                                setSelectedCatalogId(itemId);
                                downloadCatalogItem(item);
                              }}
                              onDownloadAction={onDownloadAction}
                              onLoadInstalled={configureNativeLoad}
                              onManageInstalled={manageInstalledModel}
                              onLoadArtifact={loadCompletedArtifact}
                            />
                          );
                        })}
                      </div>
                      {!displayItems.length && (modelCatalogLoading || hfLoading) && <SkeletonList count={5} />}
                      {!displayItems.length && !modelCatalogLoading && !hfLoading && (
                        <div className="models-inventory-empty">
                          {searchMode !== "catalog" ? "No available models found. Try refreshing or choosing a different category." : "No local models match. Try different filters."}
                        </div>
                      )}
                      <CatalogPagination
                        total={displayItems.length}
                        currentPage={currentPage}
                        pageCount={pageCount}
                        pageSize={pageSize}
                        onPageChange={setPage}
                        onPageSizeChange={setPageSize}
                        compact
                      />
                    </section>

                    <button
                      type="button"
                      className="models-inspector-resizer"
                      data-testid="discover-inspector-resizer"
                      role="separator"
                      aria-label="Resize discover model inspector"
                      aria-orientation="vertical"
                      aria-valuemin={260}
                      aria-valuemax={480}
                      aria-valuenow={inspectorWidth}
                      onPointerDown={startInspectorResize}
                      onKeyDown={handleInspectorResizeKeyDown}
                    />
                    <DiscoverModelInspector
                      key={selectedCatalogItem?.id || selectedCatalogItem?.modelId || "empty"}
                      item={selectedCatalogItem}
                      installedModel={findInstalledCatalogModel(selectedCatalogItem, registeredModels)}
                      installedModels={registeredModels}
                      activeTab={discoverInspectorTab}
                      onTabChange={setDiscoverInspectorTab}
                      placementFit={selectedCatalogItem ? catalogPlacementAssessment(selectedCatalogItem, effectiveHardware) : null}
                      hardwareBlocked={normalizedHardware.blocked}
                      hardwareBlockReasons={normalizedHardware.blockedReasons}
                      prepareCatalogModelForWarsat={prepareCatalogModelForWarsat}
                      searchMode={searchMode}
                      startDownload={startDownload}
                      downloadCatalogItem={downloadCatalogItem}
                      onDownloadAction={onDownloadAction}
                      activeDownloads={activeDownloads}
                      loadCompletedArtifact={loadCompletedArtifact}
                      loadingArtifact={loadingArtifact}
                      onLoadInstalled={configureNativeLoad}
                      onManageInstalled={manageInstalledModel}
                    />
                  </div>
                )}
                {!desktopOnly && (
                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" data-testid="model-catalog-grid">
                    {pagedItems.map(item => (
                      <CatalogCard
                        key={item.id || item.modelId}
                        item={item}
                        placementFit={catalogPlacementAssessment(item, effectiveHardware)}
                        hardwareBlocked={normalizedHardware.blocked}
                        hardwareBlockReasons={normalizedHardware.blockedReasons}
                        prepareCatalogModelForWarsat={prepareCatalogModelForWarsat}
                        searchMode={searchMode}
                        startDownload={startDownload}
                        loadCompletedArtifact={loadCompletedArtifact}
                        activeDownloads={activeDownloads}
                        desktopOnly={nativeModels}
                        installedModel={findInstalledCatalogModel(item, registeredModels)}
                        installedModels={registeredModels}
                        onLoadInstalled={configureNativeLoad}
                        onManageInstalled={manageInstalledModel}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Pagination */}
              {!desktopOnly && displayItems.length > 0 && (
                <div className="models-native-pagination" style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "10px", padding: "6px 0" }}>
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
              {!desktopOnly && !displayItems.length && (modelCatalogLoading || hfLoading) && (
                <SkeletonList count={5} />
              )}

              {!desktopOnly && !displayItems.length && !modelCatalogLoading && !hfLoading && (
                <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>
                  {searchMode !== "catalog" ? "No available models found. Try refreshing or choosing a different category." : "No local models match. Try different filters."}
                </div>
              )}
                </>
              )}
            </div>
          )}

          {/* ═══ INSTALLED TAB ═══ */}
          {activeTab === "installed" && (
            <div id="models-panel-installed" role="tabpanel" aria-labelledby="models-tab-installed" className="w2-section models-v3-panel studio-installed-panel" style={{ flex: 1 }}>
              <div className="models-inventory-workbench" style={{ "--models-inspector-width": `${inspectorWidth}px` }}>
                <section className="models-inventory-main" aria-labelledby="models-inventory-title">
                  <header className="model-library-welcome">
                    <div><span className="model-library-eyebrow">Your library</span><h2>Choose a model. Start a conversation.</h2><p>See what's ready, load a saved model, or fix a connection here.</p></div>
                    <div className="model-library-add-actions"><UIButton type="button" onClick={() => setActiveTab("library")}><Search size={15} /> Find a model</UIButton><UIButton type="button" variant="outline" onClick={() => setShowModelSources((value) => !value)} aria-expanded={showModelSources} aria-controls="model-library-sources">Add existing model</UIButton></div>
                  </header>
                  {showModelSources && <div id="model-library-sources"><LocalModelSources onImported={loadModels} /></div>}
                  <div className="model-library-filters" role="group" aria-label="Filter models by availability">
                    {[
                      ["all", "All models", installedModels.length],
                      ["ready", "Ready to use", installedModels.filter((item) => modelOperationalSignal(item).key === "live").length],
                      ["idle", "Not loaded", installedModels.filter((item) => modelOperationalSignal(item).label === "Not loaded").length],
                      ["help", "Needs a fix", installedModels.filter((item) => modelOperationalSignal(item).key === "down").length],
                    ].map(([id, label, count]) => <button type="button" key={id} aria-pressed={libraryStatus === id} onClick={() => setLibraryStatus(id)}><span>{label}</span><strong>{count}</strong></button>)}
                  </div>
                  <div className="models-inventory-toolbar">
                    <div className="models-inventory-heading">
                      <h2 id="models-inventory-title">My models</h2>
                      <label className="models-inventory-category">
                        <span className="sr-only">Model category</span>
                        <select value={installedCategory} onChange={(event) => setInstalledCategory(event.target.value)}>
                          <option value="all">All</option>
                          <option value="llm">LLMs</option>
                          <option value="embedding">Text Embedding</option>
                        </select>
                      </label>
                    </div>
                    <label className="models-inventory-search">
                      <Search size={15} aria-hidden="true" />
                      <span className="sr-only">Filter installed models</span>
                      <input
                        ref={installedSearchInputRef}
                        type="search"
                        value={installedSearch}
                        onChange={(event) => setInstalledSearch(event.target.value)}
                        placeholder="Filter models… (Ctrl + F)"
                        aria-label="Filter installed models"
                      />
                    </label>
                    <div className="models-inventory-tools">
                      <button className="w2-button" type="button" onClick={handleScanGguf}><HardDrive size={14} /> Find local files</button>
                      <button className="w2-button" type="button" onClick={handleRefresh}><RefreshCw size={14} /> Refresh</button>
                    </div>
                  </div>

                  <div className="studio-installed-list models-inventory-table" data-testid="studio-installed-list" role="list" aria-label="Your models">
                    {filteredInstalledModels.map(model => (
                      <InstalledCard
                        key={model.key}
                        model={model}
                        allModels={models}
                        selected={selectedInstalledModel?.key === model.key}
                        chatActive={selectedModel === model.key}
                        onSelect={() => {
                          setSelectedInstalledKey(model.key);
                          setInstalledInspectorTab("info");
                          if (window.matchMedia("(max-width: 1100px)").matches) requestAnimationFrame(() => document.getElementById("installed-model-inspector")?.scrollIntoView({ block: "start" }));
                        }}
                        onUseInChat={(item) => { setSelectedModel?.(item.key); go?.("chat"); }}
                        runModelAction={runModelAction}
                        executeAction={executeAction}
                        setUiState={setUiState}
                        nativeModels={nativeModels}
                        onConfigureLoad={configureNativeLoad}
                        onOpenActions={() => {
                          setSelectedInstalledKey(model.key);
                          setInstalledInspectorTab("actions");
                        }}
                      />
                    ))}
                  </div>

                  {!filteredInstalledModels.length && (
                    <div className="models-inventory-empty">
                      <h3>{installedModels.length ? "No models in this view" : "Your first model starts here"}</h3>
                      <p>{installedModels.length ? "Try a different filter or search term." : "Find a model to download, or add one you already have."}</p>
                      {installedModels.length ? <button type="button" className="w2-button" onClick={() => { setLibraryStatus("all"); setInstalledCategory("all"); setInstalledSearch(""); }}>Clear filters</button> : <button type="button" className="w2-button primary" onClick={() => setActiveTab("library")}>Find a model</button>}
                    </div>
                  )}
                  <footer className="models-inventory-footer">
                    <span>{filteredInstalledModels.length} of {installedModels.length} models</span>
                    <span>{reachableModels.length} reachable · {runningModels.length} loaded</span>
                  </footer>
                </section>

                <button
                  type="button"
                  className="models-inspector-resizer"
                  data-testid="models-inspector-resizer"
                  role="separator"
                  aria-label="Resize model inspector"
                  aria-orientation="vertical"
                  aria-valuemin={260}
                  aria-valuemax={480}
                  aria-valuenow={inspectorWidth}
                  onPointerDown={startInspectorResize}
                  onKeyDown={handleInspectorResizeKeyDown}
                />
                <InstalledModelInspector
                  model={selectedInstalledModel}
                  chatActive={selectedModel === selectedInstalledModel?.key}
                  activeTab={installedInspectorTab}
                  onTabChange={setInstalledInspectorTab}
                  allModels={models}
                  onUseInChat={(model) => {
                    setSelectedModel?.(model.key);
                    go?.("chat");
                  }}
                  runModelAction={runModelAction}
                  executeAction={executeAction}
                  setUiState={setUiState}
                  nativeModels={nativeModels}
                  onConfigureLoad={configureNativeLoad}
                  onSaved={loadModels}
                  onFindModels={() => setActiveTab("library")}
                />
              </div>
            </div>
          )}

          {/* ═══ RUNNING TAB ═══ */}
          {activeTab === "running" && (
            <div id="models-panel-running" role="tabpanel" aria-labelledby="models-tab-running" className="w2-section models-v3-panel models-v3-running" style={{ flex: 1 }}>
              <ActiveModelCard
                model={activeModel}
                models={models}
                healthy={healthy}
                status={status}
                runModelAction={runModelAction}
                executeAction={executeAction}
                setUiState={setUiState}
                openWarsat={openWarsat}
                desktopOnly={nativeModels}
              />

              {runningModels.length > 0 && (
                <div className="w2-card">
                  <h3 style={{ margin: 0, fontSize: "0.875rem" }}>Active Deployments ({runningModels.length})</h3>
                  {runningModels.map(m => (
                    <div key={m.key} className="w2-list-item">
                      <div className="models-source-switcher">
                        <Activity size={14} color="var(--ras-safe)" />
                        <div>
                          <strong style={{ fontSize: "0.8125rem" }}>{displayModelName(m, models)}</strong>
                          <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>{m.runtime || m.provider} · {labelize(m.role || "chat")}</div>
                        </div>
                      </div>
                      <ModelStateSignal signal={modelOperationalSignal(m)} chatActive={selectedModel === m.key} compact />
                    </div>
                  ))}
                </div>
              )}

              <InfraStatusCard warsatHardware={warsatHardware} warsatRuntimes={warsatRuntimes} warsat={warsat} desktopOnly={nativeModels} />
            </div>
          )}

          {activeTab === "serving" && (
            <div id="models-panel-serving" role="tabpanel" aria-labelledby="models-tab-serving" className="w2-section models-v3-panel models-serving-tab" style={{ flex: 1 }}>
              <ModelServingPanel onOpenModels={() => setActiveTab("running")} />
            </div>
          )}

          {/* ═══ SETTINGS TAB ═══ */}
          {activeTab === "settings" && (
            <div id="models-panel-settings" role="tabpanel" aria-labelledby="models-tab-settings" className="w2-section models-v3-panel models-developer-panel" style={{ flex: 1 }}>
              <header className="models-developer-header" data-testid="models-developer-header">
                <div className="models-runtime-state">
                  <span aria-hidden="true" />
                  <div>
                    <strong>Native model runtime</strong>
                    <small>Rasputin Desktop owns the local llama.cpp process.</small>
                  </div>
                </div>
                <div className="models-runtime-contract">
                  <Badge variant="up">Loopback only</Badge>
                  <Badge variant="muted">Runtime on demand</Badge>
                  <Badge variant="muted">No Docker</Badge>
                </div>
              </header>
              {/* Testing Mode */}
              <div className="w2-card models-testing-card">
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
              <div className="w2-card models-connection-card">
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
              <div className="w2-card models-connection-card">
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

              {/* Native runtime */}
              {desktopOnly ? (
                <div className="w2-card models-native-runtime-card" data-testid="native-runtime-settings">
                  <h3 style={{ margin: 0, fontSize: "0.875rem" }}><Cpu size={14} style={{ verticalAlign: "-2px" }} /> Native llama.cpp Runtime</h3>
                  <p style={{ fontSize: "0.75rem", color: "var(--cc-muted)", margin: 0 }}>Rasputin detects this machine and downloads one verified llama.cpp runtime on first model load. Later loads reuse it. No Docker, Python, Node, or manual runtime install is required.</p>
                </div>
              ) : (
                <div className="w2-card">
                  <h3 style={{ margin: 0, fontSize: "0.875rem" }}><Play size={14} style={{ verticalAlign: "-2px" }} /> Warsat Deployment</h3>
                  <p style={{ fontSize: "0.75rem", color: "var(--cc-muted)", margin: 0 }}>Use Warsat to deploy local model endpoints via Docker.</p>
                  <button className="w2-button primary" type="button" onClick={openWarsat} style={{ alignSelf: "flex-start" }}><Play size={14} /> Open Warsat</button>
                </div>
              )}

              {/* Full registry list */}
              <div className="w2-card models-registry-card">
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

        {/* Discover keeps the server-mode context column. My Models already
            owns a persistent inspector, so never duplicate it beside the table. */}
        {!desktopOnly && activeTab !== "installed" && (
          <div className="w2-column">
            <RightPanel
              activeTab={activeTab}
              activeModel={activeModel}
              models={models}
              healthy={healthy}
              status={status}
              warsatHardware={warsatHardware}
              desktopOnly={nativeModels}
            />
          </div>
        )}
      </div>
      </div>
      <ModelLoadDialog
        model={loadDialogModel}
        models={models}
        hardware={effectiveHardware}
        onClose={() => setLoadDialogModel(null)}
        onLoad={async (model, profile) => {
          await runModelAction?.("start", model.key, { profile });
          setUiState({ status: "success", message: "Model loaded with the selected llama.cpp profile." });
        }}
      />
    </section>
  );

  return modelsSurface;
}
