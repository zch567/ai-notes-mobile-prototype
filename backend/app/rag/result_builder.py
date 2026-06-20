from __future__ import annotations

import re
import math
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .enrichment import chunk_structure_overview
from .grounding import ground_result
from .learning_notes import enrich_learning_notes
from .schemas import SourceChunk
from .text_utils import compact, extract_keywords, split_sentences


def build_agent_result(chunks: list[SourceChunk], *, input_path: Path | None = None) -> dict[str, Any]:
    selected = _representative_chunks(chunks)
    topic = _infer_topic(chunks)
    notes = []
    heading_counts = Counter(chunk.heading for chunk in selected if chunk.heading)
    used_titles: set[str] = set()
    for index, chunk in enumerate(selected, start=1):
        title = _note_title(chunk, index, repeated_heading=heading_counts[chunk.heading] > 1)
        if title in used_titles:
            title = f"{title}（{chunk.sourceRef}）"
        used_titles.add(title)
        notes.append(
            {
                "id": f"note-{index}",
                "title": title,
                "content": _note_content(chunk),
                "summary": _note_content(chunk),
                "sourceRefs": [chunk.id],
                "source_refs": [chunk.id],
                "level": 1,
                "parentId": None,
                "citationIds": [],
            }
        )
    notes = enrich_learning_notes(notes, chunks)
    questions = _build_questions(notes)
    result: dict[str, Any] = {
        "id": f"rag-{uuid.uuid4().hex[:8]}",
        "topic": topic,
        "summary": f"已基于 {len(chunks)} 个可定位来源片段构建轻量 RAG 索引，并整理 {len(notes)} 个核心学习单元。",
        "keywords": extract_keywords(" ".join(chunk.text for chunk in chunks), limit=10),
        "outline": _build_outline(chunks),
        "agentStages": [
            {"id": "parse", "label": "Document Parsing", "text": f"统一抽取得到 {len(chunks)} 个可定位片段。"},
            {"id": "chunk", "label": "RAGFlow-style Structure Chunking", "text": "按页/幻灯片/段落边界构建层级 parentId、关键词和全局唯一 chunk ID。"},
            {"id": "retrieve", "label": "Quivr-style Hybrid Retrieval", "text": "使用 BM25、短语匹配、标题加权、查询扩展、来源多样化和邻近上下文证据包召回。"},
            {"id": "citation", "label": "Citation Grounding", "text": "为笔记和复习题绑定来源片段、原文 quote 与细粒度位置。"},
        ],
        "sources": [],
        "notes": notes,
        "citations": [],
        "mindMap": _build_mind_map(topic, notes),
        "review": {
            "questions": questions,
            "masteryScore": 0,
            "weakPoints": [note["title"] for note in notes[-2:]],
            "recommendations": [
                "先按笔记后的引用回看原文，确认每个结论的资料依据。",
                "优先复述枢纽知识点，再用应用题检查是否真正理解。",
                "对低置信度引用进行人工复核，必要时调整检索词。",
            ],
        },
        "warnings": [],
        "_meta": {
            "inputFile": str(input_path) if input_path else "",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "chunkCount": len(chunks),
            "ragVersion": "ragflow-quivr-inspired-v2",
            "ragStructure": chunk_structure_overview(chunks),
            "provider": "deterministic-grounded-builder",
        },
    }
    return ground_result(result, chunks)


def _representative_chunks(
    chunks: list[SourceChunk],
    *,
    min_notes: int = 8,
    max_notes: int = 24,
    keyword_coverage: float = 0.88,
) -> list[SourceChunk]:
    candidates = [chunk for chunk in chunks if _is_learning_chunk(chunk)]
    candidates = candidates or [chunk for chunk in chunks if not _looks_like_toc(chunk.text)] or chunks
    if len(candidates) <= min_notes:
        return candidates

    corpus_keywords = set(extract_keywords(" ".join(chunk.text for chunk in candidates), limit=32))
    covered: set[str] = set()
    selected: list[SourceChunk] = []
    low_gain_streak = 0

    for chunk in candidates:
        chunk_keywords = set(extract_keywords(f"{chunk.heading} {chunk.text}", limit=12))
        new_keywords = chunk_keywords - covered
        gain = len(new_keywords)
        selected.append(chunk)
        covered.update(chunk_keywords)

        if len(selected) < min_notes:
            continue
        if gain <= 1:
            low_gain_streak += 1
        else:
            low_gain_streak = 0
        coverage = len(covered & corpus_keywords) / max(1, len(corpus_keywords))
        if coverage >= keyword_coverage and low_gain_streak >= 3:
            break
        if len(selected) >= max_notes:
            break
    return selected


