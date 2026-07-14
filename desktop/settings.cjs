const fs = require("node:fs");
const path = require("node:path");

const DEFAULT_DESKTOP_SETTINGS = Object.freeze({
  closeBehavior: "tray",
});

function normalizedCloseBehavior(value) {
  return value === "quit" ? "quit" : "tray";
}

function loadDesktopSettings(userDataDir, environment = process.env) {
  let stored = {};
  const settingsPath = path.join(userDataDir, "desktop-settings.json");
  try {
    stored = JSON.parse(fs.readFileSync(settingsPath, "utf8"));
  } catch {
    stored = {};
  }
  const override = environment.RASPUTIN_DESKTOP_CLOSE_BEHAVIOR?.trim().toLowerCase();
  return {
    ...DEFAULT_DESKTOP_SETTINGS,
    ...stored,
    closeBehavior: normalizedCloseBehavior(override || stored.closeBehavior),
  };
}

function saveDesktopSettings(userDataDir, settings) {
  fs.mkdirSync(userDataDir, { recursive: true });
  const settingsPath = path.join(userDataDir, "desktop-settings.json");
  const temporaryPath = `${settingsPath}.tmp`;
  const value = {
    ...DEFAULT_DESKTOP_SETTINGS,
    ...settings,
    closeBehavior: normalizedCloseBehavior(settings.closeBehavior),
  };
  fs.writeFileSync(temporaryPath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  fs.renameSync(temporaryPath, settingsPath);
  return value;
}

module.exports = {
  DEFAULT_DESKTOP_SETTINGS,
  loadDesktopSettings,
  normalizedCloseBehavior,
  saveDesktopSettings,
};
