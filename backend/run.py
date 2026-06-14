from __future__ import annotations

from pathlib import Path

from scripts.ensure_requirements import ensure_backend_requirements


ensure_backend_requirements(Path(__file__).resolve().parent)

import uvicorn

from app.config import settings


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)
