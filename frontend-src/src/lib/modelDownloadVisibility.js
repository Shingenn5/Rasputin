const HIDDEN_PROGRESS_STATES = new Set(["completed", "cancelled"]);

/**
 * Terminal download receipts belong on their catalog row and in the inspector.
 * Keeping them in the global progress rail makes them look pinned while the
 * independently scrolling catalog moves underneath.
 */
export function showsGlobalDownloadProgress(state) {
  return !HIDDEN_PROGRESS_STATES.has(String(state || "").trim().toLowerCase());
}
