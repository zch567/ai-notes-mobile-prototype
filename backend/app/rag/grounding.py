from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from .retrieval import HybridRetriever, RetrievalHit
from .schemas import SourceChunk
from .text_utils import compact, split_sentences, stable_digest, tokenize


def ground_result(result: dict[str, Any], chunks: list[SourceChunk], *, top_k: int = 2) -> dict[str, Any]:
    grounded = copy.deepcopy(result)
    retriever = HybridRetriever(chunks)
    notes = _normalize_notes(grounded.get("notes", []))
    grounded["notes"] = notes
    citations: list[dict[str, Any]] = []
    citation_counter = 1

    for note in notes:
        query = f"{note.get('title', '')} {note.get('content', '')}"
        hits = _grounding_hits(note, chunks, retriever, query, top_k=top_k)
        note["citationIds"] = []
        note_citations: list[dict[str, Any]] = []
        for hit in hits:
            citation = _build_citation(
                citation_counter,
                hit.chunk,
                note_id=note["id"],
                query=query,
                retrieval_score=hit.score,
            )
            citations.append(citation)
            note_citations.append(citation)
            note["citationIds"].append(hit.chunk.id)
            citation_counter += 1
        _enrich_low_support_note(note, note_citations, chunks)

    review = grounded.setdefault("review", {})
    for question in review.setdefault("questions", []):
        related_note = _find_related_note(question, notes)
        if related_note:
            question["relatedNoteId"] = related_note["id"]
            question["citationIds"] = list(related_note.get("citationIds", []))
        else:
            query = f"{question.get('question', '')} {question.get('explanation', '')}"
            question["citationIds"] = [hit.chunk.id for hit in retriever.retrieve(query, top_k=1, include_context=True)]

    grounded["citations"] = citations
    grounded["sources"] = [chunk.to_dict() for chunk in chunks]
    grounded.setdefault("warnings", [])
    grounded["warnings"] = list(dict.fromkeys(grounded["warnings"] + _grounding_warnings(grounded, chunks)))
    grounded["citationDiagnostics"] = validate_result(grounded, chunks)
    return grounded


def repair_result(result: dict[str, Any], chunks: list[SourceChunk]) -> dict[str, Any]:
    """Repair legacy AgentResult IDs and rebuild all citation links."""
    repaired = copy.deepcopy(result)
    repaired["notes"] = _normalize_notes(repaired.get("notes", []))
    repaired.setdefault("review", {}).setdefault("questions", [])
    repaired["sources"] = [chunk.to_dict() for chunk in chunks]
    repaired["citations"] = []
    return ground_result(repaired, chunks)


def validate_result(result: dict[str, Any], chunks: list[SourceChunk]) -> dict[str, Any]:
    chunk_ids = [chunk.id for chunk in chunks]
    chunk_by_id = {chunk.id: chunk for chunk in chunks}
    valid_sources = set(chunk_ids)
    notes = result.get("notes", [])
    note_ids = {str(note.get("id")) for note in notes}
    citations = result.get("citations", [])
    note_links = [source for note in notes for source in note.get("citationIds", [])]
    question_links = [
        source
        for question in result.get("review", {}).get("questions", [])
        for source in question.get("citationIds", [])
    ]
    quote_valid = 0
    for citation in citations:
        source = chunk_by_id.get(str(citation.get("sourceId")))
        quote = str(citation.get("quote", "")).strip()
        if source and quote and _normalize_for_match(quote) in _normalize_for_match(source.text):
            quote_valid += 1
    confidence_values = [float(item.get("confidence", 0)) for item in citations]
    titles = [str(note.get("title", "")).strip().lower() for note in notes]
    contents = [_normalize_for_match(str(note.get("content", ""))).lower() for note in notes]
    return {
        "chunkCount": len(chunks),
        "uniqueChunkIdRate": round(len(set(chunk_ids)) / max(1, len(chunk_ids)), 4),
        "noteCount": len(notes),
        "citationCount": len(citations),
        "noteCitationCoverage": round(sum(bool(note.get("citationIds")) for note in notes) / max(1, len(notes)), 4),
        "citationSourceValidity": round(
            sum(item.get("sourceId") in valid_sources for item in citations) / max(1, len(citations)), 4
        ),
        "citationNoteValidity": round(
            sum(str(item.get("noteId")) in note_ids for item in citations) / max(1, len(citations)), 4
        ),
        "noteLinkValidity": round(sum(item in valid_sources for item in note_links) / max(1, len(note_links)), 4),
        "reviewLinkValidity": round(sum(item in valid_sources for item in question_links) / max(1, len(question_links)), 4),
        "quoteInSourceRate": round(quote_valid / max(1, len(citations)), 4),
        "averageConfidence": round(sum(confidence_values) / max(1, len(confidence_values)), 4),
        "noteTitleUniqueness": round(len(set(titles)) / max(1, len(titles)), 4),
        "noteContentUniqueness": round(len(set(contents)) / max(1, len(contents)), 4),
    }


