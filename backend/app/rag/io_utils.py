from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import SourceChunk


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_chunks(path: Path) -> list[SourceChunk]:
    items = read_json(path)
    return [SourceChunk.from_dict(item, index=index) for index, item in enumerate(items, start=1)]
