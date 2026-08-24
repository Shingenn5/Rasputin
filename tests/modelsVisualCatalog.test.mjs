import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const models = readFileSync(new URL("../frontend-src/src/features/models/ModelsView.jsx", import.meta.url), "utf8");
const identity = readFileSync(new URL("../frontend-src/src/features/models/ModelIdentity.jsx", import.meta.url), "utf8");
const loader = readFileSync(new URL("../frontend-src/src/features/models/ModelLoadDialog.jsx", import.meta.url), "utf8");
const app = readFileSync(new URL("../frontend-src/src/app/App.jsx", import.meta.url), "utf8");

test("desktop Models opens into a native llama.cpp visual catalog", () => {
  assert.match(models, /data-testid="model-catalog-grid"/);
  assert.match(models, /setShowAllModels\(true\)/);
  assert.match(models, /setCatalogRuntime\("llamaCppGgufServer"\)/);
  assert.match(models, /searchMode === "catalog" && !desktopOnly/);
    assert.match(models, /className="models-page-shell/);
  assert.match(models, /className="models-page-tabs"/);
  assert.match(models, /desktopLabel = \{ library: "Discover", installed: "My Models", running: "Loaded", settings: "Connections" \}/);
  assert.doesNotMatch(models, /Models <span className="text-muted-foreground">Center<\/span>/);
});

test("model cards use generated identity and collapse advanced details", () => {
  assert.match(models, /<ModelIdentity item=\{item\}/);
  assert.match(models, /<details ref=\{advancedRef\}/);
  assert.match(models, /<summary[^>]*>Advanced details<\/summary>/);
  assert.match(identity, /<Avatar name=\{\x60\$\{publisher\}\/\$\{modelName\}\x60\}/);
  assert.doesNotMatch(identity, /<img/);
});


test("desktop model catalog exposes selection details and a real llama.cpp loader", () => {
  assert.match(models, /studio-model-browser/);
  assert.match(models, /<StudioModelDetail item=\{selectedCatalogItem\}/);
  assert.match(models, /!desktopOnly && \(/);
  assert.match(models, /model-hardware-filters/);
  assert.match(models, /<ModelLoadDialog/);
  assert.match(loader, /Pool system RAM and VRAM/);
  assert.match(loader, /GPU split mode/);
  assert.match(loader, /KV cache offload/);
  assert.match(loader, /\/api\/model-catalog\/load-plan-preview/);
  assert.match(app, /runModelAction\(action, key, options = \{\}\)/);
  assert.match(app, /\{ key: resolvedKey, \.\.\.options \}/);
});
