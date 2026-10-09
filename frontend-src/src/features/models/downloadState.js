import { catalogModelId } from "./modelPresentation.js";

export function trustedDownloadProgress(download) {
  const downloaded = Number(download?.downloadedBytes ?? download?.downloaded_bytes);
  const total = Number(download?.totalBytes ?? download?.total_bytes);
  const percent = Number(download?.progress);
  return Boolean(
    (download?.progressTrusted === true || (Number.isFinite(downloaded) && Number.isFinite(total) && total > 0))
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

export const DURABLE_DOWNLOAD_STATES = ["queued", "resolving", "downloading", "paused", "verifying", "installing", "completed", "failed", "cancelled"];

const BLOCKED_VARIANT_STATES = new Set(["incompatible", "blocked", "unsupported"]);

export function downloadJobState(download) {
  return String(download?.state || download?.status || "queued").toLowerCase();
}

export function variantCompatibility(variant) {
  const state = String(variant?.compatibilityState || "unknown").toLowerCase();
  const reasons = [
    ...(Array.isArray(variant?.compatibilityReasons) ? variant.compatibilityReasons : []),
    ...(Array.isArray(variant?.nextActions) ? variant.nextActions : []),
  ].filter((reason) => typeof reason === "string" && reason.trim());
  return {
    state,
    safe: !BLOCKED_VARIANT_STATES.has(state),
    reasons: [...new Set(reasons)],
  };
}

export function preferredDownloadVariant(variants, preferMultimodal = false) {
  const options = Array.isArray(variants) ? variants.filter(Boolean) : [];
  if (!options.length) return null;
  const preferredQuantizations = ["Q4_K_M", "Q5_K_M", "Q5_K_S", "Q4_K_S", "Q6_K", "Q8_0", "F16"];
  const safeOptions = options.filter((variant) => variantCompatibility(variant).safe);
  const candidates = safeOptions.length ? safeOptions : options;
  return [...candidates].sort((left, right) => {
    const leftQuant = String(left?.quantization || "").toUpperCase();
    const rightQuant = String(right?.quantization || "").toUpperCase();
    const leftRank = preferredQuantizations.indexOf(leftQuant);
    const rightRank = preferredQuantizations.indexOf(rightQuant);
    const quantizationOrder = (leftRank < 0 ? preferredQuantizations.length : leftRank)
      - (rightRank < 0 ? preferredQuantizations.length : rightRank);
    if (quantizationOrder) return quantizationOrder;
    const leftModalityPenalty = Boolean(left?.multimodal) === preferMultimodal ? 0 : 1;
    const rightModalityPenalty = Boolean(right?.multimodal) === preferMultimodal ? 0 : 1;
    if (leftModalityPenalty !== rightModalityPenalty) return leftModalityPenalty - rightModalityPenalty;
    const leftSize = variantTotalBytes(left);
    const rightSize = variantTotalBytes(right);
    return (Number.isFinite(leftSize) ? leftSize : Number.MAX_SAFE_INTEGER)
      - (Number.isFinite(rightSize) ? rightSize : Number.MAX_SAFE_INTEGER);
  })[0];
}

export function downloadControlAvailability(download) {
  const state = downloadJobState(download);
  return {
    canPause: state === "downloading",
    canResume: state === "paused",
    canCancel: ["queued", "resolving", "downloading", "paused", "verifying", "installing"].includes(state),
    canRetry: state === "failed" && (download?.canRetry ?? download?.can_retry ?? false) === true,
  };
}

export function formatDownloadBytes(value) {
  const bytes = Number(value);
  if (value == null || !Number.isFinite(bytes) || bytes < 0) return "size unavailable";
  if (bytes >= 1024 ** 3) return (bytes / (1024 ** 3)).toFixed(2) + " GB";
  if (bytes >= 1024 ** 2) return (bytes / (1024 ** 2)).toFixed(1) + " MB";
  if (bytes >= 1024) return (bytes / 1024).toFixed(1) + " KB";
  return bytes + " B";
}

export function variantTotalBytes(variant) {
  const declared = Number(variant?.totalBytes ?? variant?.total_bytes);
  if (Number.isFinite(declared) && declared >= 0) return declared;
  const sizes = variant?.fileSizes || variant?.file_sizes || {};
  let foundSize = false;
  const total = Object.values(sizes).reduce((sum, size) => {
    const parsed = Number(size);
    if (!Number.isFinite(parsed) || parsed < 0) return sum;
    foundSize = true;
    return sum + parsed;
  }, 0);
  return foundSize ? total : null;
}

export function downloadJobsFromPayload(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.jobs)) return payload.jobs;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.data?.jobs)) return payload.data.jobs;
  if (Array.isArray(payload?.data?.items)) return payload.data.items;
  return [];
}

export function completedArtifactFor(download) {
  return download?.artifact || download?.artifactMetadata || download?.artifact_metadata || null;
}

export function artifactModelMatch(models, artifact) {
  if (!artifact) return null;
  const artifactId = artifact.artifactId || artifact.artifact_id;
  const mainModelPath = artifact.mainModelPath || artifact.main_model_path;
  return (models || []).find((model) => (
    (artifactId && String(model.artifact_id || model.artifactId) === String(artifactId))
    || (mainModelPath && String(model.host_model_path || model.hostModelPath) === String(mainModelPath))
  )) || null;
}

export function downloadJobIdentity(download) {
  return download?.id || download?.jobId || download?.job_id || completedArtifactFor(download)?.artifactId || completedArtifactFor(download)?.artifact_id || null;
}

export function catalogDownloadFor(item, activeDownloads) {
  const modelId = catalogModelId(item);
  return (activeDownloads || []).find((download) => (
    (download.modelId || download.model_id || download.repository) === modelId
  )) || null;
}
