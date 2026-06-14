from __future__ import annotations

from pathlib import Path

from .schemas import RawBlock, SourceChunk
from .text_utils import extract_keywords, normalize_text, slugify, stable_digest


def build_chunks(
    blocks: list[RawBlock],
    *,
    target_chars: int = 650,
    max_chars: int = 950,
) -> list[SourceChunk]:
    if not blocks:
        return []
    source_id = slugify(Path(blocks[0].file_name).stem)
    chunks: list[SourceChunk] = []
    buffer: list[RawBlock] = []

    def flush() -> None:
        if not buffer:
            return
        text = normalize_text("\n".join(block.text for block in buffer))
        first = buffer[0]
        last = buffer[-1]
        chunk_index = len(chunks) + 1
        locator = _locator(first)
        digest = stable_digest(f"{first.file_name}|{locator}|{text}")
        chunk_id = f"{source_id}-{locator}-c{chunk_index:04d}-{digest}"
        paragraph_start = first.paragraph
        paragraph_end = last.paragraph
        source_ref = _source_ref(first, last)
        heading = first.heading or next((block.heading for block in buffer if block.heading), "")
        title = _title(first.file_name, source_ref, heading)
        parent_id = f"{source_id}-{source_ref}"
        chunks.append(
            SourceChunk(
                id=chunk_id,
                sourceId=source_id,
                title=title,
                text=text,
                sourceType=first.source_type,
                fileName=first.file_name,
                chunkIndex=chunk_index,
                sourceRef=source_ref,
                heading=heading,
                page=first.page,
                slide=first.slide,
                paragraphStart=paragraph_start,
                paragraphEnd=paragraph_end,
                lineStart=1,
                lineEnd=max(1, text.count("\n") + 1),
                charStart=0,
                charEnd=len(text),
                parentId=parent_id,
                keywords=extract_keywords(f"{heading} {text}", limit=8),
            )
        )

    for block in blocks:
        if not buffer:
            buffer.append(block)
            continue
        current_len = sum(len(item.text) for item in buffer)
        boundary_changed = _locator(block) != _locator(buffer[0])
        heading_changed = bool(block.heading and block.heading != buffer[-1].heading and current_len >= target_chars // 2)
        would_overflow = current_len + len(block.text) > max_chars
        if boundary_changed or heading_changed or would_overflow:
            flush()
            buffer = []
        buffer.append(block)
        if sum(len(item.text) for item in buffer) >= target_chars and len(buffer) >= 2:
            flush()
            buffer = []
    flush()

    ids = [chunk.id for chunk in chunks]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Chunk IDs must be globally unique")
    return chunks


def _locator(block: RawBlock) -> str:
    if block.page is not None:
        return f"p{block.page:04d}"
    if block.slide is not None:
        return f"s{block.slide:04d}"
    return "doc"


def _source_ref(first: RawBlock, last: RawBlock) -> str:
    if first.page is not None:
        return f"page_{first.page}"
    if first.slide is not None:
        return f"slide_{first.slide}"
    start = first.paragraph or first.block_index
    end = last.paragraph or last.block_index
    return f"para_{start}" if start == end else f"para_{start}_{end}"


def _title(file_name: str, source_ref: str, heading: str) -> str:
    suffix = f" / {heading}" if heading else ""
    return f"{file_name} / {source_ref}{suffix}"
