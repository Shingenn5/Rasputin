const path = require("node:path");
const {
  app,
  BrowserWindow,
  clipboard,
  dialog,
  Menu,
  nativeImage,
  session,
  shell,
  Tray,
} = require("electron");
const { BackendSupervisor } = require("./backend-supervisor.cjs");
const { loadDesktopSettings, saveDesktopSettings } = require("./settings.cjs");

let mainWindow = null;
let tray = null;
let supervisor = null;
let quitting = false;
let shutdownComplete = false;
let desktopSettings = { closeBehavior: "tray" };

app.setName("Rasputin");
app.setPath("userData", path.join(process.env.APPDATA || app.getPath("appData"), "Rasputin"));
if (process.env.RASPUTIN_DISABLE_HARDWARE_ACCELERATION === "1") {
  app.disableHardwareAcceleration();
}

const hasInstanceLock = app.requestSingleInstanceLock();
if (!hasInstanceLock) app.quit();

function projectRoot() {
  return app.isPackaged ? process.resourcesPath : path.resolve(__dirname, "..");
}

function packagedBackend() {
  if (!app.isPackaged) return null;
  const executable = process.platform === "win32" ? "rasputin-backend.exe" : "rasputin-backend";
  return path.join(process.resourcesPath, "backend", executable);
}

function nativeDataDir() {
  if (process.env.RASPUTIN_DATA_DIR?.trim()) return path.resolve(process.env.RASPUTIN_DATA_DIR);
  const localRoot = process.env.LOCALAPPDATA || app.getPath("userData");
  return path.join(localRoot, "Rasputin", "data");
}

function nativeLogDir() {
  const localRoot = process.env.LOCALAPPDATA || app.getPath("userData");
  return path.join(localRoot, "Rasputin", "logs");
}

function trayImage() {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
      <rect width="32" height="32" rx="8" fill="#111318"/>
      <path d="M8 23V9h8.2c4 0 6.5 2.2 6.5 5.6 0 2.3-1.2 4.1-3.3 5l4.1 3.4h-5.2l-3.4-3H12v3H8zm4-6.5h4c1.7 0 2.6-.6 2.6-1.9s-.9-1.9-2.6-1.9h-4v3.8z" fill="#ff5f57"/>
    </svg>`;
  return nativeImage.createFromDataURL(`data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`);
}

function pageHtml(title, message, accent = "#ff5f57") {
  return `<!doctype html>
    <html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
    <style>
      :root{color-scheme:dark}body{margin:0;background:#0b0d11;color:#edf0f7;font:15px/1.5 system-ui;display:grid;place-items:center;height:100vh}
      main{width:min(520px,80vw);padding:36px;border:1px solid #252a35;border-radius:22px;background:#12151b;box-shadow:0 28px 90px #0008}
      i{display:block;width:42px;height:4px;border-radius:4px;background:${accent};margin-bottom:28px}h1{font-size:25px;margin:0 0 12px}p{color:#aab1c0;margin:0;white-space:pre-wrap}
    </style></head><body><main><i></i><h1>${title}</h1><p>${message}</p></main></body></html>`;
}

async function showPage(title, message, accent) {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  await mainWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(pageHtml(title, message, accent))}`);
}

function showWindow() {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show();
  mainWindow.focus();
}

function rebuildTrayMenu() {
  if (!tray || !supervisor) return;
  const attached = supervisor.status === "attached";
  const running = supervisor.status === "running" || attached;
  const busy = supervisor.status === "starting" || supervisor.status === "stopping";
  tray.setToolTip(`Rasputin Desktop — ${supervisor.status}`);
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: "Open Rasputin", click: showWindow },
    { label: attached ? "Native Server: connected" : `Desktop Runtime: ${supervisor.status}`, enabled: false },
    { type: "separator" },
    {
      label: "Start Desktop Runtime",
      enabled: !running && !busy,
      click: () => startEngine(),
    },
    {
      label: attached ? "Stop Native Server" : "Stop Desktop Runtime",
      enabled: running && !busy,
      click: () => stopEngine(),
    },
    {
      label: "Restart Desktop Runtime",
      enabled: running && !busy && !attached,
      click: () => restartEngine(),
    },
    {
      label: "Keep running when window closes",
      type: "checkbox",
      checked: desktopSettings.closeBehavior === "tray",
      click: (menuItem) => {
        desktopSettings = saveDesktopSettings(app.getPath("userData"), {
          ...desktopSettings,
          closeBehavior: menuItem.checked ? "tray" : "quit",
        });
        rebuildTrayMenu();
      },
    },
    { label: "Show logs", click: () => shell.showItemInFolder(supervisor.logPath) },
    { type: "separator" },
    {
      label: "Quit Rasputin",
      click: () => {
        quitting = true;
        app.quit();
      },
    },
  ]));
}

