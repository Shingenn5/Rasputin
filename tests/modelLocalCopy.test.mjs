import test from "node:test";
import assert from "node:assert/strict";
import { localCopyForModel } from "../frontend-src/src/features/models/nativeDeployment.js";

test("an exact local GGUF recovers an external connection or retired runtime", () => {
  const local = { key: "native", model: "Qwen-35B-Q4_K_M.gguf", runtime: "native-llamacpp", artifactAvailable: true };
  for (const connection of [
    { model: "Qwen-35B-Q4_K_M", runtime: "external-local" },
    { model: "org/Qwen-35B-Q4_K_M", runtime: "warsat-llama.cpp" },
  ]) assert.equal(localCopyForModel(connection, [local]), local);
  assert.equal(localCopyForModel({ model: "Qwen-35B-Q6_K" }, [local]), null);
  assert.equal(localCopyForModel({ model: "Qwen-35B-Q4_K_M" }, [{ ...local, artifactAvailable: false }]), null);
  assert.equal(localCopyForModel({ model: "Qwen-35B-Q4_K_M" }, [local, { ...local, key: "duplicate" }]), null);
  assert.equal(localCopyForModel({ model: "Qwen-35B-Q4_K_M", runtime: "remote-api" }, [local]), null);
});
