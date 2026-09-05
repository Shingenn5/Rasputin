import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const app = readFileSync(new URL("../frontend-src/src/app/App.jsx", import.meta.url), "utf8");

test("normal startup leaves chat model unselected", () => {
  const start = app.indexOf("function pickBootModel");
  const end = app.indexOf("\nfunction ", start + 1);
  assert.ok(start >= 0, "boot model selector exists");
  assert.ok(end > start, "boot model selector has a function boundary");
  const selector = app.slice(start, end);

  assert.match(selector, /prefs\.testingMode/);
  assert.match(selector, /models\.some\(\(model\) => model\.key === "dry-run"\) \? "dry-run" : null/);
  assert.match(selector, /\n  return null;\n/);
  assert.doesNotMatch(selector, /prefs\.selectedModel/);
});
