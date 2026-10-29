import { readFeatureSource } from "./sourceModules.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

import { darkThemes, themeOptions } from "../frontend-src/src/lib/constants.js";

const indexHtml = readFeatureSource(new URL("../frontend-src/index.html", import.meta.url));
const appSource = readFeatureSource(new URL("../frontend-src/src/app/App.jsx", import.meta.url));
const preferenceSource = readFileSync(new URL("../backend/core/preferences.py", import.meta.url), "utf8");
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

test("every palette chooses readable text for its solid primary actions", () => {
  const properties = new Map();
  const root = { dataset: {}, classList: { add() {}, remove() {} }, style: { setProperty: (key, value) => properties.set(key, value) } };
  const context = { window: {}, document: { documentElement: root, querySelector: () => ({ setAttribute() {} }) }, localStorage: { getItem: () => null } };
  runInNewContext(indexHtml.match(/<script>([\s\S]*?)<\/script>/)[1], context);
  function luminance(hex) {
    const channels = hex.slice(1).match(/../g).map((value) => parseInt(value, 16) / 255)
      .map((value) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
    return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
  }
  for (const [theme] of themeOptions) {
    context.window.rasputinTheme.apply(theme);
    const a = luminance(properties.get("--base-accent"));
    const b = luminance(properties.get("--base-accent-contrast"));
    assert.ok((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05) >= 4.5, `${theme} primary text fails contrast`);
  }
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

test("Rasputin boots dark unless the user explicitly selected light", () => {
  assert.match(indexHtml, /storedTheme \|\| "rasputin-dark"/);
  assert.match(indexHtml, /rasputin-theme-explicit/);
  assert.match(appSource, /useState\(readInitialTheme\)/);
  assert.match(appSource, /storedTheme === "rasputin-light" \? "rasputin-dark"/);
  assert.match(preferenceSource, /"theme": "rasputin-dark"/);
});
