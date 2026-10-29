import test from "node:test";
import assert from "node:assert/strict";
import { applyMotionMode, normalizeMotionMode, readStoredMotionMode } from "../frontend-src/src/lib/motion.js";

test("system motion follows the OS while explicit choices win without being overwritten", () => {
  let reduced = true;
  let stored = null;
  globalThis.localStorage = { getItem: () => stored };
  globalThis.document = { documentElement: { dataset: {} } };
  globalThis.window = { matchMedia: () => ({ matches: reduced }), dispatchEvent() {} };
  try {
    assert.equal(readStoredMotionMode(), "system");
    assert.equal(normalizeMotionMode("unexpected"), "system");
    assert.equal(applyMotionMode("system"), "reduced");
    assert.equal(applyMotionMode("full"), "full");
    reduced = false;
    assert.equal(applyMotionMode("system"), "full");
    assert.equal(applyMotionMode("reduced"), "reduced");
    stored = "full";
    assert.equal(readStoredMotionMode(), "full");
    assert.equal(stored, "full");
  } finally {
    delete globalThis.localStorage;
    delete globalThis.document;
    delete globalThis.window;
  }
});
