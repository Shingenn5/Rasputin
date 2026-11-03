const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { build, version } = require("../package.json");

// Store requires a positive major and reserves the fourth field. Keep 0.x app
// versions while preserving upgrade order when the application reaches 1.x.
const storeVersion = `${version.split(".").map((part, index) => Number(part) + (index === 0 ? 1 : 0)).join(".")}.0`;

function createStoreConfig(env = process.env) {
  const mode = env.STORE_PACKAGE_MODE || "test";
  assert.ok(["test", "submission"].includes(mode), "Unknown Store package mode");
  assert.match(version, /^\d+\.\d+\.\d+$/, "Store packages require an x.y.z version");
  assert.ok(storeVersion.split(".").every(part => Number(part) <= 65535),
    "Store version fields must fit Windows package limits");
  const identity = mode === "submission" ? {
    identityName: env.STORE_IDENTITY_NAME,
    publisher: env.STORE_PUBLISHER,
    publisherDisplayName: env.STORE_PUBLISHER_DISPLAY_NAME,
  } : {
    identityName: "Rasputin.LocalTest",
    publisher: "CN=Rasputin Local Test",
    publisherDisplayName: "Rasputin Local Test",
  };
  for (const [field, value] of Object.entries(identity)) {
    assert.ok(value?.trim(), `Missing Store ${field}; copy the exact value from Partner Center Product identity`);
    assert.ok(!/[<>&"'\r\n]/.test(value), `Unsupported XML characters in Store ${field}`);
  }
  assert.match(identity.identityName, /^[A-Za-z0-9.-]{3,50}$/, "Invalid Store package identity name");
  assert.match(identity.publisher, /^CN=.+/, "Store publisher must be the exact CN=... identity from Partner Center");
  return {
    ...structuredClone(build),
    publish: null,
    forceCodeSigning: false, // Microsoft signs the uploaded package after certification.
    // The legacy AppX kit contains macOS symlinks and fails on ordinary Windows
    // accounts. Use the modern, checksum-verified SDK bundle supported by our lockfile.
    toolsets: { ...build.toolsets, winCodeSign: "1.1.0" },
    directories: { ...build.directories, buildResources: "dist/store-resources" },
    win: { ...build.win, target: ["appx"] },
    appx: {
      ...identity,
      applicationId: "Rasputin",
      displayName: mode === "submission" ? "Rasputin" : "Rasputin Test",
      artifactName: `Rasputin-${mode}-\${version}-\${arch}.appx`,
      languages: ["en-US"],
      minVersion: "10.0.19041.0",
      maxVersionTested: "10.0.26100.0",
      setBuildNumber: false,
      addAutoLaunchExtension: false,
      capabilities: ["runFullTrust"],
      customManifestPath: path.resolve("dist/store-resources/AppxManifest.xml"),
    },
  };
}

if (require.main === module) {
  assert.ok(process.argv[2], "Pass an output JSON path");
  const config = createStoreConfig();
  fs.mkdirSync(path.dirname(config.appx.customManifestPath), { recursive: true });
  const template = fs.readFileSync(require.resolve("app-builder-lib/templates/appx/appxmanifest.xml"), "utf8");
  assert.ok(template.includes("${version}"), "Unsupported electron-builder manifest template");
  fs.writeFileSync(config.appx.customManifestPath, template.replaceAll("${version}", storeVersion));
  fs.writeFileSync(process.argv[2], JSON.stringify(config, null, 2) + "\n");
}
module.exports = { createStoreConfig, storeVersion };
