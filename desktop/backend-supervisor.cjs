const { EventEmitter } = require("node:events");
const fs = require("node:fs");
const http = require("node:http");
const https = require("node:https");
const net = require("node:net");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");

const HEALTH_TIMEOUT_MS = 45_000;

function commandWorks(command, args = ["--version"]) {
  const result = spawnSync(command, args, {
    stdio: "ignore",
    windowsHide: true,
  });
  return !result.error && result.status === 0;
}

function resolvePython(projectRoot) {
  const configured = process.env.RASPUTIN_PYTHON?.trim();
  if (configured) {
    if (!fs.existsSync(configured)) {
      throw new Error(`RASPUTIN_PYTHON does not exist: ${configured}`);
    }
    return { command: configured, prefixArgs: [] };
  }

  const localPython = process.platform === "win32"
    ? path.join(projectRoot, ".venv", "Scripts", "python.exe")
    : path.join(projectRoot, ".venv", "bin", "python");
  if (fs.existsSync(localPython)) {
    return { command: localPython, prefixArgs: [] };
  }

  if (commandWorks("python")) {
    return { command: "python", prefixArgs: [] };
  }
  if (process.platform === "win32" && commandWorks("py", ["-3", "--version"])) {
    return { command: "py", prefixArgs: ["-3"] };
  }

  throw new Error(
    "Python 3.12+ was not found. Create the repository .venv with " +
    "'.\\rasputin.ps1 start -Native' once, or set RASPUTIN_PYTHON."
  );
}

function findFreePort(host = "127.0.0.1") {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.once("error", reject);
    server.listen({ host, port: 0 }, () => {
      const address = server.address();
      server.close((error) => {
        if (error) reject(error);
        else resolve(address.port);
      });
    });
  });
}

