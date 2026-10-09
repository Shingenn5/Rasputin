import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  ExternalLink,
  Gauge,
  HardDrive,
  Play,
  Search,
  Square,
} from "lucide-react";
import { isManagedModelRunning, labelize } from "../../lib/display.js";
import { api } from "../../api/client.js";
import { Badge } from "@/components/ui/badge.jsx";
import { blockerGuidanceForReasons } from "../shared/blockerGuidance.js";
import { PublisherLogo } from "./PublisherLogo.jsx";
import { findInstalledCatalogModel } from "./modelEcosystem.js";
import {
  catalogModelFormat,
  catalogModelId,
  catalogParameterLabel,
  catalogPublisher,
  contextWindowFor,
  installedModelFile,
} from "./modelPresentation.js";
import { catalogPlacementAssessment, catalogSystemRamEstimateGb, catalogVramEstimateGb } from "./modelPlacement.js";
import {
  catalogDownloadFor,
  downloadJobIdentity,
  downloadJobState,
  formatDownloadBytes,
  preferredDownloadVariant,
  trustedDownloadProgress,
  variantCompatibility,
  variantTotalBytes,
} from "./downloadState.js";

export function DiscoverModelInspector({
  item,
  installedModel: repositoryModel,
  installedModels,
  activeTab,
  onTabChange,
  placementFit,
  hardwareBlocked = false,
  hardwareBlockReasons = [],
  prepareCatalogModelForWarsat,
  searchMode,
  startDownload,
  downloadCatalogItem,
  onDownloadAction,
  activeDownloads,
  loadCompletedArtifact,
  loadingArtifact,
  onLoadInstalled,
  onManageInstalled,
}) {
  const [variantDetail, setVariantDetail] = useState(null);
  const [variantDetailLoading, setVariantDetailLoading] = useState(false);
  const [variantDetailError, setVariantDetailError] = useState("");
  const [selectedVariantId, setSelectedVariantId] = useState("");

  if (!item) {
    return (
      <aside id="discover-model-inspector" className="models-model-inspector is-empty" data-testid="discover-model-inspector">
        <Search size={24} />
        <p>Select a model to review its developer, hardware fit, available GGUF files, and download options.</p>
      </aside>
    );
  }

  const modelId = catalogModelId(item);
  const modelName = String(item.name || modelId.split("/").pop() || modelId);
  const developer = catalogPublisher(item);
  const isHuggingFace = searchMode !== "catalog" || item.source === "huggingface";
  const placement = placementFit || catalogPlacementAssessment(item, null);
  const itemBlockedReasons = Array.isArray(item.blockedReasons) ? item.blockedReasons : [];
  const blockedReasons = [...new Set([...hardwareBlockReasons, ...itemBlockedReasons])];
  const blocked = hardwareBlocked || blockedReasons.length > 0 || !placement.canDeploy;
  const guidance = blockerGuidanceForReasons([...blockedReasons, ...(blocked ? placement.reasons || [] : [])]);
  const variants = Array.isArray(variantDetail?.variants) ? variantDetail.variants : [];
  const selectedVariant = variants.find((variant) => variant.id === selectedVariantId) || null;
  const selectedCompatibility = selectedVariant ? variantCompatibility(selectedVariant) : null;
  const variantIssues = Array.isArray(variantDetail?.variantIssues) ? variantDetail.variantIssues : [];
  const activeDownload = catalogDownloadFor(item, activeDownloads);
  const activeDownloadState = activeDownload ? downloadJobState(activeDownload) : "";
  const isDownloading = Boolean(activeDownload && !["completed", "failed", "cancelled"].includes(activeDownloadState));
  const downloadedReceipt = !selectedVariant && activeDownloadState === "completed";
  const installedModel = selectedVariant
    ? findInstalledCatalogModel(item, installedModels, selectedVariant)
    : repositoryModel;
  const installed = Boolean(installedModel);
  const installedRunning = installed && isManagedModelRunning(installedModel);
  const context = contextWindowFor(item);
  const updated = item.lastModified || item.updatedAt || item.updated_at;
  const capabilities = Array.isArray(item.capabilities) ? item.capabilities : [];
  const modalities = Array.isArray(item.modalities) ? item.modalities : capabilities.filter((capability) => ["text", "image", "audio", "vision"].includes(String(capability).toLowerCase()));
  const vramEstimate = catalogVramEstimateGb(item);
  const systemRamEstimate = catalogSystemRamEstimateGb(item);
  const tabs = ["info", "download", "fit", "source"];

  const loadVariantDetail = async () => {
    if (!isHuggingFace) return;
    setVariantDetailLoading(true);
    setVariantDetailError("");
    try {
      const encodedModelId = modelId.split("/").map(encodeURIComponent).join("/");
      const detail = await api("/api/model-catalog/model/" + encodedModelId);
      if (detail?.error) throw new Error(detail.error);
      setVariantDetail(detail);
      const nextVariants = Array.isArray(detail?.variants) ? detail.variants : [];
      setSelectedVariantId((current) => current && nextVariants.some((variant) => variant.id === current)
        ? current
        : (preferredDownloadVariant(nextVariants)?.id || ""));
    } catch (error) {
      setVariantDetailError("Unable to load exact GGUF variants: " + (error?.message || "unknown error"));
    } finally {
      setVariantDetailLoading(false);
    }
  };

  const activeDownloadId = downloadJobIdentity(activeDownload);
  const runPrimaryAction = async () => {
    if (installedRunning) {
      onManageInstalled?.(installedModel);
      return;
    }
    if (installed) {
      await onLoadInstalled?.(installedModel);
      return;
    }
    onTabChange("download");
    if (downloadedReceipt) {
      await loadCompletedArtifact?.(activeDownload);
      return;
    }
    if (isDownloading) {
      await onDownloadAction?.("cancel", activeDownloadId);
      return;
    }
    if (!isHuggingFace) {
      await prepareCatalogModelForWarsat?.(item);
      return;
    }
    if (selectedVariant) {
      if (selectedCompatibility?.safe) await startDownload(modelId, selectedVariant);
      return;
    }
    await downloadCatalogItem?.(item);
  };

  const primaryLabel = installedRunning
    ? "Manage in My Models"
    : installed
      ? "Load model"
      : isDownloading
    ? "Stop"
    : downloadedReceipt
      ? (loadingArtifact === activeDownloadId ? "Loading…" : "Load model")
      : !isHuggingFace
        ? "Prepare model"
        : "Download";
  const primaryDisabled = !installed && ((selectedVariant && !selectedCompatibility?.safe) || (downloadedReceipt && (!activeDownloadId || loadingArtifact === activeDownloadId)) || (isDownloading && !activeDownloadId));
  const exactDownloadDisabled = isDownloading || !selectedVariant || (!installed && !selectedCompatibility?.safe);
  const fitReady = installed || downloadedReceipt || item.readyWithinThreeMinutes || item.loaded || placement.canRunNow;
  const fitStatus = installedRunning ? "Loaded" : installed ? "In My Models" : downloadedReceipt ? "Downloaded" : placement.label;

  const handleTabKeyDown = (event, tab) => {
    const index = tabs.indexOf(tab);
    let nextIndex = index;
    if (event.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
    else if (event.key === "ArrowLeft") nextIndex = (index - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = tabs.length - 1;
    else return;
    event.preventDefault();
    const nextTab = tabs[nextIndex];
    onTabChange(nextTab);
    requestAnimationFrame(() => document.getElementById(`discover-inspector-tab-${nextTab}`)?.focus());
  };

  return (
    <aside id="discover-model-inspector" className="models-model-inspector models-discover-inspector" data-testid="discover-model-inspector">
      <header className="models-inspector-header">
        <div className="models-inspector-title">
          <PublisherLogo item={item} size="lg" />
          <div>
            <strong>{modelName}</strong>
            <small>{developer} · {modelId}</small>
          </div>
        </div>
        {installedModel && <p className="models-inspector-summary">Local file: {installedModelFile(installedModel)}</p>}
        <span className={`models-inspector-status ${fitReady ? "is-ready" : ""}`}>{fitStatus}</span>
        <div className="models-inspector-primary-actions">
          <button className="w2-button primary" type="button" data-testid="discover-download-action" onClick={runPrimaryAction} disabled={primaryDisabled}>
            {isDownloading && !installed ? <Square size={13} /> : installed || downloadedReceipt ? <Play size={13} /> : <Download size={13} />} {primaryLabel}
          </button>
          {item.sourceUrl ? (
            <a className="w2-button" href={item.sourceUrl} target="_blank" rel="noopener noreferrer"><ExternalLink size={13} /> Source</a>
          ) : (
            <button className="w2-button" type="button" disabled><ExternalLink size={13} /> Source</button>
          )}
        </div>
      </header>

      <div className="models-inspector-tabs" role="tablist" aria-label="Discover model inspector sections" data-testid="discover-inspector-tabs">
        {tabs.map((tab) => (
          <button
            key={tab}
            id={`discover-inspector-tab-${tab}`}
            type="button"
            role="tab"
            aria-selected={activeTab === tab}
            aria-controls={`discover-inspector-panel-${tab}`}
            tabIndex={activeTab === tab ? 0 : -1}
            onClick={() => onTabChange(tab)}
            onKeyDown={(event) => handleTabKeyDown(event, tab)}
          >
            {tab === "download" ? "Files" : labelize(tab)}
          </button>
        ))}
      </div>

      {activeTab === "info" && (
        <section id="discover-inspector-panel-info" role="tabpanel" aria-labelledby="discover-inspector-tab-info" className="models-inspector-section">
          <h3>Model information</h3>
          <p className="models-inspector-summary">{item.summary || item.description || `A ${labelize(item.purpose || "chat")} model published by ${developer}.`}</p>
          <dl className="models-inspector-facts">
            {[
              ["Developer", developer],
              ["Family", item.family || item.modelFamily || item.architecture || item.arch || "-"],
              ["Parameters", catalogParameterLabel(item)],
              ["Architecture", item.architecture || item.arch || "-"],
              ["Context", context > 0 ? context.toLocaleString() + " tokens" : "-"],
              ["Format", catalogModelFormat(item)],
              ["Purpose", labelize(item.purpose || "chat")],
              ["Modalities", modalities.length ? modalities.map(labelize).join(", ") : "Text"],
              ["License", item.license || "Not listed"],
              ["Downloads", Number(item.downloads || 0).toLocaleString()],
              ["Likes", Number(item.likes || 0).toLocaleString()],
            ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd title={String(value)}>{value}</dd></div>)}
          </dl>
          {capabilities.length > 0 && <div className="studio-model-capabilities">{capabilities.map((capability) => <Badge key={capability} variant="muted">{labelize(capability)}</Badge>)}</div>}
        </section>
      )}

      {activeTab === "download" && (
        <section id="discover-inspector-panel-download" role="tabpanel" aria-labelledby="discover-inspector-tab-download" className="models-inspector-section models-discover-download-panel">
          <h3>Download files</h3>
          {activeDownload && (
            <div className="models-inspector-callout">
              {downloadedReceipt ? <CheckCircle2 size={16} /> : <Download size={16} />}
              <span><strong>{downloadedReceipt ? "Download complete" : labelize(activeDownloadState)}</strong><small>{trustedDownloadProgress(activeDownload) ? Math.round(Number(activeDownload.progress)) + "% complete" : "Rasputin is tracking this download."}</small></span>
            </div>
          )}
          {isHuggingFace ? (
            <div className="models-discover-variant-picker" data-testid="discover-variant-picker">
              <button className="models-inspector-wide-action" type="button" onClick={loadVariantDetail} disabled={variantDetailLoading || isDownloading}>
                <Download size={13} /> {variantDetailLoading ? "Loading GGUF files." : variantDetail ? "Refresh GGUF files" : "Choose a GGUF file"}
              </button>
              {variantDetailError && <div role="alert" className="models-discover-error">{variantDetailError}</div>}
              {variantDetail && variants.length > 0 && (
                <>
                  <label>
                    <span>Exact GGUF variant</span>
                    <select value={selectedVariant?.id || ""} onChange={(event) => setSelectedVariantId(event.target.value)} aria-label={`Exact GGUF variant for ${modelName}`}>
                      {variants.map((variant) => {
                        const compatibility = variantCompatibility(variant);
                        return <option key={variant.id} value={variant.id}>{variant.quantization || "Unknown"} · {formatDownloadBytes(variantTotalBytes(variant))} · {labelize(compatibility.state)}</option>;
                      })}
                    </select>
                  </label>
                  {selectedVariant && (
                    <dl className="models-inspector-facts">
                      {[
                        ["Quantization", selectedVariant.quantization || "Unknown"],
                        ["Size", formatDownloadBytes(variantTotalBytes(selectedVariant))],
                        ["Shards", selectedVariant.shardCount || 1],
                        ["Modality", selectedVariant.multimodal ? "Multimodal" : "Text-only"],
                        ["Compatibility", labelize(selectedCompatibility?.state || "unknown")],
                      ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
                    </dl>
                  )}
                </>
              )}
              {variantDetail && variants.length === 0 && <p className="models-inspector-summary">No complete GGUF variants were returned. Choose a GGUF repository to load this model with native llama.cpp.</p>}
              {variantIssues.map((issue, index) => <div key={(issue.kind || "issue") + index} className="models-discover-warning">{issue.reason || issue.kind}{issue.nextAction ? ` · ${issue.nextAction}` : ""}</div>)}
              {variantDetail && (
                <button className="models-inspector-wide-action is-primary" type="button" onClick={() => installed ? onLoadInstalled?.(installedModel) : startDownload(modelId, selectedVariant)} disabled={exactDownloadDisabled}>
                  <Download size={13} /> {installed ? "Load selected GGUF" : variants.length ? "Download selected GGUF" : "No GGUF available"}
                </button>
              )}
            </div>
          ) : (
            <div className="models-inspector-callout"><HardDrive size={16} /><span><strong>Local catalog model</strong><small>Prepare this entry with Rasputin's native model workflow.</small></span></div>
          )}
        </section>
      )}

      {activeTab === "fit" && (
        <section id="discover-inspector-panel-fit" role="tabpanel" aria-labelledby="discover-inspector-tab-fit" className="models-inspector-section">
          <h3>Hardware fit</h3>
          <div className="models-inspector-callout">
            {placement.willFit === false ? <AlertTriangle size={16} /> : <Gauge size={16} />}
            <span><strong>{placement.label || "Fit unknown"}</strong><small>{placement.reasons?.[0] || "Refresh the hardware check to calculate model fit."}</small></span>
          </div>
          <dl className="models-inspector-facts models-hardware-fit-facts">
            {[
              ["Estimated VRAM", vramEstimate ? `~${vramEstimate} GB` : "Unknown"],
              ["Largest GPU", placement.largestSingleGpuGb == null ? "Unknown" : placement.largestSingleGpuGb.toFixed(1) + " GB"],
              ["Combined pool", placement.aggregateVramGb == null ? "Unknown" : placement.aggregateVramGb.toFixed(1) + " GB"],
              ["Safe VRAM now", placement.safeAvailableVramGb == null ? "Unknown" : placement.safeAvailableVramGb.toFixed(1) + " GB"],
              ["Estimated system RAM", systemRamEstimate ? `~${systemRamEstimate} GB` : "Unknown"],
              ["Installed system RAM", placement.installedSystemRamGb == null ? "Unknown" : placement.installedSystemRamGb.toFixed(1) + " GB"],
              ["Safe system RAM now", placement.safeAvailableSystemRamGb == null ? "Unknown" : placement.safeAvailableSystemRamGb.toFixed(1) + " GB"],
              ["Placement", placement.mode ? labelize(placement.mode) : "Automatic"],
            ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
          </dl>
          {guidance.length > 0 && (
            <div className="models-discover-guidance">
              {guidance.map((entry) => <div key={entry.raw}><strong>{entry.raw}</strong><span>{entry.next}</span></div>)}
            </div>
          )}
        </section>
      )}

      {activeTab === "source" && (
        <section id="discover-inspector-panel-source" role="tabpanel" aria-labelledby="discover-inspector-tab-source" className="models-inspector-section">
          <h3>Source and provenance</h3>
          <dl className="models-inspector-facts">
            {[
              ["Model ID", modelId],
              ["Developer", developer],
              ["Source", item.source === "huggingface" || isHuggingFace ? "Hugging Face" : labelize(item.source || "Rasputin catalog")],
              ["License", item.license || "Not listed"],
              ["Updated", updated ? new Date(updated).toLocaleDateString() : "Not listed"],
              ["Format", catalogModelFormat(item)],
            ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd title={String(value)}>{value}</dd></div>)}
          </dl>
          {item.sourceUrl && <a className="models-inspector-wide-action" href={item.sourceUrl} target="_blank" rel="noopener noreferrer"><ExternalLink size={13} /> Open model source</a>}
        </section>
      )}
    </aside>
  );
}
