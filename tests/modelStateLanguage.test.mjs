import test from "node:test";
import assert from "node:assert/strict";
import { modelOperationalSignal } from "../frontend-src/src/features/models/modelPresentation.js";

test("model state language separates live, parked, and down", () => {
  assert.deepEqual(modelOperationalSignal({ runtimeStatus: "reachable" }), { key: "live", label: "Live", detail: "Serving now" });
  assert.deepEqual(modelOperationalSignal({ runtimeStatus: "stopped" }), { key: "parked", label: "Parked", detail: "Ready to load" });
  assert.deepEqual(modelOperationalSignal({ runtimeStatus: "unhealthy" }), { key: "down", label: "Down", detail: "Needs attention" });
  assert.deepEqual(modelOperationalSignal({}), { key: "parked", label: "Parked", detail: "Status not confirmed" });
});
