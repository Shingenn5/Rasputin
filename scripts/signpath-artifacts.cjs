const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const yaml = require("js-yaml");
const { verifyWindowsSignature } = require("../desktop/update-signature.cjs");

const APP_FILES = { "Rasputin.exe": "Rasputin.exe", "rasputin-backend.exe": "resources/backend/rasputin-backend.exe" };

function configuration(root, publisher) {
  const pkg = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
  assert.match(pkg.version, /^\d+\.\d+\.\d+$/, "SignPath releases require a stable version");
  assert.ok(publisher?.trim(), "WINDOWS_PUBLISHER_NAME must match the approved signing certificate");
  return { version: pkg.version, publisher, publish: pkg.build.publish, directory: path.join(root, "dist/electron") };
}

function stageApp(root, publisher) {
  const config = configuration(root, publisher);
  const unpacked = path.join(config.directory, "win-unpacked");
  // --dir does not emit an updater feed. Put it in place before creating NSIS.
  fs.writeFileSync(path.join(unpacked, "resources/app-update.yml"), yaml.dump({ ...config.publish, publisherName: [publisher], updaterCacheDirName: "rasputin-updater" }));
  const destination = path.join(root, "dist/signpath/unsigned-app");
  fs.mkdirSync(destination, { recursive: true });
  for (const [name, relative] of Object.entries(APP_FILES)) fs.copyFileSync(path.join(unpacked, relative), path.join(destination, name));
  return config.version;
}

async function acceptFiles(source, mapping, publisher, verify) {
  assert.deepEqual(fs.readdirSync(source).sort(), Object.keys(mapping).sort(), "Unexpected signed artifact contents");
  // Validate every returned file before replacing any tested application file.
  for (const name of Object.keys(mapping)) {
    const file = path.join(source, name);
    assert.ok(fs.lstatSync(file).isFile(), "Signed artifacts must be regular files");
    assert.equal(await verify([publisher], file), null, "Missing, invalid or unexpected signing publisher");
  }
  for (const [name, destination] of Object.entries(mapping)) fs.copyFileSync(path.join(source, name), destination);
}

async function acceptApp(root, publisher, verify = verifyWindowsSignature) {
  const config = configuration(root, publisher);
  const mapping = Object.fromEntries(Object.entries(APP_FILES).map(([name, relative]) => [name, path.join(config.directory, "win-unpacked", relative)]));
  await acceptFiles(path.join(root, "dist/signpath/signed-app"), mapping, publisher, verify);
}

function stageInstaller(root, publisher) {
  const config = configuration(root, publisher);
  const name = `Rasputin-Setup-${config.version}.exe`;
  const destination = path.join(root, "dist/signpath/unsigned-installer");
  fs.mkdirSync(destination, { recursive: true });
  fs.copyFileSync(path.join(config.directory, name), path.join(destination, name));
}

async function refreshUpdateMetadata(directory, version) {
  const name = `Rasputin-Setup-${version}.exe`;
  const manifestPath = path.join(directory, "latest.yml");
  const manifest = yaml.load(fs.readFileSync(manifestPath, "utf8"));
  assert.equal(manifest.version, version);
  assert.equal(manifest.path, name);
  assert.equal(manifest.files?.length, 1);
  assert.equal(manifest.files[0].url, name);
  // Use the locked electron-builder v26 writer, not a homemade blockmap format.
  const { buildBlockMap } = require("app-builder-lib/out/targets/blockmap/blockmap.js");
  const file = path.join(directory, name);
  const info = await buildBlockMap(file, "gzip", `${file}.blockmap`);
  manifest.sha512 = info.sha512;
  manifest.files[0] = { ...manifest.files[0], sha512: info.sha512, size: info.size };
  fs.writeFileSync(manifestPath, yaml.dump(manifest));
}

async function acceptInstaller(root, publisher, verify = verifyWindowsSignature) {
  const config = configuration(root, publisher);
  const name = `Rasputin-Setup-${config.version}.exe`;
  await acceptFiles(path.join(root, "dist/signpath/signed-installer"), { [name]: path.join(config.directory, name) }, publisher, verify);
  // Authenticode changes installer bytes; old hashes and blockmaps are invalid.
  await refreshUpdateMetadata(config.directory, config.version);
}

if (require.main === module) {
  const root = path.resolve(__dirname, "..");
  const publisher = process.env.WINDOWS_PUBLISHER_NAME;
  const commands = { "stage-app": stageApp, "accept-app": acceptApp, "stage-installer": stageInstaller, "accept-installer": acceptInstaller };
  Promise.resolve().then(() => {
    assert.ok(commands[process.argv[2]], "Unknown SignPath artifact command");
    return commands[process.argv[2]](root, publisher);
  }).then((version) => {
    if (version && process.env.GITHUB_OUTPUT) fs.appendFileSync(process.env.GITHUB_OUTPUT, `version=${version}\n`);
  }).catch((error) => { console.error(error.message); process.exitCode = 1; });
}

module.exports = { stageApp, acceptApp, stageInstaller, acceptInstaller, refreshUpdateMetadata };
