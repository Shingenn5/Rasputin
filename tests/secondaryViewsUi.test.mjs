import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), "utf8");

const main = read("frontend-src/src/main.jsx");
const css = read("frontend-src/src/styles/secondary-views.css");
const history = read("frontend-src/src/features/tasks/TasksView.jsx");
const models = read("frontend-src/src/features/models/ModelsView.jsx");
const settings = read("frontend-src/src/features/settings/SettingsView.jsx");

test("loads the secondary workspace layer after the base interface and before motion", () => {
  const base = main.indexOf('import "./styles/interface.css";');
  const secondary = main.indexOf('import "./styles/secondary-views.css";');
  const motion = main.indexOf('import "./styles/motion.css";');
  assert.ok(base >= 0 && secondary > base && motion > secondary);
});

test("uses one compact visual contract across secondary workspaces", () => {
  assert.match(css, /Secondary workspace UI v2/);
  assert.match(css, /--sv-rail-width:\s*148px/);
  assert.match(css, /--sv-command-height:\s*44px/);
  assert.match(css, /--sv-radius:\s*7px/);
});

test("history keeps accessible tabs while gaining a dense timeline and inspector", () => {
  assert.match(history, /data-testid="history-view-tabs"/);
  assert.match(history, /role="tab"/);
  assert.match(history, /aria-selected=/);
  assert.match(css, /\.history-view-tab\.is-active/);
  assert.match(css, /\.history-main-grid article\s*\{/);
  assert.match(css, /\.history-inspector\s*\{/);
  assert.match(css, /minmax\(190px,\s*218px\)/);
});

test("models keeps its accessible navigation and compacts every operator surface", () => {
  assert.match(models, /className="models-page-tabs"/);
  assert.match(models, /role="tablist"/);
  assert.match(models, /data-testid="models-rail-toggle"/);
  assert.match(css, /models-page-tabs \[role="tab"\]\[aria-selected="true"\]/);
  assert.match(css, /studio-model-detail section/);
  assert.match(css, /studio-installed-row[^}]*min-height:\s*54px/s);
  assert.match(css, /model-serving-panel/);
});

test("settings retains semantic navigation and uses the shared compact rail", () => {
  assert.match(settings, /className="studio-settings-modal"/);
  assert.match(settings, /aria-label="Settings sections"/);
  assert.match(settings, /aria-current=/);
  assert.match(css, /studio-settings-layout[^}]*var\(--sv-rail-width\)/s);
  assert.match(css, /studio-settings-nav button[^}]*min-height:\s*30px/s);
  assert.match(css, /settings-command-hero/);
});

test("the rework has explicit mobile and reduced-motion behavior", () => {
  assert.match(css, /@media \(max-width:\s*780px\)/);
  assert.match(css, /@media \(prefers-reduced-motion:\s*reduce\)/);
});
