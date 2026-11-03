import { readFeatureSource } from "./sourceModules.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { useEventConnection } from "../frontend-src/src/app/useEventConnection.js";

const app = readFeatureSource("frontend-src/src/app/App.jsx");
const home = readFeatureSource("frontend-src/src/features/chat/HomeView.jsx");
const onboarding = readFeatureSource("frontend-src/src/components/Onboarding.jsx");

test("chat keeps a persistent recovery path when no healthy model is routeable", () => {
  assert.match(app, /hasHealthyRouteableChatModel/);
  assert.match(home, /data-testid="chat-launch-readiness"/);
  assert.match(home, /Find a model/);
  assert.match(home, /Connect endpoint/);
  assert.match(home, /onClick=\{onEnableTestingMode\}>Testing Mode<\/button>/);
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

test("event stream recovery survives Strict Mode cleanup and tracks degraded state", () => {
  assert.match(app, /mountedRef\.current = true;\s+boot\(\)/);
  assert.match(app, /scheduleEventReconnect/);
  assert.match(app, /startEventFallbackRefresh/);
  // The old header status badge was removed. Verify reconnection behavior rather
  // than requiring its obsolete markup to come back.
  const previousWindow = globalThis.window;
  const previousEventSource = globalThis.EventSource;
  const statuses = [];
  const sources = [];
  let reconnect;
  let refreshes = 0;
  const ref = (current = null) => ({ current });
  try {
    globalThis.window = {
      setTimeout: (callback) => { reconnect = callback; return 1; },
      clearTimeout: () => {},
      setInterval: () => 2,
      clearInterval: () => {},
    };
    globalThis.EventSource = class {
      constructor() { sources.push(this); }
      close() {}
    };
    const context = {
      eventReconnectTimerRef: ref(), eventFallbackTimerRef: ref(),
      eventGenerationRef: ref(0), eventSourceRef: ref(), mountedRef: ref(true),
      eventRetryAttemptRef: ref(0), setEventConnectionStatus: (status) => statuses.push(status),
      loadTasks: async () => { refreshes++; },
    };
    const connection = useEventConnection(context);
    connection.connectEvents();
    sources[0].onerror();
    assert.equal(statuses.at(-1), "degraded");
    assert.equal(refreshes, 1);
    assert.equal(context.eventFallbackTimerRef.current, 2);
    reconnect();
    sources[1].onopen();
    assert.equal(statuses.at(-1), "connected");
    assert.equal(context.eventFallbackTimerRef.current, null);
    assert.equal(context.eventRetryAttemptRef.current, 0);
  } finally {
    globalThis.window = previousWindow;
    globalThis.EventSource = previousEventSource;
  }
});

test("a fast task completion cannot be overwritten by the queued creation response", () => {
  assert.match(app, /function reconcileCreatedTaskSnapshot/);
  assert.match(app, /taskLifecycleRank\(existing\.status\) > taskLifecycleRank\(createdTask\.status\)/);
  assert.match(app, /setTasks\(\(current\) => reconcileCreatedTaskSnapshot\(current, task, tempId\)\)/);
  assert.match(app, /queryClient\.invalidateQueries\(\{ queryKey: \["tasks"\] \}\)/);
});
