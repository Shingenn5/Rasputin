export const MOTION_STORAGE_KEY = "rasputin-motion-mode";

export function normalizeMotionMode(value) {
  return value === "reduced" ? "reduced" : "full";
}

export function readStoredMotionMode() {
  return normalizeMotionMode(localStorage.getItem(MOTION_STORAGE_KEY));
}

export function applyMotionMode(value) {
  const mode = normalizeMotionMode(value);
  document.documentElement.dataset.motion = mode;
  localStorage.setItem(MOTION_STORAGE_KEY, mode);
  window.dispatchEvent(new CustomEvent("rasputin-motion-change", { detail: { mode } }));
  return mode;
}
