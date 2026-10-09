import {
  CheckCircle2,
  Download,
  Play,
  Settings,
  Square,
} from "lucide-react";
import { displayModelName, isManagedModelRunning, labelize, runtimeStatus } from "../../lib/display.js";
import { PublisherLogo } from "./PublisherLogo.jsx";
import { catalogModelId, installedModelFormat } from "./modelPresentation.js";
import { catalogDownloadFor, downloadJobIdentity, downloadJobState } from "./downloadState.js";
import { catalogPlacementAssessment } from "./modelPlacement.js";

export function CatalogPagination({ total, currentPage, pageCount, pageSize, onPageChange, onPageSizeChange, compact = false }) {
  if (!total) return null;
  return (
    <footer className={`models-catalog-pagination ${compact ? "is-compact" : ""}`}>
      <span>{total.toLocaleString()} models · Page {currentPage} of {pageCount}</span>
      <div>
        <button className="w2-button" type="button" disabled={currentPage <= 1} onClick={() => onPageChange(currentPage - 1)}>Prev</button>
        <button className="w2-button" type="button" disabled={currentPage >= pageCount} onClick={() => onPageChange(currentPage + 1)}>Next</button>
        <label>
          <span className="sr-only">Models per page</span>
          <select className="w2-input" value={pageSize} onChange={(event) => onPageSizeChange(Number(event.target.value))}>
            {[10, 20, 40, 80].map((count) => <option key={count} value={count}>{count} / page</option>)}
          </select>
        </label>
      </div>
    </footer>
  );
}

export function DiscoverInstalledSummary({ models, onManage }) {
  return (
    <section className="models-discover-installed" data-testid="discover-installed-models" aria-labelledby="discover-installed-title">
      <header>
        <span>
          <CheckCircle2 size={15} aria-hidden="true" />
          <strong id="discover-installed-title">On this Rasputin</strong>
        </span>
        <small>{models.length} downloaded model{models.length === 1 ? "" : "s"}</small>
      </header>
      <ul aria-label="Installed models available on this Rasputin">
        {models.map((model) => {
          const running = isManagedModelRunning(model);
          const status = runtimeStatus(model);
          const statusLabel = running ? "Loaded" : status === "reachable" ? "Ready" : "Downloaded";
          return (
            <li key={model.key} data-model-key={model.key}>
              <PublisherLogo item={model} size="sm" />
              <span className="models-discover-installed-copy">
                <strong>{displayModelName(model, models)}</strong>
                <small><span className={running ? "is-loaded" : ""}>{statusLabel}</span> · {installedModelFormat(model)}</small>
              </span>
              <button
                type="button"
                className="models-discover-installed-action"
                onClick={() => onManage?.(model)}
                aria-label={`Manage ${displayModelName(model, models)} in My Models`}
              >
                Manage
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function DiscoverCatalogRow({ item, selected, placementFit, activeDownloads, installedModel, onSelect, onDownload, onDownloadAction, onLoadInstalled, onManageInstalled, onLoadArtifact }) {
  const modelId = catalogModelId(item);
  const modelName = String(item?.name || modelId.split("/").pop() || modelId);
  const download = catalogDownloadFor(item, activeDownloads);
  const downloadState = download ? downloadJobState(download) : "";
  const activelyDownloading = Boolean(download && !["completed", "failed", "cancelled"].includes(downloadState));
  const downloadedReceipt = downloadState === "completed";
  const installed = Boolean(installedModel);
  const installedRunning = installed && isManagedModelRunning(installedModel);
  const jobId = downloadJobIdentity(download);
  const placement = placementFit || catalogPlacementAssessment(item, null);
  const fitReady = installed || downloadedReceipt || item?.readyWithinThreeMinutes || item?.loaded || placement.canRunNow;
  const fitLabel = installedRunning ? "Loaded" : installed ? "In My Models" : downloadedReceipt ? "Downloaded" : activelyDownloading ? labelize(downloadState) : placement.label;

  return (
    <div
      className={`models-discover-row ${selected ? "is-selected" : ""}`}
      data-testid="discover-model-row"
      role="row"
      tabIndex={0}
      aria-selected={selected}
      aria-controls="discover-model-inspector"
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect();
        }
      }}
    >
      <div className="models-discover-model" role="cell">
        <PublisherLogo item={item} size="md" />
        <span>
          <strong>{modelName}</strong>
          <small title={modelId}>{modelId}</small>
        </span>
      </div>
      <span className={`models-inventory-fit ${fitReady ? "is-ready" : "is-review"}`} role="cell">
        <i style={{ background: fitReady ? "var(--models-forge-bright)" : "var(--ras-warn)" }} />
        {fitLabel}
      </span>
      <div className="studio-installed-actions" role="cell">
        <button
          type="button"
          className={`models-discover-row-action ${activelyDownloading ? "is-stop" : ""}`}
          data-testid="discover-row-download"
          aria-label={installedRunning ? `Manage loaded model ${modelName}` : installed ? `Load installed model ${modelName}` : activelyDownloading ? `Stop download for ${modelName}` : downloadedReceipt ? `Load downloaded model ${modelName}` : `Download ${modelName}`}
          disabled={activelyDownloading && !jobId}
          onClick={(event) => {
            event.stopPropagation();
            if (installedRunning) onManageInstalled?.(installedModel);
            else if (installed) onLoadInstalled?.(installedModel);
            else if (activelyDownloading) onDownloadAction?.("cancel", jobId);
            else if (downloadedReceipt) onLoadArtifact?.(download);
            else onDownload?.();
          }}
        >
          {installedRunning ? <><Settings size={12} /> Manage</> : installed ? <><Play size={12} /> Load</> : activelyDownloading ? <><Square size={12} /> Stop</> : downloadedReceipt ? <><Play size={12} /> Load</> : <><Download size={12} /> Download</>}
        </button>
      </div>
    </div>
  );
}
