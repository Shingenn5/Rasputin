import test from "node:test";
import assert from "node:assert/strict";
import { isManagedModelRunning } from "../frontend-src/src/lib/display.js";

test("native registry camelCase status exposes Stop for its owned running process", () => {
  assert.equal(isManagedModelRunning({ managed: true, runtime: "native-llamacpp", containerStatus: "running", runtimeStatus: "reachable" }), true);
  assert.equal(isManagedModelRunning({ managed: true, runtimeStatus: "reachable" }), true);
  assert.equal(isManagedModelRunning({ managed: true, container_status: "running", runtime_status: "reachable" }), true);
  assert.equal(isManagedModelRunning({ managed: true, containerStatus: "running", runtimeStatus: "unreachable" }), true);
});

test("stopped or externally owned models cannot become running from stale health", () => {
  assert.equal(isManagedModelRunning({ managed: true, containerStatus: "stopped", runtimeStatus: "reachable" }), false);
  assert.equal(isManagedModelRunning({ managed: true, runtimeStatus: "stopped", lastHealth: { status: "reachable" } }), false);
  assert.equal(isManagedModelRunning({ managed: true, lastHealth: { status: "reachable" } }), false);
  assert.equal(isManagedModelRunning({ managed: false, runtimeStatus: "reachable" }), false);
  assert.equal(isManagedModelRunning(null), false);
});
