export const MOTION_STORAGE_KEY = "rasputin-motion-mode";

export function normalizeMotionMode(value) {
  return ["full", "reduced"].includes(value) ? value : "system";
}

export function readStoredMotionMode() {
  return normalizeMotionMode(localStorage.getItem(MOTION_STORAGE_KEY));
}

export function applyMotionMode(value) {
  const preference = normalizeMotionMode(value);
  const mode = preference === "system"
    ? (window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "reduced" : "full")
    : preference;
  document.documentElement.dataset.motion = mode;
  window.dispatchEvent(new CustomEvent("rasputin-motion-change", { detail: { mode } }));
  return mode;
}