async function loadRasputin(url) {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  await mainWindow.loadURL(url);
  showWindow();
}

async function startEngine() {
  try {
    await showPage("Starting Rasputin", "Preparing your Desktop Runtime and local workspace…");
    showWindow();
    const url = await supervisor.start();
    await loadRasputin(url);
  } catch (error) {
    await showPage("Rasputin could not start", `${error.message}\n\nUse the tray menu to open the desktop log.`, "#ffb454");
    showWindow();
    dialog.showErrorBox("Rasputin could not start", error.message);
  }
}

async function stopEngine() {
  try {
    await supervisor.stop({ includeAttached: true });
    await showPage("Runtime stopped", "Rasputin is still available in the system tray. Start it there whenever you are ready.", "#6f7787");
  } catch (error) {
    dialog.showErrorBox("Rasputin could not stop", error.message);
  }
}

async function restartEngine() {
  try {
    await showPage("Restarting Rasputin", "Stopping and starting the Desktop Runtime…");
    const url = await supervisor.restart();
    await loadRasputin(url);
  } catch (error) {
    await showPage("Rasputin could not restart", `${error.message}\n\nUse the tray menu to open the desktop log.`, "#ffb454");
    dialog.showErrorBox("Rasputin could not restart", error.message);
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 940,
    minWidth: 1000,
    minHeight: 680,
    show: false,
    backgroundColor: "#0b0d11",
    autoHideMenuBar: true,
    title: "Rasputin",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });

  mainWindow.on("close", (event) => {
    if (quitting) return;
    event.preventDefault();
    if (desktopSettings.closeBehavior === "tray") {
      mainWindow.hide();
      return;
    }
    quitting = true;
    app.quit();
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("https://")) shell.openExternal(url);
    return { action: "deny" };
  });
  mainWindow.webContents.on("will-navigate", (event, url) => {
    const ownUrl = supervisor?.url;
    if (!ownUrl || url.startsWith(ownUrl) || url.startsWith("data:text/html")) return;
    event.preventDefault();
    if (url.startsWith("https://")) shell.openExternal(url);
  });
}

function createTray() {
  tray = new Tray(trayImage().resize({ width: 20, height: 20 }));
  tray.on("double-click", showWindow);
  rebuildTrayMenu();
}

app.on("second-instance", () => showWindow());

app.on("before-quit", async (event) => {
  quitting = true;
  if (shutdownComplete) return;
  event.preventDefault();
  try {
    await supervisor?.stop({ includeAttached: false });
  } finally {
    shutdownComplete = true;
    app.quit();
  }
});

app.whenReady().then(async () => {
  Menu.setApplicationMenu(null);
  session.defaultSession.setPermissionRequestHandler((_webContents, permission, callback) => {
    callback(permission === "notifications");
  });
  desktopSettings = loadDesktopSettings(app.getPath("userData"));

  supervisor = new BackendSupervisor({
    projectRoot: projectRoot(),
    dataDir: nativeDataDir(),
    logDir: nativeLogDir(),
    requestedPort: process.env.RASPUTIN_DESKTOP_PORT,
    backendExecutable: packagedBackend(),
  });
  supervisor.on("status", ({ status, detail }) => {
    rebuildTrayMenu();
    if (status === "crashed" && !quitting) {
      showPage("Desktop Runtime stopped unexpectedly", `${detail}\n\nUse the tray menu to inspect the desktop log and restart.`, "#ffb454");
    }
  });
  supervisor.on("credentials", async ({ username, password }) => {
    const result = await dialog.showMessageBox(mainWindow, {
      type: "info",
      title: "Rasputin is ready",
      message: "Your local administrator account was created.",
      detail: `Username: ${username}\nPassword: ${password}\n\nCopy this password now and change it after signing in. The desktop log stores a redacted value.`,
      buttons: ["Copy password", "Continue"],
      defaultId: 1,
      cancelId: 1,
      noLink: true,
    });
    if (result.response === 0) clipboard.writeText(password);
  });

  createWindow();
  createTray();
  await startEngine();

  const smokeCloseMs = Number(process.env.RASPUTIN_DESKTOP_SMOKE_CLOSE_MS) || 0;
  if (smokeCloseMs > 0) {
    setTimeout(() => mainWindow?.close(), smokeCloseMs);
  }
  const smokeExitMs = Number(process.env.RASPUTIN_DESKTOP_SMOKE_EXIT_MS) || 0;
  if (smokeExitMs > 0) {
    setTimeout(() => {
      quitting = true;
      app.quit();
    }, smokeExitMs);
  }
});
