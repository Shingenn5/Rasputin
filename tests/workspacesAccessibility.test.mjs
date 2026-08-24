import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const component = readFileSync(new URL("../frontend-src/src/features/workspaces/WorkspacesView.jsx", import.meta.url), "utf8");
const styles = readFileSync(new URL("../frontend-src/src/styles/rasputin.css", import.meta.url), "utf8") + readFileSync(new URL("../frontend-src/src/styles/interface.css", import.meta.url), "utf8");

test("Docker workspace setup exposes saved, restart, recheck, and approval steps", () => {
  assert.match(component, /setMountWorkflowStep\(native \? "ready" : "restart"\)/);
  assert.match(component, /Runtime \{">"\} Containers/);
  assert.match(component, /api\("\/api\/workspace\/mount-requests"\)/);
  assert.match(component, /Recheck/);
  assert.match(component, /Approve folder/);
  assert.match(component, /matching\?\.ready/);
  assert.match(component, /aria-label="Folder setup progress"/);
});

test("native workspace setup remains restart-free", () => {
  assert.match(component, /native \? "ready" : "restart"/);
  assert.match(component, /right now; no mount or restart needed/);
  assert.match(component, /native && \([\s\S]*Start chatting/);
  assert.match(component, /await selectWorkspace\?\.\(saved\?\.workspace\?\.id/);
  assert.match(component, /go\?\.\("chat"\)/);
});

test("workspace roots and explorer entries are keyboard-operable tree items", () => {
  assert.match(component, /role="tree" aria-label="Approved workspace folders"/);
  assert.match(component, /role="treeitem"[\s\S]*aria-selected=\{active\}[\s\S]*onKeyDown=\{\(event\) => handleTreeItemKeyDown/);
  assert.match(component, /role="tree" aria-label="Workspace files and folders"/);
  assert.match(component, /tabIndex=\{0\}[\s\S]*aria-selected=\{selectedEntry\?\.path === entry\.path\}/);
  assert.match(component, /aria-expanded=\{entry\.kind === "folder" \? false : undefined\}/);
  assert.match(component, /event\.key !== "Enter" && event\.key !== " "/);
});

test("workspace controls have visible focus treatment and 1024px safeguards", () => {
  assert.match(styles, /\.w2-tree-item:focus-visible/);
  assert.match(styles, /\.workspace-folder-modal button:focus-visible/);
  assert.match(styles, /@media \(max-width: 1080px\)[\s\S]*\.workspaces-view \.w2-main-grid/);
  assert.match(styles, /\.folder-picker-workflow-status/);
  assert.match(styles, /\.pending-mount-heading-actions/);
});
