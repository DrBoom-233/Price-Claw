from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import config
from llm_client import (
    DEFAULT_BASE_URLS,
    SUPPORTED_PROVIDERS,
    default_base_url_for_provider,
    default_model_for_provider,
    normalize_provider,
)


SETTINGS_FILE = Path(".app_settings.json")
DEFAULT_OPENAI_MODEL = config.OPENAI_MODEL or "gpt-4o-mini"
DEFAULT_OPENAI_REASONING_MODEL = config.OPENAI_REASONING_MODEL or "o4-mini"
DEFAULT_PROVIDER = "openai"


@dataclass
class RuntimeSettings:
    provider: str
    api_key: str
    model: str
    reasoning_model: str
    base_url: str


def mask_api_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 10:
        return f"{api_key[:2]}***{api_key[-2:]}"
    return f"{api_key[:4]}***{api_key[-4:]}"


def _normalize_settings(raw: dict[str, Any]) -> RuntimeSettings | None:
    provider = normalize_provider(str(raw.get("provider", "")).strip() or DEFAULT_PROVIDER)
    api_key = str(raw.get("api_key", "")).strip()
    if not api_key:
        return None
    model = str(raw.get("model", "")).strip() or default_model_for_provider(provider)
    reasoning_model = (
        str(raw.get("reasoning_model", "")).strip() or model
    )
    base_url = (
        str(raw.get("base_url", "")).strip()
        or default_base_url_for_provider(provider)
    )
    return RuntimeSettings(
        provider=provider,
        api_key=api_key,
        model=model,
        reasoning_model=reasoning_model,
        base_url=base_url,
    )


def _read_settings_file() -> RuntimeSettings | None:
    if not SETTINGS_FILE.exists():
        return None
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    return _normalize_settings(data if isinstance(data, dict) else {})


def _read_env_settings() -> RuntimeSettings | None:
    provider = normalize_provider(config.LLM_PROVIDER or DEFAULT_PROVIDER)
    env_api_key = (
        config.LLM_API_KEY
        or (config.ANTHROPIC_API_KEY if provider == "claude" else None)
        or (config.GEMINI_API_KEY if provider == "gemini" else None)
        or (config.GOOGLE_API_KEY if provider == "gemini" else None)
        or (config.API_KEY if provider == "deepseek" else None)
        or config.OPENAI_API_KEY
        or ""
    ).strip()
    if not env_api_key:
        return None
    env_model = (
        config.LLM_MODEL
        or (config.CHAT_MODEL if provider == "deepseek" else None)
        or config.OPENAI_MODEL
        or default_model_for_provider(provider)
    ).strip()
    env_reasoning_model = (
        config.LLM_REASONING_MODEL
        or config.OPENAI_REASONING_MODEL
        or env_model
    ).strip()
    env_base_url = (
        config.LLM_BASE_URL
        or (config.URL if provider == "deepseek" else None)
        or default_base_url_for_provider(provider)
    ).strip()
    return RuntimeSettings(
        provider=provider,
        api_key=env_api_key,
        model=env_model,
        reasoning_model=env_reasoning_model,
        base_url=env_base_url,
    )


def get_runtime_settings() -> RuntimeSettings | None:
    return _read_settings_file() or _read_env_settings()


def apply_runtime_settings(settings: RuntimeSettings) -> None:
    config.LLM_PROVIDER = settings.provider
    config.LLM_API_KEY = settings.api_key
    config.LLM_MODEL = settings.model
    config.LLM_REASONING_MODEL = settings.reasoning_model
    config.LLM_BASE_URL = settings.base_url

    config.OPENAI_API_KEY = settings.api_key
    config.OPENAI_API_KEY_FOR_REASONING = settings.api_key
    config.OPENAI_MODEL = settings.model
    config.OPENAI_REASONING_MODEL = settings.reasoning_model
    config.URL = settings.base_url

    os.environ["LLM_PROVIDER"] = settings.provider
    os.environ["LLM_API_KEY"] = settings.api_key
    os.environ["LLM_MODEL"] = settings.model
    os.environ["LLM_REASONING_MODEL"] = settings.reasoning_model
    os.environ["LLM_BASE_URL"] = settings.base_url
    os.environ["OPENAI_API_KEY"] = settings.api_key
    os.environ["OPENAI_API_KEY_FOR_REASONING"] = settings.api_key
    os.environ["OPENAI_MODEL"] = settings.model
    os.environ["OPENAI_REASONING_MODEL"] = settings.reasoning_model


def save_runtime_settings(
    api_key: str,
    provider: str | None = None,
    model: str | None = None,
    reasoning_model: str | None = None,
    base_url: str | None = None,
) -> RuntimeSettings:
    normalized_provider = normalize_provider(provider or DEFAULT_PROVIDER)
    default_model = default_model_for_provider(normalized_provider)
    payload = {
        "provider": normalized_provider,
        "api_key": api_key.strip(),
        "model": (model or "").strip() or default_model,
        "reasoning_model": (reasoning_model or "").strip() or (model or "").strip() or default_model,
        "base_url": (base_url or "").strip() or default_base_url_for_provider(normalized_provider),
    }
    SETTINGS_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    settings = _normalize_settings(payload)
    if settings is None:
        raise ValueError("api_key must not be empty")
    apply_runtime_settings(settings)
    return settings


def get_settings_public_view() -> dict[str, Any]:
    current = get_runtime_settings()
    if not current:
        return {
            "configured": False,
            "apiKeyMasked": "",
            "provider": DEFAULT_PROVIDER,
            "providers": list(SUPPORTED_PROVIDERS),
            "model": default_model_for_provider(DEFAULT_PROVIDER),
            "reasoningModel": default_model_for_provider(DEFAULT_PROVIDER),
            "baseUrl": default_base_url_for_provider(DEFAULT_PROVIDER),
            "defaultBaseUrls": DEFAULT_BASE_URLS,
        }
    return {
        "configured": True,
        "provider": current.provider,
        "providers": list(SUPPORTED_PROVIDERS),
        "apiKeyMasked": mask_api_key(current.api_key),
        "model": current.model,
        "reasoningModel": current.reasoning_model,
        "baseUrl": current.base_url,
        "defaultBaseUrls": DEFAULT_BASE_URLS,
    }
