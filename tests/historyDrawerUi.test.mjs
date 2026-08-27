import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const sidebar = readFileSync(new URL("../frontend-src/src/components/shell/DashSidebar.jsx", import.meta.url), "utf8");

test("primary navigation keeps history compact instead of a full destination", () => {
  assert.doesNotMatch(sidebar, /view: "activity", label: "History"/);
  assert.match(sidebar, /data-testid="history-drawer-trigger"/);
  assert.match(sidebar, /aria-expanded=\{historyOpen\}/);
  assert.match(sidebar, /aria-controls="history-drawer"/);
});

test("history drawer supports search, recent-session actions, and the full activity route", () => {
  assert.match(sidebar, /data-testid="history-drawer"/);
  assert.match(sidebar, /role="dialog"/);
  assert.match(sidebar, /data-testid="history-search"/);
  assert.match(sidebar, /data-testid="history-session-list"/);
  assert.match(sidebar, /data-testid=\{"history-session-" \+ s\.id\}/);
  assert.match(sidebar, /data-testid="history-view-all"/);
  assert.match(sidebar, /go\("activity"\)/);
  assert.match(sidebar, /event\.key === "Escape"/);
});

test("history drawer preserves cleanup and delete controls for task-capable users", () => {
  assert.match(sidebar, /data-testid="sidebar-clear-empty-chats"/);
  assert.match(sidebar, /data-testid=\{"sidebar-delete-chat-" \+ s\.id\}/);
  assert.match(sidebar, /resumeSession\?\.\(s\.id\)/);
  assert.match(sidebar, /deleteSession\?\.\(s\)/);
});
