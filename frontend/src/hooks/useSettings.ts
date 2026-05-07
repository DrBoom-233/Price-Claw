import { useCallback, useEffect, useState } from "react";
import type { ApiClient } from "../api/client";
import {
  DEFAULT_PROVIDER_BASE_URLS,
  DEFAULT_PROVIDER_MODELS,
  normalizeProvider
} from "../config/providers";
import type { LogType, Provider, StatusType } from "../types/app";

type AppendLog = (text: string, type?: LogType) => void;

export function useSettings(api: ApiClient, appendLog: AppendLog, onSettingsSaved: () => void) {
  const [settingsConfigured, setSettingsConfigured] = useState(false);
  const [settingsStatus, setSettingsStatus] = useState("Loading settings...");
  const [settingsStatusType, setSettingsStatusType] = useState<StatusType>("info");
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [hasCheckedSettings, setHasCheckedSettings] = useState(false);

  const [configuredProvider, setConfiguredProvider] = useState<Provider>("openai");
  const [provider, setProvider] = useState<Provider>("openai");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("gpt-4o-mini");
  const [reasoningModel, setReasoningModel] = useState("o4-mini");
  const [baseUrl, setBaseUrl] = useState("");
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [modelsError, setModelsError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadSettings() {
      try {
        const data = await api.getSettings();
        if (cancelled) {
          return;
        }

        const nextProvider = normalizeProvider(data.provider);
        setSettingsConfigured(Boolean(data.configured));
        setConfiguredProvider(nextProvider);
        setProvider(nextProvider);
        setModel(data.model || "gpt-4o-mini");
        setReasoningModel(data.reasoningModel || "o4-mini");
        setBaseUrl(data.baseUrl || DEFAULT_PROVIDER_BASE_URLS[nextProvider] || "");

        if (data.configured) {
          setSettingsStatus(`Configured ${nextProvider} (${data.apiKeyMasked})`);
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

    void loadSettings();
    return () => {
      cancelled = true;
    };
  }, [api, appendLog]);

  useEffect(() => {
    if (!isSettingsOpen) {
      return;
    }

    if (!settingsConfigured && !apiKey.trim()) {
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        setIsLoadingModels(true);
        setModelsError("");
        const data = await api.getModels({
          provider,
          apiKey: apiKey.trim() || undefined,
          baseUrl
        });
        if (cancelled) {
          return;
        }

        const models = Array.isArray(data.models) ? data.models : [];
        setAvailableModels(models);
        if (data.warning) {
          setModelsError(data.warning);
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
      window.clearTimeout(timer);
    };
  }, [api, apiKey, baseUrl, isSettingsOpen, provider, settingsConfigured]);

  const handleProviderChange = useCallback((nextProvider: Provider) => {
    setProvider(nextProvider);
    setModel(DEFAULT_PROVIDER_MODELS[nextProvider] || "");
    setReasoningModel(DEFAULT_PROVIDER_MODELS[nextProvider] || "");
    setBaseUrl(DEFAULT_PROVIDER_BASE_URLS[nextProvider] || "");
    setAvailableModels([]);
    setModelsError("");
  }, []);

  const handleSaveSettings = useCallback(async () => {
    const trimmedApiKey = apiKey.trim();
    if (!settingsConfigured && !trimmedApiKey) {
      appendLog("Please input API key before saving.", "error");
      return;
    }
    if (settingsConfigured && provider !== configuredProvider && !trimmedApiKey) {
      appendLog("Please input API key when changing provider.", "error");
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

    setIsSavingSettings(true);
    try {
      const data = await api.saveSettings({
        apiKey: trimmedApiKey || apiKey,
        provider,
        model,
        reasoningModel,
        baseUrl
      });

      const nextProvider = normalizeProvider(data.provider || provider);
      setApiKey("");
      setSettingsConfigured(Boolean(data.configured));
      setConfiguredProvider(nextProvider);
      setProvider(nextProvider);
      setBaseUrl(data.baseUrl || baseUrl);
      setSettingsStatus(`Configured ${nextProvider} (${data.apiKeyMasked})`);
      setSettingsStatusType("success");
      setIsSettingsOpen(false);
      appendLog("Settings saved.", "success");
      onSettingsSaved();
    } catch (error) {
      appendLog(`Save settings failed: ${error}`, "error");
    } finally {
      setIsSavingSettings(false);
    }
  }, [
    api,
    apiKey,
    appendLog,
    baseUrl,
    configuredProvider,
    isLoadingModels,
    model,
    onSettingsSaved,
    provider,
    reasoningModel,
    settingsConfigured
  ]);

  const openSettings = useCallback(() => {
    setModelsError("");
    setIsSettingsOpen(true);
  }, []);

  return {
    settingsConfigured,
    settingsStatus,
    settingsStatusType,
    isSettingsOpen,
    setIsSettingsOpen,
    hasCheckedSettings,
    configuredProvider,
    provider,
    apiKey,
    setApiKey,
    model,
    setModel,
    reasoningModel,
    setReasoningModel,
    baseUrl,
    setBaseUrl,
    isSavingSettings,
    availableModels,
    isLoadingModels,
    modelsError,
    openSettings,
    handleProviderChange,
    handleSaveSettings
  };
}
