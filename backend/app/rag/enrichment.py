from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from .schemas import SourceChunk
from .text_utils import compact, extract_keywords, tokenize


@dataclass(frozen=True)
class EvidencePack:
    """Retrieval evidence with adjacent context for grounded synthesis."""

    focus: SourceChunk
    before: SourceChunk | None
    after: SourceChunk | None
    query_terms: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sourceId": self.focus.id,
            "sourceRef": self.focus.sourceRef,
            "title": self.focus.title,
            "heading": self.focus.heading,
            "queryTerms": self.query_terms,
            "text": compact(self.focus.text, 900),
            "before": _adjacent_dict(self.before),
            "after": _adjacent_dict(self.after),
        }


def expand_query(query: str, chunks: list[SourceChunk], *, limit: int = 6) -> str:
    """Add corpus terms that co-occur with query tokens, similar to lightweight RAG query rewriting."""

    tokens = tokenize(query)
    if not tokens:
        return query
    query_terms = set(tokens)
    cooccurrence: Counter[str] = Counter()
    for chunk in chunks:
        chunk_terms = set(tokenize(f"{chunk.heading} {chunk.text}"))
        if not query_terms & chunk_terms:
            continue
        for keyword in chunk.keywords or extract_keywords(f"{chunk.heading} {chunk.text}", limit=8):
            if keyword not in query_terms:
                cooccurrence[keyword] += 1
    additions = [term for term, _count in cooccurrence.most_common(limit)]
    return " ".join([query, *additions]).strip()


def build_evidence_packs(
    chunks: list[SourceChunk],
    source_ids: list[str],
    query: str,
) -> list[EvidencePack]:
    by_id = {chunk.id: chunk for chunk in chunks}
    by_parent: dict[str, list[SourceChunk]] = defaultdict(list)
    for chunk in chunks:
        by_parent[chunk.parentId or chunk.sourceRef].append(chunk)
    for siblings in by_parent.values():
        siblings.sort(key=lambda item: item.chunkIndex)

    packs: list[EvidencePack] = []
    query_terms = sorted(set(tokenize(query)), key=lambda item: (-len(item), item))[:10]
    for source_id in source_ids:
        focus = by_id.get(source_id)
        if not focus:
            continue
        siblings = by_parent.get(focus.parentId or focus.sourceRef, [])
        before, after = _adjacent_chunks(focus, siblings)
        packs.append(EvidencePack(focus=focus, before=before, after=after, query_terms=query_terms))
    return packs


def chunk_structure_overview(chunks: list[SourceChunk]) -> dict[str, Any]:
    parents = defaultdict(int)
    pages = set()
    slides = set()
    headings = []
    for chunk in chunks:
        parents[chunk.parentId or chunk.sourceRef] += 1
        if chunk.page is not None:
            pages.add(chunk.page)
        if chunk.slide is not None:
            slides.add(chunk.slide)
        if chunk.heading:
            headings.append(chunk.heading)
    return {
        "chunkCount": len(chunks),
        "parentCount": len(parents),
        "multiChunkParentCount": sum(count > 1 for count in parents.values()),
        "pageCount": len(pages),
        "slideCount": len(slides),
        "sampleHeadings": list(dict.fromkeys(headings))[:12],
    }


def _adjacent_chunks(focus: SourceChunk, siblings: list[SourceChunk]) -> tuple[SourceChunk | None, SourceChunk | None]:
    for index, chunk in enumerate(siblings):
        if chunk.id != focus.id:
            continue
        before = siblings[index - 1] if index > 0 else None
        after = siblings[index + 1] if index + 1 < len(siblings) else None
        return before, after
    return None, None


def _adjacent_dict(chunk: SourceChunk | None) -> dict[str, Any] | None:
    if not chunk:
        return None
    return {
        "sourceId": chunk.id,
        "sourceRef": chunk.sourceRef,
        "heading": chunk.heading,
        "text": compact(chunk.text, 360),
    }
