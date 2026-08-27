import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const view = readFileSync(new URL("../frontend-src/src/features/settings/SettingsView.jsx", import.meta.url), "utf8");
const css = readFileSync(new URL("../frontend-src/src/styles/settings-workspace-v3.css", import.meta.url), "utf8");

test("Settings v3 has a dedicated command-center composition", () => {
  assert.match(view, /settings-workspace-v3\.css/);
  assert.match(view, /settings-command-banner-v3/);
  assert.match(view, /settings-control-grid-v3/);
  assert.match(view, /settings-context-strip-v3/);
  assert.match(css, /compact command-center treatment/);
  assert.match(css, /grid-template-columns: 194px minmax\(0, 1fr\)/);
  assert.match(css, /settings-posture-v3/);
});

test("Settings v3 preserves interaction and accessibility hooks", () => {
  assert.match(view, /data-testid=\{`settings-\$\{id\}`\}/);
  assert.match(view, /aria-current=\{effectiveSection === id \? "page" : undefined\}/);
  assert.match(view, /role="status" aria-live="polite"/);
  assert.match(view, /settings-scope-essentials/);
  assert.match(view, /settings-scope-advanced/);
  assert.match(view, /handleImportClick/);
  assert.match(view, /exportSettings/);
  assert.match(view, /settings-reset-confirm/);
  assert.match(view, /IntegrationSettings/);
});

test("Settings v3 retains responsive containment and reduced motion", () => {
  assert.match(css, /@media \(max-width: 760px\)/);
  assert.match(css, /grid-template-columns: 1fr/);
  assert.match(css, /data-motion="reduced"/);
  assert.match(css, /overflow-x: auto/);
});
