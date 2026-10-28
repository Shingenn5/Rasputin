export const SIDEBAR_MIN_WIDTH = 220;
export const SIDEBAR_MAX_WIDTH = 400;
export const SIDEBAR_DEFAULT_WIDTH = 280;
export const SIDEBAR_WIDTH_KEY = "rasputin-sidebar-width";

export function clampSidebarWidth(value) {
  const width = Number(value);
  return Number.isFinite(width) && width > 0
    ? Math.round(Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, width)))
    : SIDEBAR_DEFAULT_WIDTH;
}

export function sidebarWidthForKey(key, width, largeStep = false) {
  if (key === "Home") return SIDEBAR_MIN_WIDTH;
  if (key === "End") return SIDEBAR_MAX_WIDTH;
  if (key === "Enter") return SIDEBAR_DEFAULT_WIDTH;
  const step = largeStep ? 40 : 10;
  if (key === "ArrowLeft") return clampSidebarWidth(width - step);
  if (key === "ArrowRight") return clampSidebarWidth(width + step);
  return null;
}
