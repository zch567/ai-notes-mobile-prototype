from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .bootstrap import BACKEND_ROOT, WORKSPACE_ROOT


def _path_env(name: str, default: Path) -> Path:
    return Path(os.getenv(name, str(default))).expanduser().resolve()


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("BACKEND_HOST", "127.0.0.1")
    port: int = int(os.getenv("BACKEND_PORT", "8000"))
    output_dir: Path = _path_env("BACKEND_OUTPUT_DIR", BACKEND_ROOT / "runtime")
    default_pipeline: str = os.getenv("BACKEND_DEFAULT_PIPELINE", "hybrid")
    allowed_input_root: Path = _path_env("BACKEND_ALLOWED_INPUT_ROOT", WORKSPACE_ROOT)
    cors_origins: tuple[str, ...] = tuple(
        item.strip()
        for item in os.getenv("BACKEND_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if item.strip()
    )


settings = Settings()
