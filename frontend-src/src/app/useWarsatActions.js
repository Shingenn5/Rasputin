import { api, postJson, postJsonStream } from "../api/client.js";

import { usesNativeModels, prepareNativeModel } from "../features/models/nativeDeployment.js";
import { preferredDownloadVariant } from "../features/models/ModelsView.jsx";

import { useSettingsStore } from "../features/settings/settingsStore.js";

import { ENGINE_PROTOCOLS } from "../lib/engines.js";

export function useWarsatActions(context) {
  const {
    security,
    setWarsatHardware,
    nativeModels,
    setWarsat,
    setWarsatRuntimes,
    loadModels,
    setSelectedModel,
    setGlobalStatus,
    setWarsatError,
    warsatHardware,
    setWarsatPlan,
    setWarsatDeployment,
    go,
    setWarsatLogs,
    warsatOperation,
    setWarsatOperation,
    refreshApprovals,
    warsatPlan,
    setWarsatDeploying,
    warsatDeployment,
    loadAssistantData,
  } = context;

  async function loadWarsatHardware(nativeModels = usesNativeModels(security)) {
    if (security?.native === undefined && security?.desktopOnly === undefined) return null;
    const hardware = await api(nativeModels ? "/api/warsat/hardware?native_models=true" : "/api/warsat/hardware").catch((error) => ({
      ok: false,
      status: "blocked",
      checks: [],
      warnings: [],
      blockedReasons: [error.message],
      recommendations: ["Check the Rasputin backend logs for Warsat hardware probe errors."],
      detectedHardware: {},
    }));
    setWarsatHardware(hardware);
    return hardware;
  }

  async function loadWarsat() {
    // Bootstrap may not have resolved when a saved legacy hash is restored.
    // Never probe retired providers unless a legacy runtime is explicit.
    if (nativeModels || security?.native !== false) return null;
    const [nextWarsat, runtimes, hardware] = await Promise.all([
      api("/api/warsat/protocols"),
      api("/api/warsat/runtimes"),
      loadWarsatHardware(false),
    ]);
    setWarsat(nextWarsat);
    setWarsatRuntimes(runtimes);
    return { warsat: nextWarsat, runtimes, hardware };
  }

  async function prepareCatalogModelForWarsat(item, options = {}) {
    if (!item) return null;
    if (usesNativeModels(security)) {
      try {
        const result = await prepareNativeModel(item, options, { api, postJson, selectVariant: preferredDownloadVariant });
        if (result.key) {
          await loadModels();
          setSelectedModel(result.key);
          setGlobalStatus("Imported the GGUF into the native llama.cpp library. Choose Load Model to start it.");
        } else {
          setGlobalStatus("GGUF download started. Rasputin will register it for native llama.cpp when complete.");
        }
        return result;
      } catch (error) {
        setGlobalStatus(error.message);
        return null;
      }
    }
    // Honor the Default Inference Engine setting when this model actually
    // offers that runtime; explicit choices and API-only entries still win.
    const preferredProtocol = ENGINE_PROTOCOLS[useSettingsStore.getState().models?.defaultEngine];
    const engineProtocol = preferredProtocol && item.runtimeOptions?.some((option) => option.protocolId === preferredProtocol)
      ? preferredProtocol
      : null;
    const protocolId = options.protocolId || engineProtocol || item.recommendedProtocol || item.runtimeOptions?.[0]?.protocolId || "vllmCudaOpenai";
    if (!protocolId || protocolId === "apiOnly") {
      setGlobalStatus("This catalog entry is API-only. Register it as an API model instead of sending it to Warsat.");
      return null;
    }
    const profile = options.strengthProfile || item.recommendedProfile || "balanced";
    const modelRef = item.warsatModelRef || item.modelId || item.id;
    const port = Number(options.hostPort || 0) || undefined;
    const toolCallParser = options.toolCallParser || item.toolCallParserHint || undefined;
    setWarsatError("");
    try {
      const loaded = await loadWarsat();
      const plan = await postJson("/api/warsat/plan", {
        protocolId,
        modelRef,
        modelRevision: options.modelRevision || item.modelRevision || item.model_revision || undefined,
        contextWindow: Number(options.contextWindow || 0) || undefined,
        multiGpu: options.multiGpu === true ? true : undefined,
        benchmarkCertificateId: options.benchmarkCertificateId || undefined,
        concurrency: Number(options.concurrency || 0) || undefined,
        // Only a real local file/folder goes in modelPath; for HF repos the
        // backend resolves a GGUF file and lets llama.cpp download it.
        modelPath: item.modelPath || undefined,
        strengthProfile: profile,
        hostPort: port,
        role: options.role || (item.purpose === "coding" ? "coder" : item.purpose === "research" ? "researcher" : "helper"),
        maxModelLen: !options.contextWindow && item.contextWindow && item.contextWindow <= 32768 ? item.contextWindow : undefined,
        vramEstimateGb: item.vramEstimateGb || undefined,
        quantization: options.quantization || item.quantization || undefined,
        resourceManifest: item.resourceManifest || undefined,
        capabilityProfile: loaded?.hardware?.capabilityProfile || warsatHardware?.capabilityProfile || undefined,
        containerName: options.containerName || undefined,
        assistantRequestId: options.assistantRequestId || undefined,
        // Catalog hints are deliberately conservative. When one is present,
        // use it so a known tool-capable model is deployed agent-ready.
        toolCallParser,
      });
      setWarsatPlan(plan);
      setWarsatDeployment(null);
      go("warsat");
      // Surface fit problems the moment the plan lands, not at deploy time.
      const fitWarning = (plan.warnings || []).find((w) => w.includes("VRAM"));
      setGlobalStatus(fitWarning
        ? `Plan created for ${item.name || modelRef} — heads-up: ${fitWarning}`
        : `Warsat launch plan created for ${item.name || modelRef}.`);
      return plan;
    } catch (error) {
      setWarsatError(error.message);
      setGlobalStatus(error.message);
      return null;
    }
  }

  async function loadWarsatRuntimes() {
    const runtimes = await api("/api/warsat/runtimes");
    setWarsatRuntimes(runtimes);
    return runtimes;
  }

  async function loadWarsatLogs(containerName) {
    if (!containerName) return null;
    try {
      const logs = await postJson("/api/warsat/logs", { containerName, limit: 160 });
      setWarsatLogs(logs);
      return logs;
    } catch (error) {
      setGlobalStatus(error.message);
      return null;
    }
  }

  async function requestWarsatOperation(action, containerName) {
    if (!containerName) return null;
    const currentApprovalId = warsatOperation?.containerName === containerName && warsatOperation?.action === action
      ? warsatOperation?.approval?.id || warsatOperation?.approvalId
      : null;
    try {
      const result = await postJson(`/api/warsat/${action}`, { containerName, approvalId: currentApprovalId });
      setWarsatOperation({ ...result, action });
      if (result.approvalRequired) {
        await refreshApprovals();
        setGlobalStatus(`Approval ${result.approval?.code || ""} created. Approve it before Warsat can ${action} ${containerName}.`);
      } else {
        await Promise.allSettled([loadWarsatRuntimes(), loadModels(), refreshApprovals()]);
        setGlobalStatus(`Warsat ${action} completed for ${containerName}.`);
      }
      return result;
    } catch (error) {
      setGlobalStatus(error.message);
      return null;
    }
  }

  async function createWarsatPlan(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const gpuLayers = form.get("gpuLayers");
    setWarsatError("");
    try {
      const hardware = await loadWarsatHardware();
      const plan = await postJson("/api/warsat/plan", {
        protocolId: form.get("protocolId"),
        modelRef: form.get("modelRef") || undefined,
        modelPath: form.get("modelPath") || undefined,
        strengthProfile: form.get("strengthProfile") || undefined,
        contextWindow: Number(form.get("contextWindow") || 0) || undefined,
        maxModelLen: Number(form.get("maxModelLen") || 0) || undefined,
        gpuMemoryUtilization: Number(form.get("gpuMemoryUtilization") || 0) || undefined,
        gpuLayers: gpuLayers == null || gpuLayers === "" ? undefined : Number(gpuLayers),
        tensorParallelSize: Number(form.get("tensorParallelSize") || 0) || undefined,
        multiGpu: form.get("multiGpu") === "on",
        cpuThreads: Number(form.get("cpuThreads") || 0) || undefined,
        batchSize: Number(form.get("batchSize") || 0) || undefined,
        maxNumSeqs: Number(form.get("maxNumSeqs") || 0) || undefined,
        dtype: form.get("dtype") || undefined,
        quantization: form.get("quantization") || undefined,
        kvCacheDtype: form.get("kvCacheDtype") || undefined,
        swapSpaceGb: Number(form.get("swapSpaceGb") || 0) || undefined,
        memoryLimitGb: Number(form.get("memoryLimitGb") || 0) || undefined,
        cpuLimit: Number(form.get("cpuLimit") || 0) || undefined,
        shmSizeGb: Number(form.get("shmSizeGb") || 0) || undefined,
        gpuDevice: form.get("gpuDevice") || undefined,
        hostPort: Number(form.get("hostPort") || 0) || undefined,
        role: form.get("role") || undefined,
        containerName: form.get("containerName") || undefined,
        toolCallParser: form.get("toolCallParser") || undefined,
        capabilityProfile: hardware?.capabilityProfile || warsatHardware?.capabilityProfile || undefined,
      });
      setWarsatPlan(plan);
      setWarsatDeployment(null);
      setGlobalStatus("Launch plan ready — review the Mission Brief below, then request deploy approval.");
      return plan;
    } catch (error) {
      setWarsatError(error.message);
      setWarsatPlan(null);
      return null;
    }
  }

  async function deployWarsatPlan() {
    if (!warsatPlan) return null;
    setWarsatError("");
    setWarsatDeploying(true);
    const approvalId = warsatDeployment?.approval?.id || warsatDeployment?.approvalId;
    const assistantRequestId = warsatPlan.assistantRequestId;
    setGlobalStatus(approvalId || warsatPlan.approvalGranted
      ? "Warsat is starting the deployment. Large image pulls stream their progress below."
      : "Creating Warsat deployment approval.");
    try {
      // The endpoint streams NDJSON progress when the deploy executes and
      // answers plain JSON when it only creates an approval request —
      // postJsonStream handles both.
      const deployment = await postJsonStream("/api/warsat/deploy", { plan: warsatPlan, approvalId }, (partial) => {
        setWarsatDeployment(partial);
      });
      setWarsatDeployment(deployment);
      if (deployment.approvalRequired) {
        await refreshApprovals();
        setGlobalStatus(`Approval ${deployment.approval?.code || ""} created. Approve it in Warsat, then run the approved deploy.`);
      } else if (deployment.status === "starting") {
        await Promise.allSettled([loadWarsat(), loadModels(), refreshApprovals()]);
        setGlobalStatus(`Warsat registered ${deployment.modelKey}; its container is still downloading or warming up. Leave it running until it reports healthy.`);
      } else if (deployment.status === "failed") {
        await Promise.allSettled([loadWarsat(), refreshApprovals()]);
        setGlobalStatus(`Warsat deployment failed during ${deployment.failedPhase || deployment.phase || "deployment"}. Check the launch plan details.`);
      } else {
        await Promise.allSettled([loadWarsat(), loadModels(), refreshApprovals()]);
        setGlobalStatus(`Warsat registered ${deployment.modelKey}. You can test and select it from Models.`);
      }
      if (deployment.status === "registered" && deployment.modelKey && assistantRequestId) {
        const verification = await postJson(
          `/api/assistant/model-requests/${encodeURIComponent(assistantRequestId)}/verify`,
          { modelKey: deployment.modelKey },
        );
        await Promise.allSettled([loadAssistantData(), loadModels()]);
        if (verification?.status === "selected") {
          setSelectedModel(deployment.modelKey);
          setGlobalStatus(`Assistant verified and selected ${deployment.modelKey}.`);
        }
      }
      return deployment;
    } catch (error) {
      setWarsatError(error.message);
      setGlobalStatus(error.message);
      return null;
    } finally {
      setWarsatDeploying(false);
    }
  }

  return { loadWarsatHardware, loadWarsat, prepareCatalogModelForWarsat, loadWarsatLogs, requestWarsatOperation, createWarsatPlan, deployWarsatPlan };
}