function healthIsReady(url) {
  return new Promise((resolve) => {
    const client = url.startsWith("https://") ? https : http;
    const request = client.get(`${url}/api/health`, { timeout: 1_000, rejectUnauthorized: false }, (response) => {
      response.resume();
      resolve(response.statusCode === 200);
    });
    request.once("timeout", () => {
      request.destroy();
      resolve(false);
    });
    request.once("error", () => resolve(false));
  });
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

class BackendSupervisor extends EventEmitter {
  constructor({ projectRoot, dataDir, logDir, requestedPort = 0, backendExecutable = null }) {
    super();
    this.projectRoot = projectRoot;
    this.dataDir = dataDir;
    this.logDir = logDir;
    this.requestedPort = Number(requestedPort) || 0;
    this.backendExecutable = backendExecutable;
    this.child = null;
    this.url = null;
    this.status = "stopped";
    this.logPath = path.join(logDir, "desktop.log");
    this.desktopStatePath = path.join(dataDir, "desktop-runtime.json");
    this.nativeHostStatePath = path.join(dataDir, "native-host.json");
    this.nativeHostStopPath = path.join(dataDir, "native-host.stop");
    this.logStream = null;
    this.scanBuffer = "";
    this.pendingLog = { stdout: "", stderr: "", desktop: "" };
    this.credentialsEmitted = false;
    this.stopping = false;
    this.attachedToNativeHost = false;
  }

  setStatus(status, detail = "") {
    this.status = status;
    this.emit("status", { status, detail, url: this.url });
  }

  writeLog(source, chunk) {
    const text = chunk.toString();
    this.emit("log", { source, text });

    if (!this.credentialsEmitted) {
      this.scanBuffer = `${this.scanBuffer}${text}`.slice(-8_192);
      const username = this.scanBuffer.match(/username:\s*([^\s]+)/i)?.[1];
      const password = this.scanBuffer.match(/password:\s*([^\s]+)/i)?.[1];
      if (username && password) {
        this.credentialsEmitted = true;
        this.emit("credentials", { username, password });
      }
    }

    const buffered = `${this.pendingLog[source] || ""}${text}`;
    const lines = buffered.split(/(?<=\n)/);
    this.pendingLog[source] = lines.at(-1)?.endsWith("\n") ? "" : lines.pop() || "";
    for (const line of lines) {
      this.logStream?.write(line.replace(/(password:\s*)\S+/gi, "$1[redacted]"));
    }
  }

  writeDesktopState(child) {
    const state = {
      pid: child.pid,
      ownerPid: process.pid,
      url: this.url,
      dataDir: this.dataDir,
      startedAt: new Date().toISOString(),
    };
    const temporary = `${this.desktopStatePath}.tmp`;
    fs.writeFileSync(temporary, `${JSON.stringify(state, null, 2)}\n`, "utf8");
    fs.renameSync(temporary, this.desktopStatePath);
  }

  clearDesktopState(child) {
    try {
      const state = JSON.parse(fs.readFileSync(this.desktopStatePath, "utf8"));
      if (!child || Number(state.pid) === Number(child.pid)) fs.rmSync(this.desktopStatePath, { force: true });
    } catch {
      fs.rmSync(this.desktopStatePath, { force: true });
    }
  }

  async attachToNativeHost() {
    let state;
    try {
      state = JSON.parse(fs.readFileSync(this.nativeHostStatePath, "utf8"));
    } catch {
      return false;
    }
    const url = String(state?.url || "");
    if (!url || !await healthIsReady(url)) return false;
    this.url = url;
    this.attachedToNativeHost = true;
    this.setStatus("attached", url);
    return true;
  }

  flushPendingLogs() {
    for (const [source, text] of Object.entries(this.pendingLog)) {
      if (text) this.logStream?.write(text.replace(/(password:\s*)\S+/gi, "$1[redacted]"));
      this.pendingLog[source] = "";
    }
  }

  async start() {
    if (this.child || this.attachedToNativeHost) return this.url;
    if (await this.attachToNativeHost()) return this.url;

    const packaged = Boolean(this.backendExecutable && fs.existsSync(this.backendExecutable));
    const serverPath = path.join(this.projectRoot, "server.py");
    const frontendPath = path.join(this.projectRoot, "frontend", "index.html");
    if (!packaged && !fs.existsSync(serverPath)) {
      throw new Error(`Rasputin backend was not found at ${serverPath}`);
    }
    if (!packaged && !fs.existsSync(frontendPath)) {
      throw new Error("The desktop frontend has not been built. Run 'npm run build' first.");
    }

    fs.mkdirSync(this.dataDir, { recursive: true });
    fs.mkdirSync(this.logDir, { recursive: true });
    this.logStream = fs.createWriteStream(this.logPath, { flags: "a" });
    this.logStream.write(`\n--- Rasputin Desktop ${new Date().toISOString()} ---\n`);
    this.scanBuffer = "";
    this.pendingLog = { stdout: "", stderr: "", desktop: "" };
    this.credentialsEmitted = false;
    this.stopping = false;
    this.attachedToNativeHost = false;

    const runtime = packaged
      ? { command: this.backendExecutable, prefixArgs: [], args: [], cwd: path.dirname(this.backendExecutable) }
      : { ...resolvePython(this.projectRoot), args: [serverPath], cwd: this.projectRoot };
    const port = this.requestedPort || await findFreePort();
    this.url = `http://localhost:${port}`;

    const environment = {
      ...process.env,
      HOST: "127.0.0.1",
      PORT: String(port),
      PYTHONUNBUFFERED: "1",
      RASPUTIN_DATA_DIR: this.dataDir,
      RASPUTIN_DESKTOP: "1",
      RASPUTIN_HTTPS: "0",
    };
    delete environment.WRAPPER_RUNTIME;
    delete environment.RASPUTIN_TLS_CERT_FILE;
    delete environment.RASPUTIN_TLS_KEY_FILE;

    this.setStatus("starting", `Starting native engine on ${this.url}`);
    const child = spawn(
      runtime.command,
      [...runtime.prefixArgs, ...runtime.args],
      {
        cwd: runtime.cwd,
        env: environment,
        stdio: ["ignore", "pipe", "pipe"],
        windowsHide: true,
      }
    );
    this.child = child;
    this.writeDesktopState(child);

    child.stdout.on("data", (chunk) => this.writeLog("stdout", chunk));
    child.stderr.on("data", (chunk) => this.writeLog("stderr", chunk));
    child.once("error", (error) => this.writeLog("desktop", `${error.stack || error}\n`));
    child.once("close", (code, signal) => {
      const expected = this.stopping;
      if (this.child === child) this.child = null;
      this.clearDesktopState(child);
      this.writeLog("desktop", `Native engine exited (code=${code}, signal=${signal}).\n`);
      this.flushPendingLogs();
      this.logStream?.end();
      this.logStream = null;
      this.setStatus(expected ? "stopped" : "crashed", expected ? "" : `Exit code ${code}`);
    });

    const deadline = Date.now() + HEALTH_TIMEOUT_MS;
    while (Date.now() < deadline) {
      if (!this.child) {
        throw new Error(`The native engine exited during startup. See ${this.logPath}`);
      }
      if (await healthIsReady(this.url)) {
        this.setStatus("running", this.url);
        return this.url;
      }
      await delay(250);
    }

    await this.stop();
    throw new Error(`The native engine did not become healthy. See ${this.logPath}`);
  }

  async stop({ includeAttached = false } = {}) {
    if (this.attachedToNativeHost) {
      if (!includeAttached) return;
      this.setStatus("stopping", "Stopping persistent native host");
      fs.writeFileSync(this.nativeHostStopPath, "stop\n", "utf8");
      const deadline = Date.now() + 12_000;
      while (Date.now() < deadline) {
        if (!fs.existsSync(this.nativeHostStatePath) || !await healthIsReady(this.url)) {
          this.attachedToNativeHost = false;
          this.setStatus("stopped");
          return;
        }
        await delay(200);
      }
      throw new Error("The persistent Native Host did not stop before the timeout.");
    }
    const child = this.child;
    if (!child) {
      this.setStatus("stopped");
      return;
    }

    this.stopping = true;
    this.setStatus("stopping", "Stopping native engine");
    child.kill("SIGTERM");

    const deadline = Date.now() + 4_000;
    while (this.child === child && Date.now() < deadline) {
      await delay(100);
    }
    if (this.child !== child) return;

    if (process.platform === "win32") {
      spawn("taskkill", ["/pid", String(child.pid), "/t", "/f"], {
        stdio: "ignore",
        windowsHide: true,
      });
    } else {
      child.kill("SIGKILL");
    }

    const forceDeadline = Date.now() + 2_000;
    while (this.child === child && Date.now() < forceDeadline) {
      await delay(100);
    }
    if (this.child === child) {
      throw new Error(`Could not stop native engine process ${child.pid}`);
    }
  }

  async restart() {
    if (this.attachedToNativeHost) {
      throw new Error("Restart the persistent Native Host with rasputin.ps1 native-host-restart.");
    }
    await this.stop();
    return this.start();
  }
}

module.exports = {
  BackendSupervisor,
  findFreePort,
  resolvePython,
};
