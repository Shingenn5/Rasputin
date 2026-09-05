import assert from "node:assert/strict";
import test from "node:test";
import { findInstalledCatalogModel, firstLoadCanResolvePlacement } from "../frontend-src/src/features/models/modelEcosystem.js";

test("Discover links a Hugging Face repository to its durable My Models artifact", () => {
  const installed = {
    key: "artifact-qwen",
    runtime: "native-llamacpp",
    repository: "unsloth/Qwen3.8-27B-GGUF",
    artifactAvailable: true,
  };
  assert.equal(findInstalledCatalogModel(
    { modelId: "https://huggingface.co/unsloth/Qwen3.8-27B-GGUF" },
    [{ runtime: "warsat-llama.cpp", model: "unsloth/Qwen3.8-27B-GGUF" }, installed],
  ), installed);
  assert.equal(findInstalledCatalogModel({ modelId: "other/model" }, [installed]), null);
});

test("first load can defer a capability-only layer-split decision to runtime installation", () => {
  const preview = {
    blocked: true,
    blockReasons: ["model requires 15600 MiB but no permitted GPU allocation fits"],
    resolvedSettings: { requiredMemoryMb: 15600 },
  };
  const hardware = { detectedHardware: { gpus: [
    { memoryFreeMb: 11577 },
    { memoryFreeMb: 12391 },
  ] } };
  assert.equal(firstLoadCanResolvePlacement(preview, { state: "install_required" }, hardware), true);
  assert.equal(firstLoadCanResolvePlacement({ ...preview, resolvedSettings: { requiredMemoryMb: 24000 } }, { state: "install_required" }, hardware), false);
  assert.equal(firstLoadCanResolvePlacement(preview, { state: "ready" }, hardware), false);
  assert.equal(firstLoadCanResolvePlacement({ ...preview, blockReasons: ["requested context exceeds model limit"] }, { state: "install_required" }, hardware), false);
});


test("explicit GGUF selection cannot load another installed variant or revision", () => {
  const model = { runtime: "native-llamacpp", repository: "org/model", variant_id: "q4", revision: "abc", artifactAvailable: true };
  const running = { ...model, variant_id: "q8", containerStatus: "running" };
  assert.equal(findInstalledCatalogModel({ modelId: "org/model" }, [running, model], { id: "q4", revision: "abc" }), model);
  assert.equal(findInstalledCatalogModel({ modelId: "org/model" }, [running], { id: "q4" }), null);
  assert.equal(findInstalledCatalogModel({ modelId: "org/model" }, [model], { id: "q4", revision: "different" }), null);
  assert.equal(findInstalledCatalogModel({ modelId: "org/model" }, [{ ...model, artifactAvailable: false }], { id: "q4" }), null);
});

test("provisional placement respects an explicit GPU or split restriction", () => {
  const preview = { blockReasons: ["no permitted GPU allocation fits"], resolvedSettings: { requiredMemoryMb: 15000 } };
  const runtime = { state: "install_required" };
  const hardware = { devices: [{ freeMb: 12000 }, { freeMb: 12000 }] };
  for (const profile of [{ splitMode: "none" }, { mainGpu: 0 }, { tensorSplit: "1,1" }, { gpuLayers: 0 }, { memoryMode: "cpu_only" }]) {
    assert.equal(firstLoadCanResolvePlacement(preview, runtime, hardware, profile), false);
  }
});
