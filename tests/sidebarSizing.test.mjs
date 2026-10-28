import assert from "node:assert/strict";
import test from "node:test";
import { clampSidebarWidth, sidebarWidthForKey, SIDEBAR_DEFAULT_WIDTH, SIDEBAR_MIN_WIDTH, SIDEBAR_MAX_WIDTH } from "../frontend-src/src/components/shell/sidebarSizing.js";

test("sidebar restores valid persisted width and bounds malformed or out-of-range values", () => {
  assert.equal(clampSidebarWidth("305.4"), 305);
  assert.equal(clampSidebarWidth(null), SIDEBAR_DEFAULT_WIDTH);
  assert.equal(clampSidebarWidth("bad"), SIDEBAR_DEFAULT_WIDTH);
  assert.equal(clampSidebarWidth(Infinity), SIDEBAR_DEFAULT_WIDTH);
  assert.equal(clampSidebarWidth(100), SIDEBAR_MIN_WIDTH);
  assert.equal(clampSidebarWidth(500), SIDEBAR_MAX_WIDTH);
});

test("keyboard resizing supports small and large steps, limits and reset", () => {
  assert.equal(sidebarWidthForKey("ArrowRight", 260), 270);
  assert.equal(sidebarWidthForKey("ArrowLeft", 260, true), 220);
  assert.equal(sidebarWidthForKey("ArrowRight", 390, true), 400);
  assert.equal(sidebarWidthForKey("Home", 300), SIDEBAR_MIN_WIDTH);
  assert.equal(sidebarWidthForKey("End", 300), SIDEBAR_MAX_WIDTH);
  assert.equal(sidebarWidthForKey("Enter", 300), SIDEBAR_DEFAULT_WIDTH);
  assert.equal(sidebarWidthForKey("Escape", 300), null);
});
