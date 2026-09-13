import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { catalogItemPassesFilters } from "../frontend-src/src/features/models/catalogFitFilter.js";

const source = readFileSync(new URL("../frontend-src/src/features/models/ModelsView.jsx", import.meta.url), "utf8");
const helperStart = source.indexOf("/* ── Guided advisor helpers ── */");
const helperEnd = source.indexOf("function advisorProfileFromPayload", helperStart);
assert.ok(helperStart >= 0 && helperEnd > helperStart, "catalog assessment helpers are present");
const helperSource = source
  .slice(helperStart, helperEnd)
  .replaceAll("export const ", "const ")
  .replaceAll("export function ", "function ");
const {
  catalogVramEstimateGb,
  catalogPlacementAssessment,
} = new Function(
  helperSource + "\nreturn { catalogVramEstimateGb, catalogPlacementAssessment };",
)();

function assess(item, hardware = null) {
  return catalogPlacementAssessment(item, hardware);
}

function passes(item, options = {}) {
  return catalogItemPassesFilters(item, {
    ...options,
    hardware: options.hardware || null,
    estimateVramGb: catalogVramEstimateGb,
    assessPlacement: assess,
  });
}

const readyHardware = {
  detectedHardware: {
    gpus: [{ name: "RTX 4080", memoryTotalMb: 16384, memoryFreeMb: 14336 }],
  },
  capabilityProfile: {
    cpu: { memoryTotalMb: 32768, memoryAvailableMb: 24576 },
  },
};

test("Any fit keeps unknown and blocked rows visible when no VRAM bounds are active", () => {
  const unknown = { id: "unknown" };
  const blocked = { id: "blocked", fitStatus: "blocked", fitWillFit: false };
  assert.equal(passes(unknown), true);
  assert.equal(passes(blocked), true);
});

test("Fits safely never lets missing estimates bypass placement assessment", () => {
  const unknown = { id: "unknown" };
  const blocked = { id: "blocked", fitStatus: "blocked", fitWillFit: false };
  assert.equal(passes(unknown, { catalogFit: "fits", hardware: readyHardware }), false);
  assert.equal(passes(blocked, { catalogFit: "fits", hardware: readyHardware }), false);
});

test("positive backend fit without a top-level estimate remains eligible", () => {
  const backendFit = {
    id: "backend-fit",
    resourceManifest: { fit: { status: "ready" } },
  };
  assert.equal(catalogVramEstimateGb(backendFit), null);
  assert.equal(assess(backendFit, readyHardware).willFit, true);
  assert.equal(passes(backendFit, { catalogFit: "fits", hardware: readyHardware }), true);
});

test("VRAM bounds use normalized estimates, including runtime-envelope aliases", () => {
  const item = {
    id: "enveloped",
    resource_manifest: { runtime_envelope: { estimatedVramGb: 8 } },
    systemRamEstimateGb: 4,
    recommendedProtocol: "llamaCppGgufServer",
    fitStatus: "ready",
    fitWillFit: true,
  };
  assert.equal(catalogVramEstimateGb(item), 8);
  assert.equal(passes(item, { catalogFit: "fits", vramMinGb: "4", vramMaxGb: "13", hardware: readyHardware }), true);
  assert.equal(passes(item, { catalogFit: "fits", vramMaxGb: "7", hardware: readyHardware }), false);
  assert.equal(passes(item, { catalogFit: "fits", vramMinGb: "9", hardware: readyHardware }), false);
  assert.equal(passes({ id: "unknown" }, { vramMaxGb: "13" }), false);
});
