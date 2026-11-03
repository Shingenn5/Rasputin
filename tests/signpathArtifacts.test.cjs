const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const yaml = require("js-yaml");
const { stageApp, acceptApp, stageInstaller, acceptInstaller } = require("../scripts/signpath-artifacts.cjs");
const { verifyUpdateArtifacts } = require("../scripts/verify-update-artifacts.cjs");

test("SignPath staging rejects invalid returns and rebuilds metadata for the final installer bytes", async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "rasputin-signpath-test-"));
  const directory = path.join(root, "dist/electron");
  const unpacked = path.join(directory, "win-unpacked");
  const publisher = "Fixture Publisher";
  try {
    fs.mkdirSync(path.join(unpacked, "resources/backend"), { recursive: true });
    fs.writeFileSync(path.join(root, "package.json"), JSON.stringify({ version: "1.2.3", build: { publish: { provider: "github", owner: "Shingenn5", repo: "Rasputin" } } }));
    fs.writeFileSync(path.join(unpacked, "Rasputin.exe"), "unsigned-app");
    fs.writeFileSync(path.join(unpacked, "resources/backend/rasputin-backend.exe"), "unsigned-backend");
    fs.writeFileSync(path.join(unpacked, "resources/updater.cjs"), " ".repeat(100_001));
    fs.writeFileSync(path.join(unpacked, "resources/app.asar"), "fixture");
    assert.throws(() => stageApp(root, ""), /WINDOWS_PUBLISHER_NAME/);
    assert.equal(stageApp(root, publisher), "1.2.3");
    const feed = yaml.load(fs.readFileSync(path.join(unpacked, "resources/app-update.yml"), "utf8"));
    assert.deepEqual(feed.publisherName, [publisher]);
    assert.equal(feed.updaterCacheDirName, "rasputin-updater");
    const signedApp = path.join(root, "dist/signpath/signed-app");
    fs.mkdirSync(signedApp, { recursive: true });
    // Signature verification is injected only for these synthetic byte fixtures.
    fs.writeFileSync(path.join(signedApp, "Rasputin.exe"), "signed-app-fixture");
    fs.writeFileSync(path.join(signedApp, "rasputin-backend.exe"), "signed-backend-fixture");
    await assert.rejects(acceptApp(root, publisher, async (_publishers, file) => file.endsWith("rasputin-backend.exe") ? "bad signature" : null));
    assert.equal(fs.readFileSync(path.join(unpacked, "Rasputin.exe"), "utf8"), "unsigned-app");
    fs.writeFileSync(path.join(signedApp, "unexpected.exe"), "not allowed");
    await assert.rejects(acceptApp(root, publisher, async () => null), /Unexpected signed artifact/);
    fs.unlinkSync(path.join(signedApp, "unexpected.exe"));
    await acceptApp(root, publisher, async () => null);
    assert.equal(fs.readFileSync(path.join(unpacked, "Rasputin.exe"), "utf8"), "signed-app-fixture");

    const name = "Rasputin-Setup-1.2.3.exe";
    fs.writeFileSync(path.join(directory, name), "unsigned-installer-fixture");
    fs.writeFileSync(path.join(directory, "latest.yml"), yaml.dump({ version: "1.2.3", path: name, sha512: "stale", files: [{ url: name, sha512: "stale", size: 1 }] }));
    fs.writeFileSync(path.join(directory, `${name}.blockmap`), "stale-map");
    stageInstaller(root, publisher);
    const signedInstaller = path.join(root, "dist/signpath/signed-installer");
    fs.mkdirSync(signedInstaller, { recursive: true });
    fs.writeFileSync(path.join(signedInstaller, name), "installer-with-additional-signature-fixture-bytes");
    await assert.rejects(acceptInstaller(root, publisher, async () => "wrong publisher"));
    assert.equal(fs.readFileSync(path.join(directory, name), "utf8"), "unsigned-installer-fixture");
    await acceptInstaller(root, publisher, async () => null);
    verifyUpdateArtifacts(directory, { version: "1.2.3", signed: true, publisher });
    const map = JSON.parse(require("node:zlib").gunzipSync(fs.readFileSync(path.join(directory, `${name}.blockmap`))));
    assert.equal(map.version, "2");
    assert.equal(map.files[0].sizes.reduce((sum, size) => sum + size, 0), fs.statSync(path.join(directory, name)).size);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
