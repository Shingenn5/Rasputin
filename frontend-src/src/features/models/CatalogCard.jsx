import { useState, useRef } from "react";
import { Download, ExternalLink, Play } from "lucide-react";
import { isManagedModelRunning, labelize } from "../../lib/display.js";
import { api } from "../../api/client.js";
import { Button as UIButton } from "@/components/ui/button.jsx";
import { Badge } from "@/components/ui/badge.jsx";
import { blockerGuidanceForReasons } from "../shared/blockerGuidance.js";
import { ModelIdentity } from "./ModelIdentity.jsx";
import { findInstalledCatalogModel } from "./modelEcosystem.js";
import { contextWindowFor } from "./modelPresentation.js";
import {
  downloadJobState,
  formatDownloadBytes,
  preferredDownloadVariant,
  variantCompatibility,
  variantTotalBytes,
} from "./downloadState.js";
import { catalogPlacementAssessment, catalogSystemRamEstimateGb, catalogVramEstimateGb, runtimeEnvelopeForItem } from "./modelPlacement.js";

function StudioModelDetail({ item }) {
  if (!item) {
    return <aside className="studio-model-detail"><p>Select a model to see its details.</p></aside>;
  }
  const parameterCount = item.parameterCountB ? item.parameterCountB + "B" : "Unknown";
  const context = contextWindowFor(item);
  const capabilities = Array.isArray(item.capabilities) ? item.capabilities : [];
  const format = item.format || ((item.runtimeOptions || []).some((option) => option.protocolId === "llamaCppGgufServer") ? "GGUF" : "Model");
  const updated = item.lastModified || item.updatedAt || item.updated_at;
  return (
    <aside className="studio-model-detail" data-testid="studio-model-detail">
      <header>
        <ModelIdentity item={item} />
        {item.sourceUrl && <a href={item.sourceUrl} target="_blank" rel="noopener noreferrer" aria-label="Open model source"><ExternalLink size={15} /></a>}
      </header>
      <div className="studio-model-metrics">
        {item.downloads > 0 && <span>Downloads {Number(item.downloads).toLocaleString()}</span>}
        {item.likes > 0 && <span>Likes {Number(item.likes).toLocaleString()}</span>}
        {updated && <span>Updated {new Date(updated).toLocaleDateString()}</span>}
      </div>
      <section>
        <p>{item.summary || "Model information from the local Rasputin catalog and Hugging Face metadata."}</p>
        <div className="studio-model-facts">
          <span><small>Parameters</small><strong>{parameterCount}</strong></span>
          <span><small>Architecture</small><strong>{item.architecture || item.arch || "Unknown"}</strong></span>
          <span><small>Purpose</small><strong>{labelize(item.purpose || "chat")}</strong></span>
          <span><small>Format</small><strong>{format}</strong></span>
          {context > 0 && <span><small>Context</small><strong>{context.toLocaleString()}</strong></span>}
          {item.license && <span><small>License</small><strong>{item.license}</strong></span>}
        </div>
        {capabilities.length > 0 && <div className="studio-model-capabilities">{capabilities.map((capability) => <Badge key={capability} variant="muted">{labelize(capability)}</Badge>)}</div>}
      </section>
      <section>
        <h3>About this model</h3>
        <p>{item.description || item.summary || "Select a GGUF variant to download it into Rasputin's native model library. Rasputin acquires one hardware-compatible llama.cpp runtime when first needed."}</p>
      </section>
    </aside>
  );
}

