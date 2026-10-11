import { needsNativeModelDownload } from "./nativeDeployment.js";

import { isManagedModelRunning } from "../../lib/display.js";

import { api, postJson } from "../../api/client.js";

import { findInstalledCatalogModel } from "./modelEcosystem.js";
import { artifactModelMatch, catalogDownloadFor, completedArtifactFor, downloadJobIdentity, downloadJobState, preferredDownloadVariant, variantCompatibility } from "./downloadState.js";

import { normalizeHuggingFaceSearchInput } from "./advisorSelection.js";
import { catalogModelId } from "./modelPresentation.js";

export function useModelActions(context) {
  const {
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
  } = context;

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
  const submitHfSearch = (event) => {
    event?.preventDefault?.();
    const query = normalizeHuggingFaceSearchInput(hfSearchDraft);
    if (!query) {
      setHfResults([]);
      setHfError("Enter a model name, org/model ID, or Hugging Face URL.");
      requestAnimationFrame(() => hfSearchInputRef.current?.focus());
      return;
    }
    setHfSearchDraft(query);
    setHfQuery(query);
    setHfError("");
    setSearchMode("huggingface");
    setPage(1);
  };
  const configureNativeLoad = async (model) => {
    if (!needsNativeModelDownload(model, nativeModels)) {
      setLoadDialogModel(model);
      return;
    }
    const path = model.hostModelPath || model.host_model_path || model.modelPath;
    if (path && String(path).toLowerCase().endsWith(".gguf")) {
      const imported = await prepareCatalogModelForWarsat?.(model);
      if (imported?.key) setLoadDialogModel(imported);
      return;
    }
    const source = model.repository || model.warsatModelRef || model.model || model.name || "";
    const query = String(source).split("/").pop().replace(/\.gguf$/i, "") + " GGUF";
    nativeRecoveryQueryRef.current = query;
    go?.("discover");
    setActiveTab("library");
    openSpecificHuggingFaceModel();
    setHfSearchDraft(query);
    setHfQuery(query);
    setUiState({ status: "info", message: "This entry uses a retired runtime. Choose a GGUF version below for native llama.cpp." });
  };
  const handleAdvisorRefresh = () => {
    setAdvisorRefreshToken((value) => value + 1);
    if (!warsatHardware) setHardwareRefreshToken((value) => value + 1);
  };
  const startDownload = async (modelId, variant = null) => {
    try {
      const installed = findInstalledCatalogModel({ modelId }, registeredModels, variant);
      if (installed) {
        await configureNativeLoad(installed);
        return true;
      }
      if (nativeModels && !variant) throw new Error("Choose a compatible GGUF variant for native llama.cpp; raw model weights cannot be loaded here.");
      if (variant && !variantCompatibility(variant).safe) throw new Error(variantCompatibility(variant).reasons[0] || "This GGUF variant is incompatible. Choose another variant.");
      const body = variant ? { modelId, variant } : { modelId };
      await postJson("/api/models/download", body);
      setDownloadRefreshToken((value) => value + 1);
      setUiState({ status: "success", message: "Started download of " + (variant?.id || modelId) });
      return true;
    } catch (e) {
      setUiState({ status: "failed", message: "Failed to start download: " + (e.message || "unknown error") });
      return false;
    }
  };
  const onDownloadAction = async (action, jobId) => {
    if (!jobId || !["pause", "resume", "cancel", "retry"].includes(action)) return;
    try {
      await postJson("/api/models/downloads/" + encodeURIComponent(jobId) + "/" + action, {});
      setDownloadRefreshToken((value) => value + 1);
    } catch (e) {
      setDownloadError("Unable to " + action + " download: " + (e.message || "unknown error"));
    }
  };

  const downloadCatalogItem = async (item) => {
    const modelId = catalogModelId(item);
    const installedModel = findInstalledCatalogModel(item, registeredModels);
    if (installedModel) {
      await configureNativeLoad(installedModel);
      return;
    }
    const existing = catalogDownloadFor(item, activeDownloads);
    const existingState = existing ? downloadJobState(existing) : "";
    if (existing && !["completed", "failed", "cancelled"].includes(existingState)) {
      await onDownloadAction("cancel", downloadJobIdentity(existing));
      return;
    }
    if (existingState === "completed") {
      setSelectedCatalogId(item.id || item.modelId);
      setDiscoverInspectorTab("download");
      return;
    }
    if (searchMode === "catalog" && item.source !== "huggingface") {
      await prepareCatalogModelForWarsat?.(item);
      return;
    }
    setUiState({ status: "running", message: "Choosing a balanced GGUF download for " + modelId + "..." });
    try {
      const encodedModelId = modelId.split("/").map(encodeURIComponent).join("/");
      const detail = await api("/api/model-catalog/model/" + encodedModelId);
      if (detail?.error) throw new Error(detail.error);
      const variants = Array.isArray(detail?.variants) ? detail.variants : [];
      const capabilities = [...(item.capabilities || []), ...(item.modalities || [])]
        .map((value) => String(value).toLowerCase());
      const preferred = preferredDownloadVariant(variants, capabilities.some((value) => ["vision", "image", "multimodal"].includes(value)));
      await startDownload(modelId, preferred);
    } catch (error) {
      setUiState({ status: "failed", message: "Failed to start download: " + (error?.message || "unknown error") });
    }
  };

  const manageInstalledModel = (model) => {
    if (!model?.key) return;
    setInstalledSearch("");
    setInstalledCategory("all");
    setSelectedInstalledKey(model.key);
    setInstalledInspectorTab(isManagedModelRunning(model) ? "load" : "info");
    setActiveTab("installed");
    go?.("models");
  };

  const loadCompletedArtifact = async (download) => {
    const artifact = completedArtifactFor(download);
    const identity = downloadJobIdentity(download);
    setLoadingArtifact(identity);
    try {
      let registry = models || [];
      let model = artifactModelMatch(registry, artifact);
      if (!model && loadModels) {
        registry = await loadModels();
        model = artifactModelMatch(registry, artifact);
      }
      if (!model?.key) {
        throw new Error("The completed artifact is not available in the model registry yet. Use Refresh and try Load again.");
      }
      setLoadDialogModel(model);
      setUiState({ status: "success", message: "Download complete. Review load settings, then start the model." });
    } catch (error) {
      setUiState({ status: "failed", message: "Unable to load completed model: " + (error?.message || "unknown error") });
    } finally {
      setLoadingArtifact(null);
    }
  };

  return { handleRefresh, handleScanGguf, handleLoadCatalog, openSpecificHuggingFaceModel, submitHfSearch, configureNativeLoad, handleAdvisorRefresh, startDownload, onDownloadAction, downloadCatalogItem, manageInstalledModel, loadCompletedArtifact };
}
