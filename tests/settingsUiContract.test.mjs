import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../frontend-src/src/features/settings/SettingsView.jsx", import.meta.url), "utf8");
const styles = readFileSync(new URL("../frontend-src/src/styles/interface.css", import.meta.url), "utf8");

test("reset opens a confirmation and keeps restore behind explicit confirm", () => {
  const resetButton = source.match(/<button[^>]+className="is-danger"[^>]+onClick=\{\(\) => setResetDialogOpen\(true\)\}[^>]*>[^<]*<RefreshCw[\s\S]*?<\/button>/)?.[0];
  assert.ok(resetButton, "the Reset button should only open the confirmation dialog");
  assert.doesNotMatch(resetButton, /restoreDefaults\("all"\)/);

  assert.match(source, /role="dialog"/);
  assert.match(source, /aria-modal="true"/);
  assert.match(source, /This restores every Settings section to its defaults/);
  assert.match(source, /Existing settings will be replaced/);

  const cancel = source.match(/data-testid="settings-reset-cancel"[\s\S]*?<\/button>/)?.[0];
  assert.ok(cancel);
  assert.match(cancel, /setResetDialogOpen\(false\)/);
  assert.doesNotMatch(cancel, /restoreDefaults|setAllSettings|setDomainSettings/);

  const confirmHandler = source.match(/const handleResetConfirm = async \(\) => \{([\s\S]*?)\n  \};/)?.[1];
  assert.ok(confirmHandler);
  assert.match(confirmHandler, /setResetDialogOpen\(false\)/);
  assert.match(confirmHandler, /await restoreDefaults\("all"\)/);
});

test("settings status reflects existing loading, loaded, and error state", () => {
  assert.doesNotMatch(source, /Schema valid/);
  assert.match(source, /const loading = useSettingsStore\(\(state\) => state\.loading\)/);
  assert.match(source, /const settingsErrors = useSettingsStore\(\(state\) => state\.errors\)/);
  assert.match(source, /const settingsError = Object\.values\(settingsErrors \|\| \{\}\)\.find\(Boolean\)/);
  assert.match(source, /label: "Settings action in progress…"/);
  assert.match(source, /label: statusError/);
  assert.match(source, /label: "Settings loaded"/);
  assert.match(source, /loadSettings\(\)\.finally\(\(\) => setSettingsLoaded\(true\)\)/);
  assert.match(source, /role="status" aria-live="polite"/);
  assert.match(styles, /\.settings-validation\.is-loading/);
  assert.match(styles, /\.settings-validation\.is-error/);
  assert.match(source, /className="settings-status-spinner"/);
  assert.match(styles, /\.settings-status-spinner/);
});

test("import only accepts a selected plain JSON object", () => {
  const importButton = source.match(/<button[^>]+onClick=\{handleImportClick\}[^>]*>[\s\S]*?Import<\/button>/)?.[0];
  assert.ok(importButton);
  assert.doesNotMatch(importButton, /importSettings/);
  assert.doesNotMatch(source, /importSettings\(\{\}\)/);

  assert.match(source, /type="file"/);
  assert.match(source, /accept="application\/json"/);
  assert.match(styles, /\.settings-import-input/);
  assert.match(source, /onChange=\{handleImportFile\}/);

  const importHandler = source.match(/const handleImportFile = async \(event\) => \{([\s\S]*?)\n  \};/)?.[1];
  assert.ok(importHandler);
  assert.match(importHandler, /const file = input\.files\?\.\[0\]/);
  assert.match(importHandler, /input\.value = ""/);
  assert.match(importHandler, /JSON\.parse\(await file\.text\(\)\)/);
  assert.match(importHandler, /if \(!isPlainSettingsObject\(parsed\)\)/);
  assert.match(importHandler, /Import file is empty or invalid JSON/);
  assert.match(importHandler, /Import file must contain a JSON object/);
  assert.ok(importHandler.indexOf("if (!isPlainSettingsObject(parsed))") < importHandler.indexOf("importSettings(parsed)"));
  assert.match(source, /function isPlainSettingsObject\(value\)/);
  assert.match(source, /value !== null/);
  assert.match(source, /!Array\.isArray\(value\)/);
});

test("reset controls have focused keyboard-safe defaults", () => {
  assert.match(source, /data-testid="settings-reset-cancel"[^>]+onClick=\{\(\) => setResetDialogOpen\(false\)\} autoFocus/);
  assert.match(source, /event\.key === "Escape"[\s\S]*setResetDialogOpen\(false\)/);
  assert.match(styles, /\.settings-reset-actions button:focus-visible/);
});
