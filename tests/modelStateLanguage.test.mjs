import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../frontend-src/src/features/models/ModelsView.jsx", import.meta.url), "utf8");
const start = source.indexOf("export function modelOperationalSignal");
const end = source.indexOf("function ModelStateSignal", start);
assert.ok(start >= 0 && end > start, "model signal helper has a pure-function boundary");
const helper = source.slice(start, end).replace("export function", "function");
const modelOperationalSignal = new Function("runtimeStatus", `${helper}\nreturn modelOperationalSignal;`)(
  (model) => model.runtimeStatus || "unknown",
);

test("model state language separates live, parked, and down", () => {
  assert.deepEqual(modelOperationalSignal({ runtimeStatus: "reachable" }), { key: "live", label: "Live", detail: "Serving now" });
  assert.deepEqual(modelOperationalSignal({ runtimeStatus: "stopped" }), { key: "parked", label: "Parked", detail: "Ready to load" });
  assert.deepEqual(modelOperationalSignal({ runtimeStatus: "unhealthy" }), { key: "down", label: "Down", detail: "Needs attention" });
  assert.deepEqual(modelOperationalSignal({}), { key: "parked", label: "Parked", detail: "Status not confirmed" });
});
