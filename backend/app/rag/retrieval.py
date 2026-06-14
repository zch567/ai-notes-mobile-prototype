from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

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

    def to_dict(self) -> dict:
        return {
            "sourceId": self.chunk.id,
            "sourceRef": self.chunk.sourceRef,
            "title": self.chunk.title,
            "score": round(self.score, 6),
            "bm25": round(self.bm25, 6),
            "phrase": round(self.phrase, 6),
            "heading": round(self.heading, 6),
            "matchedTerms": self.matched_terms,
        }


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
        for tokens in self.docs:
            self.df.update(set(tokens))

    def retrieve(self, query: str, *, top_k: int = 5, diversify: bool = True) -> list[RetrievalHit]:
        query_tokens = tokenize(query)
        if not query_tokens or not self.chunks:
            return []
        query_counter = Counter(query_tokens)
        hits: list[RetrievalHit] = []
        query_compact = "".join(query.lower().split())
        for chunk, tokens, counter in zip(self.chunks, self.docs, self.counters):
            bm25 = self._bm25(query_counter, tokens, counter)
            chunk_compact = "".join(chunk.text.lower().split())
            phrase = _phrase_score(query_compact, chunk_compact)
            heading_tokens = set(tokenize(chunk.heading))
            heading = len(set(query_tokens) & heading_tokens) / max(1, len(set(query_tokens)))
            matched = sorted(set(query_tokens) & set(tokens), key=lambda item: (-query_counter[item], -len(item)))[:10]
            score = bm25 + phrase * 2.0 + heading * 1.5
            if score > 0:
                hits.append(RetrievalHit(chunk, score, bm25, phrase, heading, matched))
        hits.sort(key=lambda hit: (-hit.score, hit.chunk.chunkIndex))
        return _diversify(hits, top_k) if diversify else hits[:top_k]

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
            )
        )
        source_ref_counts[hit.chunk.sourceRef] += 1
        if len(selected) >= top_k:
            break
    return selected
