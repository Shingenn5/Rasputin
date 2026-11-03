const path = require("node:path");

// Ship the updater and its dependencies as one resource. Collecting every
// frontend dependency into the Electron host adds size and can stall packaging.
module.exports = async () => {
  await require("esbuild").build({
    entryPoints: [require.resolve("electron-updater")],
    outfile: path.join(__dirname, "..", "dist", "desktop-updater.cjs"),
    bundle: true,
    platform: "node",
    format: "cjs",
    external: ["electron"],
    target: "node22",
  });
  return false;
};
