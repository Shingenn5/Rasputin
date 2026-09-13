function numericBound(value) {
  if (value == null || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function catalogItemPassesFilters(item, {
  catalogFit = "all",
  vramMinGb = "",
  vramMaxGb = "",
  hardware = null,
  estimateVramGb,
  assessPlacement,
} = {}) {
  const minVram = numericBound(vramMinGb);
  const maxVram = numericBound(vramMaxGb);
  const estimate = estimateVramGb(item);

  // A bounded VRAM query cannot safely include a model whose demand is unknown.
  if (minVram != null && (estimate == null || estimate < minVram)) return false;
  if (maxVram != null && (estimate == null || estimate > maxVram)) return false;

  // Keep this check after the VRAM bounds, but never let an unknown estimate
  // bypass the same placement assessment used by the rendered row label.
  return catalogFit !== "fits" || assessPlacement(item, hardware)?.willFit === true;
}
