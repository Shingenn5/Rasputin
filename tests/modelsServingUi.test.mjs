import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const models = readFileSync(new URL("../frontend-src/src/features/models/ModelsView.jsx", import.meta.url), "utf8");
const serving = readFileSync(new URL("../frontend-src/src/features/models/ModelServingPanel.jsx", import.meta.url), "utf8");
const interfaceCss = readFileSync(new URL("../frontend-src/src/styles/interface.css", import.meta.url), "utf8");
const backend = readFileSync(new URL("../backend/api/serving.py", import.meta.url), "utf8");

test("Models rail collapses persistently to accessible icon-only navigation", () => {
  assert.match(models, /rasputin-models-rail-collapsed/);
  assert.match(models, /data-testid="models-rail-toggle"/);
  assert.match(models, /aria-expanded={!modelsRailCollapsed}/);
  assert.match(models, /aria-controls="models-navigation"/);
  assert.match(models, /role="tablist" aria-orientation=\{desktopOnly \? "vertical" : "horizontal"\}/);
  assert.match(models, /aria-label={desktopOnly && modelsRailCollapsed \? desktopItem\.label : undefined}/);
  assert.match(models, /tabIndex={activeTab === t\.id \? 0 : -1}/);
  assert.match(models, /ArrowRight/);
  assert.match(models, /ArrowLeft/);
  assert.match(models, /event\.key === "Home"/);
  assert.match(models, /event\.key === "End"/);
  assert.match(interfaceCss, /data-models-rail-collapsed="true".*grid-template-columns: 58px/s);
  assert.match(interfaceCss, /data-models-rail-collapsed="true".*\[role="tab"\] > span/s);
  assert.match(interfaceCss, /@media \(max-width: 780px\)[\s\S]*models-page-tabs[\s\S]*overflow-x: auto/);
});

test("Models Serving panel exposes each required protocol and guarded controls", () => {
  assert.match(models, /id: "serving".*icon: RadioTower/);
  assert.match(models, /<ModelServingPanel onOpenModels=\{\(\) => setActiveTab\("running"\)\} \/>/);
  assert.match(serving, /serving-protocol-\$\{protocol\.id}/);
  assert.match(serving, /protocol\.id/);
  assert.match(serving, /serving-enable-toggle/);
  assert.match(serving, /serving-key-rotate/);
  assert.match(serving, /serving-mcp-toggle/);
  assert.match(serving, /never execute MCP tools automatically/);
  assert.match(serving, /never prompts or message text/);
  assert.match(serving, /anthropic-version: 2023-06-01/);
  assert.match(serving, /Limited MCP JSON-RPC HTTP/);
  assert.match(serving, /serving-readiness/);
  assert.match(serving, /nextActions/);
  assert.match(serving, /aria-live="polite"/);
  assert.match(serving, /Copy headers/);
  assert.doesNotMatch(serving, /One loaded model runtime/);
  assert.doesNotMatch(serving, /Local inference gateway/);
  assert.doesNotMatch(serving, /full Streamable HTTP/);
  assert.match(interfaceCss, /serving-panel-header[\s\S]*flex-wrap: wrap/);
});

test("backend owns OpenAI, Anthropic, Rasputin, and MCP serving routes", () => {
  for (const route of [
    "/v1/models",
    "/v1/chat/completions",
    "/v1/messages",
    "/rasputin/v1/responses",
    "/rasputin/v1/metrics",
    "/mcp",
  ]) {
    assert.match(backend, new RegExp(route.replaceAll("/", "\\/")));
  }
  assert.match(backend, /model_serving_config_v1/);
  assert.match(backend, /mcp_tool_execution.*False/s);
  assert.match(backend, /"prompt_logging": False/);
});
