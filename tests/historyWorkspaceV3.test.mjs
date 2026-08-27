import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
const view=readFileSync(new URL("../frontend-src/src/features/tasks/TasksView.jsx",import.meta.url),"utf8");
const css=readFileSync(new URL("../frontend-src/src/styles/history-workspace-v3.css",import.meta.url),"utf8");
test("History workspace v3 has a ledger composition",()=>{ assert.match(view,/history-workspace-v3\.css/); assert.match(view,/history-view-tabs/); assert.match(view,/aria-selected=\{tab === item\}/); assert.match(view,/history-stream-command/); assert.match(view,/history-timeline-row/); assert.match(view,/history-status-signal/); assert.match(view,/history-v3-inspector/); assert.match(view,/activityIcons/); assert.match(view,/tabCounts/); });
test("History workspace v3 CSS provides visible hierarchy and responsive behavior",()=>{ assert.match(css,/LIVE ACTIVITY LEDGER/); assert.match(css,/history-stream-list::before/); assert.match(css,/history-status-signal/); assert.match(css,/history-v3-toolbar .*history-view-tab\.is-active/); assert.match(css,/max-width: 780px/); assert.match(css,/prefers-reduced-motion/); });
