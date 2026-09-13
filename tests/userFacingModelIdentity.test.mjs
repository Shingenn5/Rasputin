import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { displayModelName, isModelHealthy, modelHealthLine } from "../frontend-src/src/lib/display.js";

test("a reachable endpoint with a mismatched model cannot submit a doomed task", () => {
  const model = { key: "fixture", model: "missing-model", runtimeStatus: "reachable", discoveredModels: ["available-model"] };
  assert.equal(isModelHealthy(model), false);
  assert.match(modelHealthLine(model, [model]), /missing-model is not listed/);
  assert.equal(isModelHealthy({ ...model, model: "available-model" }), true);
  assert.equal(isModelHealthy({ ...model, discoveredModels: [] }), true);
  assert.equal(isModelHealthy({ ...model, provider: "mock" }), true);
});

test("downloaded artifact keys resolve to the same readable name used in task details", () => {
  const model = { key: "artifact-artifact-123", model: "Qwen3-1.7B-Q4_K_M.gguf", provider: "llamacpp" };
  assert.equal(displayModelName(model, [model]), model.model);
  assert.equal(displayModelName(model.key, [model]), model.model);
  assert.equal(displayModelName(null, []), "No model selected");
  assert.equal(displayModelName("removed-model", []), "removed-model");
  assert.equal(displayModelName({ key: "dry-run" }), "Testing Mode");
});

test("header, composer and task identity use the display-name resolver", () => {
  const home = readFileSync(new URL("../frontend-src/src/features/chat/HomeView.jsx", import.meta.url), "utf8");
  assert.equal((home.match(/displayModelName\(selectedModelObject \|\| selectedModel, models\)/g) || []).length, 2);
  assert.match(home, /const taskModel = displayModelName\(task.model \|\| deploymentProfile.key, models\)/);
  assert.match(home, /data-model-key=\{selectedModel \|\| ""\}/);
});

test("catalog metadata count is not described as locally cached model weights", () => {
  const view = readFileSync(new URL("../frontend-src/src/features/models/ModelsView.jsx", import.meta.url), "utf8");
  assert.match(view, /v: catalogItems.length, l: "Catalog entries"/);
  assert.doesNotMatch(view, /l: "Cached locally"/);
});
