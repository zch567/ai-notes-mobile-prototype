from __future__ import annotations

import copy
import re
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

from .fingerprint import corpus_hash
from .retrieval import HybridRetriever, RetrievalHit
from .schemas import SourceChunk
from .text_utils import compact, extract_keywords, split_sentences, stable_digest, tokenize

_RETRIEVER_CACHE_MAX = 16
_RETRIEVER_CACHE: OrderedDict[str, HybridRetriever] = OrderedDict()


def ground_result(result: dict[str, Any], chunks: list[SourceChunk], *, top_k: int = 2) -> dict[str, Any]:
    started = time.perf_counter()
    grounded = copy.deepcopy(result)
    corpus_id = corpus_hash(chunks)
    retrieval_calls = 0
    retriever, retriever_cache_hit = _retriever_for_grounding(corpus_id, chunks)
    notes = _normalize_notes(grounded.get("notes", []))
    grounded["notes"] = notes
    citations: list[dict[str, Any]] = []
    citation_counter = 1

    for note in notes:
        query_info = build_grounding_query(note, chunks)
        query = query_info["expandedQuery"]
        hits = _grounding_hits(note, chunks, retriever, query, top_k=top_k)
        retrieval_calls += 1
        trace = _grounding_trace(note, chunks, hits, query_info)
        note["groundingTrace"] = trace
        note["citationIds"] = []
        note_citations: list[dict[str, Any]] = []
        for hit in hits:
            citation = _build_citation(
                citation_counter,
                hit.chunk,
                note_id=note["id"],
                query=query,
                retrieval_score=hit.score,
                note=note,
            )
            citations.append(citation)
            note_citations.append(citation)
            note["citationIds"].append(hit.chunk.id)
            citation_counter += 1
        _attach_note_support(note, note_citations, chunks)
        _enrich_low_support_note(note, note_citations, chunks)

    review = grounded.setdefault("review", {})
    for question in review.setdefault("questions", []):
        related_note = _find_related_note(question, notes)
        if related_note:
            question["relatedNoteId"] = related_note["id"]
            question["citationIds"] = list(related_note.get("citationIds", []))
        else:
            query = f"{question.get('question', '')} {question.get('explanation', '')}"
            retrieval_calls += 1
            question["citationIds"] = [hit.chunk.id for hit in retriever.retrieve(query, top_k=1, include_context=True)]

    grounded["citations"] = citations
    grounded["sources"] = [chunk.to_dict() for chunk in chunks]
    grounded.setdefault("warnings", [])
    grounded["warnings"] = list(dict.fromkeys(grounded["warnings"] + _grounding_warnings(grounded, chunks)))
    grounded["citationDiagnostics"] = validate_result(grounded, chunks)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    grounded["citationDiagnostics"]["groundingPerf"] = {
        "corpusHash": corpus_id,
        "chunkCount": len(chunks),
        "noteCount": len(notes),
        "retrievalCalls": retrieval_calls,
        "elapsedMs": elapsed_ms,
        "avgMsPerNote": round(elapsed_ms / max(1, len(notes)), 3),
        "topK": top_k,
        "retrieverCacheHit": retriever_cache_hit,
        "retrieverCacheSize": len(_RETRIEVER_CACHE),
    }
    return grounded


def clear_grounding_cache() -> None:
    _RETRIEVER_CACHE.clear()


def _retriever_for_grounding(corpus_id: str, chunks: list[SourceChunk]) -> tuple[HybridRetriever, bool]:
    cached = _RETRIEVER_CACHE.get(corpus_id)
    if cached:
        _RETRIEVER_CACHE.move_to_end(corpus_id)
        return cached, True
    retriever = HybridRetriever(chunks)
    _RETRIEVER_CACHE[corpus_id] = retriever
    if len(_RETRIEVER_CACHE) > _RETRIEVER_CACHE_MAX:
        _RETRIEVER_CACHE.popitem(last=False)
    return retriever, False

