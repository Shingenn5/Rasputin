/**
 * Structural contract for the first behavior-neutral stylesheet extraction.
 *
 * Interaction behavior is covered in the running-app verification; this test
 * prevents the modal/drawer rules from drifting back into the legacy bundle.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const legacy = readFileSync("frontend-src/src/styles/rasputin.css", "utf8");
const overlays = readFileSync("frontend-src/src/styles/overlays.css", "utf8");
const modal = readFileSync("frontend-src/src/components/Modal.jsx", "utf8");

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