def rekey_legacy_chunks(items: list[dict[str, Any]]) -> list[SourceChunk]:
    chunks: list[SourceChunk] = []
    used: set[str] = set()
    for index, item in enumerate(items, start=1):
        chunk = SourceChunk.from_dict(item, index=index)
        stem = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", Path(chunk.fileName).stem).strip("-") or "source"
        locator = f"p{chunk.page:04d}" if chunk.page is not None else (
            f"s{chunk.slide:04d}" if chunk.slide is not None else "doc"
        )
        digest = stable_digest(f"{chunk.fileName}|{chunk.sourceRef}|{chunk.text}")
        candidate = f"{stem}-{locator}-c{index:04d}-{digest}"
        suffix = 2
        while candidate in used:
            candidate = f"{stem}-{locator}-c{index:04d}-{digest}-{suffix}"
            suffix += 1
        chunk.id = candidate
        chunk.chunkIndex = index
        chunk.sourceId = stem
        chunk.parentId = chunk.parentId or f"{stem}-{chunk.sourceRef}"
        used.add(candidate)
        chunks.append(chunk)
    return chunks


def _normalize_notes(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    used: set[str] = set()
    for index, item in enumerate(notes, start=1):
        note = dict(item)
        note_id = str(note.get("id") or note.get("node_id") or f"note-{index}")
        if note_id in used:
            note_id = f"note-{index}"
        used.add(note_id)
        note["id"] = note_id
        note.pop("node_id", None)
        note.setdefault("title", f"知识点 {index}")
        note.setdefault("content", "")
        note["citationIds"] = list(note.get("citationIds") or note.get("refs") or note.get("source_refs") or [])
        normalized.append(note)
    return normalized


def _find_related_note(question: dict[str, Any], notes: list[dict[str, Any]]) -> dict[str, Any] | None:
    related = str(question.get("relatedNoteId") or question.get("related_note_id") or "")
    if related:
        match = next((note for note in notes if note["id"] == related), None)
        if match:
            return match
    query_tokens = set(tokenize(f"{question.get('question', '')} {question.get('explanation', '')}"))
    ranked = sorted(
        notes,
        key=lambda note: len(query_tokens & set(tokenize(f"{note.get('title', '')} {note.get('content', '')}"))),
        reverse=True,
    )
    return ranked[0] if ranked and query_tokens else None


def _grounding_hits(
    note: dict[str, Any],
    chunks: list[SourceChunk],
    retriever: HybridRetriever,
    query: str,
    *,
    top_k: int,
) -> list[RetrievalHit]:
    explicit_chunks = _resolve_note_sources(note, chunks)
    target = max(top_k, min(len(explicit_chunks), 6)) if explicit_chunks else top_k
    selected: list[RetrievalHit] = []
    seen: set[str] = set()

    for chunk in explicit_chunks:
        if len(selected) >= target:
            break
        selected.append(_retrieval_hit(chunk, _direct_source_score(query, chunk), query))
        seen.add(chunk.id)

    if len(selected) < target:
        for hit in retriever.retrieve(query, top_k=max(target * 2, top_k), diversify=True, include_context=True):
            if hit.chunk.id in seen:
                continue
            selected.append(hit)
            seen.add(hit.chunk.id)
            if len(selected) >= target:
                break
    return selected


def _resolve_note_sources(note: dict[str, Any], chunks: list[SourceChunk]) -> list[SourceChunk]:
    refs = _string_list(
        note.get("source_refs")
        or note.get("sourceRefs")
        or note.get("citationIds")
        or note.get("refs")
        or []
    )
    if not refs:
        return []
    by_id = {chunk.id: chunk for chunk in chunks}
    by_source_ref: dict[str, list[SourceChunk]] = {}
    for chunk in chunks:
        by_source_ref.setdefault(chunk.sourceRef, []).append(chunk)

    resolved: list[SourceChunk] = []
    seen: set[str] = set()
    for ref in refs:
        candidates = []
        if ref in by_id:
            candidates = [by_id[ref]]
        elif ref in by_source_ref:
            candidates = by_source_ref[ref]
        for chunk in candidates:
            if chunk.id not in seen:
                resolved.append(chunk)
                seen.add(chunk.id)
    return resolved


def _direct_source_score(query: str, chunk: SourceChunk) -> float:
    query_tokens = set(tokenize(query))
    chunk_tokens = set(tokenize(f"{chunk.heading} {chunk.text}"))
    overlap = len(query_tokens & chunk_tokens) / max(1, len(query_tokens | chunk_tokens))
    containment = len(query_tokens & chunk_tokens) / max(1, len(query_tokens))
    return 10.0 + overlap * 4.0 + containment * 4.0


def _retrieval_hit(chunk: SourceChunk, score: float, query: str) -> RetrievalHit:
    query_tokens = set(tokenize(query))
    chunk_tokens = set(tokenize(f"{chunk.heading} {chunk.text}"))
    matched = sorted(query_tokens & chunk_tokens, key=lambda item: (-len(item), item))[:10]
    return RetrievalHit(
        chunk=chunk,
        score=score,
        bm25=score,
        phrase=0.0,
        heading=0.0,
        matched_terms=matched,
    )


def _enrich_low_support_note(
    note: dict[str, Any],
    citations: list[dict[str, Any]],
    chunks: list[SourceChunk],
) -> None:
    if not citations or "原文依据：" in str(note.get("content", "")):
        return
    if _note_source_support(note, citations, chunks) >= 0.55:
        return
    quotes = [str(item.get("quote", "")).strip() for item in citations if str(item.get("quote", "")).strip()]
    if not quotes:
        return
    evidence = "；".join(dict.fromkeys(quotes[:2]))
    content = str(note.get("content") or "").strip()
    note["content"] = compact(f"{content} 原文依据：{evidence}", 520)


def _note_source_support(
    note: dict[str, Any],
    citations: list[dict[str, Any]],
    chunks: list[SourceChunk],
) -> float:
    note_tokens = set(tokenize(f"{note.get('title', '')} {note.get('content', '')}"))
    if not note_tokens:
        return 0.0
    citation_text = " ".join(str(item.get("quote", "")) for item in citations)
    quote_tokens = set(tokenize(citation_text))
    if not quote_tokens:
        chunk_by_id = {chunk.id: chunk for chunk in chunks}
        citation_text = " ".join(
            chunk_by_id[str(item.get("sourceId"))].text
            for item in citations
            if str(item.get("sourceId")) in chunk_by_id
        )
        quote_tokens = set(tokenize(citation_text))
    overlap = len(note_tokens & quote_tokens)
    return overlap / max(1, len(note_tokens))


def _build_citation(
    index: int,
    chunk: SourceChunk,
    *,
    note_id: str,
    query: str,
    retrieval_score: float,
) -> dict[str, Any]:
    quote, quote_score, sentence_index = _best_quote(query, chunk.text)
    line_start = _line_for_offset(chunk.text, chunk.text.find(quote)) if quote else chunk.lineStart
    confidence = min(0.99, 0.35 + quote_score * 0.45 + min(0.19, retrieval_score / 20))
    return {
        "id": f"citation-{index:04d}",
        "sourceId": chunk.id,
        "noteId": note_id,
        "quote": quote,
        "sourceRef": chunk.sourceRef,
        "page": chunk.page,
        "slide": chunk.slide,
        "paragraphStart": chunk.paragraphStart,
        "paragraphEnd": chunk.paragraphEnd,
        "lineStart": line_start,
        "lineEnd": line_start + max(0, quote.count("\n")),
        "sentenceIndex": sentence_index,
        "confidence": round(confidence, 4),
        "retrievalScore": round(retrieval_score, 6),
        "matchType": "hybrid_bm25_phrase_sentence_context",
    }


def _best_quote(query: str, text: str) -> tuple[str, float, int]:
    query_tokens = set(tokenize(query))
    sentences = split_sentences(text)
    best = ("", 0.0, 0)
    for index, sentence in enumerate(sentences, start=1):
        sentence_tokens = set(tokenize(sentence))
        overlap = len(query_tokens & sentence_tokens) / max(1, len(query_tokens | sentence_tokens))
        containment = len(query_tokens & sentence_tokens) / max(1, len(sentence_tokens))
        score = overlap * 0.65 + containment * 0.35
        if score > best[1]:
            best = (sentence, score, index)
    if not best[0]:
        return text[:220].strip(), 0.1, 1
    return best[0][:260].strip(), best[1], best[2]


def _line_for_offset(text: str, offset: int) -> int:
    if offset < 0:
        return 1
    return text[:offset].count("\n") + 1


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _grounding_warnings(result: dict[str, Any], chunks: list[SourceChunk]) -> list[str]:
    warnings: list[str] = []
    if len(chunks) != len({chunk.id for chunk in chunks}):
        warnings.append("检测到重复 chunk id，引用定位不可靠。")
    if any(not note.get("citationIds") for note in result.get("notes", [])):
        warnings.append("部分笔记未找到可靠来源。")
    if any(float(item.get("confidence", 0)) < 0.45 for item in result.get("citations", [])):
        warnings.append("部分引用置信度较低，建议人工复核。")
    return warnings
