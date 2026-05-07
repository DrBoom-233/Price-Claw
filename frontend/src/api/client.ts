import { DEFAULT_API_BASE_URL } from "../config/providers";
import type {
  InspectionResponse,
  ModelsPayload,
  ModelsResponse,
  SchemasResponse,
  SettingsPayload,
  SettingsResponse,
  UploadResponse
} from "../types/app";

export function joinUrl(baseUrl: string, path: string): string {
  return `${baseUrl.replace(/\/$/, "")}${path}`;
}

export function createWsUrl(httpBaseUrl: string, path: string): string {
  const normalized = httpBaseUrl.replace(/\/$/, "");
  const wsBase = normalized.startsWith("https://")
    ? normalized.replace("https://", "wss://")
    : normalized.replace("http://", "ws://");
  return `${wsBase}${path}`;
}

export async function resolveApiBaseUrl(): Promise<string> {
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

async function readJson<T>(response: Response, fallbackMessage: string): Promise<T> {
  const data = (await response.json()) as T & { detail?: string };
  if (!response.ok) {
    throw new Error(data.detail || fallbackMessage);
  }
  return data;
}

export interface ApiClient {
  getSettings: () => Promise<SettingsResponse>;
  saveSettings: (payload: SettingsPayload) => Promise<SettingsResponse>;
  getModels: (payload: ModelsPayload) => Promise<ModelsResponse>;
  getSchemas: () => Promise<SchemasResponse>;
  getInspection: () => Promise<InspectionResponse>;
  uploadFile: (formData: FormData) => Promise<UploadResponse>;
}

export function createApiClient(apiBaseUrl: string): ApiClient {
  return {
    async getSettings() {
      const response = await fetch(joinUrl(apiBaseUrl, "/api/settings"));
      return readJson<SettingsResponse>(response, "Failed to load settings");
    },
    async saveSettings(payload) {
      const response = await fetch(joinUrl(apiBaseUrl, "/api/settings"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      return readJson<SettingsResponse>(response, "Failed to save settings");
    },
    async getModels(payload) {
      const response = await fetch(joinUrl(apiBaseUrl, "/api/models"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      return readJson<ModelsResponse>(response, "Failed to fetch models");
    },
    async getSchemas() {
      const response = await fetch(joinUrl(apiBaseUrl, "/api/schemas"));
      return readJson<SchemasResponse>(response, "Failed to load schemas");
    },
    async getInspection() {
      const response = await fetch(joinUrl(apiBaseUrl, "/api/inspection?limit=50"));
      return readJson<InspectionResponse>(response, "Failed to load inspection data");
    },
    async uploadFile(formData) {
      const response = await fetch(joinUrl(apiBaseUrl, "/api/upload"), {
        method: "POST",
        body: formData
      });
      return readJson<UploadResponse>(response, "Upload failed");
    }
  };
}
