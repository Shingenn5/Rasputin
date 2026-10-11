import { Activity, AlertTriangle, CheckCircle2, Gauge, Pause } from "lucide-react";

export function statusColor(st) {
  if (["running", "reachable", "healthy", "ready", "approved", "done", "success"].includes(st)) return "var(--ras-safe)";
  if (["failed", "error", "denied", "blocked", "unhealthy"].includes(st)) return "var(--ras-danger)";
  if (["paused", "pending", "queued", "warning", "stopped", "unknown"].includes(st)) return "var(--ras-warn)";
  return "var(--cc-muted)";
}

export function formatBytes(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes < 0) return "Unknown size";
  if (bytes < 1024 ** 2) return `${Math.round(bytes / 1024)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

export function formatDuration(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value < 0) return "";
  if (value < 60) return `${Math.round(value)}s remaining`;
  const minutes = Math.floor(value / 60);
  const remainder = Math.round(value % 60);
  return `${minutes}m ${remainder}s remaining`;
}

export function DownloadProgressPanel({ progress, compact = false }) {
  if (!progress || !["downloading", "loading"].includes(progress.status)) return null;
  const downloaded = Number(progress.bytesDownloaded);
  const total = Number(progress.totalBytes);
  const percent = Number(progress.percent);
  const hasTrustedPercent = progress.progressTrusted === true
    && Number.isFinite(downloaded)
    && Number.isFinite(total)
    && total > 0
    && downloaded >= 0
    && downloaded <= total
    && Number.isFinite(percent)
    && percent >= 0
    && percent <= 100;
  const sourceFile = progress.source?.file || "model weights";
  return (
    <div
      data-testid={compact ? "warsat-container-download-progress" : "warsat-download-progress"}
      style={{
        marginTop: compact ? "8px" : "12px",
        padding: compact ? "8px 10px" : "10px 12px",
        border: "1px solid var(--cc-border)",
        borderRadius: "7px",
        background: "var(--cc-surface)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: "10px", fontSize: "0.75rem" }}>
        <strong>{progress.status === "loading" ? "Loading model into memory" : "Downloading model weights"}</strong>
        <span>{hasTrustedPercent ? `${percent.toFixed(1)}%` : "percentage unavailable"}</span>
      </div>
      {hasTrustedPercent && (
        <div
          role="progressbar"
          aria-label={`Download progress for ${sourceFile}`}
          aria-valuemin="0"
          aria-valuemax="100"
          aria-valuenow={percent}
          style={{ height: "6px", marginTop: "7px", overflow: "hidden", borderRadius: "999px", background: "var(--cc-border)" }}
        >
          <div style={{ height: "100%", width: `${percent}%`, borderRadius: "999px", background: "var(--ras-safe)", transition: "width 0.4s ease" }} />
        </div>
      )}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", marginTop: "6px", color: "var(--cc-muted)", fontSize: "0.6875rem" }}>
        <span>{sourceFile}</span>
        <span>{formatBytes(progress.bytesDownloaded)}{progress.totalBytes ? ` / ${formatBytes(progress.totalBytes)}` : " downloaded"}</span>
        {progress.rateBytesPerSecond > 0 && <span>{formatBytes(progress.rateBytesPerSecond)}/s</span>}
        {progress.etaSeconds != null && <span>{formatDuration(progress.etaSeconds)}</span>}
      </div>
    </div>
  );
}

export function taskStatusIcon(status) {
  if (["running"].includes(status)) return <Activity size={14} color="var(--ras-safe)" />;
  if (["queued"].includes(status)) return <Gauge size={14} color="var(--ras-warn)" />;
  if (["paused"].includes(status)) return <Pause size={14} color="var(--ras-warn)" />;
  if (["completed", "done", "success"].includes(status)) return <CheckCircle2 size={14} color="var(--ras-safe)" />;
  if (["failed", "error", "cancelled"].includes(status)) return <AlertTriangle size={14} color="var(--ras-danger)" />;
  return <Activity size={14} color="var(--cc-muted)" />;
}
