import { useEffect, useMemo, useState } from "react";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
const DEFAULT_REQUEST = "I want to extract all product names and prices";

function joinUrl(baseUrl, path) {
  return `${baseUrl.replace(/\/$/, "")}${path}`;
}

function createWsUrl(httpBaseUrl, path) {
  const normalized = httpBaseUrl.replace(/\/$/, "");
  const wsBase = normalized.startsWith("https://")
    ? normalized.replace("https://", "wss://")
    : normalized.replace("http://", "ws://");
  return `${wsBase}${path}`;
}

async function resolveApiBaseUrl() {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }

  if (window.desktopAPI?.getBackendBaseUrl) {
    try {
      return await window.desktopAPI.getBackendBaseUrl();
    } catch {
      return window.desktopAPI.backendBaseUrl || DEFAULT_API_BASE_URL;
    }
  }

  if (window.location.protocol.startsWith("http")) {
    return window.location.origin;
  }

  return DEFAULT_API_BASE_URL;
}

function App() {
  const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [settingsConfigured, setSettingsConfigured] = useState(false);
  const [settingsStatus, setSettingsStatus] = useState("Loading settings...");
  const [settingsStatusType, setSettingsStatusType] = useState("info");
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [hasCheckedSettings, setHasCheckedSettings] = useState(false);

  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("gpt-4o-mini");
  const [reasoningModel, setReasoningModel] = useState("o4-mini");
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [availableModels, setAvailableModels] = useState([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [modelsError, setModelsError] = useState("");

  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadedFilename, setUploadedFilename] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [requestText, setRequestText] = useState(DEFAULT_REQUEST);
  const [logs, setLogs] = useState([{ type: "info", text: "System ready." }]);

  const canStart = settingsConfigured && !!uploadedFilename && !isRunning;
  const uploadStatus = uploadedFilename ? `Uploaded: ${uploadedFilename}` : "";

  const api = useMemo(
    () => ({
      getSettings: () => fetch(joinUrl(apiBaseUrl, "/api/settings")),
      saveSettings: (payload) =>
        fetch(joinUrl(apiBaseUrl, "/api/settings"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        }),
      getModels: (payload) =>
        fetch(joinUrl(apiBaseUrl, "/api/models"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        }),
      uploadFile: (formData) =>
        fetch(joinUrl(apiBaseUrl, "/api/upload"), {
          method: "POST",
          body: formData
        })
    }),
    [apiBaseUrl]
  );

  function appendLog(text, type = "info") {
    const time = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, { type, text: `[${time}] ${text}` }]);
  }

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      const resolvedApiBaseUrl = await resolveApiBaseUrl();
      if (cancelled) {
        return;
      }
      setApiBaseUrl(resolvedApiBaseUrl);
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadSettings() {
      try {
        const response = await api.getSettings();
        const data = await response.json();
        if (cancelled) {
          return;
        }

        setSettingsConfigured(Boolean(data.configured));
        setModel(data.model || "gpt-4o-mini");
        setReasoningModel(data.reasoningModel || "o4-mini");

        if (data.configured) {
          setSettingsStatus(`Configured (${data.apiKeyMasked})`);
          setSettingsStatusType("success");
          setIsSettingsOpen(false);
        } else {
          setSettingsStatus("Not configured");
          setSettingsStatusType("error");
          setIsSettingsOpen(true);
        }
        setHasCheckedSettings(true);
      } catch (error) {
        if (cancelled) {
          return;
        }
        setSettingsStatus("Failed to load settings");
        setSettingsStatusType("error");
        setIsSettingsOpen(true);
        setHasCheckedSettings(true);
        appendLog(`Settings load failed: ${error}`, "error");
      }
    }

    loadSettings();
    return () => {
      cancelled = true;
    };
  }, [api]);

  useEffect(() => {
    if (!isSettingsOpen) {
      return;
    }

    if (!settingsConfigured && !apiKey.trim()) {
      return;
    }

    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        setIsLoadingModels(true);
        setModelsError("");
        const response = await api.getModels({ apiKey: apiKey.trim() || undefined });
        const data = await response.json();
        if (cancelled) {
          return;
        }
        if (!response.ok) {
          throw new Error(data.detail || "Failed to fetch models");
        }

        const models = Array.isArray(data.models) ? data.models : [];
        setAvailableModels(models);
        if (models.length > 0 && !models.includes(model)) {
          setModel(models[0]);
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        setAvailableModels([]);
        setModelsError(String(error));
      } finally {
        if (!cancelled) {
          setIsLoadingModels(false);
        }
      }
    }, 600);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [api, apiKey, isSettingsOpen, model, settingsConfigured]);

  async function handleSaveSettings() {
    const trimmedApiKey = apiKey.trim();
    if (!settingsConfigured && !trimmedApiKey) {
      appendLog("Please input API key before saving.", "error");
      return;
    }

    if (isLoadingModels) {
      appendLog("Models are still loading, please wait.", "error");
      return;
    }

    if (!model.trim()) {
      appendLog("Please select a model before saving.", "error");
      return;
    }

    if (modelsError) {
      appendLog("Please fix model loading error before saving.", "error");
      return;
    }

    setIsSavingSettings(true);
    try {
      const response = await api.saveSettings({
        apiKey: trimmedApiKey || apiKey,
        model,
        reasoningModel
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Failed to save settings");
      }

      setApiKey("");
      setSettingsConfigured(Boolean(data.configured));
      setSettingsStatus(`Configured (${data.apiKeyMasked})`);
      setSettingsStatusType("success");
      setIsSettingsOpen(false);
      appendLog("Settings saved.", "success");
    } catch (error) {
      appendLog(`Save settings failed: ${error}`, "error");
    } finally {
      setIsSavingSettings(false);
    }
  }

  async function handleUpload() {
    if (!selectedFile) {
      appendLog("Please select an MHTML file first.", "error");
      return;
    }

    setIsUploading(true);
    appendLog(`Uploading ${selectedFile.name} ...`);
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      const response = await api.uploadFile(formData);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Upload failed");
      }
      setUploadedFilename(data.filename);
      appendLog(`Upload successful: ${data.filename}`, "success");
    } catch (error) {
      appendLog(`Upload failed: ${error}`, "error");
    } finally {
      setIsUploading(false);
    }
  }

  function handleStart() {
    if (!canStart) {
      return;
    }

    setIsRunning(true);
    appendLog("Connecting to backend websocket ...", "ws");
    const wsUrl = createWsUrl(apiBaseUrl, "/api/ws");
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      appendLog("WebSocket connected, starting pipeline.", "success");
      ws.send(
        JSON.stringify({
          action: "start",
          filename: uploadedFilename,
          extraction_request: requestText.trim() || DEFAULT_REQUEST
        })
      );
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      switch (message.type) {
        case "log": {
          const level = message.level || "info";
          const type = level === "error" ? "error" : level === "warning" ? "ws" : "info";
          appendLog(message.message, type);
          break;
        }
        case "progress":
          appendLog(`[Executing] ${message.step}`, "ws");
          break;
        case "step_done":
          appendLog(`[Completed] ${message.step}`, "success");
          if (message.data) {
            appendLog(`Returned data: ${JSON.stringify(message.data)}`, "info");
          }
          break;
        case "result":
          appendLog(`[Final Result] ${JSON.stringify(message.data)}`, "success");
          break;
        case "error":
          appendLog(`[Step Error] ${message.message}`, "error");
          break;
        case "fatal":
          appendLog(`[Fatal Error] ${message.message}`, "error");
          break;
        case "complete":
          appendLog("Extraction completed.", "success");
          break;
        default:
          appendLog(`Unhandled message: ${JSON.stringify(message)}`, "ws");
      }
    };

    ws.onerror = () => {
      appendLog("WebSocket error.", "error");
    };

    ws.onclose = () => {
      appendLog("WebSocket closed.", "ws");
      setIsRunning(false);
    };
  }

  return (
    <div className="layout">
      <section className="card">
        <h1>Price Claw Desktop</h1>
        <p className="subtitle">Electron + React frontend, FastAPI backend</p>
        <div className="api-base">Backend: {apiBaseUrl}</div>
      </section>

      <section className="card">
        <h2>Settings</h2>
        <p className="subtitle">
          API key is configured in a secure popup and is no longer shown directly on the page.
        </p>
        <div className="actions">
          <button
            onClick={() => {
              setModelsError("");
              setIsSettingsOpen(true);
            }}
            disabled={isRunning || !hasCheckedSettings}
          >
            Open Settings
          </button>
          <span className={`status status-${settingsStatusType}`}>{settingsStatus}</span>
        </div>
      </section>

      <section className="card">
        <h2>Extraction</h2>
        <div className="actions">
          <input
            type="file"
            accept=".mhtml"
            onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
            disabled={isRunning || isUploading}
          />
          <button onClick={handleUpload} disabled={isRunning || isUploading}>
            {isUploading ? "Uploading..." : "1. Upload File"}
          </button>
        </div>
        {uploadStatus ? <div className="status status-success">{uploadStatus}</div> : null}
        <div className="form-row">
          <label htmlFor="request">Extraction Request</label>
          <textarea
            id="request"
            rows={3}
            value={requestText}
            onChange={(event) => setRequestText(event.target.value)}
            disabled={isRunning}
          />
        </div>
        <button onClick={handleStart} disabled={!canStart}>
          2. Start Extraction Task
        </button>
      </section>

      <section className="card">
        <h2>Task Console</h2>
        <div className="console">
          {logs.map((line, index) => (
            <div key={`${line.text}-${index}`} className={`log-${line.type}`}>
              {line.text}
            </div>
          ))}
        </div>
      </section>

      {isSettingsOpen ? (
        <div className="modal-backdrop" role="presentation">
          <section className="modal-card" role="dialog" aria-modal="true" aria-labelledby="settings-title">
            <h2 id="settings-title">OpenAI Settings</h2>
            <div className="form-row">
              <label htmlFor="apiKey">OpenAI API Key</label>
              <input
                id="apiKey"
                type="password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder={settingsConfigured ? "Leave empty to keep current key" : "sk-..."}
                disabled={isRunning || isSavingSettings}
              />
            </div>
            <div className="form-row-grid">
              <div className="form-row">
                <label htmlFor="model">Model</label>
                <select
                  id="model"
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                  disabled={isRunning || isSavingSettings || isLoadingModels || availableModels.length === 0}
                >
                  {availableModels.length === 0 ? (
                    <option value={model}>{isLoadingModels ? "Loading models..." : "No models available"}</option>
                  ) : (
                    availableModels.map((modelName) => (
                      <option key={modelName} value={modelName}>
                        {modelName}
                      </option>
                    ))
                  )}
                </select>
              </div>
              <div className="form-row">
                <label htmlFor="reasoningModel">Reasoning Model</label>
                <input
                  id="reasoningModel"
                  type="text"
                  value={reasoningModel}
                  onChange={(event) => setReasoningModel(event.target.value)}
                  disabled={isRunning || isSavingSettings}
                />
              </div>
            </div>
            {modelsError ? <div className="status status-error">{modelsError}</div> : null}
            <div className="actions">
              <button onClick={handleSaveSettings} disabled={isRunning || isSavingSettings || isLoadingModels}>
                {isSavingSettings ? "Saving..." : "Save Settings"}
              </button>
              <button
                className="button-secondary"
                onClick={() => setIsSettingsOpen(false)}
                disabled={isSavingSettings}
              >
                Close
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}

export default App;

