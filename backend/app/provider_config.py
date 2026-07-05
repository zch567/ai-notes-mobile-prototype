from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .bootstrap import WORKSPACE_ROOT, get_backend_env
from .providers import ModelProvider, OpenAICompatibleProvider


DEFAULT_SECRETS_FILE = WORKSPACE_ROOT / "api"


def load_key_values(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


@dataclass(frozen=True)
class ProviderConfig:
    configured_provider: str
    lanxin_api_key: str
    lanxin_base_url: str
    lanxin_model: str
    model_timeout_seconds: int
    lanxin_retries: int
    lanxin_ocr_app_id: str
    lanxin_ocr_app_key: str
    lanxin_ocr_business_id: str
    lanxin_ocr_url: str
    lanxin_ocr_timeout_seconds: int
    lanxin_ocr_pos: str
    lanxin_ocr_retries: int
    secrets_file: Path

    @classmethod
    def load(cls) -> "ProviderConfig":
        explicit_secrets_file = os.getenv("BACKEND_SECRETS_FILE")
        secrets_file = Path(
            explicit_secrets_file or get_backend_env("BACKEND_SECRETS_FILE", str(DEFAULT_SECRETS_FILE))
        ).expanduser().resolve()
        file_values = load_key_values(secrets_file)

        def value(name: str, default: str = "") -> str:
            env_value = os.getenv(name)
            if env_value is not None:
                return env_value
            if name in file_values:
                return file_values[name]
            if explicit_secrets_file is not None and name == "LANXIN_API_KEY":
                return default
            return get_backend_env(name, default)

        return cls(
            configured_provider=value("MODEL_PROVIDER", "lanxin").lower(),
            lanxin_api_key=value("LANXIN_API_KEY"),
            lanxin_base_url=value("LANXIN_BASE_URL", "https://api-ai.vivo.com.cn/v1").rstrip("/"),
            lanxin_model=value("LANXIN_MODEL", "Doubao-Seed-2.0-mini"),
            model_timeout_seconds=int(value("MODEL_TIMEOUT_MS", "90")),
            lanxin_retries=int(value("LANXIN_RETRIES", "1")),
            lanxin_ocr_app_id=value("LANXIN_OCR_APP_ID"),
            lanxin_ocr_app_key=value("LANXIN_OCR_APP_KEY") or value("LANXIN_API_KEY"),
            lanxin_ocr_business_id=value("LANXIN_OCR_BUSINESS_ID") or value("LANXIN_OCR_APP_ID"),
            lanxin_ocr_url=value("LANXIN_OCR_URL", "https://api-ai.vivo.com.cn/ocr/general_recognition"),
            lanxin_ocr_timeout_seconds=int(value("LANXIN_OCR_TIMEOUT_SECONDS", "30")),
            lanxin_ocr_pos=value("LANXIN_OCR_POS", "2"),
            lanxin_ocr_retries=int(value("LANXIN_OCR_RETRIES", "1")),
            secrets_file=secrets_file,
        )

    def status(self) -> dict[str, Any]:
        return {
            "configuredProvider": self.configured_provider,
            "lanxin": {
                "configured": bool(self.lanxin_api_key),
                "baseUrl": self.lanxin_base_url,
                "model": self.lanxin_model,
                "timeoutSeconds": self.model_timeout_seconds,
                "retries": self.lanxin_retries,
            },
            "lanxinOcr": {
                "configured": bool(self.lanxin_ocr_app_key and self.lanxin_ocr_business_id),
                "url": self.lanxin_ocr_url,
                "timeoutSeconds": self.lanxin_ocr_timeout_seconds,
                "retries": self.lanxin_ocr_retries,
            },
            "secretsFilePresent": self.secrets_file.exists(),
        }


def create_provider(requested: str | None = None) -> ModelProvider:
    config = ProviderConfig.load()
    provider_name = (requested or config.configured_provider or "lanxin").lower()
    if provider_name == "lanxin":
        if not config.lanxin_api_key:
            raise RuntimeError(
                "Lanxin is not configured. Set LANXIN_API_KEY or BACKEND_SECRETS_FILE."
            )
        return OpenAICompatibleProvider(
            name="lanxin",
            base_url=config.lanxin_base_url,
            api_key=config.lanxin_api_key,
            model=config.lanxin_model,
            timeout_seconds=config.model_timeout_seconds,
            retries=config.lanxin_retries,
        )

    provider_values = _generic_provider_values(config, provider_name)
    missing = [key for key in ("api_key", "base_url", "model") if not provider_values[key]]
    if missing:
        env_prefix = _provider_env_prefix(provider_name)
        missing_display = ", ".join(missing)
        raise RuntimeError(
            f"{provider_name} is not configured. Missing {missing_display}. "
            f"Set {env_prefix}_API_KEY, {env_prefix}_BASE_URL and {env_prefix}_MODEL "
            "or the generic MODEL_API_KEY, MODEL_BASE_URL and MODEL_MODEL."
        )

    return OpenAICompatibleProvider(
        name=provider_name,
        base_url=str(provider_values["base_url"]),
        api_key=str(provider_values["api_key"]),
        model=str(provider_values["model"]),
        timeout_seconds=config.model_timeout_seconds,
        retries=int(provider_values["retries"] or 0),
    )


def _generic_provider_values(config: ProviderConfig, provider_name: str) -> dict[str, str | int]:
    file_values = load_key_values(config.secrets_file)
    env_prefix = _provider_env_prefix(provider_name)

    def value(name: str, default: str = "") -> str:
        env_value = os.getenv(name)
        if env_value is not None:
            return env_value
        if name in file_values:
            return file_values[name]
        return get_backend_env(name, default)

    return {
        "api_key": value(f"{env_prefix}_API_KEY") or value("MODEL_API_KEY"),
        "base_url": (value(f"{env_prefix}_BASE_URL") or value("MODEL_BASE_URL")).rstrip("/"),
        "model": value(f"{env_prefix}_MODEL") or value("MODEL_MODEL") or value("MODEL_NAME"),
        "retries": int(value(f"{env_prefix}_RETRIES") or value("MODEL_RETRIES", "0")),
    }


def _provider_env_prefix(provider_name: str) -> str:
    prefix = re.sub(r"[^A-Za-z0-9]+", "_", provider_name).strip("_").upper()
    return prefix or "MODEL"
