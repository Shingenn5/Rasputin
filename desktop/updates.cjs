// Only the main process owns updates. No renderer IPC or configurable feed URL.
const { verifyWindowsSignature } = require("./update-signature.cjs");

function loadDesktopUpdater({ isPackaged, platform, windowsStore, resourcesPath, load = require }) {
  // Store packages must never cross over to the GitHub/NSIS update channel.
  if (!isPackaged || platform !== "win32" || windowsStore) return null;
  return load(require("node:path").join(resourcesPath, "updater.cjs")).autoUpdater;
}

function createDesktopUpdates({ updater, dialog, install, changed = () => {}, timers = globalThis }) {
  let status = "Check for updates";
  let busy = false;
  let downloaded = false;
  let installing = false;
  let stopped = false;
  let interval;
  let startup;

  updater.autoDownload = true;
  updater.autoInstallOnAppQuit = false;
  updater.allowPrerelease = false;
  updater.allowDowngrade = false;
  updater.verifyUpdateCodeSignature = verifyWindowsSignature;

  function setStatus(label, pending = false) {
    status = label;
    busy = pending;
    changed();
  }

  async function apply() {
    if (!downloaded || installing || stopped) return;
    installing = true;
    try {
      const { response } = await dialog.showMessageBox({
        type: "question",
        title: "Rasputin update ready",
        message: "Restart Rasputin to install the downloaded update?",
        detail: "Finish any running tasks first. The Desktop Runtime will stop before installation. Your models and application data stay in place.",
        buttons: ["Restart and install", "Later"],
        defaultId: 1,
        cancelId: 1,
        noLink: true,
      });
      if (response === 0 && !stopped) await install();
    } catch {
      setStatus("Update could not install — retry");
      await dialog.showMessageBox({ type: "error", message: "Rasputin could not stop safely for the update. Try again after finishing running tasks." }).catch(() => {});
    } finally {
      installing = false;
    }
  }

  updater.on("checking-for-update", () => setStatus("Checking for updates…", true));
  updater.on("update-available", () => setStatus("Downloading update…", true));
  updater.on("update-not-available", () => setStatus("Up to date — check again"));
  updater.on("error", () => setStatus("Update failed — retry"));
  updater.on("update-downloaded", () => {
    downloaded = true;
    setStatus("Restart to install update");
    // Background downloads never restart the app without a native confirmation.
    void apply();
  });

  async function check() {
    if (busy || stopped) return;
    if (downloaded) return apply();
    setStatus("Checking for updates…", true);
    try {
      await updater.checkForUpdates();
    } catch {
      setStatus("Update failed — retry");
    }
  }

  return {
    menuItem: () => ({ label: status, enabled: !busy && !installing, click: check }),
    check,
    start() {
      startup = timers.setTimeout(() => void check(), 30_000);
      interval = timers.setInterval(() => void check(), 6 * 60 * 60 * 1000);
      startup.unref?.();
      interval.unref?.();
    },
    stop() {
      stopped = true;
      timers.clearTimeout(startup);
      timers.clearInterval(interval);
    },
  };
}

module.exports = { createDesktopUpdates, loadDesktopUpdater };
