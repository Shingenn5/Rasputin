const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { builtinModules } = require("node:module");
const test = require("node:test");

test("desktop host requires no third-party node_modules at runtime", () => {
  const root = path.resolve(__dirname, "..");
  const allowed = new Set(["electron", ...builtinModules, ...builtinModules.map((name) => `node:${name}`)]);
  for (const name of fs.readdirSync(path.join(root, "desktop")).filter((name) => name.endsWith(".cjs"))) {
    const source = fs.readFileSync(path.join(root, "desktop", name), "utf8");
    for (const [, dependency] of source.matchAll(/require\(["']([^"']+)["']\)/g)) {
      assert.ok(dependency.startsWith(".") || allowed.has(dependency), `${name} needs ${dependency}; update desktop dependency packaging`);
    }
  }
  const config = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
  assert.equal(config.build.beforeBuild, "./desktop/before-build.cjs");
  assert.equal(require("../desktop/before-build.cjs")(), false);
});
