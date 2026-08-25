import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const packageJson = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
const icon = readFileSync(new URL("../desktop/assets/rasputin.ico", import.meta.url));
const logo = readFileSync(new URL("../desktop/assets/rasputin-logo.png", import.meta.url));
const frontendLogo = readFileSync(new URL("../frontend-src/public/rasputin-logo.png", import.meta.url));
const main = readFileSync(new URL("../desktop/main.cjs", import.meta.url), "utf8");
const app = readFileSync(new URL("../frontend-src/src/app/App.jsx", import.meta.url), "utf8");
const pngSignature = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

function iconFrames(buffer) {
  const count = buffer.readUInt16LE(4);
  return Array.from({ length: count }, (_, index) => {
    const entryOffset = 6 + (index * 16);
    const width = buffer[entryOffset] || 256;
    const height = buffer[entryOffset + 1] || 256;
    const byteLength = buffer.readUInt32LE(entryOffset + 8);
    const imageOffset = buffer.readUInt32LE(entryOffset + 12);
    assert.ok(imageOffset + byteLength <= buffer.length, `ICO frame ${width}x${height} must stay within the file`);
    return { width, height, data: buffer.subarray(imageOffset, imageOffset + byteLength) };
  });
}

test("desktop packaging declares and ships the Rasputin Windows icon", () => {
  assert.equal(packageJson.build.win.icon, "desktop/assets/rasputin.ico");
  assert.equal(packageJson.build.files.includes("desktop/assets/**/*"), true);
  assert.equal(icon.readUInt16LE(0), 0);
  assert.equal(icon.readUInt16LE(2), 1);
  const frames = iconFrames(icon);
  assert.deepEqual(frames.map(({ width, height }) => [width, height]), [16, 32, 48, 64, 128, 256].map((size) => [size, size]));
  for (const { width, height, data } of frames) {
    assert.deepEqual(data.subarray(0, pngSignature.length), pngSignature, `ICO frame ${width}x${height} must contain real PNG bytes`);
    assert.equal(data.readUInt32BE(16), width);
    assert.equal(data.readUInt32BE(20), height);
  }
  assert.ok(icon.length > 1024);
});

test("desktop startup boots without a credential dialog or login flash", () => {
  assert.doesNotMatch(main, /supervisor\.on\("credentials"/);
  assert.match(main, /app\.setAppUserModelId\("com\.rasputin\.desktop"\)/);
  assert.match(main, /icon:\s*iconPath\(\)/);
  assert.match(app, /useState\(false\);[\r\n]+  \/\/ The packaged Desktop Runtime supplies/);
});

test("desktop tray uses the Rasputin logo PNG instead of the legacy inline icon", () => {
  assert.match(main, /nativeImage\.createFromPath\(path\.join\(__dirname, ["']assets["'], ["']rasputin-logo\.png["']\)\)/);
  assert.doesNotMatch(main, /createFromDataURL/);
  assert.doesNotMatch(main, /<svg|#ff5f57.*R/);
});

test("Rasputin logo masters are identical transparent RGBA PNGs", () => {
  assert.deepEqual(logo, frontendLogo);
  for (const [label, buffer] of [["desktop", logo], ["frontend", frontendLogo]]) {
    assert.deepEqual(buffer.subarray(0, pngSignature.length), pngSignature, `${label} logo must have a PNG signature`);
    assert.equal(buffer.readUInt32BE(16), 1024, `${label} logo must be 1024px wide`);
    assert.equal(buffer.readUInt32BE(20), 1024, `${label} logo must be 1024px tall`);
    assert.equal(buffer[24], 8, `${label} logo must use 8-bit channels`);
    assert.equal(buffer[25], 6, `${label} logo must use RGBA color type`);
  }
});
