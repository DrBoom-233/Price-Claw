export type Provider = "openai" | "claude" | "gemini" | "deepseek" | "openai_compatible";

export type StatusType = "info" | "success" | "error";
export type LogType = "info" | "success" | "error" | "ws";
export type TaskMode = "uniform" | "per_file";
export type InspectionTab = "prices" | "schemas";

export interface ProviderOption {
  value: Provider;
  label: string;
}

export interface LogLine {
  type: LogType;
  text: string;
}

export interface FilePlan {
  schemaId: string;
  useLlm: boolean;
}

export type FilePlans = Record<string, FilePlan>;

export interface SchemaSummary {
  id: string;
  schemaName?: string;
  domain?: string;
  [key: string]: unknown;
}

export interface InspectionExtraction {
  id: string;
  fileName?: string;
  taskId?: string;
  createdAt?: string;
  result?: unknown;
  [key: string]: unknown;
}

export interface InspectionSchema {
  id: string;
  schemaName?: string;
  domain?: string;
  [key: string]: unknown;
}

export interface InspectionData {
  schemas: InspectionSchema[];
  extractions: InspectionExtraction[];
}

export interface SettingsPayload {
  apiKey?: string;
  provider: Provider;
  model: string;
  reasoningModel: string;
  baseUrl: string;
}

export interface SettingsResponse {
  configured: boolean;
  provider?: Provider;
  apiKeyMasked?: string;
  model?: string;
  reasoningModel?: string;
  baseUrl?: string;
}

export interface ModelsPayload {
  provider: Provider;
  apiKey?: string;
  baseUrl: string;
}

export interface ModelsResponse {
  models?: string[];
  warning?: string;
}

export interface SchemasResponse {
  schemas?: SchemaSummary[];
}

export interface InspectionResponse {
  schemas?: InspectionSchema[];
  extractions?: InspectionExtraction[];
}

export interface UploadResponse {
  filename?: string;
  filenames?: string[];
}

export interface MhtmlDownloadFile {
  url: string;
  filename?: string | null;
  success: boolean;
  error?: string;
}

export interface MhtmlDownloadResponse {
  filenames?: string[];
  files?: MhtmlDownloadFile[];
  message?: string;
}
