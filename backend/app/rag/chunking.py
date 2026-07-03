from __future__ import annotations

from pathlib import Path

from .schemas import RawBlock, SourceChunk
from .text_utils import extract_heading_level, extract_keywords, looks_like_heading, normalize_learning_text, normalize_text, slugify, stable_digest


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
    for section in _group_by_headings(blocks):
        chunks.extend(
            _chunk_section(
                section,
                source_id=source_id,
                target_chars=target_chars,
                max_chars=max_chars,
                chunk_start_index=len(chunks) + 1,
            )
        )

    ids = [chunk.id for chunk in chunks]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Chunk IDs must be globally unique")
    return chunks


def _group_by_headings(blocks: list[RawBlock]) -> list[list[RawBlock]]:
    sections: list[list[RawBlock]] = []
    current_section: list[RawBlock] = []
    current_level = 99

    for block in blocks:
        if looks_like_heading(block.text):
            level = extract_heading_level(block.text)
            if current_section and level <= current_level:
                sections.append(current_section)
                current_section = []
                current_level = level
            elif not current_section:
                current_level = level
        current_section.append(block)

    if current_section:
        sections.append(current_section)
    return sections


def _chunk_section(
    section_blocks: list[RawBlock],
    *,
    source_id: str,
    target_chars: int,
    max_chars: int,
    chunk_start_index: int,
) -> list[SourceChunk]:
    if not section_blocks:
        return []

    chunks: list[SourceChunk] = []
    buffer: list[RawBlock] = []
    chunk_index = chunk_start_index

    def flush() -> None:
        nonlocal chunk_index
        if not buffer:
            return
        text = normalize_learning_text("\n".join(block.text for block in buffer))
        if not text:
            buffer.clear()
            return

        first = buffer[0]
        last = buffer[-1]
        locator = _locator(first)
        digest = stable_digest(f"{first.file_name}|{locator}|{text}")
        chunk_id = f"{source_id}-{locator}-c{chunk_index:04d}-{digest}"
        paragraph_start = first.paragraph
        paragraph_end = last.paragraph
        source_ref = _source_ref(first, last)
        heading = normalize_learning_text(first.heading or next((b.heading for b in buffer if b.heading), ""))
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
        chunk_index += 1

    for block in section_blocks:
        if not buffer:
            buffer.append(block)
            continue

        current_len = sum(len(item.text) for item in buffer)
        boundary_changed = _locator(block) != _locator(buffer[0])
        heading_changed = bool(block.heading and block.heading != buffer[-1].heading)
        would_overflow = current_len + len(block.text) > max_chars

        if boundary_changed or heading_changed or would_overflow:
            flush()
            buffer = []

        buffer.append(block)
        if sum(len(item.text) for item in buffer) >= target_chars and len(buffer) >= 2:
            flush()
            buffer = []

    flush()
    return chunks


def _locator(block: RawBlock) -> str:
    if block.page is not None:
        return f"p{block.page:04d}"
    if block.slide is not None:
        return f"s{block.slide:04d}"
    return "doc"


def _source_ref(first: RawBlock, last: RawBlock) -> str:
    if first.page is not None:
        if last.page and last.page != first.page:
            return f"page_{first.page}_{last.page}"
        return f"page_{first.page}"
    if first.slide is not None:
        if last.slide and last.slide != first.slide:
            return f"slide_{first.slide}_{last.slide}"
        return f"slide_{first.slide}"
    start = first.paragraph or first.block_index
    end = last.paragraph or last.block_index
    return f"para_{start}" if start == end else f"para_{start}_{end}"


def _title(file_name: str, source_ref: str, heading: str) -> str:
    suffix = f" / {heading}" if heading else ""
    return f"{file_name} / {source_ref}{suffix}"