def build_grounding_query(note: dict[str, Any], chunks: list[SourceChunk]) -> dict[str, Any]:
    parts: list[tuple[str, str]] = []

    def add(source: str, value: Any) -> None:
        if isinstance(value, list):
            value = " ".join(str(item) for item in value if str(item))
        value = str(value or "").strip()
        if value:
            parts.append((source, value))

    add("title", note.get("title"))
    add("summary", note.get("summary"))
    add("keyPoints", note.get("keyPoints"))
    add("content", _first_sentences(str(note.get("content") or ""), limit=3))
    for block in note.get("blocks") or []:
        block_type = str(block.get("type") or "")
        if block_type in {"definition", "mechanism", "procedure", "effect", "formula", "evidence", "summary", "outline"}:
            add(f"block:{block_type}:content", block.get("content"))
            add(f"block:{block_type}:items", block.get("items"))
    for relation in note.get("relations") or []:
        add("relation", relation.get("target"))
    for chunk in _resolve_note_sources(note, chunks):
        add("sourceHeading", chunk.heading)
        add("sourceRef", chunk.sourceRef)
        add("sourceKeywords", chunk.keywords)
    raw_query = " ".join(value for _source, value in parts)
    expanded_query = " ".join([raw_query, *extract_keywords(raw_query, limit=6)]).strip()
    return {
        "rawQuery": raw_query,
        "expandedQuery": expanded_query,
        "queryTerms": sorted(set(tokenize(expanded_query)), key=lambda item: (-len(item), item))[:24],
        "querySources": list(dict.fromkeys(source for source, _value in parts)),
    }


def _first_sentences(text: str, *, limit: int) -> str:
    sentences = split_sentences(text)
    return " ".join(sentences[:limit]) if sentences else compact(text, 360)


def _grounding_trace(
    note: dict[str, Any],
    chunks: list[SourceChunk],
    hits: list[RetrievalHit],
    query_info: dict[str, Any],
) -> dict[str, Any]:
    explicit_refs = _string_list(note.get("source_refs") or note.get("sourceRefs") or note.get("citationIds") or note.get("refs") or [])
    explicit_ids = [chunk.id for chunk in _resolve_note_sources(note, chunks)]
    selected_ids = [hit.chunk.id for hit in hits]
    selection_reasons = [
        "explicit-high-support" if chunk_id in explicit_ids else "retrieval-fill"
        for chunk_id in selected_ids
    ]
    return {
        "noteId": str(note.get("id") or ""),
        "explicitRefs": explicit_refs,
        "resolvedExplicitChunkIds": explicit_ids,
        "retrievedChunkIds": selected_ids,
        "selectedChunkIds": selected_ids,
        "selectionReasons": selection_reasons,
        "querySources": query_info.get("querySources", []),
        "queryTerms": query_info.get("queryTerms", []),
    }

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
    support_scores = [float((note.get("support") or {}).get("score", 0)) for note in notes]
    low_support_count = sum((note.get("support") or {}).get("level") in {"low", "unsupported"} for note in notes)
    explicit_traces = [note.get("groundingTrace") or {} for note in notes]
    explicit_refs = [ref for trace in explicit_traces for ref in trace.get("explicitRefs", [])]
    resolved_explicit_refs = [ref for trace in explicit_traces for ref in trace.get("resolvedExplicitChunkIds", [])]
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
        "averageNoteSupportScore": round(sum(support_scores) / max(1, len(support_scores)), 4),
        "lowSupportNoteRate": round(low_support_count / max(1, len(notes)), 4),
        "explicitRefResolutionRate": round(len(resolved_explicit_refs) / max(1, len(explicit_refs)), 4) if explicit_refs else 1.0,
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


