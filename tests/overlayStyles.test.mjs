import { readFeatureSource } from "./sourceModules.mjs";
/**
 * Structural contract for the first behavior-neutral stylesheet extraction.
 *
 * Interaction behavior is covered in the running-app verification; this test
 * prevents the modal/drawer rules from drifting back into the legacy bundle.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const legacy = readFeatureSource("frontend-src/src/styles/rasputin.css");
const overlays = readFeatureSource("frontend-src/src/styles/overlays.css");
const modal = readFeatureSource("frontend-src/src/components/Modal.jsx");

test("modal and drawer primitives have one explicit stylesheet owner", () => {
  assert.match(legacy, /^@import "\.\/overlays\.css";/);
  assert.doesNotMatch(legacy, /\.ras-modal-layer\s*[,\{]/);
  assert.doesNotMatch(legacy, /\.ras-drawer-layer\s*[,\{]/);

  assert.match(overlays, /\.ras-modal-layer\s*,/);
  assert.match(overlays, /\.ras-modal\s*\{/);
  assert.match(overlays, /\.ras-drawer-layer\s*\{/);
  assert.match(overlays, /\.ras-drawer\.task-details-drawer\s*\{/);
  assert.match(modal, /styles\/overlays\.css/);
});
