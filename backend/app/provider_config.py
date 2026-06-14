from __future__ import annotations

import os
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
    raise ValueError(f"Unsupported provider: {provider_name}. Only 'lanxin' is supported.")
