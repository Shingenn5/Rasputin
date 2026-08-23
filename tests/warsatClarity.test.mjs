import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync("frontend-src/src/features/warsat/WarsatView.jsx", "utf8");
const guidanceSource = fs.readFileSync("frontend-src/src/features/shared/blockerGuidance.js", "utf8");
const styles = fs.readFileSync("frontend-src/src/styles/rasputin.css", "utf8");

test("WarSat maps known blockers to plain-language next actions", () => {
  assert.match(source, /combined_vram_requires_explicit_opt_in/);
  assert.match(source, /unsupported/);
  assert.match(source, /approval required/);
  assert.match(source, /download/);
  assert.match(source, /health/);
  assert.match(source, /What happened:/);
  assert.match(source, /What to do next:/);
  assert.match(source, /go\("settings", "models"\)/);
});

test("WarSat keeps unknown admission reasons visible", () => {
  assert.match(source, /Reasons:\s*\{admittedResource\.reasons\.join/);
  assert.match(source, /getWarsatGuidance/);
});

test("disabled WarSat deployment explains blockers and links the action to them", () => {
  assert.match(guidanceSource, /Unknown deployment blocker/);
  assert.match(source, /data-testid="warsat-deployment-blockers"/);
  assert.match(source, /aria-describedby=\{deployDisabled && deploymentBlockers\.length > 0/);
  assert.match(source, /Deployment blocked — how to fix it/);
  assert.match(source, /What this means:/);
  assert.match(source, /Next step:/);
});

test("WarSat tabs are labeled, keyboard navigable, and scrollable at tablet width", () => {
  assert.match(source, /role="tablist"/);
  assert.match(source, /aria-label="WarSat views"/);
  assert.match(source, /role="tab"/);
  assert.match(source, /aria-selected=\{activeTab === t\.id\}/);
  assert.match(source, /ArrowRight/);
  assert.match(source, /data-testid="warsat-tabs"/);
  assert.match(styles, /\.warsat-tabs/);
  assert.match(styles, /overflow-x:\s*auto/);
  assert.match(styles, /Scroll for more WarSat views/);
});
