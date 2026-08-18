import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const app = readFileSync("frontend-src/src/app/App.jsx", "utf8");
const home = readFileSync("frontend-src/src/features/chat/HomeView.jsx", "utf8");
const onboarding = readFileSync("frontend-src/src/components/Onboarding.jsx", "utf8");

test("chat keeps a persistent recovery path when no healthy model is routeable", () => {
  assert.match(app, /hasHealthyRouteableChatModel/);
  assert.match(home, /data-testid="chat-launch-readiness"/);
  assert.match(home, /Find a model/);
  assert.match(home, /Connect endpoint/);
  assert.match(home, /Try Testing Mode/);
  assert.match(app, /updateTestingMode\(true\)/);
});

test("unsupported task modes remain visible and blocked instead of silently rerouting", () => {
  assert.match(app, /const modeBlocked = taskMode !== "chat"/);
  assert.match(app, /modeBlocked=\{modeBlocked\}/);
  assert.match(home, /data-testid="mode-blocked"/);
});

test("completed chat messages expose the authoritative runtime identity", () => {
  assert.match(home, /data-testid="task-runtime-identity"/);
  assert.match(home, /Model " \+ taskModel \+ " · Mode "/);
  assert.match(home, /deploymentProfile/);
});

test("onboarding traps keyboard focus and restores the prior focus target", () => {
  assert.match(onboarding, /event\.key === "Tab"/);
  assert.match(onboarding, /dialogRef\.current\?\.querySelectorAll/);
  assert.match(onboarding, /returnFocusRef/);
});

test("event stream recovery survives Strict Mode cleanup and exposes degraded state", () => {
  assert.match(app, /mountedRef\.current = true;\s+boot\(\)/);
  assert.match(app, /scheduleEventReconnect/);
  assert.match(app, /startEventFallbackRefresh/);
  assert.match(home, /data-testid="event-connection-status"/);
});

test("a fast task completion cannot be overwritten by the queued creation response", () => {
  assert.match(app, /function reconcileCreatedTaskSnapshot/);
  assert.match(app, /taskLifecycleRank\(existing\.status\) > taskLifecycleRank\(createdTask\.status\)/);
  assert.match(app, /setTasks\(\(current\) => reconcileCreatedTaskSnapshot\(current, task, tempId\)\)/);
  assert.match(app, /queryClient\.invalidateQueries\(\{ queryKey: \["tasks"\] \}\)/);
});
