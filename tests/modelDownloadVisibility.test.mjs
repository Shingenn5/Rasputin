import assert from "node:assert/strict";
import test from "node:test";
import { showsGlobalDownloadProgress } from "../frontend-src/src/lib/modelDownloadVisibility.js";

test("completed and cancelled download receipts do not remain in the global progress rail", () => {
  assert.equal(showsGlobalDownloadProgress("completed"), false);
  assert.equal(showsGlobalDownloadProgress(" COMPLETED "), false);
  assert.equal(showsGlobalDownloadProgress("cancelled"), false);
});

test("actionable and in-flight downloads remain visible", () => {
  for (const state of ["queued", "resolving", "downloading", "paused", "verifying", "installing", "failed", "unknown", ""]) {
    assert.equal(showsGlobalDownloadProgress(state), true, state);
  }
});
