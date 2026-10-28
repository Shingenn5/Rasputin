// The frontend is bundled by Vite; the Electron host uses only built-ins and
// local modules. Returning false also skips electron-builder's node_modules
// collection, which can stall on the frontend dependency graph.
module.exports = () => false;
