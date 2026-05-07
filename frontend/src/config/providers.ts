import type { Provider, ProviderOption } from "../types/app";

export const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
export const DEFAULT_REQUEST = "I want to extract all product names and prices";

export const PROVIDER_OPTIONS: ProviderOption[] = [
  { value: "openai", label: "OpenAI" },
  { value: "claude", label: "Claude" },
  { value: "gemini", label: "Gemini" },
  { value: "deepseek", label: "DeepSeek" },
  { value: "openai_compatible", label: "OpenAI Compatible" }
];

export const DEFAULT_PROVIDER_MODELS: Record<Provider, string> = {
  openai: "gpt-4o-mini",
  claude: "claude-sonnet-4-5",
  gemini: "gemini-2.5-flash",
  deepseek: "deepseek-chat",
  openai_compatible: "gpt-4o-mini"
};

export const DEFAULT_PROVIDER_BASE_URLS: Record<Provider, string> = {
  openai: "",
  claude: "https://api.anthropic.com",
  gemini: "https://generativelanguage.googleapis.com/v1beta/openai/",
  deepseek: "https://api.deepseek.com",
  openai_compatible: ""
};

const PROVIDER_VALUES = PROVIDER_OPTIONS.map((option) => option.value);

export function normalizeProvider(value: unknown): Provider {
  return PROVIDER_VALUES.includes(value as Provider) ? (value as Provider) : "openai";
}
