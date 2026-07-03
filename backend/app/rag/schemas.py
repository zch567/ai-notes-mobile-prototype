from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RawBlock:
    text: str
    source_type: str
    file_name: str
    block_index: int
    page: int | None = None
    slide: int | None = None
    paragraph: int | None = None
    heading: str = ""
    source_ref: str = ""


@dataclass
class ParseDiagnosis:
    file_name: str
    source_type: str
    total_pages: int = 0
    total_slides: int = 0
    raw_block_count: int = 0
    chunk_count: int = 0
    heading_count: int = 0
    empty_page_ratio: float = 0.0
    garbled_ratio: float = 0.0
    average_block_chars: float = 0.0
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceChunk:
    id: str
    sourceId: str
    title: str
    text: str
    sourceType: str
    fileName: str
    chunkIndex: int
    sourceRef: str
    heading: str = ""
    page: int | None = None
    slide: int | None = None
    paragraphStart: int | None = None
    paragraphEnd: int | None = None
    lineStart: int = 1
    lineEnd: int = 1
    charStart: int = 0
    charEnd: int = 0
    parentId: str = ""
    keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, item: dict[str, Any], index: int = 1) -> "SourceChunk":
        text = str(item.get("text", "")).strip()
        page = _as_int(item.get("page"))
        slide = _as_int(item.get("slide"))
        paragraph = _as_int(item.get("paragraph"))
        paragraph_start = _as_int(item.get("paragraphStart")) or paragraph
        paragraph_end = _as_int(item.get("paragraphEnd")) or paragraph_start
        source_ref = str(item.get("sourceRef") or _source_ref(page, slide, paragraph_start, paragraph_end))
        return cls(
            id=str(item.get("id") or f"legacy-{index}"),
            sourceId=str(item.get("sourceId") or item.get("fileName") or "source"),
            title=str(item.get("title") or source_ref),
            text=text,
            sourceType=str(item.get("sourceType") or "text"),
            fileName=str(item.get("fileName") or "source"),
            chunkIndex=_as_int(item.get("chunkIndex")) or index,
            sourceRef=source_ref,
            heading=str(item.get("heading") or ""),
            page=page,
            slide=slide,
            paragraphStart=paragraph_start,
            paragraphEnd=paragraph_end,
            lineStart=_as_int(item.get("lineStart")) or 1,
            lineEnd=_as_int(item.get("lineEnd")) or max(1, text.count("\n") + 1),
            charStart=_as_int(item.get("charStart")) or 0,
            charEnd=_as_int(item.get("charEnd")) or len(text),
            parentId=str(item.get("parentId") or ""),
            keywords=list(item.get("keywords") or []),
        )


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _source_ref(page: int | None, slide: int | None, paragraph_start: int | None, paragraph_end: int | None) -> str:
    if page is not None:
        return f"page_{page}"
    if slide is not None:
        return f"slide_{slide}"
    if paragraph_start is not None:
        if paragraph_end and paragraph_end != paragraph_start:
            return f"para_{paragraph_start}_{paragraph_end}"
        return f"para_{paragraph_start}"
    return "document"
