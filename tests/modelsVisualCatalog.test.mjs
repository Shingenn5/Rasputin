import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const models = readFileSync(new URL("../frontend-src/src/features/models/ModelsView.jsx", import.meta.url), "utf8");
const identity = readFileSync(new URL("../frontend-src/src/features/models/ModelIdentity.jsx", import.meta.url), "utf8");

test("desktop Models opens into a native llama.cpp visual catalog", () => {
  assert.match(models, /data-testid="model-catalog-grid"/);
  assert.match(models, /setShowAllModels\(true\)/);
  assert.match(models, /setCatalogRuntime\("llamaCppGgufServer"\)/);
  assert.match(models, /searchMode === "catalog" && !desktopOnly/);
  assert.match(models, /<h1 className="text-3xl font-bold tracking-tight">Models<\/h1>/);
  assert.doesNotMatch(models, /Models <span className="text-muted-foreground">Center<\/span>/);
});

test("model cards use generated identity and collapse advanced details", () => {
  assert.match(models, /<ModelIdentity item=\{item\}/);
  assert.match(models, /<details ref=\{advancedRef\}/);
  assert.match(models, /<summary[^>]*>Advanced details<\/summary>/);
  assert.match(identity, /<Avatar name=\{\x60\$\{publisher\}\/\$\{modelName\}\x60\}/);
  assert.doesNotMatch(identity, /<img/);
});
