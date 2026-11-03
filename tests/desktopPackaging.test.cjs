const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { builtinModules } = require("node:module");
const crypto = require("node:crypto");
const os = require("node:os");
const { verifyUpdateArtifacts } = require("../scripts/verify-update-artifacts.cjs");
const test = require("node:test");

test("desktop host ships its updater as a bundle without runtime node_modules", async () => {
  const root = path.resolve(__dirname, "..");
  const allowed = new Set(["electron", ...builtinModules, ...builtinModules.map((name) => `node:${name}`)]);
  for (const name of fs.readdirSync(path.join(root, "desktop")).filter((name) => name.endsWith(".cjs"))) {
    if (name === "before-build.cjs") continue; // Build-time bundler, never loaded by the host.
    const source = fs.readFileSync(path.join(root, "desktop", name), "utf8");
    for (const [, dependency] of source.matchAll(/require\(["']([^"']+)["']\)/g)) {
      assert.ok(dependency.startsWith(".") || allowed.has(dependency), `${name} needs ${dependency}; update desktop dependency packaging`);
    }
  }
  const config = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
  assert.equal(config.build.beforeBuild, "./desktop/before-build.cjs");
  assert.equal(await require("../desktop/before-build.cjs")(), false);
  assert.ok(config.build.extraResources.some(resource => resource.from === "dist/desktop-updater.cjs" && resource.to === "updater.cjs"));
  const bundle = fs.readFileSync(path.join(root, "dist/desktop-updater.cjs"), "utf8");
  assert.ok(bundle.includes("NsisUpdater"));
  assert.equal(config.build.win.verifyUpdateCodeSignature, true);
  assert.deepEqual(config.build.publish, { provider: "github", owner: "Shingenn5", repo: "Rasputin", releaseType: "draft" });
});

test("release artifact gate rejects tampered installers and unpinned publishers", () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "rasputin-artifact-check-"));
  try {
    const resources = path.join(directory, "win-unpacked", "resources");
    fs.mkdirSync(resources, { recursive: true });
    fs.writeFileSync(path.join(resources, "updater.cjs"), " ".repeat(100_001));
    fs.writeFileSync(path.join(resources, "app.asar"), "fixture");
    fs.writeFileSync(path.join(resources, "app-update.yml"), "provider: github\nowner: Shingenn5\nrepo: Rasputin\npublisherName: Example Publisher\n");
    const bytes = Buffer.from("installer fixture");
    const sha512 = crypto.createHash("sha512").update(bytes).digest("base64");
    fs.writeFileSync(path.join(directory, "Rasputin-Setup-1.2.3.exe"), bytes);
    fs.writeFileSync(path.join(directory, "Rasputin-Setup-1.2.3.exe.blockmap"), "fixture");
    fs.writeFileSync(path.join(directory, "latest.yml"), `version: 1.2.3\npath: Rasputin-Setup-1.2.3.exe\nsha512: ${sha512}\nfiles:\n  - url: Rasputin-Setup-1.2.3.exe\n    size: ${bytes.length}\n    sha512: ${sha512}\n`);
    const options = { version: "1.2.3", signed: true, publisher: "Example Publisher" };
    verifyUpdateArtifacts(directory, options);
    assert.throws(() => verifyUpdateArtifacts(directory, { ...options, publisher: "Other Publisher" }), /pin the signing publisher/);
    fs.appendFileSync(path.join(directory, "Rasputin-Setup-1.2.3.exe"), "tampered");
    assert.throws(() => verifyUpdateArtifacts(directory, options));
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});
