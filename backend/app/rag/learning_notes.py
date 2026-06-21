from __future__ import annotations

from typing import Any

from .schemas import SourceChunk
from .semantic_notes import enrich_learning_notes_contract


def enrich_learning_notes(notes: list[dict[str, Any]], chunks: list[SourceChunk]) -> list[dict[str, Any]]:
    """Normalize model notes into the semantic note-block contract."""
    return enrich_learning_notes_contract(notes, chunks)
