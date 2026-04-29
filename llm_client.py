from __future__ import annotations

from typing import Any

import httpx
from openai import OpenAI

import config


PROVIDER_ALIASES = {
    "anthropic": "claude",
    "google": "gemini",
    "openai-compatible": "openai_compatible",
    "openai compatible": "openai_compatible",
    "custom": "openai_compatible",
}

SUPPORTED_PROVIDERS = ("openai", "claude", "gemini", "deepseek", "openai_compatible")

DEFAULT_MODELS = {
    "openai": "gpt-5.5",              
    "claude": "claude-sonnet-4-6",     
    "gemini": "gemini-3.1-flash",      
    "deepseek": "deepseek-chat",        
    "openai_compatible": "gpt-5.5",
}
DEFAULT_BASE_URLS = {
    "openai": "",
    "claude": "https://api.anthropic.com",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "deepseek": "https://api.deepseek.com",
    "openai_compatible": "",
}

DEFAULT_MODEL_SUGGESTIONS = {
    "openai": [
        "gpt-5.5",
        "gpt-5.5-mini",
        "gpt-5.5-nano",
    ],
    "claude": [
        "claude-opus-4-7",    
        "claude-sonnet-4-6",  
        "claude-haiku-3-5",   
    ],
    "gemini": [
        "gemini-3.1-pro",
        "gemini-3.1-flash",
        "gemini-3.1-flash-lite",
    ],
    "deepseek": [
        "deepseek-v4-pro",
        "deepseek-v4-flash",
        "deepseek-reasoner",
    ],
    "openai_compatible": [
        "gpt-5.5",
    ],
}


def normalize_provider(provider: str | None) -> str:
    value = (provider or "openai").strip().lower().replace("-", "_")
    value = PROVIDER_ALIASES.get(value, value)
    if value not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    return value


def default_model_for_provider(provider: str | None) -> str:
    return DEFAULT_MODELS[normalize_provider(provider)]


def default_base_url_for_provider(provider: str | None) -> str:
    return DEFAULT_BASE_URLS[normalize_provider(provider)]


def default_model_suggestions(provider: str | None) -> list[str]:
    return list(DEFAULT_MODEL_SUGGESTIONS[normalize_provider(provider)])


def _configured_api_key(provider: str) -> str:
    if config.LLM_API_KEY:
        return config.LLM_API_KEY
    if provider == "claude":
        return getattr(config, "ANTHROPIC_API_KEY", None) or ""
    if provider == "gemini":
        return getattr(config, "GEMINI_API_KEY", None) or getattr(config, "GOOGLE_API_KEY", None) or ""
    if provider == "deepseek":
        return config.API_KEY or ""
    return config.OPENAI_API_KEY or ""


def _configured_model(provider: str) -> str:
    return (
        config.LLM_MODEL
        or (config.CHAT_MODEL if provider == "deepseek" else None)
        or config.OPENAI_MODEL
        or default_model_for_provider(provider)
    )


def _configured_base_url(provider: str) -> str:
    return config.LLM_BASE_URL or (config.URL if provider == "deepseek" else None) or default_base_url_for_provider(provider)


class LLMClient:
    def __init__(
        self,
        provider: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.provider = normalize_provider(provider or config.LLM_PROVIDER)
        self.api_key = (api_key or _configured_api_key(self.provider)).strip()
        self.model = (model or _configured_model(self.provider)).strip()
        self.base_url = (base_url if base_url is not None else _configured_base_url(self.provider)).strip()

        if not self.api_key:
            raise ValueError(f"{self.provider} API key is not configured")
        if not self.model:
            raise ValueError(f"{self.provider} model is not configured")

        self._openai_client: OpenAI | None = None
        if self.provider != "claude":
            kwargs: dict[str, Any] = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._openai_client = OpenAI(**kwargs)

    def chat_text(self, messages: list[dict[str, str]], max_tokens: int = 2048) -> str:
        if self.provider == "claude":
            return self._claude_chat_text(messages, max_tokens=max_tokens)
        if self._openai_client is None:
            raise RuntimeError("OpenAI-compatible client is not initialized")

        response = self._openai_client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return response.choices[0].message.content or ""

    def _claude_chat_text(self, messages: list[dict[str, str]], max_tokens: int) -> str:
        system_parts: list[str] = []
        claude_messages: list[dict[str, str]] = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "system":
                system_parts.append(content)
            elif role in {"user", "assistant"}:
                claude_messages.append({"role": role, "content": content})
            else:
                claude_messages.append({"role": "user", "content": content})

        if not claude_messages:
            claude_messages.append({"role": "user", "content": "\n".join(system_parts)})
            system_parts = []

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": claude_messages,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)

        response = httpx.post(
            f"{(self.base_url or DEFAULT_BASE_URLS['claude']).rstrip('/')}/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("content", [])
        text_parts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        return "\n".join(part for part in text_parts if part).strip()


def list_available_models(provider: str | None, api_key: str | None = None, base_url: str | None = None) -> list[str]:
    normalized = normalize_provider(provider)
    key = (api_key or _configured_api_key(normalized)).strip()
    if not key:
        return default_model_suggestions(normalized)

    if normalized == "claude":
        response = httpx.get(
            f"{(base_url or default_base_url_for_provider(normalized)).rstrip('/')}/v1/models",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        raw_models = data.get("data", [])
        model_ids = [str(model.get("id", "")).strip() for model in raw_models if isinstance(model, dict)]
    else:
        kwargs: dict[str, Any] = {"api_key": key}
        resolved_base_url = (base_url if base_url is not None else default_base_url_for_provider(normalized)).strip()
        if resolved_base_url:
            kwargs["base_url"] = resolved_base_url
        client = OpenAI(**kwargs)
        raw_models = client.models.list()
        model_ids = [str(getattr(model, "id", "")).strip() for model in raw_models]

    return sorted(dict.fromkeys(model_id for model_id in model_ids if model_id))
