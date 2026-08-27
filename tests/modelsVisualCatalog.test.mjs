import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const models = readFileSync(new URL("../frontend-src/src/features/models/ModelsView.jsx", import.meta.url), "utf8");
const identity = readFileSync(new URL("../frontend-src/src/features/models/ModelIdentity.jsx", import.meta.url), "utf8");
const publisherLogo = readFileSync(new URL("../frontend-src/src/features/models/PublisherLogo.jsx", import.meta.url), "utf8");
const loader = readFileSync(new URL("../frontend-src/src/features/models/ModelLoadDialog.jsx", import.meta.url), "utf8");
const app = readFileSync(new URL("../frontend-src/src/app/App.jsx", import.meta.url), "utf8");
const sidebar = readFileSync(new URL("../frontend-src/src/components/shell/DashSidebar.jsx", import.meta.url), "utf8");

test("desktop Discover Models opens into a native llama.cpp visual catalog", () => {
  assert.match(models, /data-testid="model-catalog-grid"/);
  assert.match(models, /useState\(\(\) => view === "discover" \? "library" : "installed"\)/);
  assert.match(models, /setShowAllModels\(true\)/);
  assert.match(models, /setSearchMode\("browse"\)/);
  assert.match(models, /q: searchMode === "browse" \? "" : hfQuery/);
  assert.match(models, /data-testid="discover-browse-models"/);
  assert.match(models, /data-testid="discover-search-models"/);
  assert.match(models, /data-testid="discover-model-catalog"/);
  assert.match(models, /data-table-kind="discover-model-table"/);
  assert.match(models, /data-testid="discover-model-row"/);
  assert.match(models, /data-testid="discover-model-inspector"/);
  assert.match(models, /data-testid="discover-inspector-resizer"/);
  assert.match(models, /<PublisherLogo item=\{item\} size="md" \/>/);
  assert.match(models, /<strong>\{searchMode === "browse" \? "Available Models"/);
  assert.match(models, /setCatalogRuntime\("llamaCppGgufServer"\)/);
  assert.match(models, /searchMode === "catalog" && !desktopOnly/);
  assert.match(models, /className="models-page-shell/);
  assert.match(models, /className="models-page-tabs"/);
  assert.match(models, /const desktopItem = \{/);
  assert.match(sidebar, /view: "discover", label: "Discover Models"/);
  assert.doesNotMatch(models, /id: "library",\s+label: "Library"/);
  assert.match(models, /settings: \{ label: "Developer", hint: "Runtime and connections" \}/);
  assert.match(models, /className="models-catalog-toolbar"/);
  assert.match(models, /aria-label="Refresh model catalog"/);
  assert.doesNotMatch(models, /Models <span className="text-muted-foreground">Center<\/span>/);
  assert.match(models, /data-testid="studio-installed-list"/);
  assert.match(models, /data-testid="models-developer-header"/);
  assert.match(models, />No Docker<\/Badge>/);
});

test("model cards use generated identity and collapse advanced details", () => {
  assert.match(models, /<ModelIdentity item=\{item\}/);
  assert.match(models, /<details ref=\{advancedRef\}/);
  assert.match(models, /<summary[^>]*>Advanced details<\/summary>/);
  assert.match(identity, /<PublisherLogo item=\{\{ \.\.\.item, publisher, modelId \}\}/);
  assert.match(publisherLogo, /id: "qwen"/);
  assert.match(publisherLogo, /id: "deepseek"/);
  assert.match(publisherLogo, /id: "meta"/);
  assert.match(publisherLogo, /aria-label=\{`\$\{brand\.label\} logo`\}/);
  assert.doesNotMatch(identity, /<img/);
});


test("desktop model catalog exposes selection details and a real llama.cpp loader", () => {
  assert.match(models, /models-discover-workbench/);
  assert.match(models, /<DiscoverModelInspector/);
  assert.match(models, /aria-label="Discover model inspector sections"/);
  assert.match(models, /const tabs = \["info", "download", "fit", "source"\]/);
  assert.match(models, /data-testid="discover-variant-picker"/);
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
