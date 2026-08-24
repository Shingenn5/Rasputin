import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const app = readFileSync(new URL("../frontend-src/src/app/App.jsx", import.meta.url), "utf8");

test("desktop navigation uses minimal project and history aliases", () => {
  assert.match(app, /rawView === "project" \? "workspaces"/);
  assert.match(app, /rawView === "history" \? "activity"/);
  assert.match(app, /if \(view === "workspaces"\) return "#project"/);
  assert.match(app, /if \(view === "activity"\) return "#history"/);
  assert.match(app, /const desktopDefaultView = data\.security\?\.desktopOnly \? "chat" : "home"/);
  assert.match(app, /desktopPrimaryViews = new Set\(\["chat", "workspaces", "activity", "models", "settings"\]\)/);
});

test("desktop command palette describes the simplified primary workflow", () => {
  assert.match(app, /label: "Open project", hint: "Choose a folder and work from it\."/);
  assert.match(app, /label: "Open history", hint: "Review conversations, runs, failures, and notifications\."/);
  assert.match(app, /label: "Open models", hint: "Browse, download, and load local models\."/);
  assert.doesNotMatch(app, /label: "Open workspaces"/);
  assert.doesNotMatch(app, /label: "Open activity inbox"/);
});
