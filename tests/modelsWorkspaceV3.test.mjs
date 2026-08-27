import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const models = readFileSync(new URL("../frontend-src/src/features/models/ModelsView.jsx", import.meta.url), "utf8");
const styles = readFileSync(new URL("../frontend-src/src/styles/models-workspace-v3.css", import.meta.url), "utf8");

test("Models workspace v3 adds a distinct command-console hierarchy", () => {
  assert.match(models, /models-workspace-v3/);
  assert.match(models, /models-v3-command-band/);
  assert.match(models, /models-v3-runtime-metrics/);
  assert.match(models, /models-v3-catalog-stage/);
  assert.match(models, /models-v3-model-card/);
  assert.match(models, /models-v3-running/);
  assert.match(styles, /models-v3-command-band/);
  assert.match(styles, /models-v3-metric/);
  assert.match(styles, /models-v3-tab/);
});

test("My Models opens as a dense selectable inventory with a persistent inspector", () => {
  assert.match(models, /useState\(\(\) => view === "discover" \? "library" : "installed"\)/);
  assert.match(models, /className="models-inventory-workbench"/);
  assert.match(models, /role="table" aria-label="Installed models"/);
  for (const heading of ["Model", "Developer", "Params", "Context", "Format", "Fit", "Actions"]) {
    assert.match(models, new RegExp(`role="columnheader">${heading}<`));
  }
  assert.match(models, /data-testid="installed-model-row"/);
  assert.match(models, /aria-selected=\{selected\}/);
  assert.match(models, /data-testid="installed-model-inspector"/);
  assert.match(models, /aria-label="Model inspector sections"/);
  assert.match(models, /installedSearchInputRef\.current\?\.focus\(\)/);
  assert.match(models, /event\.ctrlKey \|\| event\.metaKey/);
  assert.match(models, /if \(view === "discover"\) setActiveTab\("library"\)/);
  assert.doesNotMatch(models, /data-testid="models-search-button"/);
  assert.match(models, /<PublisherLogo item=\{model\} size="md" \/>/);
  assert.match(models, /data-table-kind="installed-model-table"/);
  assert.match(models, /data-testid="models-inspector-resizer"/);
  assert.match(models, /aria-valuemin=\{260\}/);
  assert.match(models, /const tabs = \["info", "load", "inference", "actions"\]/);
  assert.match(models, /Reasoning budget/);
  assert.match(models, /Delete model/);
  assert.match(models, /runModelAction\?\.\("delete", model\.key\)/);
  assert.match(models, /Use in New Chat/);
  assert.match(models, /Load Model/);
});

test("Discover Models mirrors the dense inventory and persistent inspector contract", () => {
  assert.match(models, /data-testid="discover-model-workbench"/);
  assert.match(models, /role="table"\s+aria-label="Available models"/);
  for (const heading of ["Model", "Developer", "Params", "Context", "Downloads", "Fit", "Actions"]) {
    assert.match(models, new RegExp(`role="columnheader">${heading}<`));
  }
  assert.match(models, /data-table-kind="discover-model-table"/);
  assert.match(models, /data-testid="discover-model-row"/);
  assert.match(models, /aria-controls="discover-model-inspector"/);
  assert.match(models, /data-testid="discover-model-inspector"/);
  assert.match(models, /data-testid="discover-inspector-tabs"/);
  assert.match(models, /data-testid="discover-inspector-resizer"/);
  assert.match(models, /aria-label="Resize discover model inspector"/);
  assert.match(models, /data-testid="discover-row-download"/);
  assert.match(models, /data-testid="discover-download-action"/);
  assert.match(models, /data-testid="discover-variant-picker"/);
  assert.match(models, /Purpose/);
  assert.match(models, /Modalities/);
  assert.match(models, /License/);
});

test("Models inventory uses the forge-green workspace language and responsive inspector layout", () => {
  assert.match(styles, /--models-forge:\s*#4f8a70/);
  assert.match(styles, /models-inventory-workbench[^}]*grid-template-columns/s);
  assert.match(styles, /studio-installed-row\.is-selected/);
  assert.match(styles, /models-model-inspector/);
  assert.match(styles, /is-discover-route \.models-page-content \{ grid-column: 1;/);
  assert.match(styles, /model-publisher-logo\.is-qwen/);
  assert.match(styles, /models-workspace-v3\.models-view \.models-page-tabs \{ gap: 0;/);
  assert.match(styles, /models-page-tabs > \.models-v3-tab[^}]*margin-top: 0/s);
  assert.match(styles, /models-discover-head/);
  assert.match(styles, /models-discover-row\.is-selected/);
  assert.match(styles, /models-discover-workbench/);
  assert.match(styles, /models-catalog-pagination\.is-compact/);
  assert.match(styles, /@media \(max-width: 1050px\)/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
});

test("Models workspace v3 remains scoped and responsive", () => {
  assert.match(styles, /models-workspace-v3/);
  assert.match(styles, /@media \(max-width: 900px\)/);
  assert.match(styles, /@media \(max-width: 640px\)/);
  assert.doesNotMatch(styles, /!important/);
});
