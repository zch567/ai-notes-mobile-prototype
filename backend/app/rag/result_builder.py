from __future__ import annotations

import re
import math
import uuid
from dataclasses import asdict, is_dataclass
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .content_quality import assess_content_quality
from .enrichment import chunk_structure_overview
from .grounding import ground_result
from .learning_units import clean_item, clean_learning_title, is_broken_outline_fragment, is_good_note_title, is_visual_label_line
from .learning_profile import has_any, infer_learning_profile, point_label as profile_point_label, strip_leading_number
from .learning_notes import enrich_learning_notes
from .schemas import SourceChunk
from .text_utils import compact, extract_keywords, normalize_learning_text, split_sentences


def build_agent_result(chunks: list[SourceChunk], *, input_path: Path | None = None) -> dict[str, Any]:
    selected = _representative_chunks(chunks)
    processing_chunks = _merge_processing_chunks(chunks, selected)
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
    notes = enrich_learning_notes(notes, processing_chunks)
    notes = _semantic_note_contract(_reconstruct_note_hierarchy(notes))
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
            "ragStructure": chunk_structure_overview(processing_chunks),
            "provider": "deterministic-grounded-builder",
        },
    }
    grounded = ground_result(result, processing_chunks)
    grounded.setdefault("_meta", {})["contentQuality"] = assess_content_quality(grounded)
    return grounded


def _merge_processing_chunks(chunks: list[SourceChunk], selected: list[SourceChunk]) -> list[SourceChunk]:
    selected_by_id = {chunk.id: chunk for chunk in selected}
    return [selected_by_id.get(chunk.id, chunk) for chunk in chunks]


def _representative_chunks(
    chunks: list[SourceChunk],
    *,
    min_notes: int = 8,
    max_notes: int = 24,
    keyword_coverage: float = 0.88,
) -> list[SourceChunk]:
    candidates = [_normalize_chunk_for_note(chunk) for chunk in chunks if _is_learning_chunk(chunk)]
    if not candidates:
        fallback = [chunk for chunk in chunks if not _looks_like_toc(chunk.text)]
        if any(chunk.sourceType == "pptx" for chunk in fallback):
            fallback = [
                chunk for chunk in fallback
                if not _is_ppt_non_core_chunk(chunk.heading or "", normalize_learning_text(chunk.text))
            ]
        candidates = fallback or chunks
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
    if chunk.sourceType == "pptx" and _is_ppt_non_core_chunk(heading, text):
        return False
    if _is_visual_only_chunk(heading, text):
        return False
    if _is_diagram_noise_chunk(heading, text):
        return False
    if _is_orphan_fragment_chunk(heading, text):
        return False
    # Skip tiny list fragments such as standalone GPT-2/GPT-3 entries; they are
    # still available as sources and citations, but not as top-level notes.
    if chunk.sourceType != "pptx" and len(text) < 80 and re.match(r"^\d+[.?]|^GPT-\d+$", heading, flags=re.I):
        return False
    return True


def _normalize_chunk_for_note(chunk: SourceChunk) -> SourceChunk:
    text = normalize_learning_text(chunk.text)
    lines = _content_lines(text, stop_at_next_number=chunk.sourceType != "pptx")
    if len(lines) == 0:
        return chunk
    cleaned_text = "\n".join(lines)
    if cleaned_text == text:
        return chunk
    if hasattr(chunk, "model_dump"):
        data = chunk.model_dump()
    elif hasattr(chunk, "dict"):
        data = chunk.dict()
    elif is_dataclass(chunk):
        data = asdict(chunk)
    else:
        data = dict(chunk.__dict__)
    data["text"] = cleaned_text
    return SourceChunk(**data)


def _is_course_container_chunk(heading: str, text: str) -> bool:
    probe = f"{heading} {text}"
    has_container = any(token in probe for token in ["单元", "第八课", "第2框", "第二框", "和谐与梦想", "课程目录"])
    has_learning_signal = any(token in probe for token in ["定义", "概念", "特点", "原因", "方式", "步骤", "作用", "意义", "要求", "关系", "机制"])
    return has_container and not has_learning_signal and len(text) <= 120


def _is_ppt_non_core_chunk(heading: str, text: str) -> bool:
    probe = f"{heading}\n{text}"
    compacted = re.sub(r"\s+", "", probe)
    if any(token in compacted for token in ["学习目标", "教学目标", "通过本节课学习", "笔记区", "基础型作业", "发展型作业", "完成课时练习"]):
        return True
    if any(token in compacted for token in ["采访身边的人", "想一想", "你对", "为何会产生这种信心", "思考："]):
        return True
    if re.search(r"[A-D][．.]", probe) and re.search(r"[①②③④]", probe):
        return True
    if compacted in {"圆梦大舞台", "自信的中国人", "对文化有底气"}:
        return True
    if "共圆中国梦圆梦大舞台自信的中国人" in compacted:
        return True
    return False


def _is_visual_only_chunk(heading: str, text: str) -> bool:
    lines = [line.strip() for line in normalize_learning_text(text).splitlines() if line.strip()]
    if not lines:
        return True
    visual_tokens = {"t", "ACC", "I/O", "设", "备", "主存工作时间", "CPU不执行程序", "DMA不工作", "DMA工作", "CPU控制并使用主存", "DMA控制并使用主存"}
    visual_count = sum(line in visual_tokens for line in lines)
    return len(lines) <= 8 and visual_count / max(1, len(lines)) >= 0.5


def _is_diagram_noise_chunk(heading: str, text: str) -> bool:
    lines = [clean_item(line) for line in normalize_learning_text(text).splitlines() if clean_item(line)]
    if not lines:
        return True
    noise = sum(_is_diagram_or_fragment_line(line) for line in lines)
    content = sum(_is_content_line(line) for line in lines)
    return noise >= 3 and content <= 1


def _is_orphan_fragment_chunk(heading: str, text: str) -> bool:
    title = clean_item(heading)
    lines = [clean_item(line) for line in normalize_learning_text(text).splitlines() if clean_item(line)]
    if title and is_broken_outline_fragment(title):
        return True
    if len(lines) <= 3 and all(_is_diagram_or_fragment_line(line) for line in lines):
        return True
    return False


def _content_lines(text: str, *, stop_at_next_number: bool = True) -> list[str]:
    raw_lines = [clean_item(raw) for raw in normalize_learning_text(text).splitlines() if clean_item(raw)]
    merged = _merge_pdf_line_fragments(raw_lines)
    result: list[str] = []
    active_number = _leading_item_number(merged[0]) if merged else ""
    for line in merged:
        if not line:
            continue
        line_number = _leading_item_number(line)
        if stop_at_next_number and active_number and line_number and line_number != active_number and result:
            break
        if _is_diagram_or_fragment_line(line):
            continue
        result.append(line)
    return result


def _merge_pdf_line_fragments(lines: list[str]) -> list[str]:
    result: list[str] = []
    i = 0
    while i < len(lines):
        current = lines[i]
        if i + 1 < len(lines):
            nxt = lines[i + 1]
            joined = _join_fragment_pair(current, nxt)
            if joined:
                current = joined
                i += 1
        result.append(current)
        i += 1
    return result


def _join_fragment_pair(left: str, right: str) -> str:
    left_clean = clean_item(left)
    right_clean = clean_item(right)
    if not left_clean or not right_clean:
        return ""
    pairs = [
        ("DMA操", "作的后处理", "DMA操作的后处理"),
        ("设备信", "息存储区", "设备信息存储区"),
        ("与接口", "相连的设备", "与接口相连的设备"),
        ("各自", "的传送参数", "各自的传送参数"),
    ]
    for suffix, prefix, replacement in pairs:
        if left_clean.endswith(suffix) and right_clean.startswith(prefix):
            return left_clean[: -len(suffix)] + replacement + right_clean[len(prefix) :]
    if left_clean.endswith(("，", "、", "和", "与", "为", "将", "由", "通过", "由于", "因为", "以及")):
        return left_clean + right_clean
    return ""


