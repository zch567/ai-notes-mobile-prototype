from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from .enrichment import build_evidence_packs, expand_query
from .schemas import SourceChunk
from .text_utils import tokenize


@dataclass
class RetrievalHit:
    chunk: SourceChunk
    score: float
    bm25: float
    phrase: float
    heading: float
    matched_terms: list[str]
    expanded_query: str = ""
    evidence: dict[str, Any] | None = None

    def to_dict(self) -> dict:
        item = {
            "sourceId": self.chunk.id,
            "sourceRef": self.chunk.sourceRef,
            "title": self.chunk.title,
            "chunkIndex": self.chunk.chunkIndex,
            "chunkHeading": self.chunk.heading,
            "score": round(self.score, 6),
            "bm25": round(self.bm25, 6),
            "phrase": round(self.phrase, 6),
            "heading": round(self.heading, 6),
            "matchedTerms": self.matched_terms,
            "expandedQuery": self.expanded_query,
        }
        if self.evidence:
            item["evidence"] = self.evidence
        return item


class HybridRetriever:
    """Dependency-free BM25 + phrase/heading boost retriever."""

    def __init__(self, chunks: list[SourceChunk], *, k1: float = 1.5, b: float = 0.75) -> None:
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.docs = [tokenize(f"{chunk.heading} {chunk.text}") for chunk in chunks]
        self.counters = [Counter(tokens) for tokens in self.docs]
        self.avg_len = sum(map(len, self.docs)) / max(1, len(self.docs))
        self.df: Counter[str] = Counter()
        self.inverted: dict[str, set[int]] = defaultdict(set)
        self.heading_token_sets = [set(tokenize(chunk.heading)) for chunk in chunks]
        self.chunk_compacts = ["".join(chunk.text.lower().split()) for chunk in chunks]
        for index, tokens in enumerate(self.docs):
            unique_tokens = set(tokens)
            self.df.update(unique_tokens)
            for token in unique_tokens:
                self.inverted[token].add(index)

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        diversify: bool = True,
        expand: bool = True,
        include_context: bool = False,
    ) -> list[RetrievalHit]:
        expanded_query = expand_query(query, self.chunks) if expand else query
        query_tokens = tokenize(expanded_query)
        if not query_tokens or not self.chunks:
            return []
        query_counter = Counter(query_tokens)
        hits: list[RetrievalHit] = []
        query_compact = "".join(expanded_query.lower().split())
        candidate_indexes = self._candidate_indexes(query_tokens)
        query_token_set = set(query_tokens)
        for index in candidate_indexes:
            chunk = self.chunks[index]
            tokens = self.docs[index]
            counter = self.counters[index]
            bm25 = self._bm25(query_counter, tokens, counter)
            phrase = _phrase_score(query_compact, self.chunk_compacts[index])
            heading = len(query_token_set & self.heading_token_sets[index]) / max(1, len(query_token_set))
            matched = sorted(query_token_set & set(tokens), key=lambda item: (-query_counter[item], -len(item)))[:10]
            score = bm25 + phrase * 2.0 + heading * 1.5
            if score > 0:
                hits.append(RetrievalHit(chunk, score, bm25, phrase, heading, matched, expanded_query=expanded_query))
        hits.sort(key=lambda hit: (-hit.score, hit.chunk.chunkIndex))
        selected = _diversify(hits, top_k) if diversify else hits[:top_k]
        return _attach_context(selected, self.chunks, expanded_query) if include_context else selected

    def _candidate_indexes(self, query_tokens: list[str]) -> list[int]:
        candidates: set[int] = set()
        for token in set(query_tokens):
            candidates.update(self.inverted.get(token, set()))
        if not candidates:
            return list(range(len(self.chunks)))
        return sorted(candidates, key=lambda index: self.chunks[index].chunkIndex)

    def _bm25(self, query: Counter[str], tokens: list[str], counter: Counter[str]) -> float:
        score = 0.0
        doc_len = len(tokens)
        total = len(self.docs)
        for term, query_freq in query.items():
            frequency = counter.get(term, 0)
            if not frequency:
                continue
            df = self.df.get(term, 0)
            idf = math.log(1 + (total - df + 0.5) / (df + 0.5))
            denom = frequency + self.k1 * (1 - self.b + self.b * doc_len / max(1, self.avg_len))
            score += idf * (frequency * (self.k1 + 1) / denom) * min(2, query_freq)
        return score


def _phrase_score(query: str, text: str) -> float:
    if not query or not text:
        return 0.0
    if len(query) >= 6 and query in text:
        return 1.0
    width = min(12, max(4, len(query) // 3))
    phrases = {query[index : index + width] for index in range(0, max(1, len(query) - width + 1), width)}
    return sum(1 for phrase in phrases if phrase and phrase in text) / max(1, len(phrases))


def _diversify(hits: list[RetrievalHit], top_k: int) -> list[RetrievalHit]:
    selected: list[RetrievalHit] = []
    source_ref_counts: Counter[str] = Counter()
    for hit in hits:
        penalty = 0.72 ** source_ref_counts[hit.chunk.sourceRef]
        adjusted = hit.score * penalty
        if adjusted <= 0:
            continue
        selected.append(
            RetrievalHit(
                hit.chunk,
                adjusted,
                hit.bm25,
                hit.phrase,
                hit.heading,
                hit.matched_terms,
                hit.expanded_query,
                hit.evidence,
            )
        )
        source_ref_counts[hit.chunk.sourceRef] += 1
        if len(selected) >= top_k:
            break
    return selected


def _attach_context(hits: list[RetrievalHit], chunks: list[SourceChunk], query: str) -> list[RetrievalHit]:
    packs = build_evidence_packs(chunks, [hit.chunk.id for hit in hits], query)
    evidence_by_id = {pack.focus.id: pack.to_dict() for pack in packs}
    return [
        RetrievalHit(
            hit.chunk,
            hit.score,
            hit.bm25,
            hit.phrase,
            hit.heading,
            hit.matched_terms,
            hit.expanded_query,
            evidence_by_id.get(hit.chunk.id),
        )
        for hit in hits
    ]
