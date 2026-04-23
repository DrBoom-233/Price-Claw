const { contextBridge, ipcRenderer } = require("electron");

const backendBaseUrl = process.env.BACKEND_BASE_URL || "http://127.0.0.1:8000";

contextBridge.exposeInMainWorld("desktopAPI", {
  isElectron: true,
  backendBaseUrl,
  getBackendBaseUrl: () => ipcRenderer.invoke("backend:getBaseUrl")
});

