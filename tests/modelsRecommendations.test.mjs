import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../frontend-src/src/features/models/ModelsView.jsx", import.meta.url), "utf8");
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
} = new Function(
  helperSource + "\nreturn { shortlistAdvisorModels, selectAdvisorWinner, hardwarePlacementCapacity, catalogPlacementAssessment, shouldProbeHardware, withAdvisorTimeout };",
)();

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
  const hardware = { detectedHardware: { gpus: [
    { memoryTotalMb: 12288 },
    { memoryTotalMb: 16384 },
  ] } };
  const capacity = hardwarePlacementCapacity(hardware);
  assert.equal(capacity.largestSingleGpuGb, 16);
  assert.equal(capacity.aggregateVramGb, 28);
  const assessment = catalogPlacementAssessment({ vramEstimateGb: 22, recommendedProtocol: "vllm" }, hardware);
  assert.equal(assessment.kind, "blocked-unproven");
  assert.equal(assessment.canDeploy, false);
});

test("hardware capacity accepts GB fields without dividing them twice", () => {
  const capacity = hardwarePlacementCapacity({ detectedHardware: { gpus: [
    { memoryGb: 12 },
    { memory_gb: 16 },
  ] } });
  assert.equal(capacity.largestSingleGpuGb, 16);
  assert.equal(capacity.aggregateVramGb, 28);
});

test("exact measured llama.cpp multi-GPU evidence is the only combined placement exception", () => {
  const hardware = { detectedHardware: { gpus: [
    { memoryTotalMb: 12288 },
    { memoryTotalMb: 16384 },
  ] } };
  const assessment = catalogPlacementAssessment(
    { vramEstimateGb: 22, recommendedProtocol: "llamaCppGgufServer" },
    hardware,
    { exact: true, protocolId: "llamaCppGgufServer", placementMode: "multi-gpu" },
  );
  assert.equal(assessment.kind, "measured-multi-gpu");
  assert.equal(assessment.canDeploy, true);
});

test("fresh Models without a hardware prop probes once and can reach ready or error", async () => {
  assert.equal(shouldProbeHardware("models", false, -1, 0), true);
  assert.equal(shouldProbeHardware("models", false, 0, 0), false);
  assert.equal(shouldProbeHardware("home", false, -1, 0), false);
  await assert.rejects(
    () => withAdvisorTimeout(() => new Promise(() => {}), 5),
    (error) => error.name === "TimeoutError" && /timed out/.test(error.message),
  );
  assert.match(source, /setHardwareProbeState\(\{ status: "ready"/);
  assert.match(source, /setHardwareProbeState\(\{ status: "error"/);
  assert.match(source, /api\("\/api\/warsat\/hardware"/);
  assert.match(source, /hardwareProbeAttempt = useRef\(-1\)/);
});

test("catalog search stays usable and starting a download restarts bounded polling", () => {
  assert.match(source, /className="model-catalog-filters"/);
  assert.match(source, /className="w2-input model-catalog-search"/);
  assert.match(source, /minWidth: "240px"/);
  assert.match(source, /await postJson\("\/api\/models\/download", \{ modelId \}\)/);
  assert.match(source, /setDownloadRefreshToken\(\(value\) => value \+ 1\)/);
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
  assert.match(source, /Paste org\/model or a huggingface\.co URL/);
  assert.match(source, /Exact matches appear first and still require WarSat review/);
});