export function CatalogCard({ item, selected = false, onSelect, placementFit, hardwareBlocked = false, hardwareBlockReasons = [], prepareCatalogModelForWarsat, searchMode, startDownload, loadCompletedArtifact, activeDownloads, desktopOnly = false, installedModel: repositoryModel = null, installedModels = [], onLoadInstalled, onManageInstalled }) {
  const modelId = item.modelId || item.id;
  const isHuggingFace = searchMode !== "catalog" || item.source === "huggingface";
  const [variantDetail, setVariantDetail] = useState(null);
  const [variantDetailLoading, setVariantDetailLoading] = useState(false);
  const [variantDetailError, setVariantDetailError] = useState("");
  const [selectedVariantId, setSelectedVariantId] = useState("");
  const advancedRef = useRef(null);
  const downloadState = (activeDownloads || []).find((dl) => (
    (dl.modelId || dl.model_id || dl.repository) === modelId
  ));
  const downloadStateName = downloadJobState(downloadState);
  const isDownloading = Boolean(downloadState && !["failed", "completed", "cancelled"].includes(downloadStateName));
  const variants = Array.isArray(variantDetail?.variants) ? variantDetail.variants : [];
  const selectedVariant = variants.find((variant) => variant.id === selectedVariantId) || null;
  const installedModel = selectedVariant
    ? findInstalledCatalogModel(item, installedModels, selectedVariant)
    : repositoryModel;
  const installed = Boolean(installedModel);
  const installedRunning = installed && isManagedModelRunning(installedModel);
  const downloadedReceipt = !selectedVariant && downloadStateName === "completed";
  const selectedCompatibility = selectedVariant ? variantCompatibility(selectedVariant) : null;
  const legacyDownloadAvailable = Boolean(variantDetail && variants.length === 0);
  const itemBlockedReasons = Array.isArray(item.blockedReasons) ? item.blockedReasons : [];
  const blockedReasons = [...new Set([...hardwareBlockReasons, ...itemBlockedReasons])];
  const fitReasons = Array.isArray(item.fitReasons) ? item.fitReasons : [];
  const placement = placementFit || catalogPlacementAssessment(item, null);
  const blocked = hardwareBlocked || blockedReasons.length > 0 || (desktopOnly ? placement.status === "blocked" : !placement.canDeploy);
  const fitNotes = fitReasons.length ? fitReasons : placement.reasons || [];
  const blockerGuidance = blockerGuidanceForReasons([...blockedReasons, ...(blocked ? placement.reasons : [])]);
  const blockerDetailsId = "model-deployment-blockers-" + String(modelId).replace(/[^a-zA-Z0-9_-]/g, "-");
  const runtimeEnvelope = runtimeEnvelopeForItem(item);
  const vramEstimateGb = catalogVramEstimateGb(item);
  const systemRamEstimateGb = catalogSystemRamEstimateGb(item);
  const estimateRange = runtimeEnvelope?.rangeGb || runtimeEnvelope?.range || null;
  const estimateBreakdown = runtimeEnvelope?.breakdown || null;
  const estimateConfidence = runtimeEnvelope?.confidence || runtimeEnvelope?.estimateSource || null;
  const fmt = (n) => n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? (n / 1e3).toFixed(1) + "K" : n;
  const contextWindow = contextWindowFor(item);

  const loadVariantDetail = async () => {
    setVariantDetailLoading(true);
    setVariantDetailError("");
    try {
      const encodedModelId = String(modelId).split("/").map(encodeURIComponent).join("/");
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

  const openVariantDetails = async () => {
    if (advancedRef.current) advancedRef.current.open = true;
    await loadVariantDetail();
  };

  const variantIssues = Array.isArray(variantDetail?.variantIssues) ? variantDetail.variantIssues : [];
  const primaryAction = installedRunning
    ? () => onManageInstalled?.(installedModel)
    : installed
      ? () => onLoadInstalled?.(installedModel)
      : downloadedReceipt
    ? () => loadCompletedArtifact?.(downloadState)
    : isHuggingFace && desktopOnly && !variantDetail
    ? openVariantDetails
    : isHuggingFace
      ? () => startDownload(modelId, selectedVariant || null)
      : item.deployable
        ? () => prepareCatalogModelForWarsat?.(item)
        : undefined;
  const primaryLabel = installedRunning
    ? "Manage in My Models"
    : installed
      ? "Load model"
      : downloadedReceipt
    ? "Load model"
    : isDownloading
    ? "Downloading…"
    : isHuggingFace && desktopOnly && !variantDetail
      ? "Choose GGUF variant"
      : isHuggingFace && desktopOnly && selectedVariant
        ? "Download selected GGUF"
        : isHuggingFace && desktopOnly && legacyDownloadAvailable
          ? "No GGUF available"
          : item.deployable && desktopOnly
            ? "Download model"
            : item.deployable
              ? "Deploy via Warsat"
              : isHuggingFace
                ? "Download weights"
                : "View details";
  const primaryDisabled = Boolean(
    !installed && (
      isDownloading
      || (!downloadedReceipt && isHuggingFace && desktopOnly && variantDetail && !selectedVariant)
      || (!downloadedReceipt && selectedCompatibility && !selectedCompatibility.safe)
      || (item.deployable && !desktopOnly && blocked)
    )
  );
  const stateLabel = installedRunning
    ? "Loaded"
    : installed
      ? "In My Models"
      : downloadedReceipt
    ? "Downloaded"
    : item.readyWithinThreeMinutes || item.loaded
      ? "Ready"
      : placement.label;
  const parameterLabel = item.parameterCountB ? item.parameterCountB + "B parameters" : null;

  return (
    <article
      className={"ras-list-item glow-card models-v3-model-card flex min-w-0 flex-col gap-4 rounded-2xl border border-border bg-card p-4 " + (selected ? "is-selected" : "")}
      data-testid="model-catalog-card"
      tabIndex={onSelect ? 0 : undefined}
      aria-selected={onSelect ? selected : undefined}
      onClick={onSelect}
      onKeyDown={onSelect ? (event) => {
        if (event.target === event.currentTarget && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          onSelect();
        }
      } : undefined}
    >
      <div className="flex items-start justify-between gap-3">
        <ModelIdentity item={item} />
        <Badge variant={downloadedReceipt || item.readyWithinThreeMinutes ? "up" : blocked ? "down" : "muted"}>
          {stateLabel}
        </Badge>
      </div>

      <div className="flex min-h-10 flex-wrap items-center gap-1.5">
        <Badge variant="muted">{labelize(item.purpose || "chat")}</Badge>
        {item.capabilities?.slice(0, 3).map((capability) => <Badge key={capability} variant="muted">{labelize(capability)}</Badge>)}
        {item.downloads > 0 && <Badge variant="muted">↓ {fmt(item.downloads)}</Badge>}
        {item.likes > 0 && <Badge variant="muted">♥ {fmt(item.likes)}</Badge>}
      </div>

      <div className="models-card-facts grid grid-cols-2 gap-2 text-xs text-muted-foreground">
        {parameterLabel && <div><strong className="text-foreground">{parameterLabel}</strong></div>}
        {contextWindow > 0 && <div><strong className="text-foreground">{contextWindow.toLocaleString()} context</strong></div>}
        {vramEstimateGb && <div><strong className="text-foreground">Estimated ~{vramEstimateGb} GB VRAM</strong></div>}
        {systemRamEstimateGb && <div><strong className="text-foreground">Estimated ~{systemRamEstimateGb} GB system RAM</strong></div>}
        {item.license && <div className="truncate" title={item.license}>{item.license}</div>}
      </div>

      {item.summary && <p className="m-0 line-clamp-2 text-xs leading-5 text-muted-foreground">{item.summary.slice(0, 180)}</p>}

      <div className="models-card-actions mt-auto flex min-w-0 flex-wrap items-center gap-2">
        {primaryAction && (
          <UIButton
            variant="default"
            size="sm"
            type="button"
            disabled={primaryDisabled}
            aria-describedby={blocked ? blockerDetailsId : undefined}
            onClick={primaryAction}
            data-testid="model-card-primary-action"
          >
            {isDownloading ? <Download size={12} /> : item.deployable && !desktopOnly ? <Play size={12} /> : <Download size={12} />}
            {primaryLabel}
          </UIButton>
        )}
        <details ref={advancedRef} className="min-w-0 flex-1 rounded-lg border border-border bg-muted/20 px-3 py-2" data-testid="model-card-advanced">
          <summary className="cursor-pointer text-xs font-semibold text-foreground">Advanced details</summary>
          <div className="mt-3 grid gap-3">
            <div className="text-xs text-muted-foreground">
              <div>Largest single GPU: <strong className="text-foreground">{placement.largestSingleGpuGb == null ? "unknown" : placement.largestSingleGpuGb.toFixed(1) + " GB"}</strong></div>
              <div>Combined GPU pool: <strong className="text-foreground">{placement.aggregateVramGb == null ? "unknown" : placement.aggregateVramGb.toFixed(1) + " GB"}</strong></div>
              {placement.reasons?.[0] && <div className="mt-1">{placement.reasons[0]}</div>}
              {estimateRange && <div className="mt-1">Estimated range: {typeof estimateRange === "object" ? String(estimateRange.min ?? "?") + "–" + String(estimateRange.max ?? "?") + " GB" : String(estimateRange)}</div>}
              {estimateConfidence && <div className="mt-1">Confidence: {String(estimateConfidence)}</div>}
              {estimateBreakdown && <div className="mt-1">Estimator includes runtime overhead and cache headroom.</div>}
            </div>

            {(blocked || fitNotes.length > 0) && (
              <div id={blocked ? blockerDetailsId : undefined} data-testid={blocked ? "model-deployment-blockers" : undefined} role={blocked ? "alert" : undefined} className={"rounded-lg border px-3 py-2 text-xs " + (blocked ? "border-destructive/40 bg-destructive/5 text-destructive" : "border-border bg-muted/30 text-muted-foreground")}>
                <strong className="mr-1">{blocked ? "Deployment blocked:" : placement.status === "unknown" ? "Fit not yet verified:" : "Fit guidance:"}</strong>
                {blocked ? blockerGuidance.map((entry) => (
                  <div key={entry.raw} className="mt-1">
                    <div><strong>Reason:</strong> {entry.raw}</div>
                    <div><strong>What this means:</strong> {entry.happened}</div>
                    <div><strong>Next step:</strong> {entry.next}</div>
                  </div>
                )) : fitNotes.join(" ")}{!blocked && placement.status === "unknown" && " Load model checks the downloaded GGUF and selected hardware before starting."}
              </div>
            )}

            {isHuggingFace && (
              <div className="grid gap-2" data-testid="model-variant-picker">
                <UIButton variant="outline" size="sm" type="button" onClick={loadVariantDetail} disabled={variantDetailLoading || isDownloading} aria-expanded={Boolean(variantDetail)}>
                  <Download size={12} /> {variantDetailLoading ? "Loading GGUF variants…" : variantDetail ? "Refresh GGUF variants" : "Choose GGUF variant"}
                </UIButton>
                {variantDetailError && <div role="alert" className="text-xs text-destructive">{variantDetailError}</div>}
                {variantDetail && variants.length > 0 && (
                  <div className="grid gap-1.5">
                    <label htmlFor={"variant-" + String(modelId).replace(/[^a-zA-Z0-9_-]/g, "-")} className="text-xs font-medium">Exact GGUF variant</label>
                    <select
                      id={"variant-" + String(modelId).replace(/[^a-zA-Z0-9_-]/g, "-")}
                      className="w2-input"
                      value={selectedVariant?.id || ""}
                      onChange={(event) => setSelectedVariantId(event.target.value)}
                      aria-label={"Exact GGUF variant for " + modelId}
                    >
                      {variants.map((variant) => {
                        const compatibility = variantCompatibility(variant);
                        const size = variantTotalBytes(variant);
                        const mmprojFiles = Array.isArray(variant.mmprojFiles) ? variant.mmprojFiles : [];
                        return (
                          <option key={variant.id} value={variant.id}>
                            {(variant.quantization || "Unknown quantization") + " · " + formatDownloadBytes(size) + " · " + (variant.shardCount || 1) + " shard" + ((variant.shardCount || 1) === 1 ? "" : "s") + " · " + (variant.multimodal || mmprojFiles.length ? "mmproj" : "text-only") + " · " + (compatibility.state === "unknown" ? "Needs review" : labelize(compatibility.state))}
                          </option>
                        );
                      })}
                    </select>
                    {selectedVariant && (
                      <div className="text-xs text-muted-foreground">
                        <div>Quantization: <strong className="text-foreground">{selectedVariant.quantization || "unknown"}</strong>{" · "}Size: <strong className="text-foreground">{formatDownloadBytes(variantTotalBytes(selectedVariant))}</strong>{" · "}Shards: <strong className="text-foreground">{selectedVariant.shardCount || 1}</strong></div>
                        <div>{selectedVariant.multimodal ? "Multimodal" : "Text-only"}{" · "}mmproj: {Array.isArray(selectedVariant.mmprojFiles) && selectedVariant.mmprojFiles.length ? "included" : "not included"}</div>
                        <div>Compatibility: <strong className={selectedCompatibility?.safe ? "text-amber-300" : "text-destructive"}>{selectedCompatibility?.state === "unknown" ? "Needs review" : labelize(selectedCompatibility?.state || "unknown")}</strong></div>
                        {selectedCompatibility?.reasons?.map((reason) => <div key={reason}>{reason}</div>)}
                      </div>
                    )}
                  </div>
                )}
                {variantDetail && variants.length === 0 && <div className="text-xs text-muted-foreground">No complete GGUF variants were returned. Choose another GGUF repository to load a model locally.</div>}
                {variantIssues.length > 0 && (
                  <div className="text-xs text-amber-300">
                    {variantIssues.map((issue, index) => (
                      <div key={(issue.kind || "issue") + "-" + index}>
                        <strong>{issue.reason || issue.kind || "Variant issue"}</strong>
                        {issue.nextAction && <div>{issue.nextAction}</div>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {item.sourceUrl && item.source === "huggingface" && (
              <a href={item.sourceUrl} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-xs text-sky-400 no-underline">
                <ExternalLink size={11} /> Open Hugging Face page
              </a>
            )}
          </div>
        </details>
      </div>
    </article>
  );
}