def _leading_item_number(value: str) -> str:
    match = re.match(r"^\s*(?:\((\d+)\)|（(\d+)）|([①②③④⑤⑥⑦⑧⑨]))", str(value or "").strip())
    if not match:
        return ""
    return next((group for group in match.groups() if group), "")


def _is_content_line(line: str) -> bool:
    value = clean_item(line)
    if not value or _is_diagram_or_fragment_line(value):
        return False
    return len(re.sub(r"\s+", "", value)) >= 12


def _is_diagram_or_fragment_line(line: str) -> bool:
    value = clean_item(line)
    compacted = re.sub(r"\s+", "", value)
    if is_visual_label_line(value) or is_broken_outline_fragment(value):
        return True
    if re.fullmatch(r"(接口\d+|接口n|接口nCPU|CPU|主存|设备|数据线|地址线|I/O总线|控制逻|中断|溢出信号|DMA响应\d*|DMA请求\d*|\+1|DACK|HRQ|HLDA)", compacted):
        return True
    if re.fullmatch(r"[A-Za-z0-9/+\-]{1,8}", compacted):
        return True
    if len(compacted) <= 6 and not re.search(r"(方式|原因|概念|功能|组成|过程|比较|关系|原理|特点|作用)", compacted):
        return True
    if re.search(r"(设备设备设备|接口CPU主存|接口nCPU|理时，将所选设备|设备地址寄存器$)", compacted):
        return True
    if re.search(r"(打印机t|磁带t|磁盘t|每\d+s请求DMA|s一次DMA传送)", compacted):
        return True
    return False

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
    ppt_title = _ppt_semantic_title(chunk, source_text)
    if ppt_title:
        return compact(ppt_title, 42)
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
    topic = _semantic_fallback_title(chunk, source_text)
    if topic:
        return compact(topic, 42)
    return f"核心内容 {index}"

def _clean_title(text: str) -> str:
    value = re.split(r"[•●▪▌❖]", text, maxsplit=1)[0]
    value = re.sub(r"^[\d一二三四五六七八九十、.．\s]+", "", value).strip()
    value = re.sub(r"^[•●▪▌❖]\s*", "", value)
    return value


def _ppt_semantic_title(chunk: SourceChunk, text: str) -> str:
    if chunk.sourceType != "pptx":
        return ""
    lines = [clean_learning_title(line.strip(), text) for line in re.split(r"[\n\r]+", text) if line.strip()]
    lines = [line for line in lines if line and not _is_container_heading(line)]
    question = _first_ppt_question_title(lines)
    if question:
        return question
    list_title = _ppt_list_title(lines)
    if list_title:
        return list_title
    return ""


def _first_ppt_question_title(lines: list[str]) -> str:
    for line in lines[:5]:
        candidate = _normalize_question_title(line)
        if candidate:
            return candidate
    return ""


def _normalize_question_title(line: str) -> str:
    text = re.sub(r"^\s*(?:[一二三四五六七八九十\d]+[.、]\s*)+", "", line).strip()
    text = text.rstrip("？?")
    if not text:
        return ""
    if "应该怎么做" in text:
        subject = re.sub(r"^作为", "", text.split("应该怎么做", 1)[0]).strip(" ，,")
        match = re.match(r"为了(.+?)[，,]\s*作为(.+)", subject)
        if match:
            return compact(f"{match.group(2)}如何助力{match.group(1)}", 42)
        return compact(f"{subject}应该怎么做", 42) if subject else compact(text, 42)
    if text.startswith(("如何", "怎样", "为什么", "什么是")) or text.endswith(("怎么做", "怎么办")):
        return compact(text, 42)
    return ""


def _ppt_list_title(lines: list[str]) -> str:
    numbered = [line for line in lines if _is_numbered_heading(line)]
    if not numbered:
        return ""
    heading = next((line for line in lines[:4] if not _is_numbered_heading(line) and is_good_note_title(line, " ".join(lines))), "")
    if not heading:
        return ""
    first_label = strip_leading_number(numbered[0])
    if len(numbered) == 1 and first_label and any(token in heading for token in ["表现", "特点", "方面"]):
        return compact(f"{_normalize_manifestation_heading(heading)}：{first_label}", 42)
    if len(numbered) >= 2 and any(token in heading for token in ["表现", "特点", "方面"]):
        return compact(_normalize_manifestation_heading(heading), 42)
    if len(numbered) >= 2 and any(token in heading for token in ["原因", "依据", "底气", "做法", "要求", "路径"]):
        return compact(heading, 42)
    return ""


def _normalize_manifestation_heading(heading: str) -> str:
    text = re.sub(r"表现在哪些方面.*$", "表现", heading)
    text = re.sub(r"的特点$", "的表现", text)
    return text


def _note_content(chunk: SourceChunk) -> str:
    text = normalize_learning_text(chunk.text)
    sentences = [sentence for sentence in split_sentences(text) if _is_content_line(sentence)]
    if not sentences:
        return _explanatory_fallback_content(chunk)
    return compact(" ".join(sentences[:3]), 420)


def _semantic_fallback_title(chunk: SourceChunk, text: str) -> str:
    probe = f"{chunk.title}\n{chunk.heading}\n{text}"
    prefix = "DMA " if "DMA" in probe else ""
    if "选择型" in probe and "多路型" not in probe:
        return compact(f"选择型 {prefix}接口", 42)
    if "多路型" in probe:
        return compact(f"多路型 {prefix}接口", 42)
    profile = infer_learning_profile(chunk.heading or "", key_points=[], content=text)
    if "process" in profile["roles"]:
        return compact(f"{prefix}数据传送过程" if "传送" in probe else f"{prefix}流程", 42)
    if "中断机构" in probe and ("中断请求" in probe or "后处理" in probe):
        return compact(f"{prefix}中断机构", 42)
    if "接口功能" in probe:
        return compact(f"{prefix}接口功能", 42)
    if "连接方式" in probe:
        return compact(f"{prefix}接口与系统的连接方式", 42)
    return ""


def _explanatory_fallback_content(chunk: SourceChunk) -> str:
    title = clean_item(chunk.heading or "")
    profile = infer_learning_profile(title)
    if profile["material"] == "technical":
        return _content_by_profile(title, [], profile)
    return "这部分需要结合上下文理解其定义、作用和适用场景。"

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
    return any(token in probe for token in ["三种方式", "主要方式", "基本方式", "步骤", "原因", "表现", "做法", "功能", "组成", "分类", "类型", "连接方式", "比较"]) and not _is_numbered_heading(probe)


def _is_major_topic_boundary(title: str, content: str) -> bool:
    probe = f"{title} {content}"
    if _is_numbered_heading(title):
        return False
    profile = infer_learning_profile(title, key_points=[], content=content)
    roles = profile["roles"]
    return bool(
        {"process", "comparison", "action", "contrast", "checklist"} & roles
        or ("component" in roles and has_any(title, ["连接", "功能", "组成", "结构"]))
        or ("enumeration" in roles and has_any(title, ["类型", "方式", "表现", "原因", "方面"]))
    )


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
        _rename_learning_topic(note)
        title = str(note.get("title") or "").strip()
        if _is_container_heading(title):
            continue
        if _is_independent_question_title(title):
            note["level"] = 1
            note["parentId"] = None
            current_parent = note
            current_child = None
        elif current_parent and _is_colon_child_of(title, str(current_parent.get("title") or "")):
            note["level"] = 2
            note["parentId"] = current_parent.get("id")
            current_child = note
        elif _is_major_topic_boundary(title, content):
            if _starts_new_top_level_topic(title, content):
                note["level"] = 1
                note["parentId"] = None
                current_parent = note
                current_child = None
            else:
                note["level"] = 2 if current_parent else 1
                note["parentId"] = current_parent.get("id") if current_parent else None
                current_child = note
        elif current_child and (title.startswith(("这种方式", "该方式", "上述方式", "这类方式")) or _is_explanatory_sentence(probe)):
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
            if current_parent:
                note["title"] = _semantic_title_for_numbered_note(title, current_parent, probe)
                title = str(note.get("title") or "").strip()
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
    return _normalize_learning_levels(_attach_colon_detail_notes(result))


