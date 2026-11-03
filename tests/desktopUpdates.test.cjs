const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const test = require("node:test");
const { createDesktopUpdates, loadDesktopUpdater } = require("../desktop/updates.cjs");
const { verifyWindowsSignature } = require("../desktop/update-signature.cjs");

test("Store packages never load the GitHub updater, while packaged NSIS installs do", () => {
  const calls = [];
  const updater = {};
  const options = {
    isPackaged: true, platform: "win32", windowsStore: false, resourcesPath: "resources",
    load: (file) => { calls.push(file); return { autoUpdater: updater }; },
  };
  assert.equal(loadDesktopUpdater({ ...options, windowsStore: true }), null);
  assert.equal(loadDesktopUpdater({ ...options, isPackaged: false }), null);
  assert.equal(loadDesktopUpdater({ ...options, platform: "linux" }), null);
  assert.deepEqual(calls, []);
  assert.equal(loadDesktopUpdater(options), updater);
  assert.deepEqual(calls, [require("node:path").join("resources", "updater.cjs")]);
});

function fixture({ response = 1, failure = false } = {}) {
  const updater = new EventEmitter();
  const calls = [];
  const pending = [];
  updater.checkForUpdates = async () => {
    calls.push("check");
    if (failure) throw new Error("offline");
  };
  const updates = createDesktopUpdates({
    updater,
    dialog: { showMessageBox: async () => ({ response }) },
    install: async () => { calls.push("install"); },
    timers: {
      setTimeout: (fn, ms) => { pending.push({ fn, ms }); return 1; },
      setInterval: (fn, ms) => { pending.push({ fn, ms }); return 2; },
      clearTimeout: (id) => calls.push(`clear:${id}`),
      clearInterval: (id) => calls.push(`clear:${id}`),
    },
  });
  return { updates, updater, calls, pending };
}

test("updates download automatically, stay stable, and never install on ordinary quit", () => {
  const { updates, updater, pending, calls } = fixture();
  assert.equal(updater.autoDownload, true);
  assert.equal(updater.autoInstallOnAppQuit, false);
  assert.equal(updater.allowPrerelease, false);
  assert.equal(updater.allowDowngrade, false);
  assert.equal(updater.verifyUpdateCodeSignature, verifyWindowsSignature);
  updates.start();
  assert.deepEqual(pending.map(item => item.ms), [30_000, 21_600_000]);
  updates.stop();
  assert.deepEqual(calls, ["clear:1", "clear:2"]);
});

test("signature verification requires a valid signature, matching file and pinned publisher", async () => {
  const file = require("node:path").resolve("fixture-update.exe");
  const run = (result, error = null, stderr = "") => (_exe, args, options, callback) => {
    assert.equal(options.env.RASPUTIN_UPDATE_FILE, file);
    assert.ok(!args.at(-1).includes(file), "The installer path must not be interpolated into PowerShell code");
    callback(error, JSON.stringify(result), stderr);
  };
  const valid = { status: 0, path: file, publisher: "Expected Publisher" };
  assert.equal(await verifyWindowsSignature([valid.publisher], file, run(valid)), null);
  for (const invalid of [
    { ...valid, status: 2 }, { ...valid, publisher: "Wrong Publisher" },
    { ...valid, path: file + ".other" }, {},
  ]) assert.ok(await verifyWindowsSignature([valid.publisher], file, run(invalid)));
  assert.ok(await verifyWindowsSignature([valid.publisher], file, run(valid, new Error("PowerShell unavailable"))));
  assert.ok(await verifyWindowsSignature([valid.publisher], file, run(valid, null, "verification failed")));
  assert.ok(await verifyWindowsSignature([], file, () => { throw new Error("must not execute"); }));
});

test("a pending check suppresses duplicate requests, then supports retry after failure", async () => {
  const { updates, updater, calls } = fixture({ failure: true });
  updater.emit("checking-for-update");
  await updates.check();
  assert.deepEqual(calls, []);
  updater.emit("error", new Error("offline"));
  await updates.check();
  assert.deepEqual(calls, ["check"]);
  assert.match(updates.menuItem().label, /failed/);
  assert.equal(updates.menuItem().enabled, true);
});

test("Later preserves a downloaded update and keeps the manual restart action", async () => {
  const { updates, updater, calls } = fixture();
  updater.emit("update-downloaded");
  await new Promise(setImmediate);
  assert.deepEqual(calls, []);
  assert.equal(updates.menuItem().label, "Restart to install update");
  await updates.menuItem().click();
  assert.deepEqual(calls, []);
});

test("explicit confirmation installs exactly once and a stopped controller cannot install", async () => {
  const { updates, updater, calls } = fixture({ response: 0 });
  updater.emit("update-downloaded");
  updater.emit("update-downloaded");
  await new Promise(setImmediate);
  assert.deepEqual(calls, ["install"]);
  updates.stop();
  await updates.check();
  assert.deepEqual(calls.filter(item => item === "install"), ["install"]);
});

test("failure to stop the runtime leaves installation retryable", async () => {
  const updater = new EventEmitter();
  let installs = 0;
  const updates = createDesktopUpdates({
    updater,
    dialog: { showMessageBox: async () => ({ response: 0 }) },
    install: async () => { installs++; throw new Error("stop failed"); },
  });
  updater.emit("update-downloaded");
  await new Promise(setImmediate);
  assert.match(updates.menuItem().label, /could not install/);
  await updates.check();
  assert.equal(installs, 2);
});
