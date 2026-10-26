import test from "node:test";
import assert from "node:assert/strict";
import { modelOperationalSignal } from "../frontend-src/src/features/models/modelPresentation.js";

test("model state language separates ready, unloaded, and disconnected models", () => {
  for (const [model, expected] of [
    [{ runtimeStatus: "reachable" }, { key: "live", label: "Ready", action: "chat" }],
    [{ runtime: "native-llamacpp", runtimeStatus: "stopped" }, { key: "parked", label: "Not loaded", action: "load" }],
    [{ runtimeStatus: "unhealthy" }, { key: "down", label: "App not connected", action: "connection" }],
    [{ runtime: "native-llamacpp" }, { key: "parked", label: "Not loaded", action: "load" }],
  ]) {
    const { key, label, action, detail, next } = modelOperationalSignal(model);
    assert.deepEqual({ key, label, action }, expected);
    assert.ok(detail && next, "Each state explains the problem and next action");
  }
});
