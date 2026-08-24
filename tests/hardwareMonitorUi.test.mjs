import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const shell = readFileSync(new URL("../frontend-src/src/components/AppShell.jsx", import.meta.url), "utf8");
const monitor = readFileSync(new URL("../frontend-src/src/components/shell/HardwareMonitor.jsx", import.meta.url), "utf8");
const resources = readFileSync(new URL("../frontend-src/src/features/settings/ResourceSettings.jsx", import.meta.url), "utf8");
const modelSettings = readFileSync(new URL("../frontend-src/src/features/settings/ModelSettings.jsx", import.meta.url), "utf8");
const settingsView = readFileSync(new URL("../frontend-src/src/features/settings/SettingsView.jsx", import.meta.url), "utf8");
const app = readFileSync(new URL("../frontend-src/src/app/App.jsx", import.meta.url), "utf8");

test("AppShell mounts the persistent hardware monitor from settings", () => {
  assert.match(shell, /useSettingsStore/);
  assert.match(shell, /HardwareMonitor/);
  assert.match(shell, /showLiveUsage/);
});

test("hardware monitor polls only when enabled and exposes compact usage", () => {
  assert.match(monitor, /enabled = false/);
  assert.match(monitor, /api\("\/api\/warsat\/system-metrics"\)/);
  assert.match(monitor, /data-testid="hardware-monitor"/);
  assert.match(monitor, /GPU telemetry unavailable/);
  assert.doesNotMatch(monitor, /docker/i);
});

test("resource settings persist the always-show toggle", () => {
  assert.match(resources, /data-testid="hardware-monitor-switch"/);
  assert.match(resources, /updateSetting\("hardware", "showLiveUsage"/);
  assert.match(resources, /Always show live hardware usage/);
});


test("model settings expose real memory placement and keep desktop llama.cpp-only", () => {
  assert.match(modelSettings, /data-testid="model-memory-mode"/);
  assert.match(modelSettings, /value="hybrid">Hybrid CPU\/GPU/);
  assert.match(modelSettings, /RAM is not presented as VRAM/);
  assert.match(settingsView, /<ModelSettings desktopOnly=\{desktopOnly\}/);
  assert.match(modelSettings, /!desktopOnly && <Form.Check type="radio" id="engine-vllm"/);
  assert.match(modelSettings, /!desktopOnly && <Form.Check type="radio" id="engine-ollama"/);
});


test("desktop boot hydrates administrator settings for the global monitor", () => {
  assert.match(app, /async function loadBasics\(activeRole/);
  assert.match(app, /if \(activeRole === "admin"\) loadSettings\(\)/);
  assert.doesNotMatch(app, /if \(data\.session\?\.role === "admin"\) loadSettings\(\)/);
});
