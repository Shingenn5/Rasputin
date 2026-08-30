import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { blockerGuidanceForReason } from "../frontend-src/src/features/shared/blockerGuidance.js";

const source = readFileSync(new URL("../frontend-src/src/features/models/ModelsView.jsx", import.meta.url), "utf8");
const guidanceSource = readFileSync(new URL("../frontend-src/src/features/shared/blockerGuidance.js", import.meta.url), "utf8");
const helperStart = source.indexOf("/* ── Guided advisor helpers ── */");
const helperEnd = source.indexOf("function advisorProfileFromPayload", helperStart);
assert.ok(helperStart >= 0, "advisor helper block is present");
assert.ok(helperEnd > helperStart, "advisor helper block has a pure-function boundary");

const helperSource = source
  .slice(helperStart, helperEnd)
  .replaceAll("export const ", "const ")
  .replaceAll("export function ", "function ");
const {
  shortlistAdvisorModels,
  selectAdvisorWinner,
  hardwarePlacementCapacity,
  catalogPlacementAssessment,
  shouldProbeHardware,
  withAdvisorTimeout,
  normalizeHardwareSnapshot,
  advisorStateForInputs,
  catalogVramEstimateGb,
  catalogSystemRamEstimateGb,
  systemMemoryCapacity,
} = new Function(
  helperSource + "\nreturn { shortlistAdvisorModels, selectAdvisorWinner, hardwarePlacementCapacity, catalogPlacementAssessment, shouldProbeHardware, withAdvisorTimeout, normalizeHardwareSnapshot, advisorStateForInputs, catalogVramEstimateGb, catalogSystemRamEstimateGb, systemMemoryCapacity };",
)();

test("system RAM fit evidence gets host-memory guidance", () => {
  const guidance = blockerGuidanceForReason("Estimated 2.8 GB system RAM fits 24.6 GB safely available now.");
  assert.match(guidance.happened, /system RAM demand/);
  assert.match(guidance.next, /memory-heavy applications/);
});

function catalogItem(index, overrides = {}) {
  return {
    id: "model-" + index,
    modelId: "model-" + index,
    name: "Model " + index,
    deployable: true,
    apiOnly: false,
    fitScore: index,
    downloads: index * 10,
    likes: index,
    ...overrides,
  };
}

function withSystemRam(hardware, totalMb = 65536, availableMb = 60000) {
  return {
    ...hardware,
    capabilityProfile: {
      ...(hardware.capabilityProfile || {}),
      cpu: { memoryTotalMb: totalMb, memoryAvailableMb: availableMb },
    },
  };
}

test("advisor shortlist is deployable, unblocked, deterministic, and capped at twelve", () => {
  const items = [
    ...Array.from({ length: 20 }, (_, index) => catalogItem(index)),
    catalogItem(99, { blockedReasons: ["too large"], fitScore: 999 }),
    catalogItem(100, { apiOnly: true, fitScore: 1000 }),
    { id: "not-deployable", deployable: false, fitScore: 200 },
  ];
  const shortlist = shortlistAdvisorModels(items);
  assert.equal(shortlist.length, 12);
  assert.equal(shortlist[0].id, "model-19");
  assert.ok(shortlist.every((item) => item.deployable === true && !item.blockedReasons?.length && item.apiOnly !== true));
});

test("exact measured evidence outranks a higher-scoring estimate", () => {
  const estimated = {
    item: catalogItem(1),
    profile: { profileScore: 999, benchmarkEvidence: { basis: "catalog-estimate" } },
  };
  const measured = {
    item: catalogItem(2),
    profile: { profileScore: 1, benchmarkEvidence: { exact: true, basis: "measured-exact" } },
  };
  assert.equal(selectAdvisorWinner([estimated, measured], "balanced"), measured);
});

test("blocked profiles cannot win over an available profile", () => {
  const blocked = {
    item: catalogItem(1),
    profile: { status: "blocked", profileScore: 999, benchmarkEvidence: { exact: true } },
  };
  const ready = {
    item: catalogItem(2),
    profile: { status: "ready", profileScore: 1, benchmarkEvidence: { basis: "catalog-estimate" } },
  };
  assert.equal(selectAdvisorWinner([blocked, ready], "balanced"), ready);
});