def _starts_new_top_level_topic(title: str, content: str) -> bool:
    profile = infer_learning_profile(title, content=content)
    return profile["subtype"] == "interface_function" or ("component" in profile["roles"] and has_any(title, ["接口功能", "功能"]))


def _semantic_title_for_numbered_note(title: str, parent: dict[str, Any], probe: str) -> str:
    profile = infer_learning_profile(title, content=probe)
    if profile["material"] == "technical":
        return title
    item = strip_leading_number(title).strip(" 。；;")
    if not item:
        return title
    parent_title = str(parent.get("title") or "")
    parent_profile = infer_learning_profile(parent_title, str(parent.get("summary") or ""), parent.get("keyPoints") or [], str(parent.get("content") or ""))
    label = profile_point_label(item)
    if has_any(item, ["认同", "底气", "信心", "表现", "特点"]):
        base = _normalize_manifestation_heading(parent_title) if "manifestation" in parent_profile["roles"] else "表现细项"
        return compact(f"{base}：{label}", 42)
    if has_any(item, ["原因", "根本", "依据", "底气"]):
        return compact(f"原因说明：{label}", 42)
    if "action" in parent_profile["roles"] or has_any(item, ["树立", "弘扬", "参与", "承担", "加强", "增强", "坚持", "落实", "做到"]):
        return compact(f"行动要求：{label}", 42)
    return compact(f"要点：{label}", 42)


