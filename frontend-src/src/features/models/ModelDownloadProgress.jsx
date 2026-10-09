import { Play, Square } from "lucide-react";
import { Button as UIButton } from "@/components/ui/button.jsx";
import {
  completedArtifactFor,
  downloadControlAvailability,
  downloadJobState,
  formatDownloadBytes,
  trustedDownloadProgress,
} from "./downloadState.js";

export function ModelDownloadProgress({ download, onDownloadAction, onLoadArtifact, loadingArtifact }) {
  const hasTrustedProgress = trustedDownloadProgress(download);
  const downloaded = Number(download?.downloadedBytes ?? download?.downloaded_bytes) || 0;
  const total = Number(download?.totalBytes ?? download?.total_bytes) || 0;
  const percent = Number(download?.progress);
  const state = downloadJobState(download);
  const controls = downloadControlAvailability(download);
  const modelLabel = download?.modelId || download?.model_id || download?.repository || "Model download";
  const jobId = download?.id || download?.jobId || download?.job_id;
  const artifact = completedArtifactFor(download);
  const completed = state === "completed";
  const variantId = artifact?.variantId || artifact?.variant_id || download?.variant_id || download?.variantId;
  const quantization = artifact?.quantization || download?.quantization;
  return (
    <div className="w2-card" data-testid="model-download-progress" style={{ padding: "8px 12px", gap: "4px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8125rem" }}>
        <strong>{modelLabel}</strong>
        <span style={{ color: "var(--cc-muted)" }}>{state}</span>
      </div>
      {hasTrustedProgress && (
        <div
          role="progressbar"
          aria-label={"Download progress for " + modelLabel}
          aria-valuemin="0"
          aria-valuemax="100"
          aria-valuenow={percent}
          style={{ height: "4px", background: "var(--cc-border)", borderRadius: "2px", overflow: "hidden" }}
        >
          <div style={{ height: "100%", width: percent + "%", background: "var(--ras-safe)", transition: "width 0.5s ease" }} />
        </div>
      )}
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.6875rem", color: "var(--cc-muted)" }}>
        <span>{formatDownloadBytes(downloaded) + " / " + (total > 0 ? formatDownloadBytes(total) : "size unavailable")}</span>
        <span>{hasTrustedProgress ? percent.toFixed(1) + "%" : "percentage unavailable"}</span>
      </div>
      {completed && (
        <div data-testid="model-download-completed-artifact" className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-3 py-2 text-xs">
          <strong className="text-emerald-300">Download complete. Model registered and ready to load.</strong>
          <div className="mt-1 text-muted-foreground">
            Variant: <strong className="text-foreground">{variantId || "exact GGUF variant"}</strong>
            {quantization && <> · Quantization: <strong className="text-foreground">{quantization}</strong></>}
          </div>
          {(artifact?.mainModelPath || artifact?.main_model_path) && (
            <div className="mt-1 truncate text-muted-foreground" title={artifact.mainModelPath || artifact.main_model_path}>
              Local file: {artifact.mainModelPath || artifact.main_model_path}
            </div>
          )}
          {onLoadArtifact && (
            <UIButton
              variant="default"
              size="sm"
              type="button"
              data-testid="model-download-load"
              aria-label={"Load completed model " + (variantId || modelLabel)}
              disabled={loadingArtifact}
              onClick={() => onLoadArtifact(download)}
              className="mt-2"
            >
              <Play size={12} /> {loadingArtifact ? "Loading…" : "Load"}
            </UIButton>
          )}
        </div>
      )}
      {download?.error && <div role="alert" style={{ color: "var(--ras-danger)", fontSize: "0.75rem" }}>{download.error}</div>}
      {(controls.canPause || controls.canResume || controls.canCancel || controls.canRetry) && (
        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
          {controls.canPause && <UIButton variant="outline" size="sm" type="button" onClick={() => onDownloadAction?.("pause", jobId)} aria-label={"Pause download for " + modelLabel}>Pause</UIButton>}
          {controls.canResume && <UIButton variant="outline" size="sm" type="button" onClick={() => onDownloadAction?.("resume", jobId)} aria-label={"Resume download for " + modelLabel}>Resume</UIButton>}
          {controls.canCancel && <UIButton variant="outline" size="sm" type="button" onClick={() => onDownloadAction?.("cancel", jobId)} aria-label={"Stop download for " + modelLabel}><Square size={12} /> Stop</UIButton>}
          {controls.canRetry && <UIButton variant="outline" size="sm" type="button" onClick={() => onDownloadAction?.("retry", jobId)} aria-label={"Retry download for " + modelLabel}>Retry</UIButton>}
        </div>
      )}
    </div>
  );
}
