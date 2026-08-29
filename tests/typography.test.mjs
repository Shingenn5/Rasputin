import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const main = readFileSync(new URL("../frontend-src/src/main.jsx", import.meta.url), "utf8");
const dashboardStyles = readFileSync(new URL("../frontend-src/src/styles/dashboard.css", import.meta.url), "utf8");
const interfaceStyles = readFileSync(new URL("../frontend-src/src/styles/interface.css", import.meta.url), "utf8");
const startup = readFileSync(new URL("../frontend-src/index.html", import.meta.url), "utf8");
const packageJson = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));

test("application typography bundles one readable variable font", () => {
  assert.equal(packageJson.dependencies["@fontsource-variable/atkinson-hyperlegible-next"], "^5.3.0");
  assert.equal(packageJson.dependencies["@fontsource/rajdhani"], undefined);
  assert.match(main, /@fontsource-variable\/atkinson-hyperlegible-next\/wght\.css/);
  assert.match(main, /@fontsource-variable\/atkinson-hyperlegible-next\/wght-italic\.css/);
  assert.doesNotMatch(main, /rajdhani/i);
});

test("body, display text, controls, and startup UI share the readable font", () => {
  assert.match(dashboardStyles, /--ras-font-display:\s*"Atkinson Hyperlegible Next Variable"/);
  assert.match(dashboardStyles, /--ras-font-ui:\s*"Atkinson Hyperlegible Next Variable"/);
  assert.match(interfaceStyles, /body\s*\{[^}]*font-family:\s*var\(--ras-font-ui\)/s);
  assert.match(interfaceStyles, /button,\s*input,\s*textarea,\s*select\s*\{[^}]*font-family:\s*var\(--ras-font-ui\)/s);
  assert.match(startup, /font:\s*700 18px\/1 "Atkinson Hyperlegible Next Variable"/);
  assert.doesNotMatch(startup, /rajdhani/i);
});

test("technical content remains differentiated with the mono token", () => {
  assert.match(dashboardStyles, /--ras-font-mono:/);
  assert.match(interfaceStyles, /code,\s*pre,\s*kbd,\s*\.log-box\s*\{[^}]*font-family:\s*var\(--ras-font-mono\)/s);
});