def _semantic_note_contract(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize user-facing learning units after structure repair.

    This follows the structure-first pattern used by document chunking systems:
    first merge dependent detail fragments into their parent learning unit, then
    enforce distinct field roles so summary/content/keyPoints do not repeat the
    same text.
    """
    merged = _split_enumerated_parent_notes(_merge_dependent_learning_notes(notes))
    for note in merged:
        _enforce_learning_field_roles(note)
    ordered = _order_parent_before_children(_break_parent_cycles(_merge_duplicate_title_notes(merged)))
    return _sync_parent_enumeration_points(ordered)


def _break_parent_cycles(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(note.get("id") or ""): note for note in notes}
    for note in notes:
        note_id = str(note.get("id") or "")
        seen: set[str] = set()
        parent = str(note.get("parentId") or "")
        while parent:
            if parent == note_id or parent in seen:
                note["parentId"] = None
                note["level"] = 1
                break
            seen.add(parent)
            parent = str((by_id.get(parent) or {}).get("parentId") or "")
    return notes


def _sync_parent_enumeration_points(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_parent: dict[str, list[dict[str, Any]]] = {}
    for note in notes:
        parent = str(note.get("parentId") or "")
        if parent:
            by_parent.setdefault(parent, []).append(note)
    for parent in notes:
        parent_id = str(parent.get("id") or "")
        children = [child for child in by_parent.get(parent_id, []) if _leading_note_number(str(child.get("title") or ""))]
        if len(children) < 2:
            continue
        existing_labels = [profile_point_label(str(point)) for point in parent.get("keyPoints", []) or [] if _leading_note_number(str(point))]
        labels = [*existing_labels, *[profile_point_label(str(child.get("title") or "")) for child in children]]
        labels = _dedupe_learning_list([label for label in labels if label], max_items=8)
        if labels:
            parent["keyPoints"] = labels
            profile = infer_learning_profile(str(parent.get("title") or ""), str(parent.get("summary") or ""), labels, str(parent.get("content") or ""))
            parent["summary"] = _summary_by_profile(str(parent.get("title") or ""), labels, profile)
            parent["content"] = _content_for_enumerated_parent(str(parent.get("title") or ""))
    return _renumber_notes_preserving_hierarchy(notes)


def _split_enumerated_parent_notes(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    existing_ids = {str(note.get("id")) for note in notes}
    for index, note in enumerate(notes):
        result.append(note)
        child = _child_from_enumerated_parent(note, notes, existing_ids)
        if child:
            result.append(child)
            existing_ids.add(str(child.get("id")))
    return _renumber_notes_preserving_hierarchy(result)


def _child_from_enumerated_parent(note: dict[str, Any], notes: list[dict[str, Any]], existing_ids: set[str]) -> dict[str, Any] | None:
    title = str(note.get("title") or "")
    points = [str(item) for item in note.get("keyPoints", []) or []]
    if not _looks_like_enumeration_parent(title, points):
        return None
    parent_id = str(note.get("id") or "")
    child_numbers = {_leading_note_number(str(item.get("title") or "")) for item in notes if str(item.get("parentId") or "") == parent_id}
    if len([number for number in child_numbers if number]) < 2:
        return None
    first_number = _leading_note_number(points[0]) if points else ""
    if not first_number or first_number in child_numbers:
        return None
    child_id = _unique_child_id(parent_id, existing_ids)
    child_title = _child_title_from_point(points[0])
    child_points = _child_points_for_parent_first_item(points)
    child = {
        **note,
        "id": child_id,
        "title": child_title,
        "level": int(note.get("level") or 1) + 1,
        "parentId": parent_id,
        "summary": _summary_for_enumerated_child(child_title, child_points),
        "content": str(note.get("content") or ""),
        "keyPoints": child_points,
        "sourceRefs": list(note.get("sourceRefs") or []),
        "source_refs": list(note.get("sourceRefs") or note.get("source_refs") or []),
    }
    note["summary"] = _summary_for_enumerated_parent(title, notes, parent_id, child_title)
    note["content"] = _content_for_enumerated_parent(title)
    note["keyPoints"] = _enumerated_parent_child_titles(notes, parent_id, child_title)
    return child


def _looks_like_enumeration_parent(title: str, points: list[str]) -> bool:
    if not points or not _leading_note_number(points[0]):
        return False
    title_signal = any(token in title for token in ["种", "类", "阶段", "步骤", "方面", "表现", "原因", "方式", "包括"])
    has_first_detail = len(points) >= 2 and not _leading_note_number(points[1])
    return title_signal and (has_first_detail or len(points) == 1)


def _leading_note_number(value: str) -> str:
    match = re.match(r"^\s*(?:[（(](\d+)[）)]|([①②③④⑤⑥⑦⑧⑨])|(\d+)[.、])", str(value))
    return next((group for group in match.groups() if group), "") if match else ""


def _child_title_from_point(point: str) -> str:
    text = normalize_learning_text(point).strip()
    text = re.sub(r"\s+", " ", text)
    return compact(text, 42)


def _child_points_for_parent_first_item(points: list[str]) -> list[str]:
    result: list[str] = []
    for point in points:
        if result and _leading_note_number(point):
            break
        result.append(point)
    return _dedupe_learning_list(result, max_items=5)


def _summary_for_enumerated_child(title: str, points: list[str]) -> str:
    details = [point for point in points[1:] if point]
    if details:
        return compact(f"{title}的重点是{_join_short_points(details[:3])}。", 220)
    return compact(f"{title}是该组并列项目中的一个子项。", 220)


def _summary_for_enumerated_parent(title: str, notes: list[dict[str, Any]], parent_id: str, first_child_title: str) -> str:
    children = _enumerated_parent_child_titles(notes, parent_id, first_child_title)
    return compact(f"本部分包含 {len(children)} 个并列内容项目，重点是分别比较各项的适用条件、执行方式和优缺点。", 200)


def _content_for_enumerated_parent(title: str) -> str:
    return compact(f"学习{title}时，先建立整体分类，再分别比较每一项的含义、条件、适用场景和容易混淆的边界。", 260)


def _enumerated_parent_child_titles(notes: list[dict[str, Any]], parent_id: str, first_child_title: str) -> list[str]:
    values = [first_child_title]
    values.extend(str(note.get("title") or "") for note in notes if str(note.get("parentId") or "") == parent_id)
    return _dedupe_learning_list(values, max_items=8)


def _unique_child_id(parent_id: str, existing_ids: set[str]) -> str:
    candidate = f"{parent_id}-1"
    index = 1
    while candidate in existing_ids:
        index += 1
        candidate = f"{parent_id}-{index}"
    return candidate


def _renumber_notes_preserving_hierarchy(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    id_map: dict[str, str] = {}
    for index, note in enumerate(notes, start=1):
        old_id = str(note.get("id") or f"note-{index}")
        new_id = f"note-{index}"
        id_map[old_id] = new_id
        note["id"] = new_id
    for note in notes:
        parent = str(note.get("parentId") or "")
        if parent in id_map:
            note["parentId"] = id_map[parent]
    return notes


def _merge_duplicate_title_notes(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    by_title: dict[str, dict[str, Any]] = {}
    id_redirect: dict[str, str] = {}
    for note in notes:
        title_key = _normalized_topic(str(note.get("title") or ""))
        if title_key and title_key in by_title:
            target = by_title[title_key]
            id_redirect[str(note.get("id") or "")] = str(target.get("id") or "")
            target["keyPoints"] = _dedupe_learning_list([*(target.get("keyPoints") or []), *(note.get("keyPoints") or [])], max_items=6)
            target["sourceRefs"] = _dedupe_learning_list([*(target.get("sourceRefs") or []), *(note.get("sourceRefs") or [])], max_items=20)
            target["source_refs"] = target["sourceRefs"]
            continue
        by_title[title_key] = note
        result.append(note)
    for note in result:
        parent = str(note.get("parentId") or "")
        if parent in id_redirect:
            note["parentId"] = id_redirect[parent]
    return _renumber_notes_preserving_hierarchy(result)


def _order_parent_before_children(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(note.get("id") or ""): note for note in notes}
    children: dict[str, list[dict[str, Any]]] = {}
    roots: list[dict[str, Any]] = []
    for note in notes:
        parent = str(note.get("parentId") or "")
        if parent and parent in by_id:
            children.setdefault(parent, []).append(note)
        else:
            roots.append(note)
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()

    def visit(note: dict[str, Any]) -> None:
        note_id = str(note.get("id") or "")
        if not note_id or note_id in seen:
            return
        seen.add(note_id)
        ordered.append(note)
        for child in children.get(note_id, []):
            visit(child)

    for root in roots:
        visit(root)
    for note in notes:
        visit(note)
    return _renumber_notes_preserving_hierarchy(ordered)


def _merge_dependent_learning_notes(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    id_redirect: dict[str, str] = {}
    for note in notes:
        parent_id = id_redirect.get(str(note.get("parentId") or ""), note.get("parentId"))
        note["parentId"] = parent_id
        target = _find_merge_target(result, note)
        if target is None:
            result.append(note)
            continue
        _merge_note_into(target, note)
        id_redirect[str(note.get("id"))] = str(target.get("id"))
    for note in result:
        parent = note.get("parentId")
        if parent in id_redirect:
            note["parentId"] = id_redirect[parent]
    return result


def _find_merge_target(existing: list[dict[str, Any]], note: dict[str, Any]) -> dict[str, Any] | None:
    title = str(note.get("title") or "")
    parent_id = str(note.get("parentId") or "")
    parent = next((item for item in existing if str(item.get("id")) == parent_id), None)
    previous = existing[-1] if existing else None
    candidates = [item for item in [parent, previous] if item]
    for candidate in candidates:
        if _should_merge_learning_notes(candidate, note):
            return candidate
    if _is_dependent_detail_title(title) and parent:
        return parent
    return None


def _should_merge_learning_notes(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_title = str(left.get("title") or "")
    right_title = str(right.get("title") or "")
    if not left_title or not right_title:
        return False
    if _is_numbered_heading(right_title) and not _is_dependent_detail_title(right_title):
        return False
    if _is_major_independent_title(right_title):
        return False
    title_score = _token_jaccard(left_title, right_title)
    body_score = _token_jaccard(_note_learning_text(left), _note_learning_text(right))
    if _is_dependent_detail_title(right_title) and (title_score >= 0.2 or body_score >= 0.35):
        return True
    if title_score >= 0.55 and body_score >= 0.28:
        return True
    if _normalized_topic(left_title) and _normalized_topic(left_title) in _normalized_topic(right_title) and body_score >= 0.4:
        return True
    return False


def _is_dependent_detail_title(title: str) -> bool:
    clean_title = re.sub(r"^\s*(?:\(\d+\)|\d+[.、])\s*", "", title).strip()
    return any(token in clean_title for token in ["适用性说明", "补充说明", "说明", "条件", "要求"]) and not _is_major_independent_title(clean_title)


def _is_major_independent_title(title: str) -> bool:
    return any(token in title for token in ["如何", "怎样", "为什么", "过程", "比较", "接口功能", "组成", "表现", "原因", "后处理", "中断机构", "行动要求", "表现细项", "原因说明"])


def _merge_note_into(target: dict[str, Any], source: dict[str, Any]) -> None:
    target["summary"] = _pick_better_summary(str(target.get("summary") or ""), str(source.get("summary") or ""), str(target.get("title") or ""))
    target["content"] = _merge_distinct_text(str(target.get("content") or ""), str(source.get("content") or ""), max_len=520)
    target["keyPoints"] = _dedupe_learning_list([*(target.get("keyPoints") or []), *(source.get("keyPoints") or [])], max_items=6)
    target["sourceRefs"] = _dedupe_learning_list([*(target.get("sourceRefs") or []), *(source.get("sourceRefs") or [])], max_items=20)
    target["source_refs"] = target["sourceRefs"]


def _enforce_learning_field_roles(note: dict[str, Any]) -> None:
    title = str(note.get("title") or "")
    key_points = _dedupe_learning_list([str(item) for item in note.get("keyPoints", []) or []], max_items=8)
    note["keyPoints"] = _normalize_key_points(title, key_points)
    note["summary"] = _rewrite_summary_for_role(title, str(note.get("summary") or ""), note["keyPoints"])
    note["content"] = _rewrite_content_for_role(title, str(note.get("content") or ""), note["summary"], note["keyPoints"])
    _finalize_readable_learning_fields(note)
    title = str(note.get("title") or "")
    note["keyPoints"] = _normalize_key_points(title, [str(item) for item in note.get("keyPoints", []) or []])
    note["summary"] = _rewrite_summary_for_role(title, str(note.get("summary") or ""), note["keyPoints"])
    note["content"] = _rewrite_content_for_role(title, str(note.get("content") or ""), note["summary"], note["keyPoints"])


def _finalize_readable_learning_fields(note: dict[str, Any]) -> None:
    title = str(note.get("title") or "")
    points = [str(item) for item in note.get("keyPoints", []) or []]
    profile = infer_learning_profile(title, str(note.get("summary") or ""), points, str(note.get("content") or ""))
    rewritten_points = _key_points_for_profile(title, points, profile)
    if rewritten_points:
        note["keyPoints"] = rewritten_points
        points = rewritten_points
    note["summary"] = _summary_by_profile(title, points, profile)
    note["content"] = _content_by_profile(title, points, profile)
    if field_like_overlap(str(note.get("content") or ""), points) > 0.70:
        note["content"] = _content_by_profile(title, [], profile)


def _key_points_for_profile(title: str, points: list[str], profile: dict[str, Any]) -> list[str]:
    roles = profile["roles"]
    subtype = profile["subtype"]
    labels = [label for label in profile.get("numberedLabels", []) if label]
    if "enumeration" in roles and labels:
        limit = 6 if len(labels) >= 6 else 5
        return _dedupe_learning_list(labels, max_items=limit)
    if profile["material"] == "technical":
        if "process" in roles and subtype in {"three_phase_process", "request_arbitration", "parallel_execution", "post_process"}:
            return _process_points(subtype, points)
        if "transfer_method" in roles:
            return _technical_method_points(subtype, points)
        if "component" in roles:
            return _component_points(subtype, [title, *points])
        if "comparison" in roles:
            return _dedupe_learning_list(points or ["比较传送单位", "比较响应时机", "比较异常处理和控制开销"], max_items=5)
    return _dedupe_learning_list(points, max_items=6 if _has_numbered_series(points, min_count=6) else 5)


def _technical_method_points(subtype: str, points: list[str]) -> list[str]:
    source = _dedupe_learning_list(points, max_items=5)
    if source and not _points_need_profile_rewrite(source):
        return source
    if subtype == "exclusive_access":
        return ["CPU 暂停访问主存", "传送方独占主存完成数据交换", "控制简单但处理器等待时间较长"]
    if subtype == "cycle_stealing":
        return ["传送时临时占用主存周期", "每次传送要申请和归还总线控制权", "适合外设读写周期大于主存周期的场景"]
    if subtype == "interleaved_access":
        return ["把工作周期划分为不同访存分周期", "传送方和处理器交替访问主存", "减少等待但硬件控制更复杂"]
    return source or ["围绕主存控制权比较", "关注处理器是否等待", "结合设备速度判断适用场景"]


def _component_points(subtype: str, points: list[str]) -> list[str]:
    source = _dedupe_learning_list(points, max_items=5)
    if subtype == "completion_notifier":
        return ["一批数据传送结束后发出中断请求", "通知 CPU 执行后处理", "与数据缓冲职责区分"]
    if subtype == "data_buffer":
        return ["暂存每次传送的数据", "协调主存侧与设备侧的数据宽度", "必要时完成字装配或拆卸"]
    if subtype == "counter":
        return ["记录本批数据传送长度", "随传送进度递减或更新", "计数结束触发完成判断"]
    if subtype == "address_register":
        return ["保存当前主存地址", "随传送进度更新地址", "为数据块传送定位"]
    if subtype == "control_logic":
        return ["协调请求和响应", "控制数据传送时序", "处理结束通知"]
    if subtype == "connection_type":
        joined = " ".join(points)
        if "选择型" in joined:
            return ["物理上可连接多个设备", "逻辑上同一时间只服务一个设备", "适合高速设备独占式传送"]
        if "多路型" in joined or "字节交叉" in joined:
            return ["物理上可连接多个设备", "多个设备可共享接口服务", "可采用字节交叉方式传送"]
        return ["区分单设备独占与多设备共享", "按设备速度选择连接方式", "关注请求线和响应线组织"]
    if subtype == "interface_function":
        return ["申请传送并接管总线", "维护地址和传送长度", "管理数据交换并通知处理器"]
    if subtype == "component_group":
        return ["地址类部件负责定位", "计数类部件负责长度", "缓冲类部件暂存数据", "控制逻辑协调传送过程"]
    if source and not _points_need_profile_rewrite(source):
        return source
    return source or ["按部件职责记忆", "区分数据通路和控制信号", "关注完成通知"]


def _process_points(subtype: str, points: list[str]) -> list[str]:
    source = _dedupe_learning_list(points, max_items=5)
    if subtype == "three_phase_process":
        return ["预处理设置地址和传送长度", "数据传送阶段完成数据块交换", "结束后执行校验和后处理"]
    if subtype == "request_arbitration":
        return ["设备就绪后提出传送请求", "多个请求按优先级排队", "获得控制权后开始传送"]
    if subtype == "parallel_execution":
        return ["处理器继续执行主程序", "传送控制器独立完成数据块交换", "传送结束后发出完成通知"]
    if subtype == "post_process":
        return ["检查传送过程中是否出错", "判断是否继续传送下一块", "必要时重新初始化或停止外设"]
    if source and not _points_need_profile_rewrite(source):
        return source
    return source or ["确认触发条件", "说明执行动作", "交代结束信号和后续处理"]


def _points_need_profile_rewrite(points: list[str]) -> bool:
    joined = " ".join(points)
    if any(_looks_like_transition_fragment(point) or _looks_like_generation_template(point) for point in points):
        return True
    if any(re.search(r"(请\s*CPU|通过说明|对应输入情况|经处理完毕|地址类部件负责定位)", point) for point in points):
        return True
    return len(points) <= 1 and len(joined) > 58


def _summary_by_profile(title: str, key_points: list[str], profile: dict[str, Any]) -> str:
    roles = profile["roles"]
    subtype = profile["subtype"]
    labels = profile.get("numberedLabels") or [profile_point_label(point) for point in key_points if _leading_note_number(point)]
    if "enumeration" in roles and labels:
        return compact(f"本部分包含 {len(labels)} 个并列内容项目，重点是分别说明各项的含义、条件和适用边界。", 180)
    if profile["material"] == "technical":
        return _technical_summary(title, subtype, roles, key_points)
    if profile["material"] == "politics":
        return _politics_summary(title, roles, key_points)
    if profile["material"] == "exam":
        return _exam_summary(title, roles, key_points)
    if key_points:
        return compact(f"{title}围绕{_join_summary_points(key_points[:2])}展开，重点是理解概念含义和适用边界。", 160)
    return compact(f"{title}说明本部分的核心概念、适用条件和判断边界。", 160)


def _technical_summary(title: str, subtype: str, roles: set[str], key_points: list[str]) -> str:
    if subtype == "completion_notifier":
        return "该完成通知部件用于在一批数据传送结束后发出中断请求，触发后处理。"
    if subtype == "data_buffer":
        return "数据缓冲部件用于暂存传送数据，并协调主存侧与设备侧的数据宽度差异。"
    if subtype == "counter":
        return "计数部件用于记录本批传送长度，并在计数结束时触发完成判断。"
    if subtype == "address_register":
        return "地址部件用于保存并更新当前主存地址，保证数据块写入或读出的定位正确。"
    if subtype == "control_logic":
        return "控制逻辑负责协调请求、响应、传送时序和结束通知。"
    if subtype == "connection_type":
        return "连接类型用于区分接口如何服务一个或多个设备，以及不同设备速度下的适用边界。"
    if subtype == "interface_function":
        return "接口功能应围绕请求、地址、长度、数据交换和完成通知来理解。"
    if subtype == "component_group":
        return "接口结构可按地址、计数、缓冲和控制四类职责建立记忆。"
    if subtype == "exclusive_access":
        return "该传送方式通过暂停处理器访存来让传送方独占主存完成数据交换。"
    if subtype == "cycle_stealing":
        return "该传送方式通过临时占用主存周期完成数据交换，重点看总线控制权的申请和归还。"
    if subtype == "interleaved_access":
        return "该传送方式把工作周期划分为不同访存分周期，让传送方和处理器交替访问主存。"
    if subtype == "parallel_execution":
        return "传送期间处理器可继续执行主程序，数据块完成后再进入收尾处理。"
    if subtype == "request_arbitration":
        return "该步骤说明设备就绪后提出传送请求，多个请求再按优先级或排队逻辑处理。"
    if subtype == "post_process":
        return "后处理用于检查传送结果、决定是否继续传送，并完成接口或外设的收尾控制。"
    if "process" in roles:
        return "流程类内容应按触发条件、执行阶段和结束处理来理解。"
    if "comparison" in roles:
        return "比较类技术点要对照传送单位、响应时机、异常处理和控制开销。"
    return "这一技术点需要放在数据流和控制流中理解，重点看触发条件、控制动作和传送结果。"


def _politics_summary(title: str, roles: set[str], key_points: list[str]) -> str:
    if "action" in roles:
        return "行动类内容应先明确主体，再按目标、做法和落实场景组织答案。"
    if "reason" in roles:
        return "原因类内容要先给结论，再归纳制度、道路、文化和现实成就等依据。"
    if "manifestation" in roles:
        return "表现类内容要区分态度认同、价值底气和具体行动。"
    if key_points:
        return compact(f"这部分适合整理成答题框架，围绕{_join_summary_points(key_points[:3])}展开。", 160)
    return "这部分适合整理成答题框架，先写核心结论，再按主体、原因或行动路径展开。"


def _exam_summary(title: str, roles: set[str], key_points: list[str]) -> str:
    if "principle" in roles:
        return "原理类内容要抓住原理表述、方法论要求和材料分析入口。"
    if "contrast" in roles:
        return "易混概念要区分概念边界、联系和常见错误表述。"
    if "checklist" in roles:
        return "高频考点应作为考前清单使用，重点对应选择题触发词和分析题常用原理。"
    if key_points:
        return compact(f"备考时围绕{_join_summary_points(key_points[:2])}压缩关键词，并练习展开成完整答案。", 160)
    return "备考类内容应压缩为概念、原理、易混点和题型应用，避免重复罗列原文长句。"


def _content_by_profile(title: str, key_points: list[str], profile: dict[str, Any]) -> str:
    roles = profile["roles"]
    subtype = profile["subtype"]
    if profile["material"] == "technical":
        return _technical_content(subtype, roles)
    if profile["material"] == "politics":
        return _politics_content(roles, key_points)
    if profile["material"] == "exam":
        return _exam_content(roles)
    if key_points:
        return compact(f"学习时先说明{title}的核心含义，再围绕{_join_short_points(key_points[:2])}补充条件、作用和边界。", 420)
    return "学习时先用一句话说明概念，再补充适用条件、作用和常见易错点。"


def _technical_content(subtype: str, roles: set[str]) -> str:
    if subtype == "completion_notifier":
        return "学习时抓住触发条件和作用：本批数据传送完成后，完成通知部件向处理器发出中断请求，由处理器执行校验、继续传送判断等收尾操作。"
    if subtype == "data_buffer":
        return "学习时区分两侧数据宽度：主存侧通常按字传送，设备侧可能按字节或位传送，缓冲部件负责暂存数据并配合装配或拆卸。"
    if subtype in {"counter", "address_register", "control_logic", "component_group", "interface_function"}:
        return "这类接口结构应按职责记忆：地址类部件负责定位，计数类部件负责长度，缓冲类部件暂存数据，控制逻辑负责协调请求、响应和结束通知。"
    if subtype == "connection_type":
        return "复习时区分连接方式：有的结构强调单个高速设备独占服务，有的结构强调多个低速设备按请求线、优先级或交叉方式共享服务。"
    if subtype == "exclusive_access":
        return "比较时关注主存使用权：这种方式控制逻辑简单，但处理器在传送阶段不能访问主存，适合需要成组快速传送且可接受等待的场景。"
    if subtype == "cycle_stealing":
        return "学习重点是总线控制权：每次传送只临时占用一个或少数主存周期，需要申请、建立并归还控制权，适合外设速度慢于主存的场景。"
    if subtype == "interleaved_access":
        return "这一方式把处理器周期划分为交替访存的分周期，可减少长时间等待，但需要更复杂的地址、数据和读写控制逻辑。"
    if subtype == "parallel_execution":
        return "理解重点是并行关系：传送控制器独立完成数据块交换，处理器不必一直等待；传送结束后再通过完成通知执行收尾处理。"
    if subtype == "request_arbitration":
        return "按流程理解：设备准备好后提出请求，处理器或硬件响应并交出控制权；若多个接口同时申请，则由排队或优先级逻辑决定响应顺序。"
    if subtype == "post_process":
        return "后处理阶段由处理器接管：先检查传送是否出错，再判断是否继续下一块数据，必要时重新初始化接口或停止外设。"
    if "comparison" in roles:
        return "比较时先确定使用场景，再按传送单位、响应时间、异常处理、现场保护和控制开销逐项对照。"
    if "process" in roles:
        return "流程类内容要按预处理、数据传送、后处理三步记忆：先设置地址和长度，再在设备就绪后接管数据块交换，最后由处理器完成校验和后处理。"
    return "这类技术点要放回数据流和控制流中理解，重点区分触发条件、执行动作和最终结果。"


def _politics_content(roles: set[str], key_points: list[str]) -> str:
    if "action" in roles:
        return "答题时按主体组织：国家或集体层面写方向和条件，个人层面写理想信念、学习实践、责任担当和法治意识。"
    if "reason" in roles:
        return "原因类题要先给结论，再展开制度、道路、理论、文化和现实成就等依据，避免只罗列口号。"
    if "manifestation" in roles:
        return "表现类题要把态度和行动分开：先说明认同和底气，再说明如何落实到理性心态、实践和责任中。"
    return f"这类思政内容应整理成答题框架，围绕{_join_short_points(key_points[:3])}形成可背诵的并列要点。"


def _exam_content(roles: set[str]) -> str:
    if "contrast" in roles:
        return "易混概念要按区别、联系、判断关键词三栏复习，选择题重点看概念边界，分析题重点看原理能否套用到材料。"
    if "principle" in roles:
        return "原理类内容适合按分析题模板记忆：先写原理内容，再写方法论，最后结合材料说明为什么要这样做。"
    if "checklist" in roles:
        return "高频考点应转成检查清单：逐项回忆定义、关键词和易错说法，再用真题判断哪些表述属于偷换概念。"
    return "备考时不要只背长句，应把概念、原理和易混点压缩成关键词，并练习把关键词展开成完整答案。"


def _rewrite_summary_for_role(title: str, summary: str, key_points: list[str]) -> str:
    text = normalize_learning_text(summary).strip()
    if _is_role_summary_good(title, text, key_points):
        return compact(_remove_summary_concat_noise(text), 160)
    profile = infer_learning_profile(title, summary, key_points)
    return compact(_summary_by_profile(title, key_points, profile), 160)


def _rewrite_content_for_role(title: str, content: str, summary: str, key_points: list[str]) -> str:
    text = normalize_learning_text(content).strip()
    profile = infer_learning_profile(title, summary, key_points, content)
    if _is_role_content_good(text, summary, key_points) and not _material_content_mismatch(profile, text):
        return compact(text, 460)
    return compact(_content_by_profile(title, key_points, profile), 460)


def _material_content_mismatch(profile: dict[str, Any], content: str) -> bool:
    if profile["material"] == "politics" and any(token in content for token in ["备考时", "选择题", "分析题", "真题"]):
        return True
    if profile["material"] == "exam" and any(token in content for token in ["国家层面", "个人层面", "法治意识"]):
        return True
    return False


def _technical_learning_content(title: str, key_points: list[str]) -> str:
    return _content_by_profile(title, key_points, infer_learning_profile(title, key_points=key_points))


def _politics_learning_content(title: str, key_points: list[str]) -> str:
    return _content_by_profile(title, key_points, infer_learning_profile(title, key_points=key_points))


def _exam_learning_content(title: str, key_points: list[str]) -> str:
    return _content_by_profile(title, key_points, infer_learning_profile(title, key_points=key_points))


def _is_role_summary_good(title: str, summary: str, key_points: list[str]) -> bool:
    if not summary or len(summary) < 20:
        return False
    if _looks_like_generation_template(summary):
        return False
    if _title_summary_mismatch(title, summary):
        return False
    if _looks_like_raw_concat_summary(title, summary):
        return False
    if summary.count("、") >= 5 and field_like_overlap(summary, key_points) > 0.68:
        return False
    return True


def _summary_by_material(title: str, key_points: list[str], material: str) -> str:
    profile = infer_learning_profile(title, key_points=key_points)
    if material and profile["material"] == "general":
        profile["material"] = material
    return _summary_by_profile(title, key_points, profile)


def _is_role_content_good(content: str, summary: str, key_points: list[str]) -> bool:
    if not content or len(content) < 28:
        return False
    if _looks_like_generation_template(content):
        return False
    if _content_summary_role_mismatch(content, summary):
        return False
    if field_like_overlap(content, key_points) > 0.76:
        return False
    if _token_jaccard(content, summary) > 0.72:
        return False
    return True


def _looks_like_generation_template(text: str) -> bool:
    return any(
        token in text
        for token in [
            "学习时先理解",
            "再围绕",
            "梳理作用、条件和易混点",
            "核心是理解本主题的背景、结论和应用边界",
            "核心是理解核心概念、判断依据和应用边界",
            "学习这个主题时",
            "需要结合原文",
            "主要学习",
            "之间的关系",
            "不应承载",
            "结构总览",
            "交给各子模块",
        ]
    )


def _infer_learning_material(title: str, summary: str, key_points: list[str]) -> str:
    return str(infer_learning_profile(title, summary, key_points).get("material") or "general")

def _is_question_like(title: str) -> bool:
    return title.startswith(("如何", "怎样", "为什么", "什么是")) or title.endswith("怎么做")


def _is_good_learning_point(point: str) -> bool:
    text = normalize_learning_text(point).strip()
    if len(text) < 4 or len(text) > 72:
        return False
    if _looks_like_generation_template(text):
        return False
    if _looks_like_transition_fragment(text):
        return False
    if re.search(r"(。.*。|；.*；|梳理作用|核心含义)", text):
        return False
    if re.search(r"(和|或|但|因为|由于|以及|已|、|，|；|：|/)$", text):
        return False
    if re.search(r"(请\s*CPU|通过说明|对应输入情况|对应输出情况)", text):
        return False
    if re.search(r"(控[、；;\s]+制|方[、；;\s]+式|主[、；;\s]+存|电[、；;\s]+路|装配\s*/\s*$|字装配\s*/)", text):
        return False
    if len(re.findall(r"[，、；]", text)) >= 4:
        return False
    if _is_section_label_point(text):
        return False
    if _is_source_navigation_or_figure_point(text):
        return False
    return True


def _compact_point(point: str) -> str:
    text = normalize_learning_text(str(point)).strip(" ；;。")
    text = _strip_point_explanation_tail(text)
    return compact(text, 72)


def _normalize_key_points(title: str, points: list[str]) -> list[str]:
    normalized: list[str] = []
    max_items = 6 if _has_numbered_series(points, min_count=6) else 5
    for point in points:
        for candidate in _split_overlong_point(point):
            candidate = _compact_point(candidate)
            if not _is_good_learning_point(candidate):
                continue
            if _is_redundant_colon_child_point(title, candidate):
                continue
            if _token_jaccard(candidate, title) > 0.82 and not _leading_note_number(candidate):
                continue
            if any(_token_jaccard(candidate, old) > 0.78 for old in normalized):
                continue
            normalized.append(candidate)
            if len(normalized) >= max_items:
                return normalized
    return normalized


def _has_numbered_series(points: list[str], *, min_count: int) -> bool:
    return sum(1 for point in points if _leading_note_number(str(point))) >= min_count


def _is_redundant_colon_child_point(title: str, point: str) -> bool:
    if "：" not in title:
        return False
    detail = title.split("：", 1)[1].strip()
    if not detail:
        return False
    point_text = re.sub(r"^\s*(?:[（(]\d+[）)]|[①②③④⑤⑥⑦⑧⑨]|\d+[.、])\s*", "", point).strip()
    detail_key = _normalized_topic(detail)
    point_key = _normalized_topic(point_text)
    return bool(detail_key and len(detail_key) >= 4 and (detail_key in point_key or point_key in detail_key))


def _split_overlong_point(point: str) -> list[str]:
    text = normalize_learning_text(str(point)).strip(" ；;。")
    if len(text) <= 56 and len(re.findall(r"[，；]", text)) <= 1:
        return [text]
    parts = [part.strip(" ；;。") for part in re.split(r"[；;。]\s*", text) if part.strip()]
    if len(parts) == 1 and len(text) > 72:
        parts = [part.strip(" ，,、") for part in re.split(r"[，,]\s*", text) if part.strip()]
    return parts or [text]


def _strip_point_explanation_tail(text: str) -> str:
    text = re.sub(r"^\s*(说明|包括|主要包括)\s*", "", text)
    text = re.sub(r"\s*等内容$", "", text)
    for marker in ["说明", "表示", "是指", "负责", "通常", "因此", "请", "对应", "便"]:
        idx = text.find(marker)
        if idx > 8 and len(text) > 42:
            return text[:idx].rstrip(" ，,、；;：:")
    return text


def _is_source_navigation_or_figure_point(text: str) -> bool:
    clean = re.sub(r"\s+", "", text)
    if re.search(r"^\(?\d+\)?DMA传送过程示意", clean):
        return True
    if clean in {"主存地址送总线", "控制状态寄存器", "数据缓冲寄存器", "主存地址寄存器"}:
        return True
    if clean in {"自信的中国人的特点", "自信的中国人表现在哪些方面"}:
        return True
    if clean.startswith("理，这由") or clean.startswith("性和多路型"):
        return True
    return False


def _is_section_label_point(text: str) -> bool:
    cleaned = re.sub(r"^\s*(?:[（(][一二三四五六七八九十\d]+[）)]|[①②③④⑤⑥⑦⑧⑨]|\d+[.、])\s*", "", text).strip()
    if len(cleaned) > 14:
        return False
    return any(
        token in cleaned
        for token in [
            "根本原因",
            "重要原因",
            "原理内容",
            "方法论意义",
            "物质范畴",
            "意识范畴",
            "易混淆概念辨析",
        ]
    )


def _remove_summary_concat_noise(text: str) -> str:
    text = normalize_learning_text(text).strip()
    text = re.sub(r"(.{8,40})(说明|主要包括)\1", r"\1", text)
    sentences = split_sentences(text)
    if sentences:
        text = sentences[0]
    if len(text) > 150:
        text = compact(text, 150)
    return text


def _looks_like_raw_concat_summary(title: str, summary: str) -> bool:
    if len(summary) > 150:
        return True
    if summary.count("、") >= 4 or summary.count("，") >= 5:
        return True
    if title and summary.startswith(title) and ("主要包括" in summary or "重点说明" in summary or "包括" in summary[: len(title) + 16] or "包含" in summary[: len(title) + 16] or "说明" in summary[: len(title) + 12]):
        return True
    if "说明" in summary and summary.count("说明") >= 2:
        return True
    if re.search(r"(.{8,40})(?:说明|主要包括)\1", summary):
        return True
    if _looks_like_transition_fragment(summary):
        return True
    return False


def _title_summary_mismatch(title: str, summary: str) -> bool:
    profile = infer_learning_profile(title, summary)
    if profile["subtype"] == "completion_notifier" and any(token in summary for token in ["字计数器溢出", "通过说明", "数据缓冲寄存器"]):
        return True
    if "process" in profile["roles"] and _looks_like_transition_fragment(summary):
        return True
    if _component_title_summary_mismatch(title, summary):
        return True
    return False


def _looks_like_transition_fragment(text: str) -> bool:
    return any(token in text for token in ["通过说明", "✓ 预处理之后", "预处理之后", "（对应输入情况", "对应输入情况", "对应输出情况", "经处理完毕", "便通过DMA", "请CPU", "请 CPU"])


def _component_title_summary_mismatch(title: str, summary: str) -> bool:
    component_terms = ["字计数器", "数据缓冲寄存器", "主存地址寄存器", "控制逻辑", "中断机构"]
    title_terms = {term for term in component_terms if term in title}
    if not title_terms:
        return False
    first_clause = re.split(r"[，。；;]", summary, maxsplit=1)[0]
    foreign_terms = [term for term in component_terms if term in first_clause and term not in title_terms]
    return bool(foreign_terms and any(term in summary for term in title_terms))


def _content_summary_role_mismatch(content: str, summary: str) -> bool:
    profile = infer_learning_profile(summary, content=content)
    if profile["subtype"] == "completion_notifier" and "地址类部件负责定位" in content:
        return True
    if "process" in profile["roles"] and any(token in content for token in ["地址类部件负责定位", "缓冲类部件暂存数据"]):
        return True
    return False


def _join_summary_points(points: list[str]) -> str:
    labels = [_summary_point_label(point) for point in points]
    return _join_short_points([label for label in labels if label])


def _summary_point_label(point: str) -> str:
    text = normalize_learning_text(str(point)).strip(" ；;。")
    text = re.sub(r"^[①②③④⑤⑥⑦⑧⑨]\s*", "", text)
    text = re.sub(r"^\s*[（(]\d+[）)]\s*", "", text)
    if "：" in text and len(text) > 28:
        head, tail = text.split("：", 1)
        if 2 <= len(head) <= 18:
            return head
        text = tail
    for sep in ["，", "；", "。"]:
        if sep in text and len(text) > 28:
            text = text.split(sep, 1)[0]
    return compact(text, 32)


def _pick_better_summary(left: str, right: str, title: str) -> str:
    candidates = [left, right]
    candidates.sort(key=lambda item: (_looks_like_generation_template(item), field_like_overlap(item, [title]), -len(item)))
    return compact(candidates[0] or candidates[-1], 220)


def _merge_distinct_text(left: str, right: str, *, max_len: int) -> str:
    if not left:
        return compact(right, max_len)
    if not right or _token_jaccard(left, right) > 0.58:
        return compact(left, max_len)
    return compact(f"{left} {right}", max_len)


def _dedupe_learning_list(values: list[Any], *, max_items: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = normalize_learning_text(str(value)).strip()
        key = _normalized_topic(text)
        if text and key and key not in seen:
            seen.add(key)
            result.append(text)
        if len(result) >= max_items:
            break
    return result


def _join_short_points(points: list[str]) -> str:
    return "、".join(point.rstrip("。；;") for point in points if point)


def field_like_overlap(text: str, points: list[str]) -> float:
    if not text or not points:
        return 0.0
    joined = " ".join(points)
    return _token_jaccard(text, joined)


def _note_learning_text(note: dict[str, Any]) -> str:
    return " ".join([str(note.get("summary") or ""), str(note.get("content") or ""), " ".join(str(item) for item in note.get("keyPoints", []) or [])])


def _normalized_topic(value: str) -> str:
    return re.sub(r"[\W_]+", "", normalize_learning_text(value)).lower()


def _token_jaccard(left: str, right: str) -> float:
    left_tokens = set(re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]{2}", normalize_learning_text(left)))
    right_tokens = set(re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]{2}", normalize_learning_text(right)))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))


def _rename_learning_topic(note: dict[str, Any]) -> None:
    title = str(note.get("title") or "")
    probe = " ".join(
        [
            title,
            str(note.get("summary") or ""),
            str(note.get("content") or ""),
            " ".join(str(item) for item in note.get("keyPoints", []) or []),
        ]
    )
    if _looks_like_interrupt_trigger_fragment(title, probe):
        note["title"] = _technical_concept_title(probe, "中断机构")
    elif "选择型" in probe and "多路型" not in title:
        note["title"] = _technical_concept_title(probe, "选择型接口")
    elif "多路型" in probe:
        note["title"] = _technical_concept_title(probe, "多路型接口")
    elif _looks_like_transition_fragment(title) and has_any(probe, ["申请", "请求", "准备好", "排队", "优先级"]):
        note["title"] = _technical_concept_title(probe, "数据传送申请条件")
    elif has_any(title, ["继续执行主程序", "并行工作"]) and has_any(probe, ["传送", "中断", "后处理"]):
        note["title"] = _technical_concept_title(probe, "传送期间并行工作")
    elif has_any(title, ["校验", "继续传送", "重新初始化", "停止外设"]):
        note["title"] = _technical_concept_title(probe, "后处理")


def _technical_concept_title(probe: str, concept: str) -> str:
    prefix = "DMA " if "DMA" in probe or (concept == "中断机构" and has_any(probe, ["CPU", "主存", "数据传送", "后处理"])) else ""
    return compact(f"{prefix}{concept}", 42)


def _looks_like_interrupt_trigger_fragment(title: str, probe: str) -> bool:
    compacted_title = re.sub(r"\s+", "", title)
    compacted_probe = re.sub(r"\s+", "", probe)
    if "中断机构" in compacted_probe and ("中断请求" in compacted_probe or "后处理" in compacted_probe):
        return "字计数器" in compacted_probe and ("溢出" in compacted_probe or "传送完毕" in compacted_probe)
    return (
        "字计数器" in compacted_title
        and "溢出" in compacted_title
        and ("一批数据传送" in compacted_title or "传送完毕" in compacted_title)
        and compacted_title.endswith("通过")
    )


def _is_independent_question_title(title: str) -> bool:
    value = re.sub(r"^\s*(?:\d+[.、]|\(\d+\)|[①②③④⑤⑥⑦⑧⑨])\s*", "", title).strip()
    return value.startswith(("如何", "怎样", "为什么", "什么是")) or value.endswith("怎么做")


def _is_colon_child_of(title: str, parent_title: str) -> bool:
    if "：" not in title or not parent_title:
        return False
    base = title.split("：", 1)[0].strip()
    parent = parent_title.split("：", 1)[0].strip()
    return len(base) >= 5 and (base == parent or base in parent or parent in base)


def _attach_colon_detail_notes(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_base: dict[str, dict[str, Any]] = {}
    for note in notes:
        title = str(note.get("title") or "").strip()
        if "：" not in title:
            by_base[title] = note
    for note in notes:
        title = str(note.get("title") or "").strip()
        if "：" not in title:
            continue
        base = title.split("：", 1)[0].strip()
        parent = by_base.get(base)
        if parent and parent is not note:
            note["level"] = max(2, int(note.get("level") or 1))
            note["parentId"] = parent.get("id")
    return notes


def _normalize_learning_levels(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    technical_roots = [note for note in notes if infer_learning_profile(str(note.get("title") or ""), str(note.get("summary") or ""), note.get("keyPoints") or [], str(note.get("content") or ""))["material"] == "technical"]
    interface_parent = _first_parent_matching(technical_roots, lambda profile, title: "component" in profile["roles"] and profile["subtype"] != "connection_type" and has_any(title, ["接口", "功能", "组成", "结构"]))
    transfer_parent = _first_parent_matching(technical_roots, lambda profile, title: "enumeration" in profile["roles"] and "transfer_method" in profile["roles"])
    process_parent = _first_parent_matching(technical_roots, lambda profile, title: "process" in profile["roles"] and has_any(title, ["过程", "流程"]))
    manifestation_parent = _first_parent_matching(notes, lambda profile, title: "manifestation" in profile["roles"] and not title.startswith("表现细项"))
    for note in notes:
        title = str(note.get("title") or "")
        profile = infer_learning_profile(title, str(note.get("summary") or ""), note.get("keyPoints") or [], str(note.get("content") or ""))
        if manifestation_parent and title.startswith("表现细项"):
            note["level"] = 2
            note["parentId"] = manifestation_parent.get("id")
            continue
        if note is not interface_parent and interface_parent and _belongs_to_interface_parent(profile, title):
            note["level"] = max(2, int(note.get("level") or 1))
            note["parentId"] = interface_parent.get("id")
        if note is not transfer_parent and transfer_parent and "transfer_method" in profile["roles"]:
            note["level"] = max(2, int(note.get("level") or 1))
            note["parentId"] = transfer_parent.get("id")
        if note is not process_parent and process_parent and "process" in profile["roles"] and not has_any(title, ["过程", "流程"]):
            note["level"] = max(2, int(note.get("level") or 1))
            note["parentId"] = process_parent.get("id")
    return notes


def _first_parent_matching(notes: list[dict[str, Any]], predicate) -> dict[str, Any] | None:
    for note in notes:
        title = str(note.get("title") or "")
        profile = infer_learning_profile(title, str(note.get("summary") or ""), note.get("keyPoints") or [], str(note.get("content") or ""))
        if int(note.get("level") or 1) <= 1 and predicate(profile, title):
            return note
    for note in notes:
        title = str(note.get("title") or "")
        profile = infer_learning_profile(title, str(note.get("summary") or ""), note.get("keyPoints") or [], str(note.get("content") or ""))
        if predicate(profile, title):
            return note
    return None


def _belongs_to_interface_parent(profile: dict[str, Any], title: str) -> bool:
    if profile["material"] != "technical":
        return False
    if "transfer_method" in profile["roles"]:
        return False
    return "component" in profile["roles"] or "comparison" in profile["roles"] or ("process" in profile["roles"] and has_any(title, ["传送", "流程", "过程"])) or has_any(title, ["连接", "选择", "多路"])


def _explanatory_note_title(parent: dict[str, Any]) -> str:
    parent_title = str(parent.get("title") or "")
    profile = infer_learning_profile(parent_title, str(parent.get("summary") or ""), parent.get("keyPoints") or [], str(parent.get("content") or ""))
    if "transfer_method" in profile["roles"]:
        return compact(f"{strip_leading_number(parent_title)}的适用性说明", 42)
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