test("recommendation deployment forwards the selected profile planSeed", () => {
  assert.match(source, /planSeed: profile\?\.planSeed \|\| recommendation/);
  assert.match(source, /\.\.\.planSeed/);
  assert.match(source, /prepareCatalogModelForWarsat\?\.\(item, \{/);
});


test("mixed GPU capacity never treats aggregate VRAM as a single-GPU vLLM fit", () => {
  const hardware = withSystemRam({ detectedHardware: { gpus: [
    { memoryTotalMb: 12288 },
    { memoryTotalMb: 16384 },
  ] } }, 65536, undefined);
  const capacity = hardwarePlacementCapacity(hardware);
  assert.equal(capacity.largestSingleGpuGb, 16);
  assert.equal(capacity.aggregateVramGb, 28);
  const assessment = catalogPlacementAssessment({ vramEstimateGb: 22, recommendedProtocol: "vllm" }, hardware);
  assert.equal(assessment.kind, "blocked");
  assert.equal(assessment.canDeploy, false);
  assert.equal(assessment.willFit, false);
});

test("hardware capacity accepts GB fields without dividing them twice", () => {
  const capacity = hardwarePlacementCapacity({ detectedHardware: { gpus: [
    { memoryGb: 12 },
    { memory_gb: 16 },
  ] } });
  assert.equal(capacity.largestSingleGpuGb, 16);
  assert.equal(capacity.aggregateVramGb, 28);
});

test("llama.cpp multi-GPU placement uses combined installed capacity", () => {
  const hardware = withSystemRam({ detectedHardware: { gpus: [
    { memoryTotalMb: 12288 },
    { memoryTotalMb: 16384 },
  ] } });
  const assessment = catalogPlacementAssessment(
    { vramEstimateGb: 22, systemRamEstimateGb: 14, recommendedProtocol: "llamaCppGgufServer" },
    hardware,
    { exact: true, protocolId: "llamaCppGgufServer", placementMode: "multi-gpu" },
  );
  assert.equal(assessment.kind, "capacity-fit");
  assert.equal(assessment.canDeploy, true);
  assert.equal(assessment.willFit, true);
});

test("live free VRAM separates ready, temporarily busy, and impossible models", () => {
  const readyHardware = withSystemRam({ detectedHardware: { gpus: [
    { name: "RTX 4080", memoryTotalMb: 16384, memoryFreeMb: 14336 },
  ] } });
  const busyHardware = withSystemRam({ detectedHardware: { gpus: [
    { name: "RTX 4080", memoryTotalMb: 16384, memoryFreeMb: 4096 },
  ] } });
  const ready = catalogPlacementAssessment({ vramEstimateGb: 12, systemRamEstimateGb: 8, recommendedProtocol: "vllm" }, readyHardware);
  const busy = catalogPlacementAssessment({ vramEstimateGb: 12, systemRamEstimateGb: 8, recommendedProtocol: "vllm" }, busyHardware);
  const impossible = catalogPlacementAssessment({ vramEstimateGb: 18, systemRamEstimateGb: 8, recommendedProtocol: "vllm" }, readyHardware);

  assert.equal(ready.status, "ready");
  assert.equal(ready.label, "Will fit");
  assert.equal(ready.canRunNow, true);
  assert.equal(busy.status, "queued");
  assert.equal(busy.label, "Fits when memory is free");
  assert.equal(busy.willFit, true);
  assert.equal(busy.canRunNow, false);
  assert.equal(impossible.status, "blocked");
  assert.equal(impossible.label, "Will not fit");
  assert.equal(impossible.willFit, false);
});

test("llama.cpp uses combined live safe-free VRAM while mixed vLLM does not", () => {
  const hardware = withSystemRam({ detectedHardware: { gpus: [
    { name: "RTX 3060", memoryTotalMb: 12288, memoryFreeMb: 12288 },
    { name: "RTX 5060 Ti", memoryTotalMb: 16384, memoryFreeMb: 16384 },
  ] } });
  const gguf = catalogPlacementAssessment({ vramEstimateGb: 22, systemRamEstimateGb: 14, recommendedProtocol: "llamaCppGgufServer" }, hardware);
  const vllm = catalogPlacementAssessment({ vramEstimateGb: 22, systemRamEstimateGb: 14, recommendedProtocol: "vllmCudaOpenai" }, hardware);

  assert.equal(gguf.status, "ready");
  assert.equal(gguf.canRunNow, true);
  assert.equal(vllm.status, "blocked");
  assert.equal(vllm.willFit, false);
});

test("system RAM participates in ready, temporarily busy, and impossible fit states", () => {
  const gpu = { detectedHardware: { gpus: [
    { name: "RTX 4080", memoryTotalMb: 16384, memoryFreeMb: 14336 },
  ] } };
  const item = { vramEstimateGb: 4, systemRamEstimateGb: 8, recommendedProtocol: "vllmCudaOpenai" };
  const ready = catalogPlacementAssessment(item, withSystemRam(gpu, 32768, 24576));
  const busy = catalogPlacementAssessment(item, withSystemRam(gpu, 32768, 8192));
  const impossible = catalogPlacementAssessment({ ...item, systemRamEstimateGb: 10 }, withSystemRam(gpu, 8192, 8192));

  assert.deepEqual(systemMemoryCapacity(withSystemRam(gpu, 32768, 24576)), {
    totalGb: 32,
    availableGb: 24,
    safeAvailableGb: 22,
    headroomGb: 2,
  });
  assert.equal(catalogSystemRamEstimateGb(item), 8);
  assert.equal(ready.status, "ready");
  assert.equal(ready.safeAvailableSystemRamGb, 22);
  assert.equal(busy.status, "queued");
  assert.equal(busy.label, "Fits when memory is free");
  assert.equal(impossible.status, "blocked");
  assert.equal(impossible.label, "Will not fit");

  const backendZero = catalogPlacementAssessment({
    fitStatus: "queued",
    fitLabel: "Fits when memory is free",
    fitWillFit: true,
    fitCapacity: { installedSystemRamGb: 32, safeAvailableSystemRamGb: 0 },
  }, {});
  assert.equal(backendZero.safeAvailableSystemRamGb, 0);
});

test("fresh Models without a hardware prop probes once and can reach ready or error", async () => {
  assert.equal(shouldProbeHardware("models", false, -1, 0), true);
  assert.equal(shouldProbeHardware("models", false, 0, 0), false);
  assert.equal(shouldProbeHardware("home", false, -1, 0), false);
  await assert.rejects(
    () => withAdvisorTimeout(() => new Promise(() => {}), 5),
    (error) => error.name === "TimeoutError" && /timed out/.test(error.message),
  );
  assert.match(source, /status: snapshot\.blocked \? "blocked" : "ready"/);
  assert.match(source, /setHardwareProbeState\(\{ status: "error"/);
  assert.match(source, /\/api\/warsat\/hardware\?native_models=true/);
  assert.match(source, /hardwareProbeAttempt = useRef\(-1\)/);
});

test("HTTP-200 blocked hardware snapshots are received with exact blockers and next steps", () => {
  const snapshot = normalizeHardwareSnapshot({
    ok: false,
    status: "blocked",
    blockedReasons: ["Docker control is disabled."],
    recommendations: ["Enable Docker control in Settings.", "Add a model folder."],
    checks: [{ id: "gpu", status: "ready", message: "RTX 3060 detected." }],
    detectedHardware: { gpus: [{ name: "RTX 3060", memoryGb: 12 }] },
  });
  assert.equal(snapshot.received, true);
  assert.equal(snapshot.blocked, true);
  assert.equal(snapshot.status, "blocked");
  assert.deepEqual(snapshot.blockedReasons, ["Docker control is disabled."]);
  assert.deepEqual(snapshot.recommendations, ["Enable Docker control in Settings.", "Add a model folder."]);
  assert.deepEqual(snapshot.checkMessages, ["RTX 3060 detected."]);
  const state = advisorStateForInputs({
    hasHardware: true,
    hardwareSnapshot: snapshot,
    catalogCount: 1,
    candidateCount: 1,
  });
  assert.equal(state.status, "hardware-blocked");
  assert.match(state.reason, /snapshot received/);
  assert.deepEqual(state.hardwareReasons, ["Docker control is disabled."]);
  assert.deepEqual(state.hardwareRecommendations, ["Enable Docker control in Settings.", "Add a model folder."]);
  assert.match(source, /data-testid="hardware-blocked-reasons"/);
  assert.match(source, /Hardware snapshot received/);
  assert.match(source, /disabled=\{blocked\}/);
});

test("advisor states distinguish catalog, hardware, and recommendation readiness", () => {
  const readyHardware = normalizeHardwareSnapshot({ ok: true, status: "ready", detectedHardware: { gpus: [{ memoryGb: 8 }] } });
  assert.equal(advisorStateForInputs({ catalogLoading: true }).status, "catalog-loading");
  assert.equal(advisorStateForInputs({ hasHardware: false }).status, "hardware-loading");
  assert.equal(advisorStateForInputs({ hardwareProbeStatus: "error", hardwareError: "probe failed" }).status, "hardware-error");
  assert.equal(advisorStateForInputs({ hasHardware: true, hardwareSnapshot: readyHardware, catalogCount: 0 }).status, "catalog-empty");
  assert.equal(advisorStateForInputs({ hasHardware: true, hardwareSnapshot: readyHardware, catalogCount: 1, candidateCount: 0 }).status, "no-deployable-candidates");
  assert.equal(advisorStateForInputs({ hasHardware: true, hardwareSnapshot: readyHardware, catalogCount: 1, candidateCount: 1 }), null);
  assert.match(source, /Waiting for a hardware snapshot before requesting recommendations/);
  assert.doesNotMatch(source, /advisorState\.status === "waiting"/);
  assert.match(source, /Browse full catalog/);
});

test("runtime envelope estimate takes precedence and is labeled as estimated", () => {
  assert.equal(catalogVramEstimateGb({
    vramEstimateGb: 8,
    resourceManifest: { runtimeEnvelope: { estimatedVramGb: 11, confidence: "estimated" } },
  }), 11);
  assert.equal(catalogVramEstimateGb({ vramEstimateGb: 8 }), 8);
});

test("blocked model deployment exposes actionable guidance and accessible linkage", () => {
  const retired = blockerGuidanceForReason("Docker control is not enabled");
  assert.match(retired.happened, /retired deployment workflow/);
  assert.match(retired.next, /Get GGUF/);
  assert.doesNotMatch(retired.next, /enable.*docker|safety settings/i);
  assert.match(guidanceSource, /model folder/);
  assert.match(guidanceSource, /multi-GPU/);
  assert.match(guidanceSource, /runtime/);
  assert.match(guidanceSource, /exact reason above/);
  assert.match(source, /data-testid=\{blocked \? "model-deployment-blockers"/);
  assert.match(source, /aria-describedby=\{blocked \? blockerDetailsId/);
  assert.match(source, /What this means:/);
  assert.match(source, /Next step:/);
  assert.match(source, /Estimated ~\{vramEstimateGb\} GB VRAM/);
});

test("catalog search stays usable and starting a download restarts bounded polling", () => {
  assert.match(source, /className="model-catalog-filters"/);
  assert.match(source, /className="w2-input model-catalog-search"/);
  assert.match(source, /minWidth: "240px"/);
  assert.match(source, /const startDownload = async \(modelId, variant = null\) =>/);
  assert.match(source, /const body = variant \? \{ modelId, variant \} : \{ modelId \};/);
  assert.match(source, /await postJson\("\/api\/models\/download", body\)/);
  assert.match(source, /setDownloadRefreshToken\(\(value\) => value \+ 1\)/);
});

test("completed artifacts expose an explicit user Load action", () => {
  assert.match(source, /data-testid="model-download-load"/);
  assert.match(source, /const loadCompletedArtifact = async \(download\) =>/);
  assert.match(source, /await loadModels\(\);/);
  assert.match(source, /let registry = models \|\| \[\];/);
  assert.match(source, /model = artifactModelMatch\(registry, artifact\);/);
  assert.match(source, /registry = await loadModels\(\);/);
  assert.match(source, /setLoadDialogModel\(model\)/);
  assert.match(source, /Review load settings, then start the model/);
});

test("guided selection presents one primary choice with collapsed advanced paths", () => {
  assert.match(source, /Best match for your computer/);
  assert.match(source, /data-testid="primary-model-recommendation"/);
  assert.match(source, /<details className="model-alternatives/);
  assert.doesNotMatch(source, /<details className="model-alternatives[^>]* open/);
  assert.match(source, /Technical details/);
  assert.match(source, /Review WarSat plan/);
  assert.doesNotMatch(source, /Deploy recommendation/);
  assert.match(source, /Browse full catalog/);
});

test("specific Hugging Face action opens and focuses exact-model search", () => {
  assert.match(source, /const openSpecificHuggingFaceModel = \(\) =>/);
  assert.match(source, /setShowAllModels\(true\)/);
  assert.match(source, /setSearchMode\("huggingface"\)/);
  assert.match(source, /hfSearchInputRef\.current\?\.focus\(\)/);
  assert.match(source, /data-testid="use-specific-hf-model"/);
  assert.match(source, /onUseSpecificModel=\{openSpecificHuggingFaceModel\}/);
  assert.match(source, /Model name, org\/model, or Hugging Face URL/);
  assert.match(source, /then press Enter or Search\. Exact matches appear first/);
  assert.match(source, /data-testid="model-specific-hf-submit"/);
});