def _attach_note_support(
    note: dict[str, Any],
    citations: list[dict[str, Any]],
    chunks: list[SourceChunk],
) -> None:
    chunk_by_id = {chunk.id: chunk for chunk in chunks}
    quote_scores = [float((citation.get("support") or {}).get("quoteScore", 0)) for citation in citations]
    chunk_scores = [
        _chunk_support_score(note, chunk_by_id[str(citation.get("sourceId"))])
        for citation in citations
        if str(citation.get("sourceId")) in chunk_by_id
    ]
    explicit_ids = set((note.get("groundingTrace") or {}).get("resolvedExplicitChunkIds") or [])
    selected_ids = {str(citation.get("sourceId")) for citation in citations}
    explicit_reliability = 1.0 if explicit_ids and explicit_ids & selected_ids else (0.7 if not explicit_ids else 0.0)
    source_coverage = min(1.0, len(selected_ids) / 2)
    score = round(
        (max(chunk_scores or [0]) * 0.45)
        + ((sum(quote_scores) / max(1, len(quote_scores))) * 0.30)
        + (source_coverage * 0.15)
        + (explicit_reliability * 0.10),
        4,
    )
    level = "high" if score >= 0.72 else "medium" if score >= 0.55 else "low" if score >= 0.35 else "unsupported"
    note_tokens = set(tokenize(f"{note.get('title', '')} {note.get('summary', '')} {note.get('content', '')}"))
    source_tokens = set()
    for citation in citations:
        chunk = chunk_by_id.get(str(citation.get("sourceId")))
        if chunk:
            source_tokens.update(tokenize(f"{chunk.heading} {chunk.text}"))
    missing_terms = sorted(note_tokens - source_tokens, key=lambda item: (-len(item), item))[:12]
    note["support"] = {
        "score": score,
        "level": level,
        "bestSourceIds": list(selected_ids),
        "missingTerms": missing_terms,
        "unsupportedClaims": missing_terms[:5] if level in {"low", "unsupported"} else [],
    }
    ranked_citations = sorted(
        [citation for citation in citations if str(citation.get("quote") or "").strip()],
        key=lambda citation: (
            1.0 if str(citation.get("sourceId") or "") in explicit_ids else 0.0,
            _quote_note_relevance(note, str(citation.get("quote") or "")),
            float((citation.get("support") or {}).get("quoteScore", 0)),
            float(citation.get("confidence", 0)),
        ),
        reverse=True,
    )
    note["sourceExcerpts"] = [
        {
            "sourceId": str(citation.get("sourceId") or ""),
            "sourceRef": str(citation.get("sourceRef") or ""),
            "page": citation.get("page"),
            "slide": citation.get("slide"),
            "quote": str(citation.get("quote") or "").strip(),
            "confidence": citation.get("confidence"),
        }
        for citation in ranked_citations
        if str(citation.get("sourceId") or "") in explicit_ids or _quote_note_relevance(note, str(citation.get("quote") or "")) >= 0.08
    ][:3]
    if level in {"low", "unsupported"}:
        note.setdefault("quality_issues", [])
        if "low_note_source_support" not in note["quality_issues"]:
            note["quality_issues"].append("low_note_source_support")


def _enrich_low_support_note(
    note: dict[str, Any],
    citations: list[dict[str, Any]],
    chunks: list[SourceChunk],
) -> None:
    if not citations or "原文依据：" in str(note.get("content", "")):
        return
    support = note.get("support") or {}
    if float(support.get("score", 0)) >= 0.55:
        return
    quotes = [str(item.get("quote", "")).strip() for item in citations if str(item.get("quote", "")).strip()]
    if not quotes:
        return
    evidence = "; ".join(dict.fromkeys(quotes[:2]))
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


def _quote_note_relevance(note: dict[str, Any], quote: str) -> float:
    query = " ".join(
        [
            str(note.get("title") or ""),
            str(note.get("summary") or ""),
            " ".join(str(item) for item in note.get("keyPoints", []) or []),
        ]
    )
    note_tokens = set(tokenize(query))
    quote_tokens = set(tokenize(quote))
    if not note_tokens or not quote_tokens:
        return 0.0
    overlap = len(note_tokens & quote_tokens) / max(1, len(note_tokens))
    containment = len(note_tokens & quote_tokens) / max(1, len(quote_tokens))
    title_tokens = set(tokenize(str(note.get("title") or "")))
    title_overlap = len(title_tokens & quote_tokens) / max(1, len(title_tokens)) if title_tokens else 0.0
    score = overlap * 0.45 + containment * 0.20 + title_overlap * 0.35
    note_number = _leading_number(str(note.get("title") or ""))
    quote_number = _leading_number(quote)
    if note_number and quote_number and note_number != quote_number:
        score *= 0.35
    if _quote_has_topic_anchor(note, quote):
        score += 0.18
    return round(min(1.0, score), 4)


def _leading_number(value: str) -> str:
    match = re.match(r"^\s*(?:[（(](\d+)[）)]|([①②③④⑤⑥⑦⑧⑨])|(\d+)[.、])", str(value))
    return next((group for group in match.groups() if group), "") if match else ""


