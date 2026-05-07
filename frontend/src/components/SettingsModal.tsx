import { DEFAULT_PROVIDER_BASE_URLS, DEFAULT_PROVIDER_MODELS, PROVIDER_OPTIONS } from "../config/providers";
import type { Provider } from "../types/app";

interface SettingsModalProps {
  configuredProvider: Provider;
  provider: Provider;
  apiKey: string;
  model: string;
  reasoningModel: string;
  baseUrl: string;
  settingsConfigured: boolean;
  isRunning: boolean;
  isSavingSettings: boolean;
  isLoadingModels: boolean;
  availableModels: string[];
  modelsError: string;
  onProviderChange: (provider: Provider) => void;
  onApiKeyChange: (apiKey: string) => void;
  onModelChange: (model: string) => void;
  onReasoningModelChange: (model: string) => void;
  onBaseUrlChange: (baseUrl: string) => void;
  onSave: () => void;
  onClose: () => void;
}

export function SettingsModal({
  configuredProvider,
  provider,
  apiKey,
  model,
  reasoningModel,
  baseUrl,
  settingsConfigured,
  isRunning,
  isSavingSettings,
  isLoadingModels,
  availableModels,
  modelsError,
  onProviderChange,
  onApiKeyChange,
  onModelChange,
  onReasoningModelChange,
  onBaseUrlChange,
  onSave,
  onClose
}: SettingsModalProps) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-card" role="dialog" aria-modal="true" aria-labelledby="settings-title">
        <h2 id="settings-title">LLM Settings</h2>
        <div className="form-row-grid">
          <div className="form-row">
            <label htmlFor="provider">Provider</label>
            <select
              id="provider"
              value={provider}
              onChange={(event) => onProviderChange(event.target.value as Provider)}
              disabled={isRunning || isSavingSettings}
            >
              {PROVIDER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div className="form-row">
            <label htmlFor="apiKey">API Key</label>
            <input
              id="apiKey"
              type="password"
              value={apiKey}
              onChange={(event) => onApiKeyChange(event.target.value)}
              placeholder={settingsConfigured && provider === configuredProvider ? "Leave empty to keep current key" : "API key"}
              disabled={isRunning || isSavingSettings}
            />
          </div>
        </div>
        <div className="form-row">
          <label htmlFor="baseUrl">Base URL</label>
          <input
            id="baseUrl"
            type="text"
            value={baseUrl}
            onChange={(event) => onBaseUrlChange(event.target.value)}
            placeholder={DEFAULT_PROVIDER_BASE_URLS[provider] || "https://api.example.com/v1"}
            disabled={isRunning || isSavingSettings}
          />
        </div>
        <div className="form-row-grid">
          <div className="form-row">
            <label htmlFor="model">Model</label>
            <input
              id="model"
              type="text"
              value={model}
              onChange={(event) => onModelChange(event.target.value)}
              list="available-models"
              placeholder={DEFAULT_PROVIDER_MODELS[provider] || "model-name"}
              disabled={isRunning || isSavingSettings}
            />
            <datalist id="available-models">
              {availableModels.map((modelName) => (
                <option key={modelName} value={modelName} />
              ))}
            </datalist>
          </div>
          <div className="form-row">
            <label htmlFor="reasoningModel">Schema Model</label>
            <input
              id="reasoningModel"
              type="text"
              value={reasoningModel}
              onChange={(event) => onReasoningModelChange(event.target.value)}
              placeholder={model || DEFAULT_PROVIDER_MODELS[provider]}
              disabled={isRunning || isSavingSettings}
            />
          </div>
        </div>
        {modelsError ? <div className="status status-error">{modelsError}</div> : null}
        <div className="actions">
          <button onClick={onSave} disabled={isRunning || isSavingSettings || isLoadingModels}>
            {isSavingSettings ? "Saving..." : "Save Settings"}
          </button>
          <button className="button-secondary" onClick={onClose} disabled={isSavingSettings}>
            Close
          </button>
        </div>
      </section>
    </div>
  );
}
