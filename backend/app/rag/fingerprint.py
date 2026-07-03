from __future__ import annotations

import hashlib
import json

from .schemas import SourceChunk


def corpus_hash(chunks: list[SourceChunk]) -> str:
    """Stable content fingerprint for retriever and grounding caches."""
    payload = [
        {
            "id": chunk.id,
            "sourceRef": chunk.sourceRef,
            "fileName": chunk.fileName,
            "chunkIndex": chunk.chunkIndex,
            "textSha1": hashlib.sha1(chunk.text.encode("utf-8")).hexdigest(),
        }
        for chunk in sorted(chunks, key=lambda item: (item.fileName, item.sourceRef, item.chunkIndex, item.id))
    ]
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()