def _is_learning_chunk(chunk: SourceChunk) -> bool:
    if _looks_like_toc(chunk.text):
        return False
    text = chunk.text.strip()
    if len(text) < 40:
        return False
    heading = (chunk.heading or "").strip()
    # Skip tiny list fragments such as standalone GPT-2/GPT-3 entries; they are
    # still available as sources and citations, but not as top-level notes.
    if len(text) < 80 and re.match(r"^\d+[.、]|^GPT-\d+$", heading, flags=re.I):
        return False
    return True
def _looks_like_toc(text: str) -> bool:
    value = re.sub(r"\s+", "", text)
    return value.startswith("目录") and len(value) < 250


def _infer_topic(chunks: list[SourceChunk]) -> str:
    if not chunks:
        return "学习资料"
    stem = Path(chunks[0].fileName).stem
    headings = [chunk.heading for chunk in chunks if chunk.heading and len(chunk.heading) <= 50]
    heading = headings[0] if headings else ""
    generic_stems = {"项目汇报", "学术汇报", "课程资料", "学习资料", "document", "presentation"}
    return heading if stem.lower() in generic_stems and heading else stem


def _note_title(chunk: SourceChunk, index: int, *, repeated_heading: bool = False) -> str:
    if chunk.heading and not _looks_like_toc(chunk.heading) and not repeated_heading:
        return compact(_clean_title(chunk.heading), 42)
    sentences = split_sentences(chunk.text)
    if sentences:
        for sentence in sentences:
            candidate = sentence
            if repeated_heading and chunk.heading and candidate.startswith(chunk.heading):
                candidate = candidate[len(chunk.heading) :].strip()
            candidate = _clean_title(candidate)
            if candidate and candidate != _clean_title(chunk.heading):
                return compact(candidate, 42)
    return f"知识点 {index}"


def _clean_title(text: str) -> str:
    value = re.split(r"[•●▪▌❖]", text, maxsplit=1)[0]
    value = re.sub(r"^[\d一二三四五六七八九十、.．\s]+", "", value).strip()
    value = re.sub(r"^[•●▪▌❖]\s*", "", value)
    return value


def _note_content(chunk: SourceChunk) -> str:
    sentences = split_sentences(chunk.text)
    if not sentences:
        return compact(chunk.text, 360)
    return compact(" ".join(sentences[:3]), 420)


def _build_questions(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    difficulties = ["easy", "medium", "hard", "medium", "easy"]
    types = ["concept_explanation", "short_answer", "application", "judgement", "short_answer"]
    for index, note in enumerate(notes[:5], start=1):
        questions.append(
            {
                "id": f"q{index}",
                "type": types[index - 1],
                "difficulty": difficulties[index - 1],
                "question": f"请解释“{note['title']}”的核心含义，并指出它在资料中的作用。",
                "options": [],
                "answer": compact(note["content"], 160),
                "explanation": "答案应严格依据关联笔记及其来源片段。",
                "relatedNoteId": note["id"],
                "citationIds": [],
            }
        )
    return questions


def _build_outline(chunks: list[SourceChunk]) -> list[dict[str, Any]]:
    outline: list[dict[str, Any]] = []
    seen: set[str] = set()
    for chunk in chunks:
        title = chunk.heading or chunk.sourceRef
        key = f"{title}|{chunk.sourceRef}"
        if key in seen:
            continue
        seen.add(key)
        outline.append(
            {
                "id": f"section-{len(outline) + 1}",
                "title": compact(title, 60),
                "brief": compact(chunk.text, 100),
                "sourceRefs": [chunk.sourceRef],
            }
        )
        if len(outline) >= 12:
            break
    return outline


def _build_mind_map(topic: str, notes: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = [{"id": "root", "label": topic, "desc": "????", "detail": topic, "x": 50, "y": 45}]
    edges = []
    total = max(1, len(notes))
    for index, note in enumerate(notes):
        angle = -math.pi / 2 + (2 * math.pi * index / total)
        x = round(50 + 36 * math.cos(angle), 2)
        y = round(48 + 34 * math.sin(angle), 2)
        nodes.append(
            {
                "id": note["id"],
                "label": compact(note["title"], 24),
                "desc": compact(note.get("summary") or note.get("content", ""), 52),
                "detail": note.get("summary") or note.get("content", ""),
                "x": x,
                "y": y,
            }
        )
        edges.append({"from": "root", "to": note["id"]})
    return {"nodes": nodes, "edges": edges}