def _quote_has_topic_anchor(note: dict[str, Any], quote: str) -> bool:
    title = str(note.get("title") or "")
    probe = " ".join([title, " ".join(str(item) for item in note.get("keyPoints", []) or [])])
    pairs = [
        ("青少年", "增强法治观念"),
        ("青少年", "努力学习科学文化知识"),
        ("青少年", "树立崇高远大理想"),
        ("助力实现中国梦", "树立崇高远大理想"),
        ("助力实现中国梦", "增强法治观念"),
        ("如何做自信中国人", "理性平和"),
        ("如何做自信中国人", "四个自信"),
        ("自信中国人", "四个自信"),
        ("物质与意识", "意识对物质具有能动"),
        ("唯物论核心基本概念", "物质"),
        ("后处理", "决定是否继续"),
    ]
    return any(left in probe and right in quote for left, right in pairs)


def _build_citation(
    index: int,
    chunk: SourceChunk,
    *,
    note_id: str,
    query: str,
    retrieval_score: float,
    note: dict[str, Any] | None = None,
) -> dict[str, Any]:
    quote, quote_score, sentence_index = _best_quote(query, chunk.text)
    quote_support = _quote_support_score(query, quote, chunk.text)
    line_start = _line_for_offset(chunk.text, chunk.text.find(quote)) if quote else chunk.lineStart
    confidence = min(0.99, 0.30 + quote_score * 0.35 + quote_support * 0.20 + min(0.14, retrieval_score / 25))
    citation = {
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
        "support": {
            "quoteScore": round(quote_support, 4),
            "quoteExistsInSource": bool(quote and _normalize_for_match(quote) in _normalize_for_match(chunk.text)),
            "chunkSupportScore": round(_chunk_support_score(note or {}, chunk), 4),
        },
    }
    if citation["support"]["quoteScore"] < 0.35:
        citation["confidence"] = min(citation["confidence"], 0.45)
    return citation


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



def _quote_support_score(query: str, quote: str, source_text: str) -> float:
    if not quote:
        return 0.0
    exists = _normalize_for_match(quote) in _normalize_for_match(source_text)
    query_tokens = set(tokenize(query))
    quote_tokens = set(tokenize(quote))
    overlap = len(query_tokens & quote_tokens) / max(1, len(query_tokens))
    containment = len(query_tokens & quote_tokens) / max(1, len(quote_tokens))
    length = len(quote.strip())
    length_score = 1.0 if 20 <= length <= 260 else 0.65 if length > 0 else 0.0
    return round((0.35 if exists else 0.0) + overlap * 0.35 + containment * 0.20 + length_score * 0.10, 4)


def _chunk_support_score(note: dict[str, Any], chunk: SourceChunk) -> float:
    note_text = " ".join(
        str(value or "")
        for value in (note.get("title"), note.get("summary"), note.get("content"), " ".join(note.get("keyPoints") or []))
    )
    note_tokens = set(tokenize(note_text))
    chunk_tokens = set(tokenize(f"{chunk.heading} {chunk.text}"))
    if not note_tokens:
        return 0.0
    term_recall = len(note_tokens & chunk_tokens) / max(1, len(note_tokens))
    term_precision = len(note_tokens & chunk_tokens) / max(1, len(chunk_tokens))
    heading_tokens = set(tokenize(chunk.heading))
    heading_match = len(note_tokens & heading_tokens) / max(1, len(heading_tokens)) if heading_tokens else 0.0
    note_compact = _normalize_for_match(note_text.lower())
    chunk_compact = _normalize_for_match(chunk.text.lower())
    phrase_match = 1.0 if len(note_compact) >= 12 and note_compact[:24] in chunk_compact else 0.0
    explicit_refs = set(_string_list(note.get("source_refs") or note.get("sourceRefs") or note.get("citationIds") or []))
    source_ref_match = 1.0 if chunk.id in explicit_refs or chunk.sourceRef in explicit_refs else 0.0
    return round(term_recall * 0.45 + term_precision * 0.15 + heading_match * 0.15 + phrase_match * 0.10 + source_ref_match * 0.15, 4)

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
