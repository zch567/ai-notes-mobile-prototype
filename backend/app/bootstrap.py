from __future__ import annotations

import os
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = BACKEND_ROOT.parent


def load_backend_env() -> dict[str, str]:
    env_file = BACKEND_ROOT / ".env"
    if not env_file.exists():
        return {}

    values: dict[str, str] = {}
    for raw in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = value.strip().strip('"').strip("'")
    return values


ENV_FILE_VALUES = load_backend_env()


def get_backend_env(name: str, default: str = "") -> str:
    return os.getenv(name, ENV_FILE_VALUES.get(name, default))
