// Runs the frozen backend with the production supervisor and fresh temporary
// state. This is packaged-runtime proof, not an installed upgrade or model test.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { BackendSupervisor } = require("../desktop/backend-supervisor.cjs");

async function main() {
  const resources = path.resolve(process.argv[2] || "dist/electron/win-unpacked/resources");
  const executable = path.join(resources, "backend", "rasputin-backend.exe");
  assert.ok(fs.existsSync(executable), "Missing frozen backend; source fallback is forbidden");
  for (const key of Object.keys(process.env)) {
    if (key.toUpperCase().startsWith("RASPUTIN_")) delete process.env[key];
  }
  const scratch = fs.mkdtempSync(path.join(os.tmpdir(), "rasputin-package-smoke-"));
  const supervisor = new BackendSupervisor({
    projectRoot: resources,
    backendExecutable: executable,
    dataDir: path.join(scratch, "data"),
    logDir: path.join(scratch, "logs"),
    requestedPort: 0,
  });
  try {
    const url = await supervisor.start();
    assert.equal(supervisor.status, "running");
    const state = JSON.parse(fs.readFileSync(supervisor.desktopStatePath, "utf8"));
    assert.equal(state.ownerPid, process.pid);
    const health = await fetch(`${url}/api/health`, { signal: AbortSignal.timeout(10_000) });
    assert.equal(health.status, 200);
    const frontend = await fetch(url, { signal: AbortSignal.timeout(10_000) });
    assert.equal(frontend.status, 200);
    assert.match(await frontend.text(), /<html/i);
    console.log("PASS frozen backend startup, owned isolated runtime, health and packaged frontend");
  } finally {
    await supervisor.stop({ includeAttached: false });
    fs.rmSync(scratch, { recursive: true, force: true });
  }
}

main().catch(() => {
  // Avoid publishing generated credentials or private runtime paths.
  console.error("FAIL packaged runtime smoke; inspect the failing contract locally with isolated state.");
  process.exitCode = 1;
});
