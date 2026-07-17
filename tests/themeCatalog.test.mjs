import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { darkThemes, themeOptions } from "../frontend-src/src/lib/constants.js";

const indexHtml = readFileSync(new URL("../frontend-src/index.html", import.meta.url), "utf8");
const bootThemeEntries = [...indexHtml.matchAll(/^\s+"([a-z0-9-]+)": \{[^\n]+dark: (true|false) \}/gm)]
  .map((match) => ({ key: match[1], dark: match[2] === "true" }));

test("every picker theme has exactly one boot-time palette", () => {
  const pickerKeys = themeOptions.map(([key]) => key).sort();
  const bootKeys = bootThemeEntries.map(({ key }) => key).sort();
  assert.deepEqual(bootKeys, pickerKeys);
  assert.equal(new Set(pickerKeys).size, pickerKeys.length);
});

test("dark theme metadata matches the boot-time palette", () => {
  const bootDarkKeys = bootThemeEntries.filter(({ dark }) => dark).map(({ key }) => key).sort();
  assert.deepEqual([...darkThemes].sort(), bootDarkKeys);
});

test("expanded library contains balanced new light and dark palettes", () => {
  const additions = [
    "violet-circuit",
    "evergreen-console",
    "ember-noir",
    "porcelain-blue",
    "sepia-studio",
    "orchid-paper",
  ];
  const pickerKeys = new Set(themeOptions.map(([key]) => key));
  additions.forEach((key) => assert.ok(pickerKeys.has(key), `${key} is missing`));
  assert.equal(additions.filter((key) => darkThemes.has(key)).length, 3);
});
