const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");
const test = require("node:test");

const {
  BackendSupervisor,
  pidIsAlive,
  terminateProcessTree,
} = require("../desktop/backend-supervisor.cjs");
const {
  loadDesktopSettings,
  saveDesktopSettings,
} = require("../desktop/settings.cjs");

const projectRoot = path.resolve(__dirname, "..");

function temporaryDirectory(label) {
  const root = process.env.RASPUTIN_TEST_TMP || os.tmpdir();
  fs.mkdirSync(root, { recursive: true });
  return fs.mkdtempSync(path.join(root, `rasputin-${label}-`));
}

function sleepingProcess() {
  return spawn(process.execPath, ["-e", "setInterval(() => {}, 1000)"], {
    stdio: "ignore",
    windowsHide: true,
  });
}

async function requestStatus(url) {
  return new Promise((resolve, reject) => {
    const request = http.get(url, { timeout: 2_000 }, (response) => {
      response.resume();
      resolve(response.statusCode);
    });
    request.once("timeout", () => request.destroy(new Error("request timed out")));
    request.once("error", reject);
  });
}

test("desktop close behavior is persistent and supports an environment override", () => {
  const directory = temporaryDirectory("desktop-settings");
  try {
    assert.equal(loadDesktopSettings(directory, {}).closeBehavior, "tray");
    saveDesktopSettings(directory, { closeBehavior: "quit" });
    assert.equal(loadDesktopSettings(directory, {}).closeBehavior, "quit");
    saveDesktopSettings(directory, { closeBehavior: "tray" });
    assert.equal(loadDesktopSettings(directory, {}).closeBehavior, "tray");
    assert.equal(
      loadDesktopSettings(directory, { RASPUTIN_DESKTOP_CLOSE_BEHAVIOR: "tray" }).closeBehavior,
      "tray"
    );
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test("a new Desktop Runtime removes an abandoned backend process tree", async () => {
  const directory = temporaryDirectory("desktop-orphan");
  const orphan = sleepingProcess();
  const supervisor = new BackendSupervisor({
    projectRoot,
    dataDir: directory,
    logDir: path.join(directory, "logs"),
  });
  try {
    fs.writeFileSync(supervisor.desktopStatePath, JSON.stringify({
      pid: orphan.pid,
      ownerPid: 999_999_999,
      url: "http://127.0.0.1:1",
      dataDir: directory,
    }));
    await supervisor.recoverAbandonedDesktopRuntime();
    assert.equal(pidIsAlive(orphan.pid), false);
    assert.equal(fs.existsSync(supervisor.desktopStatePath), false);
  } finally {
    await terminateProcessTree(orphan.pid).catch(() => {});
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test("a live Desktop owner cannot be replaced", async () => {
  const directory = temporaryDirectory("desktop-owner");
  const owner = sleepingProcess();
  const runtime = sleepingProcess();
  const supervisor = new BackendSupervisor({
    projectRoot,
    dataDir: directory,
    logDir: path.join(directory, "logs"),
  });
  try {
    fs.writeFileSync(supervisor.desktopStatePath, JSON.stringify({
      pid: runtime.pid,
      ownerPid: owner.pid,
      url: "http://127.0.0.1:1",
      dataDir: directory,
    }));
    await assert.rejects(
      supervisor.recoverAbandonedDesktopRuntime(),
      /Another Rasputin Desktop Runtime owns this data store/
    );
    assert.equal(pidIsAlive(runtime.pid), true);
  } finally {
    await terminateProcessTree(runtime.pid).catch(() => {});
    await terminateProcessTree(owner.pid).catch(() => {});
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test("Desktop attaches to a Native Server and ordinary quit leaves it running", async () => {
  const directory = temporaryDirectory("desktop-attach");
  const server = http.createServer((request, response) => {
    if (request.url === "/api/health") {
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end('{"ok":true}');
      return;
    }
    response.writeHead(404).end();
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  const url = `http://127.0.0.1:${address.port}`;
  const supervisor = new BackendSupervisor({
    projectRoot,
    dataDir: directory,
    logDir: path.join(directory, "logs"),
  });
  try {
    fs.writeFileSync(supervisor.nativeHostStatePath, JSON.stringify({ pid: process.pid, url }));
    assert.equal(await supervisor.start(), url);
    assert.equal(supervisor.status, "attached");
    assert.equal(supervisor.child, null);

    await supervisor.stop();
    assert.equal(supervisor.attachedToNativeHost, true);
    assert.equal(await requestStatus(`${url}/api/health`), 200);

    const explicitStop = supervisor.stop({ includeAttached: true });
    setTimeout(() => {
      fs.rmSync(supervisor.nativeHostStatePath, { force: true });
      fs.rmSync(supervisor.nativeHostStopPath, { force: true });
      server.close();
    }, 150);
    await explicitStop;
    assert.equal(supervisor.attachedToNativeHost, false);
  } finally {
    await new Promise((resolve) => server.close(resolve));
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test("Desktop Runtime starts on loopback and removes its ownership state on stop", async () => {
  const directory = temporaryDirectory("desktop-runtime");
  const supervisor = new BackendSupervisor({
    projectRoot,
    dataDir: directory,
    logDir: path.join(directory, "logs"),
  });
  try {
    const url = await supervisor.start();
    assert.match(url, /^http:\/\/localhost:\d+$/);
    assert.equal(supervisor.status, "running");
    assert.ok(supervisor.child?.pid);
    assert.equal(fs.existsSync(supervisor.desktopStatePath), true);
    assert.equal(await requestStatus(`${url}/api/health`), 200);

    await supervisor.stop();
    assert.equal(supervisor.status, "stopped");
    assert.equal(supervisor.child, null);
    assert.equal(fs.existsSync(supervisor.desktopStatePath), false);
  } finally {
    await supervisor.stop().catch(() => {});
    fs.rmSync(directory, { recursive: true, force: true });
  }
});
