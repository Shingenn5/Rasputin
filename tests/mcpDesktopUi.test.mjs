import { readFeatureSource } from "./sourceModules.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const settings = readFeatureSource(new URL("../frontend-src/src/features/settings/SettingsView.jsx", import.meta.url));
const app = readFeatureSource(new URL("../frontend-src/src/app/App.jsx", import.meta.url));
const constants = readFeatureSource(new URL("../frontend-src/src/lib/constants.js", import.meta.url));
const mcp = readFeatureSource(new URL("../frontend-src/src/features/settings/McpSettings.jsx", import.meta.url));

 test("desktop settings exposes the MCP management surface", () => {
  assert.match(constants, /\["mcp", "MCP Servers"/);
  assert.match(settings, /import \{ McpSettings \} from "\.\/McpSettings\.jsx"/);
  assert.match(settings, /effectiveSection === "mcp"/);
  assert.match(settings, /registerMcpFixture=\{registerMcpFixture\}/);
  assert.match(app, /restartMcpRelay=\{restartMcpRelay\}/);
  assert.match(app, /removeMcpRelay=\{removeMcpRelay\}/);
});

test("MCP settings keeps registration and execution guarded", () => {
  assert.match(mcp, /Add Streamable HTTP/);
  assert.match(mcp, /Add local stdio/);
  assert.match(mcp, /data-testid="mcp-settings"/);
  assert.match(mcp, /data-testid="mcp-server-dialog"/);
  assert.match(mcp, /Registration is waiting for administrator approval/);
  assert.match(mcp, /approved Rasputin workspace/);
  assert.match(mcp, /Allow guarded/);
  assert.match(mcp, /Test tool/);
  assert.match(mcp, /third-party MCP server packages still need their own executable/i);
});
