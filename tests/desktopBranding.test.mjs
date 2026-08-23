import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const packageJson = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
const icon = readFileSync(new URL("../desktop/assets/rasputin.ico", import.meta.url));
const main = readFileSync(new URL("../desktop/main.cjs", import.meta.url), "utf8");
const app = readFileSync(new URL("../frontend-src/src/app/App.jsx", import.meta.url), "utf8");

test("desktop packaging declares and ships the Rasputin Windows icon", () => {
  assert.equal(packageJson.build.win.icon, "desktop/assets/rasputin.ico");
  assert.equal(packageJson.build.files.includes("desktop/assets/**/*"), true);
  assert.equal(icon.readUInt16LE(0), 0);
  assert.equal(icon.readUInt16LE(2), 1);
  assert.ok(icon.readUInt16LE(4) >= 1);
  assert.ok(icon.length > 1024);
});

test("desktop startup boots without a credential dialog or login flash", () => {
  assert.doesNotMatch(main, /supervisor\.on\("credentials"/);
  assert.match(main, /app\.setAppUserModelId\("com\.rasputin\.desktop"\)/);
  assert.match(main, /icon:\s*iconPath\(\)/);
  assert.match(app, /useState\(false\);[\r\n]+  \/\/ The packaged Desktop Runtime supplies/);
});
