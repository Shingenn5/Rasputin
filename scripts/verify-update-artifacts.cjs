const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const yaml = require("js-yaml");

function verifyUpdateArtifacts(directory, { version, signed = false, publisher = "" }) {
  const resources = path.join(directory, "win-unpacked", "resources");
  const config = yaml.load(fs.readFileSync(path.join(resources, "app-update.yml"), "utf8"));
  assert.equal(config.provider, "github");
  assert.equal(config.owner, "Shingenn5");
  assert.equal(config.repo, "Rasputin");
  if (signed) {
    assert.ok(publisher, "A signed release needs an expected publisher");
    assert.ok([config.publisherName].flat().includes(publisher), "Update metadata must pin the signing publisher");
  }
  const bundle = path.join(resources, "updater.cjs");
  assert.ok(fs.statSync(bundle).size > 100_000, "Missing bundled updater dependencies");
  assert.ok(fs.existsSync(path.join(resources, "app.asar")), "Missing Electron application");
  const metadata = yaml.load(fs.readFileSync(path.join(directory, "latest.yml"), "utf8"));
  assert.equal(metadata.version, version);
  const installer = `Rasputin-Setup-${version}.exe`;
  assert.equal(metadata.path, installer);
  assert.ok(metadata.files?.length > 0, "No update files declared");
  for (const file of metadata.files) {
    assert.equal(file.url, installer, "Update metadata must reference the versioned installer");
    const bytes = fs.readFileSync(path.join(directory, file.url));
    assert.equal(file.size, bytes.length);
    assert.equal(file.sha512, crypto.createHash("sha512").update(bytes).digest("base64"));
    assert.equal(metadata.sha512, file.sha512);
  }
  assert.ok(fs.statSync(path.join(directory, `${installer}.blockmap`)).size > 0, "Missing differential update blockmap");
}

if (require.main === module) {
  verifyUpdateArtifacts(path.resolve("dist/electron"), {
    version: require("../package.json").version,
    signed: process.env.EXPECT_SIGNED === "true",
    publisher: process.env.PUBLISHER_NAME || "",
  });
  console.log("PASS packaged updater, feed identity, version, SHA-512, size and blockmap");
}

module.exports = { verifyUpdateArtifacts };
