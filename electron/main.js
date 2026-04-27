const path = require("path");
const { spawn } = require("child_process");
const { app, BrowserWindow, ipcMain, shell } = require("electron");

const PROJECT_ROOT = path.resolve(__dirname, "..");
const FRONTEND_DIST_INDEX = path.join(PROJECT_ROOT, "frontend", "dist", "index.html");
const BACKEND_BASE_URL = process.env.BACKEND_BASE_URL || "http://127.0.0.1:8000";
const BACKEND_COMMAND = process.env.BACKEND_COMMAND || "uv";
const BACKEND_ARGS = (process.env.BACKEND_ARGS || "run python server.py").split(" ");
const ELECTRON_START_URL = process.env.ELECTRON_START_URL || "";
const ELECTRON_OPEN_DEVTOOLS = process.env.ELECTRON_OPEN_DEVTOOLS === "1";

let mainWindow = null;
let backendProcess = null;
let backendSpawnedByElectron = false;

ipcMain.handle("backend:getBaseUrl", () => BACKEND_BASE_URL);

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1300,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  if (ELECTRON_START_URL) {
    mainWindow.loadURL(ELECTRON_START_URL);
    if (ELECTRON_OPEN_DEVTOOLS) {
      mainWindow.webContents.openDevTools({ mode: "detach" });
    }
  } else {
    mainWindow.loadFile(FRONTEND_DIST_INDEX);
  }
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function isBackendHealthy() {
  try {
    const response = await fetch(`${BACKEND_BASE_URL}/api/health`);
    return response.ok;
  } catch {
    return false;
  }
}

function launchBackendProcess() {
  if (process.env.ELECTRON_SKIP_BACKEND === "1") {
    return;
  }

  backendProcess = spawn(BACKEND_COMMAND, BACKEND_ARGS, {
    cwd: PROJECT_ROOT,
    stdio: "pipe",
    shell: false
  });
  backendSpawnedByElectron = true;

  backendProcess.stdout.on("data", (chunk) => {
    process.stdout.write(`[backend] ${chunk}`);
  });
  backendProcess.stderr.on("data", (chunk) => {
    process.stderr.write(`[backend] ${chunk}`);
  });
  backendProcess.on("exit", (code) => {
    process.stdout.write(`[backend] exited with code ${code}\n`);
    backendProcess = null;
  });
}

async function ensureBackendReady(timeoutMs = 30000) {
  if (await isBackendHealthy()) {
    return;
  }

  launchBackendProcess();

  const startTime = Date.now();
  while (Date.now() - startTime < timeoutMs) {
    if (await isBackendHealthy()) {
      return;
    }
    await wait(500);
  }
  throw new Error("Backend failed to become healthy in time");
}

function stopBackendProcess() {
  if (!backendProcess || !backendSpawnedByElectron) {
    return;
  }

  if (process.platform === "win32") {
    spawn("taskkill", ["/pid", String(backendProcess.pid), "/t", "/f"], { shell: false });
  } else {
    backendProcess.kill("SIGTERM");
  }
}

app.whenReady().then(async () => {
  try {
    await ensureBackendReady();
    createMainWindow();
  } catch (error) {
    process.stderr.write(`[electron] startup failed: ${error}\n`);
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createMainWindow();
  }
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  stopBackendProcess();
});

