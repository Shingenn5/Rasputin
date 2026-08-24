import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const app = readFileSync(new URL("../frontend-src/src/app/App.jsx", import.meta.url), "utf8");
const sidebar = readFileSync(new URL("../frontend-src/src/components/shell/DashSidebar.jsx", import.meta.url), "utf8");
const settings = readFileSync(new URL("../frontend-src/src/features/settings/SettingsView.jsx", import.meta.url), "utf8");
const mcp = readFileSync(new URL("../frontend-src/src/features/settings/McpSettings.jsx", import.meta.url), "utf8");
const modal = readFileSync(new URL("../frontend-src/src/components/Modal.jsx", import.meta.url), "utf8");
const history = readFileSync(new URL("../frontend-src/src/features/tasks/TasksView.jsx", import.meta.url), "utf8");
const projects = readFileSync(new URL("../frontend-src/src/features/workspaces/WorkspacesView.jsx", import.meta.url), "utf8");
const interfaceCss = readFileSync(new URL("../frontend-src/src/styles/interface.css", import.meta.url), "utf8");

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


test("desktop shell uses a quiet icon rail and Settings opens as a modal", () => {
  assert.match(sidebar, /"sm:w-\[54px\]"/);
  assert.match(sidebar, /const expanded = mobileOpen \|\| !collapsed/);
  assert.match(sidebar, /collapsed \? "sm:w-\[54px\]" : "sm:w-\[220px\]"/);
  assert.match(sidebar, /data-testid="sidebar-project-list"/);
  assert.match(sidebar, /Index and Graphify/);
  assert.match(settings, /className="studio-settings-modal"/);
  assert.match(settings, /open=\{view === "settings"\}/);
  assert.doesNotMatch(settings, /AccountsSettings/);
  assert.doesNotMatch(settings, /accounts: Users/);
});

test("desktop Settings closes from the visual backdrop", () => {
  assert.match(modal, /classList\?\.contains\("ras-modal-backdrop"\)/);
  assert.match(settings, /onClose=\{\(\) => go\("chat"\)\}/);
});

test("History uses one visible view strip instead of nested advanced disclosures", () => {
  assert.match(history, /data-testid="history-view-tabs"/);
  assert.match(history, /const activityGroups = \[/);
  assert.match(history, /history-nav-group/);
  assert.match(history, /history-inspector-heading/);
  assert.doesNotMatch(history, /history-advanced-tabs/);
  assert.doesNotMatch(history, /history-advanced-disclosure/);
});

test("Projects keeps Graphify available in the compact viewport-contained surface", () => {
  assert.match(projects, /useState\(true\)/);
  assert.match(projects, /data-testid="project-graphify"/);
  assert.match(projects, /Graphify/);
  assert.match(projects, /workspace-access-menu/);
  assert.match(projects, /> Open Folder/);
  assert.match(interfaceCss, /height: calc\(100dvh - 120px\) !important/);
});

test("primary desktop views use coherent local section rails", () => {
  assert.match(interfaceCss, /Coherent desktop section navigation/);
  assert.match(interfaceCss, /grid-template-columns: 172px minmax\(0, 1fr\)/);
  assert.match(interfaceCss, /\.models-catalog-toolbar/);
});

test("desktop MCP management is a compact searchable integrations surface", () => {
  assert.match(mcp, /compact = false/);
  assert.match(mcp, /placeholder="Filter integrations\.\.\."/);
  assert.match(mcp, /mcp-compact/);
  assert.match(mcp, /filteredServers\.map/);
});
