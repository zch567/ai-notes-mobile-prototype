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
from .learning_units import clean_learning_title, is_good_note_title
from .learning_notes import enrich_learning_notes
from .schemas import SourceChunk
from .text_utils import compact, extract_keywords, normalize_learning_text, split_sentences


def build_agent_result(chunks: list[SourceChunk], *, input_path: Path | None = None) -> dict[str, Any]:
    selected = _representative_chunks(chunks)
    topic = _infer_topic(chunks)
    notes = []
    heading_counts = Counter(chunk.heading for chunk in selected if chunk.heading)
    used_titles: set[str] = set()
    hierarchy = _note_hierarchy_map(selected)
    for index, chunk in enumerate(selected, start=1):
        title = _note_title(chunk, index, repeated_heading=heading_counts[chunk.heading] > 1)
        if title in used_titles:
            title = f"{title}（{chunk.sourceRef}）"
        used_titles.add(title)
        relation = hierarchy.get(index - 1, {"parent": None, "level": 1})
        parent_idx = relation.get("parent")
        notes.append(
            {
                "id": f"note-{index}",
                "title": title,
                "content": _note_content(chunk),
                "summary": _note_content(chunk),
                "sourceRefs": [chunk.id],
                "source_refs": [chunk.id],
                "level": relation.get("level", 1),
                "parentId": f"note-{parent_idx + 1}" if isinstance(parent_idx, int) else None,
                "citationIds": [],
            }
        )
    notes = enrich_learning_notes(notes, chunks)
    notes = _reconstruct_note_hierarchy(notes)
    questions = _build_questions(notes)
    result: dict[str, Any] = {
        "id": f"rag-{uuid.uuid4().hex[:8]}",
        "topic": topic,
        "summary": f"已基于 {len(chunks)} 个可定位来源片段构建轻量 RAG 索引，并整理 {len(notes)} 个核心学习单元。",
        "keywords": extract_keywords(normalize_learning_text(" ".join(chunk.text for chunk in chunks)), limit=10),
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
    text = normalize_learning_text(chunk.text).strip()
    if len(text) < 40:
        return False
    heading = (chunk.heading or "").strip()
    if _is_course_container_chunk(heading, text):
        return False
    # Skip tiny list fragments such as standalone GPT-2/GPT-3 entries; they are
    # still available as sources and citations, but not as top-level notes.
    if len(text) < 80 and re.match(r"^\d+[.?]|^GPT-\d+$", heading, flags=re.I):
        return False
    return True


def _is_course_container_chunk(heading: str, text: str) -> bool:
    probe = f"{heading} {text}"
    has_container = any(token in probe for token in ["单元", "第八课", "第2框", "第二框", "和谐与梦想", "课程目录"])
    has_learning_signal = any(token in probe for token in ["定义", "概念", "特点", "原因", "方式", "步骤", "作用", "意义", "要求", "关系", "机制"])
    return has_container and not has_learning_signal and len(text) <= 120

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
    source_text = normalize_learning_text(chunk.text)
    heading = clean_learning_title(_clean_title(chunk.heading), source_text) if chunk.heading else ""
    if heading and is_good_note_title(heading, source_text) and not _looks_like_toc(heading) and not repeated_heading:
        return compact(heading, 42)
    sentences = split_sentences(source_text)
    if sentences:
        for sentence in sentences:
            candidate = sentence
            if repeated_heading and chunk.heading and candidate.startswith(chunk.heading):
                candidate = candidate[len(chunk.heading) :].strip()
            candidate = clean_learning_title(_clean_title(candidate), source_text)
            if candidate and candidate != heading and is_good_note_title(candidate, source_text):
                return compact(candidate, 42)
    return f"note-{index}"

def _clean_title(text: str) -> str:
    value = re.split(r"[•●▪▌❖]", text, maxsplit=1)[0]
    value = re.sub(r"^[\d一二三四五六七八九十、.．\s]+", "", value).strip()
    value = re.sub(r"^[•●▪▌❖]\s*", "", value)
    return value


def _note_content(chunk: SourceChunk) -> str:
    text = normalize_learning_text(chunk.text)
    sentences = split_sentences(text)
    if not sentences:
        return compact(text, 360)
    return compact(" ".join(sentences[:3]), 420)

def _note_hierarchy_map(chunks: list[SourceChunk]) -> dict[int, dict[str, Any]]:
    parents: dict[int, dict[str, Any]] = {}
    current_parent: int | None = None
    current_child: int | None = None
    for idx, chunk in enumerate(chunks):
        raw_heading = str(chunk.heading or "").strip()
        raw_text = normalize_learning_text(chunk.text)
        probe = f"{raw_heading}\n{raw_text}"
        if _is_parent_topic(raw_heading, raw_text):
            current_parent = idx
            current_child = None
            parents[idx] = {"parent": None, "level": 1}
            continue
        if _is_numbered_heading(raw_heading) or _is_numbered_heading(raw_text):
            current_child = idx
            parents[idx] = {"parent": current_parent, "level": 2 if current_parent is not None else 1}
            continue
        if current_child is not None and _is_explanatory_sentence(probe):
            parents[idx] = {"parent": current_child, "level": 3}
            continue
        parents[idx] = {"parent": current_parent, "level": 2 if current_parent is not None else 1}
    return parents


def _is_parent_topic(heading: str, text: str) -> bool:
    probe = f"{heading} {text}"
    title = heading.strip()
    if title.startswith(("这种方式", "该方式", "上述方式", "这类方式")):
        return False
    return any(token in probe for token in ["三种方式", "主要方式", "基本方式", "步骤", "原因", "表现", "做法", "功能", "组成", "分类", "类型"]) and not _is_numbered_heading(probe)


def _is_container_heading(value: str) -> bool:
    compacted = re.sub(r"\s+", "", value)
    return bool(re.search(r"^第[一二三四五六七八九十\d]+(单元|课|框)", compacted)) or (
        any(token in compacted for token in ["课程目录", "学习目标", "教学目标", "PPT模板"]) and len(compacted) <= 30
    )


def _is_numbered_heading(value: str) -> bool:
    return bool(re.match(r"^\s*([（(]\d+[）)]|\d+[.、]|[①②③④⑤⑥⑦⑧⑨⑩])", value))


def _is_explanatory_sentence(text: str) -> bool:
    value = normalize_learning_text(text).strip()
    if _is_parent_topic("", value) or _is_numbered_heading(value):
        return False
    return len(value) > 20


def _reconstruct_note_hierarchy(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Repair user-facing note hierarchy after enrichment normalizes fields."""
    result: list[dict[str, Any]] = []
    current_parent: dict[str, Any] | None = None
    current_child: dict[str, Any] | None = None
    for note in notes:
        title = str(note.get("title") or "").strip()
        content = str(note.get("content") or note.get("summary") or "")
        probe = f"{title} {content}"
        if _is_container_heading(title):
            continue
        if current_child and (title.startswith(("这种方式", "该方式", "上述方式", "这类方式")) or _is_explanatory_sentence(probe)):
            if title.startswith(("这种方式", "该方式", "上述方式", "这类方式")):
                note["title"] = _explanatory_note_title(current_child)
            note["level"] = 3
            note["parentId"] = current_child.get("id")
        elif _is_parent_topic(title, content):
            note["level"] = 1
            note["parentId"] = None
            current_parent = note
            current_child = None
        elif _is_numbered_heading(title):
            note["level"] = 2 if current_parent else 1
            note["parentId"] = current_parent.get("id") if current_parent else None
            current_child = note
        elif current_child and _is_explanatory_sentence(probe):
            note["level"] = 3
            note["parentId"] = current_child.get("id")
        elif current_parent:
            note["level"] = max(2, int(note.get("level") or 1))
            note["parentId"] = note.get("parentId") or current_parent.get("id")
        result.append(note)
    return result


def _explanatory_note_title(parent: dict[str, Any]) -> str:
    parent_title = str(parent.get("title") or "")
    if "周期挪用" in parent_title or "周期窃取" in parent_title:
        return "周期挪用的适用性说明"
    if "交替访问" in parent_title:
        return "交替访问的适用性说明"
    return "补充说明"


def _build_questions(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    difficulties = ["easy", "medium", "hard", "medium", "easy"]
    for index, note in enumerate(notes[:5], start=1):
        title = clean_learning_title(str(note.get("title") or f"note-{index}"), str(note.get("content") or ""))
        body = str(note.get("summary") or note.get("content") or "")
        q_type, question = _question_for_note(title, body)
        questions.append(
            {
                "id": f"q{index}",
                "type": q_type,
                "difficulty": difficulties[index - 1],
                "question": question,
                "options": [],
                "answer": compact(str(note.get("content") or note.get("summary") or ""), 160),
                "explanation": "\u7b54\u6848\u5e94\u4f9d\u636e\u5173\u8054\u7b14\u8bb0\u548c\u6765\u6e90\u7247\u6bb5\uff0c\u4f18\u5148\u590d\u8ff0\u5173\u952e\u5b9a\u4e49\u3001\u6b65\u9aa4\u6216\u56e0\u679c\u5173\u7cfb\u3002",
                "relatedNoteId": note["id"],
                "citationIds": [],
            }
        )
    return questions


def _question_for_note(title: str, body: str) -> tuple[str, str]:
    probe = f"{title} {body}"
    if any(token in probe for token in ["\u6b65\u9aa4", "\u6d41\u7a0b", "\u7b97\u6cd5", "\u8bad\u7ec3", "\u9884\u6d4b", "\u5b9e\u73b0", "\u600e\u6837", "\u5982\u4f55"]):
        return "procedure", f"{title} \u7684\u5173\u952e\u6b65\u9aa4\u6216\u5904\u7406\u6d41\u7a0b\u662f\u4ec0\u4e48\uff1f"
    if any(token in probe for token in ["\u539f\u56e0", "\u4e3a\u4ec0\u4e48", "\u5f71\u54cd", "\u5bfc\u81f4", "\u610f\u4e49", "\u4f5c\u7528"]):
        return "cause_effect", f"\u4e3a\u4ec0\u4e48\u4f1a\u51fa\u73b0 {title}\uff1f\u5b83\u5e26\u6765\u4ec0\u4e48\u4f5c\u7528\u6216\u5f71\u54cd\uff1f"
    if any(token in probe for token in ["\u6bd4\u8f83", "\u5dee\u5f02", "\u533a\u522b", "v.s", "vs", "\u4e0e", "\u751f\u6210\u5f0f", "\u5224\u51b3\u5f0f"]):
        return "comparison", f"\u6bd4\u8f83 {title} \u4e2d\u76f8\u5173\u6982\u5ff5\u7684\u5dee\u5f02\uff0c\u5e76\u8bf4\u660e\u5224\u65ad\u4f9d\u636e\u3002"
    if any(token in probe for token in ["\u5e94\u7528", "\u573a\u666f", "\u4f8b", "\u4efb\u52a1"]):
        return "application", f"\u7ed9\u5b9a\u4e00\u4e2a\u5b9e\u9645\u573a\u666f\u65f6\uff0c\u5982\u4f55\u5e94\u7528 {title} \u89e3\u51b3\u95ee\u9898\uff1f"
    return "concept_explanation", f"\u4ec0\u4e48\u662f {title}\uff1f\u8bf7\u7528\u8d44\u6599\u4e2d\u7684\u5173\u952e\u8868\u8ff0\u8bf4\u660e\u3002"

def _build_outline(chunks: list[SourceChunk]) -> list[dict[str, Any]]:
    outline: list[dict[str, Any]] = []
    seen: set[str] = set()
    for chunk in chunks:
        cleaned_text = normalize_learning_text(chunk.text)
        title = clean_learning_title(chunk.heading or cleaned_text, cleaned_text)
        if not is_good_note_title(title, cleaned_text):
            title = chunk.sourceRef
        key = f"{title}|{chunk.sourceRef}"
        if key in seen:
            continue
        seen.add(key)
        outline.append(
            {
                "id": f"section-{len(outline) + 1}",
                "title": compact(title, 60),
                "brief": compact(cleaned_text, 100),
                "sourceRefs": [chunk.sourceRef],
            }
        )
        if len(outline) >= 12:
            break
    return outline


def _build_mind_map(topic: str, notes: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = [{"id": "root", "label": topic, "desc": "核心主题", "detail": topic, "x": 50, "y": 45}]
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
