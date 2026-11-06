// Measurement fixture: the same backend supervisor, without production tray or
// updater work. It gives Electron a deliberately conservative comparison.
const { app, BrowserWindow, session } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const { BackendSupervisor } = require('../../desktop/backend-supervisor.cjs');
const started = performance.now();
const root = process.env.RASPUTIN_BASELINE_ROOT;
if (!root) throw new Error('The benchmark must provide an isolated baseline root');
app.setPath('userData', path.join(root, 'webview'));
let supervisor;
let window;
let stopped = false;
app.whenReady().then(async () => {
  supervisor = new BackendSupervisor({
    projectRoot: path.resolve(__dirname, '../..'),
    dataDir: path.join(root, 'data'),
    logDir: path.join(root, 'logs'),
    backendExecutable: process.env.RASPUTIN_BASELINE_BACKEND || null,
  });
  const url = await supervisor.start();
  const healthMs = performance.now() - started;
  window = new BrowserWindow({ width: 1440, height: 940, autoHideMenuBar: true,
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true } });
  // The fixture exercises no browser permission features. Keep these denied and
  // independent of any uncommitted production permission-handler changes.
  session.defaultSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  session.defaultSession.setPermissionCheckHandler(() => false);
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  window.webContents.on('will-navigate', (event, target) => {
    if (new URL(target).origin !== new URL(url).origin) event.preventDefault();
  });
  await window.loadURL(url);
  fs.writeFileSync(path.join(root, 'startup.json'), JSON.stringify({
    backend_health_ms: healthMs, navigation_finished_ms: performance.now() - started,
    shell_pid: process.pid, backend_pid: supervisor.child.pid, url,
  }));
}).catch(() => app.exit(1));
app.on('window-all-closed', () => app.quit());
app.on('before-quit', async event => {
  if (stopped) return;
  event.preventDefault();
  await supervisor?.stop({ includeAttached: false });
  stopped = true;
  app.quit();
});
