import test from "node:test";
import assert from "node:assert/strict";
import { usesNativeModels, needsNativeModelDownload, prepareNativeModel } from "../frontend-src/src/features/models/nativeDeployment.js";

test("native browser servers and desktop use native models, Docker servers retain Docker", () => {
  assert.equal(usesNativeModels({ native: true, desktopOnly: false }), true);
  assert.equal(usesNativeModels({ desktopOnly: true }), true);
  assert.equal(usesNativeModels({ native: false, desktopOnly: false }), false);
  assert.equal(needsNativeModelDownload({ managed: true, runtime: "warsat-vllm" }, true), true);
  assert.equal(needsNativeModelDownload({ managed: true, runtime: "native-llamacpp" }, true), false);
  assert.equal(needsNativeModelDownload({ managed: false, runtime: "external-local" }, true), false);
});
test("native local GGUF preparation imports the existing file without Docker or downloads", async () => {
  const calls = [];
  const result = await prepareNativeModel({ hostModelPath: "C:/models/coder.gguf", purpose: "coding" }, {}, {
    api: () => { throw Error("unexpected request"); },
    postJson: async (...args) => { calls.push(args); return { key: "coder", runtime: "native-llamacpp" }; },
  });
  assert.equal(result.runtime, "native-llamacpp");
  assert.deepEqual(calls, [["/api/model-registry/import-gguf", { path: "C:/models/coder.gguf", role: "coder", context: 4096 }]]);
});
test("native catalog deployment submits an exact compatible GGUF variant", async () => {
  const calls = [];
  const variant = { id: "Q4_K_M", compatibilityState: "compatible" };
  const result = await prepareNativeModel({ modelId: "org/model" }, {}, {
    api: async (url) => { calls.push(url); return { variants: [variant] }; },
    selectVariant: (variants) => variants[0],
    postJson: async (...args) => { calls.push(args); return { id: "job" }; },
  });
  assert.equal(result.status, "downloading");
  assert.deepEqual(calls, ["/api/model-catalog/model/org/model", ["/api/models/download", { modelId: "org/model", variant }]]);
});
test("missing or incompatible GGUF variants cannot trigger raw-weight or Docker deployment", async () => {
  for (const variants of [[], [{ compatibilityState: "blocked" }]]) {
    await assert.rejects(prepareNativeModel({ modelId: "org/model" }, {}, {
      api: async () => ({ variants }), selectVariant: (items) => items[0],
      postJson: () => { throw Error("must not submit"); },
    }), /no compatible GGUF variant/);
  }
});
