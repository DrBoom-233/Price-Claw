from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import config


SETTINGS_FILE = Path(".app_settings.json")
DEFAULT_OPENAI_MODEL = config.OPENAI_MODEL or "gpt-4o-mini"
DEFAULT_OPENAI_REASONING_MODEL = config.OPENAI_REASONING_MODEL or "o4-mini"


@dataclass
class RuntimeSettings:
    api_key: str
    model: str
    reasoning_model: str


def mask_api_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 10:
        return f"{api_key[:2]}***{api_key[-2:]}"
    return f"{api_key[:4]}***{api_key[-4:]}"


def _normalize_settings(raw: dict[str, Any]) -> RuntimeSettings | None:
    api_key = str(raw.get("api_key", "")).strip()
    if not api_key:
        return None
    model = str(raw.get("model", "")).strip() or DEFAULT_OPENAI_MODEL
    reasoning_model = (
        str(raw.get("reasoning_model", "")).strip() or DEFAULT_OPENAI_REASONING_MODEL
    )
    return RuntimeSettings(api_key=api_key, model=model, reasoning_model=reasoning_model)


def _read_settings_file() -> RuntimeSettings | None:
    if not SETTINGS_FILE.exists():
        return None
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    return _normalize_settings(data if isinstance(data, dict) else {})


def _read_env_settings() -> RuntimeSettings | None:
    env_api_key = (config.OPENAI_API_KEY or "").strip()
    if not env_api_key:
        return None
    env_model = (config.OPENAI_MODEL or "").strip() or DEFAULT_OPENAI_MODEL
    env_reasoning_model = (
        (config.OPENAI_REASONING_MODEL or "").strip() or DEFAULT_OPENAI_REASONING_MODEL
    )
    return RuntimeSettings(
        api_key=env_api_key,
        model=env_model,
        reasoning_model=env_reasoning_model,
    )


def get_runtime_settings() -> RuntimeSettings | None:
    return _read_settings_file() or _read_env_settings()


def apply_runtime_settings(settings: RuntimeSettings) -> None:
    config.OPENAI_API_KEY = settings.api_key
    config.OPENAI_API_KEY_FOR_REASONING = settings.api_key
    config.OPENAI_MODEL = settings.model
    config.OPENAI_REASONING_MODEL = settings.reasoning_model

    os.environ["OPENAI_API_KEY"] = settings.api_key
    os.environ["OPENAI_API_KEY_FOR_REASONING"] = settings.api_key
    os.environ["OPENAI_MODEL"] = settings.model
    os.environ["OPENAI_REASONING_MODEL"] = settings.reasoning_model


def save_runtime_settings(
    api_key: str,
    model: str | None = None,
    reasoning_model: str | None = None,
) -> RuntimeSettings:
    payload = {
        "api_key": api_key.strip(),
        "model": (model or "").strip() or DEFAULT_OPENAI_MODEL,
        "reasoning_model": (reasoning_model or "").strip()
        or DEFAULT_OPENAI_REASONING_MODEL,
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
            "model": DEFAULT_OPENAI_MODEL,
            "reasoningModel": DEFAULT_OPENAI_REASONING_MODEL,
        }
    return {
        "configured": True,
        "apiKeyMasked": mask_api_key(current.api_key),
        "model": current.model,
        "reasoningModel": current.reasoning_model,
    }

