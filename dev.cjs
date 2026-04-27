const { spawn, spawnSync } = require("child_process");
const path = require("path");
const waitOn = require("wait-on");

const ROOT_DIR = path.resolve(__dirname, ".");
const FRONTEND_DIR = path.join(ROOT_DIR, "frontend");
const FRONTEND_URL = "http://127.0.0.1:5173";
const BACKEND_HEALTH_URL = "http://127.0.0.1:8000/api/health";

const children = new Map();
let isShuttingDown = false;
let userInterrupted = false;

function log(prefix, message) {
  process.stdout.write(`[${prefix}] ${message}\n`);
}

function pipeWithPrefix(stream, prefix) {
  if (!stream) {
    return;
  }

  let buffer = "";
  stream.setEncoding("utf8");
  stream.on("data", (chunk) => {
    buffer += chunk;
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (line.trim().length > 0) {
        log(prefix, line);
      }
    }
  });
  stream.on("end", () => {
    if (buffer.trim().length > 0) {
      log(prefix, buffer);
    }
  });
}

function startProcess(name, command, args, options = {}) {
  const child = spawn(command, args, {
    cwd: ROOT_DIR,
    env: process.env,
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
    ...options,
  });

  children.set(name, child);
  pipeWithPrefix(child.stdout, name);
  pipeWithPrefix(child.stderr, name);

  child.on("exit", (code, signal) => {
    if (isShuttingDown) {
      return;
    }

    const isFailure = code !== 0 && code !== null;
    const exitedBySignal = signal !== null;

    if (isFailure || exitedBySignal) {
      const reason = exitedBySignal ? `signal ${signal}` : `code ${code}`;
      log(name, `exited unexpectedly with ${reason}`);
      shutdown(1);
      return;
    }

    if (name === "electron") {
      log("dev", "electron closed, stopping dev services");
      shutdown(0);
    }
  });

  child.on("error", (error) => {
    if (isShuttingDown) {
      return;
    }
    log(name, `failed to start: ${error.message}`);
    shutdown(1);
  });

  return child;
}

function killTreeWindows(pid) {
  spawnSync("taskkill", ["/PID", String(pid), "/T", "/F"], {
    stdio: "ignore",
    windowsHide: true,
  });
}

function killChild(child) {
  if (!child || child.killed || child.exitCode !== null) {
    return;
  }

  try {
    if (process.platform === "win32") {
      killTreeWindows(child.pid);
    } else {
      child.kill("SIGTERM");
    }
  } catch {
    // best-effort shutdown
  }
}

function waitForExit(child) {
  if (!child || child.exitCode !== null) {
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    child.once("exit", () => resolve());
  });
}

async function shutdown(code) {
  if (isShuttingDown) {
    return;
  }

  isShuttingDown = true;
  const childrenSnapshot = Array.from(children.values());
  for (const child of childrenSnapshot) {
    killChild(child);
  }

  await Promise.all(childrenSnapshot.map(waitForExit));
  process.exit(code);
}

function waitForServices() {
  return new Promise((resolve, reject) => {
    waitOn(
      {
        resources: [BACKEND_HEALTH_URL, FRONTEND_URL],
        timeout: 120000,
        interval: 250,
        tcpTimeout: 1000,
        validateStatus: (status) => status >= 200 && status < 500,
      },
      (error) => {
        if (error) {
          reject(error);
          return;
        }
        resolve();
      }
    );
  });
}

async function main() {
  process.on("SIGINT", () => {
    userInterrupted = true;
    log("dev", "received SIGINT, shutting down");
    shutdown(0);
  });

  process.on("SIGTERM", () => {
    userInterrupted = true;
    log("dev", "received SIGTERM, shutting down");
    shutdown(0);
  });

  log("dev", "starting backend");
  startProcess("backend", "uv", ["run", "python", "server.py"]);

  log("dev", "starting frontend");
  startProcess("frontend", "node", ["node_modules/vite/bin/vite.js", "--host", "127.0.0.1"], {
    cwd: FRONTEND_DIR,
  });

  try {
    log("dev", "waiting for backend/frontend readiness");
    await waitForServices();
  } catch (error) {
    log("dev", `service readiness failed: ${error.message}`);
    await shutdown(1);
    return;
  }

  const electronBinary = require("electron");
  log("dev", "starting electron");
  startProcess("electron", electronBinary, ["./electron/main.js"], {
    env: {
      ...process.env,
      ELECTRON_START_URL: FRONTEND_URL,
    },
  });
}

main().catch(async (error) => {
  log("dev", `fatal: ${error.message}`);
  await shutdown(userInterrupted ? 0 : 1);
});
