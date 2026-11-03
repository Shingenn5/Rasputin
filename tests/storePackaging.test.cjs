const assert = require("node:assert/strict");
const test = require("node:test");
const { createStoreConfig, storeVersion } = require("../scripts/store-config.cjs");

test("submission packaging fails without a reserved identity and test identity cannot leak into it", () => {
  const testConfig = createStoreConfig({});
  assert.equal(testConfig.appx.identityName, "Rasputin.LocalTest");
  assert.equal(testConfig.publish, null);
  assert.equal(testConfig.appx.setBuildNumber, false);
  const parts = require("../package.json").version.split(".").map(Number);
  assert.equal(storeVersion, `${parts[0] + 1}.${parts[1]}.${parts[2]}.0`);
  const env = {
    STORE_PACKAGE_MODE: "submission", STORE_IDENTITY_NAME: "12345.Example",
    STORE_PUBLISHER: "CN=11111111-2222-3333-4444-555555555555",
    STORE_PUBLISHER_DISPLAY_NAME: "Example Developer",
  };
  for (const field of ["STORE_IDENTITY_NAME", "STORE_PUBLISHER", "STORE_PUBLISHER_DISPLAY_NAME"]) {
    assert.throws(() => createStoreConfig({ ...env, [field]: "" }), /Missing Store/);
  }
  assert.throws(() => createStoreConfig({ ...env, STORE_IDENTITY_NAME: '<broken>' }), /XML/);
  const submission = createStoreConfig(env);
  assert.equal(submission.appx.identityName, env.STORE_IDENTITY_NAME);
  assert.equal(submission.appx.publisher, env.STORE_PUBLISHER);
  assert.equal(submission.appx.displayName, "Rasputin");
  assert.equal(submission.extraResources.find(item => item.to === "backend").from, "dist/desktop-backend/rasputin-backend");
});
