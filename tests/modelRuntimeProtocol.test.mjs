import test from "node:test";
import assert from "node:assert/strict";
import { modelRuntimeProtocol } from "../frontend-src/src/lib/engines.js";

const llama = "llamaCppGgufServer";
const vllm = "vllmCudaOpenai";
const model = (...protocols) => ({
  recommendedProtocol: protocols[0],
  runtimeOptions: protocols.map(protocolId => ({ protocolId })),
});

test("llama.cpp is the default before settings or model metadata arrive", () => {
  assert.equal(modelRuntimeProtocol(null), llama);
  assert.equal(modelRuntimeProtocol(null, null), llama);
});

test("automatic prefers llama.cpp over catalog order and legacy engine settings", () => {
  assert.equal(modelRuntimeProtocol(model(vllm, llama)), llama);
  assert.equal(modelRuntimeProtocol(model(vllm, llama), { selectionMode: "automatic", defaultEngine: "vllm" }), llama);
});

test("automatic follows the model's supported formats on each selection", () => {
  for (const protocol of [llama, vllm, "ollamaOpenaiServer", llama]) {
    assert.equal(modelRuntimeProtocol(model(protocol)), protocol);
  }
  assert.equal(modelRuntimeProtocol({ recommendedProtocol: vllm }), vllm);
  assert.equal(modelRuntimeProtocol({ ...model(vllm), recommendedProtocol: llama }), vllm);
});

test("manual preferences apply only when the model supports them", () => {
  const settings = { selectionMode: "manual", defaultEngine: "vllm" };
  assert.equal(modelRuntimeProtocol(model(llama, vllm), settings), vllm);
  assert.equal(modelRuntimeProtocol(model(llama), settings), llama);
});

test("API-only models are never converted into local inference requests", () => {
  assert.equal(modelRuntimeProtocol(model("apiOnly")), "apiOnly");
  assert.equal(modelRuntimeProtocol({ apiOnly: true, ...model(llama) }), "apiOnly");
});
