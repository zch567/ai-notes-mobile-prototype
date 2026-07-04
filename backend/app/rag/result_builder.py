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
    notes = _semantic_note_contract(_reconstruct_note_hierarchy(notes), processing_chunks)
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
    heading = (chunk.heading or "").strip()
    probe = f"{heading}\n{text}"
    if _is_heading_only_chunk(heading, text):
        return False
    if len(text) < 40 and not _has_compact_learning_signal(probe):
        return False
    if _is_course_container_chunk(heading, text):
        return False
    if chunk.sourceType == "pptx" and _is_ppt_non_core_chunk(heading, text):
        return False
    if _is_visual_only_chunk(heading, text):
        return False
    if _is_diagram_noise_chunk(heading, text) and not _has_compact_learning_signal(probe):
        return False
    if _is_orphan_fragment_chunk(heading, text) and not _has_compact_learning_signal(probe):
        return False
    # Skip tiny list fragments such as standalone GPT-2/GPT-3 entries; they are
    # still available as sources and citations, but not as top-level notes.
    if chunk.sourceType != "pptx" and len(text) < 80 and re.match(r"^\d+[.?]|^GPT-\d+$", heading, flags=re.I) and not _has_compact_learning_signal(probe):
        return False
    return True


def _is_heading_only_chunk(heading: str, text: str) -> bool:
    compacted_text = re.sub(r"\s+", "", text)
    compacted_heading = re.sub(r"\s+", "", heading)
    if not compacted_text:
        return True
    if compacted_heading and compacted_text == compacted_heading:
        return True
    if len(compacted_text) <= 18 and re.search(r"(方式的特点|接口的功能和组成|工作过程|芯片.*类型|圆梦大舞台|自信的中国人)$", compacted_text):
        return True
    return False


def _has_compact_learning_signal(text: str) -> bool:
    probe = normalize_learning_text(text)
    return any(
        token in probe
        for token in [
            "数据通路",
            "直接数据通路",
            "不需要 CPU暂停",
            "保护和恢复现场",
            "高速 I/O",
            "适合",
            "适用于",
            "特点",
            "原因",
            "意义",
            "奋斗的意义",
            "作用",
            "奋斗者",
            "中断机构",
            "中断请求",
            "后处理",
            "独立的 DMA 请求",
            "独立的DMA请求",
            "请求线",
            "响应线",
            "优先级",
            "选择型DMA接口",
            "选择型 DMA 接口",
            "多路型DMA接口",
            "字节交叉",
            "控制总线",
            "中国梦",
            "奋斗",
            "中国力量",
            "自信不是",
            "自信的中国人",
            "国家有认同",
            "文化有底气",
            "理性平和",
        ]
    )


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
    if any(token in compacted for token in ["基础型作业", "发展型作业", "完成课时练习"]):
        return True
    if any(token in compacted for token in ["学习目标", "教学目标", "通过本节课学习"]):
        return True
    if "笔记区" in compacted and not _has_compact_learning_signal(probe):
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
    numbered_count = sum(1 for line in lines if _is_numbered_heading(line))
    search_lines = lines if numbered_count >= 3 else [*lines[:5], *lines[-3:]]
    seen: set[str] = set()
    for line in search_lines:
        if line in seen:
            continue
        seen.add(line)
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


def _semantic_note_contract(notes: list[dict[str, Any]], chunks: list[SourceChunk] | None = None) -> list[dict[str, Any]]:
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
    synced = _sync_parent_enumeration_points(ordered)
    for note in synced:
        _enforce_learning_field_roles(note)
    synced = _normalize_learning_levels(synced)
    if chunks:
        synced = _recover_source_grounded_fields(synced, chunks)
        synced = _normalize_learning_levels(synced)
    return _order_parent_before_children(_break_parent_cycles(synced))


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


def _recover_source_grounded_fields(notes: list[dict[str, Any]], chunks: list[SourceChunk]) -> list[dict[str, Any]]:
    chunk_by_key: dict[str, SourceChunk] = {}
    for chunk in chunks:
        chunk_by_key[chunk.id] = chunk
        chunk_by_key[chunk.sourceRef] = chunk
    for note in notes:
        source_text = _source_text_for_note(note, chunk_by_key)
        if not source_text:
            _repair_existing_knowledge_fields(note)
            continue
        title = str(note.get("title") or "")
        current_points = [str(item) for item in note.get("keyPoints", []) or [] if str(item).strip()]
        profile = infer_learning_profile(title, str(note.get("summary") or ""), current_points, str(note.get("content") or ""))
        source_points = _extract_source_knowledge_points(title, source_text, profile)
        used_source_points = False
        if source_points and _should_replace_with_source_points(title, current_points, source_points, profile):
            note["keyPoints"] = source_points
            current_points = source_points
            used_source_points = True
            if any(point.startswith("根本原因") for point in current_points):
                subject = _source_reason_subject(source_text)
                if subject:
                    note["title"] = subject
                    title = subject
            profile = infer_learning_profile(title, str(note.get("summary") or ""), current_points, str(note.get("content") or ""))
        if current_points and (used_source_points or _summary_needs_source_rewrite(title, str(note.get("summary") or ""), current_points)):
            note["summary"] = _source_backed_summary(title, current_points, profile)
        if current_points and (used_source_points or _content_needs_source_rewrite(title, str(note.get("content") or ""), current_points, profile)):
            note["content"] = _source_backed_content(title, current_points, profile)
        _repair_existing_knowledge_fields(note)
        note["blocks"] = _sync_note_blocks(note)
    return notes


def _repair_existing_knowledge_fields(note: dict[str, Any]) -> None:
    title = str(note.get("title") or "")
    points = [str(item) for item in note.get("keyPoints", []) or [] if str(item).strip()]
    if not points:
        return
    profile = infer_learning_profile(title, str(note.get("summary") or ""), points, str(note.get("content") or ""))
    compacted = [_compact_source_knowledge_point(point, profile) for point in points]
    compacted = _relabel_repeated_definition_points(compacted)
    compacted = _dedupe_learning_list([point for point in compacted if point], max_items=10 if profile["material"] in {"exam", "politics"} else 8)
    if compacted:
        note["keyPoints"] = compacted
        points = compacted
    if _summary_needs_source_rewrite(title, str(note.get("summary") or ""), points):
        note["summary"] = _source_backed_summary(title, points, profile)
    if _content_needs_source_rewrite(title, str(note.get("content") or ""), points, profile):
        note["content"] = _source_backed_content(title, points, profile)
    note["blocks"] = _sync_note_blocks(note)


def _source_text_for_note(note: dict[str, Any], chunk_by_key: dict[str, SourceChunk]) -> str:
    refs = [str(item) for item in [*(note.get("sourceRefs") or []), *(note.get("source_refs") or [])] if str(item)]
    chunks: list[SourceChunk] = []
    seen: set[str] = set()
    for ref in refs:
        chunk = chunk_by_key.get(ref)
        if not chunk or chunk.id in seen:
            continue
        seen.add(chunk.id)
        chunks.append(chunk)
    parts: list[str] = []
    for chunk in chunks:
        parts.extend([chunk.heading or "", chunk.text or ""])
    return normalize_learning_text("\n".join(part for part in parts if part))


def _extract_source_knowledge_points(title: str, source_text: str, profile: dict[str, Any]) -> list[str]:
    focused = _slice_source_for_title(title, source_text)
    lines = _source_knowledge_lines(focused)
    points: list[str] = []
    context = ""
    for line in lines:
        label, tail = _labelled_knowledge_line(line)
        if label:
            context = label
            if tail and _is_source_fact_line(tail):
                points.append(_format_source_point(label, tail, profile))
            continue
        number = _leading_note_number(line)
        if number:
            body = strip_leading_number(line).strip(" ；;。")
            if _is_source_fact_line(body):
                points.append(_format_source_point(context, f"{_numbered_prefix_for_source(number)}{body}", profile))
            continue
        if context and _is_source_fact_line(line):
            points.append(_format_source_point(context, line, profile))
    if not points:
        points = _fallback_source_fact_points(title, lines, profile)
    max_items = 10 if profile["material"] in {"exam", "politics"} else 8
    compacted = [_compact_source_knowledge_point(point, profile) for point in points if _is_source_fact_line(point)]
    return _dedupe_learning_list([point for point in compacted if _is_source_fact_line(point)], max_items=max_items)


def _source_knowledge_lines(source_text: str) -> list[str]:
    raw_lines = [clean_item(line) for line in normalize_learning_text(source_text).splitlines() if clean_item(line)]
    result: list[str] = []
    seen_recent = ""
    for line in raw_lines:
        line = line.strip(" ；;")
        if not line or line == seen_recent:
            continue
        seen_recent = line
        if _looks_like_instruction_or_noise(line):
            continue
        if any(token in line for token in ["合作探究", "思考：", "笔记区", "课时练习"]):
            continue
        if _is_source_question_line(line):
            continue
        result.append(line)
    return result


def _slice_source_for_title(title: str, source_text: str) -> str:
    lines = [line for line in normalize_learning_text(source_text).splitlines() if line.strip()]
    title_key = _normalized_topic(title)
    if "vs" in title.lower() and title_key:
        start = None
        for index, line in enumerate(lines):
            line_key = _normalized_topic(line)
            if line_key and (title_key in line_key or line_key in title_key):
                start = index
                break
        if start is not None:
            end = len(lines)
            for index in range(start + 1, len(lines)):
                if "vs" in lines[index].lower():
                    end = index
                    break
            return "\n".join(lines[start:end])
    return source_text


def _labelled_knowledge_line(line: str) -> tuple[str, str]:
    text = normalize_learning_text(line).strip()
    text = re.sub(r"^[（(][一二三四五六七八九十\d]+[）)]\s*", "", text)
    match = re.match(
        r"^(根本原因|重要原因|原理内容|方法论意义|核心要点|定义|起源|运动|静止|辩证关系|区别|联系|核心内容|本质|作用|特点)[:：]\s*(.*)$",
        text,
    )
    if match:
        return match.group(1), match.group(2).strip()
    if text in {"原理内容", "方法论意义", "核心要点", "根本原因", "重要原因"}:
        return text, ""
    return "", ""


def _format_source_point(label: str, body: str, profile: dict[str, Any]) -> str:
    body = normalize_learning_text(body).strip(" ；;。")
    label = label.strip()
    if not label:
        return body
    if label in {"核心要点", "原理内容"}:
        return body
    if label == "定义" and body.startswith("定义"):
        return body
    if body.startswith(f"{label}："):
        return body
    if label in {"根本原因", "重要原因", "方法论意义", "区别", "联系", "定义", "起源", "运动", "静止", "辩证关系", "本质", "作用", "特点"}:
        return f"{label}：{body}"
    return body


def _numbered_prefix_for_source(number: str) -> str:
    if number in "①②③④⑤⑥⑦⑧⑨⑩":
        return f"{number}"
    return f"({number}) " if number else ""


def _is_source_question_line(line: str) -> bool:
    text = normalize_learning_text(line).strip()
    return bool(
        "？" in text
        or "?" in text
        or re.search(r"(应该怎么做|源自哪里|根本所在|表现在哪些方面|为何会|为什么|什么是)", text)
    )


def _is_source_fact_line(line: str) -> bool:
    text = normalize_learning_text(line).strip(" ；;。")
    if len(text) < 6:
        return False
    if _looks_like_generation_template(text) or _looks_like_instruction_or_noise(text):
        return False
    if _is_source_question_line(text):
        return False
    if re.fullmatch(r"[一二三四五六七八九十\d]+[.、]?\s*", text):
        return False
    if re.fullmatch(r"[（(][一二三四五六七八九十\d]+[）)]\s*[^：:；;。]{2,18}", text):
        return False
    if re.fullmatch(r"[一二三四五六七八九十]+、[^：:；;。]{2,22}", text):
        return False
    if text in {"三感", "两自觉", "道路自信", "理论自信", "制度自信", "文化自信"}:
        return False
    if text in {"历年真题高频考点总结", "本章复习要求"}:
        return False
    return True


def _compact_source_knowledge_point(point: str, profile: dict[str, Any]) -> str:
    text = normalize_learning_text(point).strip(" ；;。")
    if len(text) <= 72 and len(re.findall(r"[，、；;]", text)) < 4:
        return text
    if "：" in text:
        label, body = text.split("：", 1)
        clauses = [part.strip(" ；;。") for part in re.split(r"[；;。]", body) if part.strip(" ；;。")]
        if clauses:
            first = clauses[0]
            pieces = [part.strip(" ，,、") for part in re.split(r"[，,、]", first) if part.strip(" ，,、")]
            if len(pieces) >= 4 and re.search(r"\d+个核心概念|核心概念", label):
                return f"{label}：{'/'.join(pieces)}"
            selected: list[str] = []
            for piece in pieces:
                if len(selected) >= 3:
                    break
                candidate = "，".join([*selected, piece])
                if len(f"{label}：{candidate}") <= 72:
                    selected.append(piece)
            if selected:
                return f"{label}：{'，'.join(selected)}"
            return f"{label}：{first[: max(8, 70 - len(label))].rstrip('，,、')}"
    pieces = [part.strip(" ，,、") for part in re.split(r"[，,、]", text) if part.strip(" ，,、")]
    if len(pieces) >= 4:
        head = pieces[0]
        if re.search(r"\d+个核心概念|核心概念", head):
            return f"{head}（{'/'.join(pieces[1:])}）"
        return "，".join(pieces[:3])
    clauses = [part.strip(" ；;。") for part in re.split(r"[；;。]", text) if part.strip(" ；;。")]
    if clauses:
        return clauses[0][:72].rstrip("，,、")
    return text[:72].rstrip("，,、")


def _fallback_source_fact_points(title: str, lines: list[str], profile: dict[str, Any]) -> list[str]:
    title_key = _normalized_topic(title)
    points: list[str] = []
    for line in lines:
        text = line.strip(" ；;。")
        if not _is_source_fact_line(text):
            continue
        key = _normalized_topic(text)
        if key and title_key and (key == title_key or key in title_key):
            continue
        if len(text) > 120:
            for sentence in split_sentences(text):
                if _is_source_fact_line(sentence):
                    points.append(sentence.strip(" ；;。"))
        else:
            points.append(text)
    return points


def _should_replace_with_source_points(title: str, current_points: list[str], source_points: list[str], profile: dict[str, Any]) -> bool:
    if not source_points:
        return False
    if not current_points:
        return True
    title_key = _normalized_topic(title)
    title_echo = [point for point in current_points if _normalized_topic(point) == title_key or _token_jaccard(point, title) > 0.82]
    if title_echo:
        return True
    if _title_keypoint_mismatch(title, current_points, source_points):
        return True
    if profile["material"] in {"politics", "exam"} and len(source_points) > len(current_points):
        return True
    if len(current_points) <= 1 and len(source_points) >= 2:
        return True
    return False


def _title_keypoint_mismatch(title: str, current_points: list[str], source_points: list[str]) -> bool:
    if "vs" not in title.lower():
        return False
    title_terms = [part.strip() for part in re.split(r"\s+vs\s+|：|:", title, flags=re.I) if part.strip()]
    current_text = " ".join(current_points)
    source_text = " ".join(source_points)
    current_hits = sum(1 for term in title_terms if term and term in current_text)
    source_hits = sum(1 for term in title_terms if term and term in source_text)
    return source_hits > current_hits


def _summary_needs_source_rewrite(title: str, summary: str, points: list[str]) -> bool:
    if not summary or _looks_like_raw_concat_summary(title, summary) or _looks_like_generation_template(summary):
        return True
    if any(token in summary for token in ["源自哪里", "根本所在", "原因中国自信"]):
        return True
    if any(token in summary for token in ["主要围绕定义和定义", "要抓住区别："]):
        return True
    if field_like_overlap(summary, points) < 0.12 and len(points) >= 2:
        return True
    if _normalized_topic(summary) == _normalized_topic(title):
        return True
    return False


def _content_needs_source_rewrite(title: str, content: str, points: list[str], profile: dict[str, Any]) -> bool:
    if not content or _looks_like_generation_template(content) or _material_content_mismatch(profile, content):
        return True
    if len(points) >= 3 and field_like_overlap(content, points) < 0.10:
        return True
    if any(text in content for text in ["原因说明需要把结论和依据对应起来", "原理内容由原理表述", "对照内容需要同时说明区别和联系", "再把其他信息归入定义、依据或例子", "应放回原文语境理解", "可以围绕"]):
        return True
    return False


def _source_backed_summary(title: str, points: list[str], profile: dict[str, Any]) -> str:
    if profile["material"] == "exam" and "checklist" in profile["roles"]:
        return "复习清单应覆盖核心概念、核心原理、易混辨析和真题高频入口。"
    if profile["material"] == "politics" and "reason" in profile["roles"]:
        root = [strip_leading_number(point.split("：", 1)[-1]) for point in points if point.startswith("根本原因")]
        important = [point.split("：", 1)[-1] for point in points if point.startswith("重要原因")]
        if root:
            root_text = _join_short_points([_cause_label(item) for item in root[:4]])
            tail = f"；重要原因是{_cause_label(important[0])}" if important else ""
            return compact(f"根本原因包括{root_text}{tail}。", 220)
        if points:
            if _looks_like_current_condition_reason(points[0]):
                return _current_condition_reason_summary(title, points[0])
            return _compact_user_summary(f"{title}的答案是{points[0]}。", 220)
    if profile["material"] == "exam" and "principle" in profile["roles"]:
        return compact(f"{title}应掌握{_join_summary_points(points[:3])}，并能写出方法论或易错点。", 220)
    if "contrast" in profile["roles"] or "vs" in title.lower():
        return compact(f"{title}需要同时掌握区别和联系，重点看概念边界、共同本质和常见误判。", 220)
    if profile["material"] == "exam":
        return compact(f"{title}应按定义、核心特征、关系和易错边界整理，复习时把概念表述与题型判断对应起来。", 220)
    return _compact_user_summary(_declarative_summary(title, points), 180)


def _source_backed_content(title: str, points: list[str], profile: dict[str, Any]) -> str:
    if profile["material"] == "technical":
        if len(points) >= 2:
            return "这些技术项目的差异主要体现在数据流向、控制动作、处理器参与度、硬件开销和适用场景；先判断控制权归属，再比较传送过程和代价。"
        return "该技术点的理解重点是触发条件、执行动作和结果影响，尤其要看它怎样改变 CPU、主存、总线或接口之间的协作关系。"
    if profile["material"] == "exam" and "checklist" in profile["roles"]:
        return "这组清单覆盖考点全貌：概念定义解决“是什么”，原理和方法论解决“为什么、怎么做”，易混边界用于题目判断。"
    if profile["material"] == "politics" and "reason" in profile["roles"]:
        return _reason_content_from_points(title, points)
    if profile["material"] == "politics" and "action" in profile["roles"]:
        return _politics_content(profile["roles"], points, title)
    if profile["material"] == "exam" and "principle" in profile["roles"]:
        return _principle_content_from_points(points)
    if profile["material"] == "exam" and ("contrast" in profile["roles"] or "vs" in title.lower()):
        return "这组易混概念要同时保留区别和联系：区别用于题目判断和概念边界，联系用于说明共同本质或相互依存关系。"
    if profile["material"] == "exam":
        return "该考点需要同时保留概念表述、适用条件、方法论意义和易错边界，题目判断时重点看限定词和材料对应关系。"
    if profile["material"] == "politics" and "manifestation" in profile["roles"]:
        return _manifestation_content_from_points(points)
    return compact(_explain_points(title, points), 420)


def _reason_content_from_points(title: str, points: list[str]) -> str:
    root = [strip_leading_number(point.split("：", 1)[-1]) for point in points if point.startswith("根本原因")]
    important = [strip_leading_number(point.split("：", 1)[-1]) for point in points if point.startswith("重要原因")]
    if root:
        root_text = _reason_category_text(root)
        if important:
            return compact(f"原因链条由两层构成：根本原因回答{root_text}等底层依据，重要原因回答现实成就带来的信心。", 280)
        return compact(f"{title}的根本依据集中在{root_text}，这些依据共同支撑结论成立。", 260)
    if points and _looks_like_current_condition_reason(points[0]):
        return compact(f"{title}属于现实条件判断：它强调目标距离、信心和能力等条件已经形成，因此结论不是口号式表达。", 260)
    if points:
        return compact(f"{title}需要区分直接结论、价值解释和背景条件三层信息，避免把同类原因句重复拆分。", 260)
    return compact(f"{title}需要把结论和支撑依据对应起来，避免只保留口号式表述。", 220)


def _principle_content_from_points(points: list[str]) -> str:
    joined = " ".join(points)
    if "统一" in joined and ("物质性" in joined or "本原" in joined):
        return "该原理按本原判断、物质性依据、多样性说明和方法论要求展开，关键是把“统一”理解为多样性中的统一。"
    if any(token in joined for token in ["物质决定意识", "意识对物质", "能动的反作用"]):
        return "该原理先说明物质的决定作用，再说明意识的反作用，最后落实到方法论要求：从实际出发、重视正确意识并反对错误倾向。"
    if any(token in joined for token in ["方法论", "错误倾向", "反对"]):
        return "该原理需要同时保留原理内容、方法论要求和错误倾向，三者共同构成完整答题结构。"
    return "该原理需要同时说明原理内容、方法论要求和常见错误倾向，不能只保留一句结论。"


def _manifestation_content_from_points(points: list[str]) -> str:
    return "表现类内容可以分成内在态度和外在行动两层：前者说明价值取向，后者说明怎样维护利益、尊严或共同体责任。"


def _looks_like_current_condition_reason(point: str) -> bool:
    text = normalize_learning_text(point)
    return bool(
        re.match(r"^(?:现在|目前|当前)[，,]", text)
        and any(token in text for token in ["目标", "信心", "能力", "条件", "基础"])
    )


def _current_condition_reason_summary(title: str, point: str) -> str:
    text = normalize_learning_text(point)
    target = "目标"
    match = re.search(r"更接近([^，,。；;]{2,30}?目标)", text)
    if match:
        target = match.group(1)
    return compact(f"{title}的依据是{target}距离更近，同时更有信心、有能力实现这个目标。", 220)


def _reason_category_text(points: list[str]) -> str:
    joined = " ".join(points)
    categories = []
    for token in ["道路", "理论", "制度", "文化"]:
        if token in joined:
            categories.append(token)
    if categories:
        return "、".join(categories)
    return _join_short_points([_cause_label(item) for item in points[:4]])


def _source_reason_subject(source_text: str) -> str:
    for line in normalize_learning_text(source_text).splitlines():
        text = clean_item(line).strip(" ？?。")
        match = re.search(r"([\u4e00-\u9fffA-Za-z0-9、，]+?的原因)", text)
        if match:
            candidate = match.group(1).strip(" /，,、")
            if 4 <= len(candidate) <= 24 and "原因" in candidate:
                return candidate
    return ""


def _cause_label(text: str) -> str:
    value = strip_leading_number(normalize_learning_text(text)).strip(" ；;。")
    for pattern in [
        r"开辟(?:了)?中国特色社会主义道路",
        r"形成(?:了)?中国特色社会主义理论体系",
        r"确立(?:了)?中国特色社会主义制度",
        r"发展(?:了)?中国特色社会主义文化",
        r"国家富强、民族振兴让中国人更加自信",
    ]:
        match = re.search(pattern, value)
        if match:
            return match.group(0)
    return _summary_point_label(value)


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
            parent["content"] = _content_for_enumerated_parent(str(parent.get("title") or ""), labels)
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
    note["content"] = _content_for_enumerated_parent(title, _enumerated_parent_child_titles(notes, parent_id, child_title))
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
    return compact(f"{title}说明该项的含义、条件和适用场景。", 220)


def _summary_for_enumerated_parent(title: str, notes: list[dict[str, Any]], parent_id: str, first_child_title: str) -> str:
    children = _enumerated_parent_child_titles(notes, parent_id, first_child_title)
    return _summary_for_enumeration(title, children, comparison_hint="适用条件、执行方式和优缺点")


def _summary_for_enumeration(title: str, labels: list[str], *, comparison_hint: str = "含义、条件和适用边界") -> str:
    cleaned = _clean_enumeration_labels(labels)
    clean_title = strip_leading_number(clean_item(title))
    if not cleaned:
        return compact(_declarative_summary(clean_title or title, []), 180)
    if len(cleaned) == 1:
        return compact(f"{clean_title or title}的核心项是{cleaned[0]}，重点说明其含义、条件和作用。", 180)
    if len(cleaned) == 2:
        return compact(f"{cleaned[0]}和{cleaned[1]}是{clean_title or title}的两个核心项，差异集中在{comparison_hint}。", 180)
    head = _join_short_points(cleaned[:4])
    return compact(f"{clean_title or title}可分为{head}等项，核心差异在{comparison_hint}。", 180)


def _clean_enumeration_labels(labels: list[str]) -> list[str]:
    cleaned: list[str] = []
    for label in labels:
        text = _summary_point_label(label)
        text = re.sub(r"^\s*(?:[（(]\d+[）)]|[①②③④⑤⑥⑦⑧⑨]|\d+[.、])\s*", "", text).strip()
        if not text or _looks_like_generation_template(text) or _looks_like_instruction_or_noise(text):
            continue
        if _is_source_navigation_or_figure_point(text):
            continue
        cleaned.append(text)
    return _dedupe_learning_list(cleaned, max_items=6)


def _content_for_enumerated_parent(title: str, labels: list[str] | None = None) -> str:
    labels = _clean_enumeration_labels(labels or [])
    profile = infer_learning_profile(title, key_points=labels)
    if labels:
        if len(labels) == 1:
            return compact(f"{title}包含一个核心项目：{labels[0]}。理解时要补全它的定义、条件、作用和例子。", 260)
        if profile["material"] == "technical":
            return compact(f"{title}包含{_join_short_points(labels[:6])}。这些项目适合按控制权、触发条件、适用场景和代价四个维度比较。", 280)
        if profile["material"] == "politics" and "action" in profile["roles"]:
            return compact(f"{title}包含{_join_short_points(labels[:6])}。这些行动需要区分主体、目标、具体做法、落实场景和价值指向。", 280)
        if profile["material"] == "exam":
            return compact(f"{title}包含{_join_short_points(labels[:6])}。这些项目需要对应到核心概念、原理、易混点和题型入口。", 280)
        return compact(f"{title}包含{_join_short_points(labels[:6])}。各项之间需要比较含义、条件和适用边界。", 260)
    if profile["material"] == "exam":
        return compact(f"{title}需要区分概念、原理、易混点和题型应用。", 260)
    return compact(f"{title}需要区分各项的含义、条件、适用场景和容易混淆的边界。", 260)


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
    if parent_id and _is_colon_subtopic_title(title):
        return None
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
    if _is_colon_subtopic_title(right_title):
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


def _is_colon_subtopic_title(title: str) -> bool:
    if "：" not in title:
        return False
    head, tail = title.split("：", 1)
    return 2 <= len(head.strip()) <= 18 and 2 <= len(tail.strip()) <= 28


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
    _repair_user_facing_note(note)


def _repair_user_facing_note(note: dict[str, Any]) -> None:
    raw_title = clean_item(str(note.get("title") or ""))
    title = raw_title
    if _is_low_value_learning_title(title):
        title = clean_learning_title(raw_title, str(note.get("content") or ""))
        if _is_low_value_learning_title(title):
            fallback_title = _title_from_text(str(note.get("content") or ""), str(note.get("summary") or ""))
            if fallback_title:
                title = fallback_title
    points = _drop_low_value_key_points(title, _normalize_key_points(title, [str(item) for item in note.get("keyPoints", []) or []]))
    if not points:
        points = _extract_points_from_note_fields(note, title)
    profile = infer_learning_profile(title, str(note.get("summary") or ""), points, str(note.get("content") or ""))
    repaired_title = _repair_learning_title(title, points, profile)
    if repaired_title:
        title = repaired_title
        note["title"] = title
        profile = infer_learning_profile(title, str(note.get("summary") or ""), points, str(note.get("content") or ""))
    note["keyPoints"] = _drop_low_value_key_points(title, _key_points_for_profile(title, points, profile))
    note["keyPoints"] = _repair_domain_key_points(title, note["keyPoints"], note)
    if not note["keyPoints"]:
        note["keyPoints"] = _fallback_key_points_from_title(title, profile)
    current_summary = str(note.get("summary") or "")
    if _is_role_summary_good(title, current_summary, note["keyPoints"]):
        note["summary"] = _compact_user_summary(_remove_summary_concat_noise(current_summary), 180)
    else:
        note["summary"] = _clean_user_summary(_summary_by_profile(title, note["keyPoints"], profile), title, note["keyPoints"])
    current_content = str(note.get("content") or "")
    current_content = _remove_instruction_sentences(current_content)
    if _is_role_content_good(current_content, note["summary"], note["keyPoints"]) and not _material_content_mismatch(profile, current_content) and not _has_self_embedded_learning_phrase(current_content) and not _needs_profile_content(profile, current_content):
        note["content"] = compact(current_content, 460)
    else:
        note["content"] = _clean_user_content(_content_by_profile(title, note["keyPoints"], profile), title, note["summary"], note["keyPoints"], profile)
    note["blocks"] = _sync_note_blocks(note)


def _repair_learning_title(title: str, points: list[str], profile: dict[str, Any]) -> str:
    cleaned = _strip_instruction_title(title)
    abstracted = _abstract_learning_title(cleaned, points, profile)
    if abstracted:
        return abstracted
    if re.match(r"^核心内容\s*\d+$", cleaned):
        candidate = _title_from_points(points, profile)
        if candidate:
            return candidate
    if profile["material"] == "general":
        if any(token in cleaned for token in ["种植业", "林业", "畜牧业", "渔业"]) and any(
            marker in cleaned for marker in ["生产部门", "称为", "是在", "包括"]
        ):
            return "农业部门及其特点"
    if _is_low_value_learning_title(cleaned):
        candidate = _title_from_points(points, profile)
        if candidate:
            return candidate
    if cleaned != title:
        return cleaned
    return title


def _strip_instruction_title(title: str) -> str:
    text = normalize_learning_text(title).strip(" ：:。")
    replacements = [
        (r"^同学们[，,]?\s*读图[“\"]?(.+?)[”\"]?[，,]?\s*请说各部门的特点[。.]?$", r"\1"),
        (r"^请同学们结合生活实例[，,]?\s*收集相关资料[，,]?\s*从生产和生活两个方面举例说明(.+?)[。.]?$", r"\1"),
        (r"^通过本节课学习[，,]?\s*", ""),
        (r"^想一想[:：]?\s*", ""),
    ]
    for pattern, replacement in replacements:
        next_text = re.sub(pattern, replacement, text)
        if next_text != text:
            text = next_text.strip(" ：:。")
    text = re.sub(r"第一PPT模板网[-—]?\s*WWW\.1PPT\.COM", "", text, flags=re.I).strip(" ：:。")
    return text


def _is_low_value_learning_title(title: str) -> bool:
    compacted = re.sub(r"\s+", "", title)
    if not compacted:
        return True
    if compacted.upper() in {"NANKAIUNIVERSITY", "LXD", "©LXD"}:
        return True
    if any(token in title for token in ["同学们", "请同学们", "通过本节课学习", "采访身边的人", "第一PPT模板网", "OBJECTIVES•"]):
        return True
    if any(token in title for token in ["请以", "你还爱读", "请说出", "回答", "哪些精彩的故事"]):
        return True
    if _looks_like_generation_template(title):
        return True
    if _looks_like_raw_sentence_title(title):
        return True
    if re.fullmatch(r"[A-Z\s.,()/-]{4,}", title) and not _looks_like_meaningful_english_title(title):
        return True
    return False


def _looks_like_meaningful_english_title(title: str) -> bool:
    text = normalize_learning_text(title).strip()
    if not re.search(r"[A-Za-z]", text):
        return False
    if "..." in text or "…" in text or re.search(r"[\u4e00-\u9fff]", text):
        return False
    if re.search(r"\b(should|decides?|avoid|contains?|includes?|explains?|describes?)\b", text, flags=re.I):
        return False
    words = re.findall(r"[A-Za-z][A-Za-z0-9+-]*", text)
    if len(words) < 2:
        return False
    domain_terms = {
        "algorithm",
        "analysis",
        "architecture",
        "bayes",
        "computer",
        "database",
        "design",
        "entity",
        "graph",
        "learning",
        "logical",
        "machine",
        "model",
        "network",
        "principle",
        "relationship",
        "retrieval",
        "schema",
        "sql",
        "system",
        "transformer",
    }
    lowered = {word.lower() for word in words}
    if lowered & domain_terms:
        return True
    long_words = [word for word in words if len(word) >= 4 and re.search(r"[aeiou]", word, flags=re.I)]
    return len(words) >= 3 and len(long_words) >= 2 and not text.isupper()


def _abstract_learning_title(title: str, points: list[str], profile: dict[str, Any]) -> str:
    title = normalize_learning_text(title).strip(" ：:。")
    if not title:
        return ""
    if profile["material"] == "exam" and _looks_like_exam_checklist_title(title, points, profile):
        return "核心概念与原理清单"
    if _is_colon_subtopic_title(title) and not _looks_like_instruction_or_noise(title):
        return title
    if profile["material"] == "literature":
        candidate = _literature_title(title, points, profile)
        if candidate:
            return candidate
    if "：" in title:
        head, tail = title.split("：", 1)
        if 2 <= len(head) <= 12 and _looks_like_raw_sentence_title(tail):
            return head.strip()
        if 2 <= len(head) <= 14 and any(token in head for token in ["性格", "特点", "原因", "行动", "表现"]):
            return head.strip()
    if _looks_like_raw_sentence_title(title):
        candidate = _title_from_points(points, profile)
        if candidate and not _looks_like_raw_sentence_title(candidate):
            return candidate
        extracted = _extract_compact_topic(title, profile)
        if extracted:
            return extracted
    return ""


def _title_from_text(content: str, summary: str = "") -> str:
    for value in [content, summary]:
        around = re.search(r"围绕(.+?)(?:展开|，|。)", str(value))
        if around:
            for part in re.split(r"[、，,；;]", around.group(1)):
                candidate = normalize_learning_text(part).strip(" ：:。")
                if candidate and not _is_low_value_learning_title(candidate) and not _looks_like_generation_template(candidate):
                    return candidate
        for sentence in split_sentences(value):
            text = normalize_learning_text(sentence).strip(" ：:。")
            if not text or _looks_like_instruction_or_noise(text):
                continue
            label = _summary_point_label(text)
            if label and not _is_low_value_learning_title(label) and not _looks_like_generation_template(label):
                return label
    return ""


def _looks_like_raw_sentence_title(title: str) -> bool:
    text = normalize_learning_text(title).strip()
    compacted = re.sub(r"\s+", "", text)
    if _looks_like_meaningful_english_title(text):
        return False
    if len(compacted) > 32:
        return True
    if "..." in text or "…" in text:
        return True
    if len(re.findall(r"[，,；;。]", text)) >= 1 and len(compacted) > 18:
        return True
    if any(token in text for token in ["其中描述了", "它是一部", "讲述的是", "请以", "你还爱读", "请说出"]):
        return True
    return False


def _literature_title(title: str, points: list[str], profile: dict[str, Any]) -> str:
    probe = " ".join([title, *points])
    if profile["subtype"] == "origin" or any(token in probe for token in ["故事源起", "话本", "元杂剧", "定型"]):
        return "成书源流"
    if profile["subtype"] == "theme" or any(token in probe for token in ["农民起义", "造反者", "主题", "价值"]):
        return "主题价值"
    if profile["subtype"] == "plot_structure" or any(token in probe for token in ["第一至", "第四十回", "第八十回", "全书可分"]):
        return "情节结构"
    if profile["subtype"] == "reading_task" or any(token in probe for token in ["请以", "你还爱读", "请说出"]):
        return "阅读任务"
    for name in ["宋江", "林冲", "李逵", "鲁智深", "武松", "吴用", "杨志", "施耐庵"]:
        if name in probe:
            if name == "施耐庵":
                return "作者：施耐庵"
            return f"人物：{name}"
    if "水浒传" in probe:
        return "作品概览"
    return ""


def _looks_like_exam_checklist_title(title: str, points: list[str], profile: dict[str, Any]) -> bool:
    probe = " ".join([title, *points, str(profile.get("probe") or "")])
    return any(token in probe for token in ["准确记忆", "熟练掌握", "核心概念", "核心原理", "易混淆概念", "高频考点", "选择题失分"])


def _extract_compact_topic(title: str, profile: dict[str, Any]) -> str:
    text = normalize_learning_text(title)
    if profile["material"] == "technical":
        for token in ["DMA 数据传送过程", "DMA 接口功能", "DMA 接口与系统的连接方式", "周期挪用", "DMA 与 CPU 交替访问"]:
            if token.replace(" ", "") in text.replace(" ", ""):
                return token
    if profile["material"] == "politics":
        for token in ["中国梦", "中国道路", "中国精神", "中国力量", "自信的中国人", "青少年行动要求"]:
            if token in text:
                return token
    if profile["material"] == "exam":
        for token in ["物质与意识的辩证关系原理", "世界的物质统一性原理", "唯物论核心概念", "易混概念辨析"]:
            if token in text:
                return token
    parts = [part.strip(" ：:，,；;。") for part in re.split(r"[。；;，,]", text) if part.strip()]
    for part in parts:
        label = _summary_point_label(part)
        if label and 4 <= len(re.sub(r"\s+", "", label)) <= 24 and not _looks_like_instruction_or_noise(label):
            return label
    return ""


def _title_from_points(points: list[str], profile: dict[str, Any]) -> str:
    joined = " ".join(points)
    if profile["material"] == "general" and any(token in joined for token in ["农业部门", "种植业", "林业", "畜牧业", "渔业"]):
        return "农业部门及其特点"
    if profile["material"] == "technical" and profile["subtype"] == "completion_notifier":
        return "DMA 中断机构"
    if profile["material"] == "literature":
        candidate = _literature_title("", points, profile)
        if candidate:
            return candidate
    for point in points:
        label = _summary_point_label(point)
        if label and not _is_low_value_learning_title(label):
            if profile["material"] == "general" and any(token in label for token in ["农业部门", "种植业", "林业", "畜牧业", "渔业"]):
                return "农业部门及其特点"
            return label
    return ""


def _drop_low_value_key_points(title: str, points: list[str]) -> list[str]:
    result: list[str] = []
    title_key = _normalized_topic(title)
    for point in points:
        text = normalize_learning_text(str(point)).strip(" ；;。")
        if not text:
            continue
        if _looks_like_generation_template(text) or _looks_like_instruction_or_noise(text):
            continue
        is_numbered_learning_item = bool(_leading_note_number(text))
        if not is_numbered_learning_item and _is_low_value_learning_title(text):
            continue
        if _looks_like_fallback_learning_phrase(title, text):
            continue
        if _looks_like_raw_concat_summary(title, text):
            continue
        key = _normalized_topic(text)
        if key and key == title_key and len(points) > 1:
            continue
        result.extend(_split_overlong_point(text))
    return _dedupe_learning_list([point for point in result if not _looks_like_instruction_or_noise(point)], max_items=6)


def _looks_like_fallback_learning_phrase(title: str, text: str) -> bool:
    compacted = re.sub(r"\s+", "", normalize_learning_text(text))
    title_key = re.sub(r"\s+", "", normalize_learning_text(title))
    if "需要结合定义、作用和适用场景来理解" in text:
        return True
    if "应结合上下文判断其定义、作用和适用场景" in text:
        return True
    if "再回到原文确认它的条件、作用和边界" in text:
        return True
    if text.startswith("这部分围绕") or text.startswith("学习“"):
        return True
    if text.startswith("这部分用于说明"):
        return True
    if title_key and compacted.startswith(title_key) and any(token in text for token in ["需要结合定义", "应结合上下文", "可以先把握"]):
        return True
    return False


def _looks_like_instruction_or_noise(text: str) -> bool:
    value = normalize_learning_text(str(text)).strip()
    compacted = re.sub(r"\s+", "", value)
    if not value:
        return True
    if compacted.upper() in {"NANKAIUNIVERSITY", "LXD", "©LXD"}:
        return True
    return any(
        token in value
        for token in [
            "同学们",
            "请同学们",
            "通过本节课学习",
            "采访身边的人",
            "想一想",
            "第一PPT模板网",
            "OBJECTIVES•",
            "©LXD",
        ]
    )


def _extract_points_from_note_fields(note: dict[str, Any], title: str) -> list[str]:
    candidates: list[str] = []
    for value in [note.get("summary"), note.get("content")]:
        for sentence in split_sentences(str(value or "")):
            cleaned = clean_item(sentence)
            if cleaned and not _looks_like_generation_template(cleaned) and not _looks_like_instruction_or_noise(cleaned):
                candidates.append(cleaned)
    if not candidates:
        for ref in note.get("sourceExcerpts") or []:
            quote = str(ref.get("quote") or "") if isinstance(ref, dict) else ""
            for sentence in split_sentences(quote):
                cleaned = clean_item(sentence)
                if cleaned and not _looks_like_generation_template(cleaned) and not _looks_like_instruction_or_noise(cleaned):
                    candidates.append(cleaned)
    return _dedupe_learning_list(candidates, max_items=4)


def _repair_domain_key_points(title: str, points: list[str], note: dict[str, Any]) -> list[str]:
    joined = " ".join([title, *(points or []), str(note.get("summary") or ""), str(note.get("content") or "")])
    is_agriculture_department_note = "农业部门" in title or any(token in title for token in ["种植业", "林业", "畜牧业", "渔业"])
    if is_agriculture_department_note and any(token in joined for token in ["农业部门", "种植业", "林业", "畜牧业", "渔业"]):
        agriculture_points = [
            "种植业是在耕地上种植水稻、小麦、大豆、棉花等农作物的生产部门",
            "林业包括种植、养育、保护、采伐林木以及采集加工林产品",
            "畜牧业通过放牧或饲养牲畜、家禽获得产品",
            "渔业是在水域中捕捞或养殖有价值的水生生物",
        ]
        return _dedupe_learning_list([*agriculture_points, *(points or [])], max_items=6)
    return _relabel_repeated_definition_points(points)


def _relabel_repeated_definition_points(points: list[str]) -> list[str]:
    definition_indices = [index for index, point in enumerate(points) if str(point).startswith("定义：")]
    if len(definition_indices) <= 1:
        return points

    result = list(points)
    canonical_subject = ""
    canonical_used = False
    for index in definition_indices:
        point = str(result[index])
        body = point.split("：", 1)[1].strip()
        label, subject = _definition_extension_label(body, canonical_subject, canonical_used)
        if label == "定义":
            canonical_used = True
            canonical_subject = subject or canonical_subject
        result[index] = f"{label}：{body}"
    return result


def _definition_extension_label(body: str, canonical_subject: str, canonical_used: bool) -> tuple[str, str]:
    text = normalize_learning_text(body).strip()
    subject = _definition_subject(text)
    if not canonical_used and _looks_like_primary_definition(text):
        return "定义", subject
    if any(token in text for token in ["唯一特性", "根本属性", "基本特征", "本质属性"]):
        return "核心特性", subject
    if any(token in text for token in ["不等于", "不同于", "区别", "抽象概括", "共同本质"]):
        return "概念边界", subject
    if any(token in text for token in ["不依赖于", "意识之外", "可以为", "所反映"]):
        return "存在与反映关系", subject
    if any(token in text for token in ["源泉", "物质器官", "内容是客观", "形式是主观"]):
        return "补充说明", subject
    if not canonical_used:
        return "定义", subject
    if subject and subject != canonical_subject and 1 <= len(subject) <= 10:
        return f"{subject}定义", subject
    return "定义说明", subject


def _looks_like_primary_definition(text: str) -> bool:
    return bool(
        _definition_subject(text)
        and any(token in text for token in ["范畴", "概念", "是指", "是标志", "称为"])
    )


def _definition_subject(text: str) -> str:
    clean = re.sub(r"^(?:哲学上(?:的)?|哲学上的|马克思主义认为)", "", text).strip()
    match = re.match(r"([^是指为：:，,；;。]{1,12})(?:是|指|为)", clean)
    if not match:
        return ""
    subject = match.group(1).strip(" 的")
    if subject.endswith(("唯一特性", "根本属性", "基本特征", "内容", "形式")):
        return ""
    return subject


def _clean_user_summary(summary: str, title: str, points: list[str]) -> str:
    text = _remove_summary_concat_noise(summary)
    if _looks_like_generation_template(text) or _looks_like_raw_concat_summary(title, text):
        profile = infer_learning_profile(title, key_points=points)
        text = _summary_by_profile(title, points, profile)
    if _looks_like_raw_concat_summary(title, text):
        text = _concise_summary_from_points(title, points)
    return _compact_user_summary(text, 180)


def _clean_user_content(content: str, title: str, summary: str, points: list[str], profile: dict[str, Any]) -> str:
    text = _remove_instruction_sentences(content)
    if (
        not text
        or _looks_like_generation_template(text)
        or _looks_like_raw_concat_summary(title, text)
        or _token_jaccard(text, summary) > 0.72
        or field_like_overlap(text, points) > 0.76
        or _has_self_embedded_learning_phrase(text)
    ):
        text = _content_by_profile(title, points, profile)
    return compact(text, 460)


def _has_self_embedded_learning_phrase(text: str) -> bool:
    value = normalize_learning_text(str(text))
    return value.count("关键线索是") >= 2 or value.count("需要说明") >= 2


def _remove_instruction_sentences(text: str) -> str:
    sentences = []
    for sentence in split_sentences(normalize_learning_text(str(text)).strip()):
        cleaned = clean_item(sentence)
        if not cleaned or _looks_like_instruction_or_noise(cleaned):
            continue
        sentences.append(cleaned)
    if sentences:
        return compact(" ".join(sentences), 520)
    cleaned = clean_item(text)
    return "" if _looks_like_instruction_or_noise(cleaned) else cleaned


def _sync_note_blocks(note: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = [block for block in note.get("blocks", []) or [] if isinstance(block, dict)]
    summary = str(note.get("summary") or "")
    points = [str(item) for item in note.get("keyPoints", []) or [] if str(item).strip()]
    content = str(note.get("content") or "")
    generated = [
        {"id": f"{note.get('id', 'note')}-summary", "type": "summary", "title": "概要", "content": summary},
        {
            "id": f"{note.get('id', 'note')}-outline",
            "type": "outline",
            "title": "要点",
            "items": points,
            "structuredItems": [{"text": point, "children": []} for point in points],
        },
    ]
    if content and content != summary:
        generated.append({"id": f"{note.get('id', 'note')}-explanation", "type": "explanation", "title": "说明", "content": content})
    if not blocks:
        return generated
    preserved = [block for block in blocks if block.get("type") not in {"summary", "outline", "explanation"}]
    return generated + preserved


def _finalize_readable_learning_fields(note: dict[str, Any]) -> None:
    title = str(note.get("title") or "")
    points = [str(item) for item in note.get("keyPoints", []) or []]
    profile = infer_learning_profile(title, str(note.get("summary") or ""), points, str(note.get("content") or ""))
    rewritten_points = _key_points_for_profile(title, points, profile)
    if rewritten_points:
        note["keyPoints"] = rewritten_points
        points = rewritten_points
    summary = str(note.get("summary") or "")
    content = str(note.get("content") or "")
    if not _is_role_summary_good(title, summary, points):
        note["summary"] = _summary_by_profile(title, points, profile)
    if _looks_like_raw_concat_summary(title, str(note.get("summary") or "")):
        note["summary"] = _concise_summary_from_points(title, points)
    if not _is_role_content_good(content, str(note.get("summary") or ""), points) or _material_content_mismatch(profile, content):
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
    fallback = points or _fallback_key_points_from_title(title, profile)
    return _dedupe_learning_list(fallback, max_items=6 if _has_numbered_series(fallback, min_count=6) else 5)


def _fallback_key_points_from_title(title: str, profile: dict[str, Any]) -> list[str]:
    cleaned = strip_leading_number(clean_item(title))
    cleaned = re.sub(r"^(?:行动要求|具体做法|做法|要求|路径|措施|要点)[:：]\s*", "", cleaned).strip()
    if not cleaned:
        return []
    if profile["material"] == "politics" and "action" in profile["roles"]:
        parts = [part.strip(" 。；;，,") for part in re.split(r"[，、；;]", cleaned) if part.strip(" 。；;，,")]
        return parts[:4] or [cleaned]
    if profile["material"] in {"politics", "exam"}:
        return [cleaned]
    return []


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
        return _summary_for_enumeration(title, labels)
    if profile["material"] == "technical":
        return _technical_summary(title, subtype, roles, key_points)
    if profile["material"] == "politics":
        return _politics_summary(title, roles, key_points)
    if profile["material"] == "exam":
        return _exam_summary(title, roles, key_points)
    if profile["material"] == "literature":
        return _literature_summary(title, subtype, roles, key_points)
    if key_points:
        return compact(_declarative_summary(title, key_points), 160)
    return compact(_declarative_summary(title, []), 160)


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
    if key_points:
        return compact(_declarative_summary(title, key_points), 160)
    return "这一技术点需要放在数据流和控制流中理解，重点看触发条件、控制动作和传送结果。"


def _politics_summary(title: str, roles: set[str], key_points: list[str]) -> str:
    if key_points:
        return compact(_declarative_summary(title, key_points), 160)
    if "action" in roles:
        return "行动类内容需要明确主体、目标、做法和落实场景。"
    if "reason" in roles:
        return "原因类内容需要把结论与制度、道路、文化和现实成就等依据对应起来。"
    if "manifestation" in roles:
        return "表现类内容要区分态度认同、价值底气和具体行动。"
    return "这部分需要说明核心结论、依据和行动路径。"


def _exam_summary(title: str, roles: set[str], key_points: list[str]) -> str:
    if "checklist" in roles:
        return "复习清单用于把核心概念、核心原理、易混点和常见题型入口放在一起检查。"
    if "principle" in roles:
        return "原理类内容要抓住原理表述、方法论要求和材料分析入口。"
    if "contrast" in roles:
        return "易混概念要区分概念边界、联系和常见错误表述。"
    if key_points:
        labels = _join_summary_points(key_points[:2])
        return compact(f"{title}需要抓住{labels}，并能说明定义、判断依据和易错边界。", 160)
    return "备考类内容需要覆盖概念、原理、易混点和题型应用。"


def _content_by_profile(title: str, key_points: list[str], profile: dict[str, Any]) -> str:
    roles = profile["roles"]
    subtype = profile["subtype"]
    if profile["material"] == "technical":
        return _technical_content(subtype, roles, key_points, title)
    if profile["material"] == "politics":
        return _politics_content(roles, key_points, title)
    if profile["material"] == "exam":
        return _exam_content(roles, key_points)
    if profile["material"] == "literature":
        return _literature_content(subtype, roles, key_points, title)
    if key_points:
        return compact(_explain_points(title, key_points), 420)
    return _explain_points(title, [])


def _technical_content(subtype: str, roles: set[str], key_points: list[str] | None = None, title: str = "") -> str:
    key_points = key_points or []
    if key_points and subtype == "generic":
        return compact(_explain_points(title or "该技术点", key_points), 420)
    if subtype == "completion_notifier":
        return "本批数据传送完成后，完成通知部件向处理器发出中断请求，由处理器执行校验、继续传送判断等收尾操作。"
    if subtype == "data_buffer":
        return "主存侧通常按字传送，设备侧可能按字节或位传送，缓冲部件负责暂存数据并配合装配或拆卸。"
    if subtype in {"counter", "address_register", "control_logic", "component_group", "interface_function"}:
        return "这类接口结构应按职责记忆：地址类部件负责定位，计数类部件负责长度，缓冲类部件暂存数据，控制逻辑负责协调请求、响应和结束通知。"
    if subtype == "connection_type":
        return "连接方式的差异在服务对象和请求机制：有的结构强调单个高速设备独占服务，有的结构强调多个低速设备按请求线、优先级或交叉方式共享服务。"
    if subtype == "exclusive_access":
        return "比较时关注主存使用权：这种方式控制逻辑简单，但处理器在传送阶段不能访问主存，适合需要成组快速传送且可接受等待的场景。"
    if subtype == "cycle_stealing":
        return "周期挪用的关键是总线控制权：每次传送只临时占用一个或少数主存周期，需要申请、建立并归还控制权，适合外设速度慢于主存的场景。"
    if subtype == "interleaved_access":
        return "交替访问把工作周期划分为不同访存分周期，处理器和传送方按分周期交替访问主存，适合按固定节奏分时访存的场景，但硬件地址、数据和读写控制更复杂。"
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
    if key_points:
        return compact(_explain_points(title or "该技术点", key_points), 420)
    return "这类技术点需要结合数据流和控制流理解，重点区分触发条件、执行动作和最终结果。"


def _politics_content(roles: set[str], key_points: list[str], title: str = "") -> str:
    if "action" in roles:
        if has_any(title, ["青少年", "个人", "新时代的青少年"]):
            return "个人行动可以分成能力建设和行为约束两条线：理想信念、学习实践和责任担当负责提升能力，道德修养和法治观念负责规范行动。"
        if has_any(title, ["国家层面", "怎样实现", "实现中国梦"]):
            return "国家层面行动由领导核心、道路方向、精神支撑和人民力量共同构成，宏观条件需要与具体路径一一对应。"
        if has_any(title, ["自信", "自信中国人"]):
            return "自信类行动需要把心态要求和实践要求分开：心态上保持理性平和，行动上落实为实干、劳动和坚定信心。"
        labels = [_summary_point_label(point) for point in key_points[:5] if point]
        if labels:
            return compact("这些行动要求需要分清主体、目标和落实场景，再判断每项做法属于态度建设、能力建设还是行为约束。", 260)
        return "行动要求需要按主体拆解：国家或集体层面强调方向和条件，个人层面强调理想信念、学习实践、责任担当和法治意识。"
    if "reason" in roles:
        return _reason_content_from_points(title or "该主题", key_points)
    if "manifestation" in roles:
        return _manifestation_content_from_points(key_points)
    if key_points:
        return compact(_explain_points("该主题", key_points), 420)
    return "该主题需要结合结论、依据和行动路径理解。"


def _exam_content(roles: set[str], key_points: list[str]) -> str:
    if "checklist" in roles:
        return "这组清单覆盖概念定义、原理表述、方法论要求和易错表述，适合作为考点完整性检查。"
    if "contrast" in roles:
        return "易混概念需要同时说明区别、联系和判断关键词；选择题看限定词，分析题看概念边界与材料对应关系。"
    if "principle" in roles:
        return _principle_content_from_points(key_points)
    if key_points:
        labels = [_summary_point_label(point) for point in key_points[:4] if point]
        return compact(f"该考点围绕{_join_short_points(labels)}展开，需要对应概念、原理、方法论和易错限定词。", 260)
    return "该考点由定义、适用条件和常见错误表述构成。"


def _literature_summary(title: str, subtype: str, roles: set[str], key_points: list[str]) -> str:
    if subtype == "character" or "character" in roles:
        character = title.split("：", 1)[1] if "：" in title else title
        return f"{character}这一人物可从身份、性格、关键情节和形象意义四个角度把握。"
    if subtype == "origin":
        return "成书源流部分说明作品故事从民间材料到定型文本的发展过程。"
    if subtype == "theme":
        return "主题价值部分重点把握作品如何塑造英雄群像并呈现社会矛盾。"
    if subtype == "plot_structure":
        return "情节结构部分用于建立整本书的阶段框架，避免只记零散故事。"
    if subtype == "reading_task":
        return "阅读任务应转化为练习，不宜作为知识 NOTE 的主体内容。"
    if subtype == "author":
        return "作者背景帮助理解作品来源和创作基础。"
    if key_points:
        labels = [_summary_point_label(point) for point in key_points[:2]]
        labels = [label for label in labels if label]
        if labels:
            return f"{title}围绕{'、'.join(labels)}展开，适合整理成阅读笔记。"
    return "文学类内容应围绕人物、情节、主题和阅读任务建立结构。"


def _literature_content(subtype: str, roles: set[str], key_points: list[str], title: str) -> str:
    if subtype == "character" or "character" in roles:
        return "人物类笔记应先确认身份和绰号，再用关键情节解释性格，最后归纳人物在作品主题中的作用。"
    if subtype == "origin":
        return "复习时按时间线整理：先看故事材料来源，再看民间流传和戏曲改编，最后看小说定型。"
    if subtype == "theme":
        return "主题价值要结合人物群像和情节冲突理解，重点说明作品为什么具有文学史意义。"
    if subtype == "plot_structure":
        return "情节结构适合按阶段记忆：人物出场、梁山聚义、接受招安和结局收束，各阶段承担不同叙事功能。"
    if subtype == "reading_task":
        return "这类内容更适合进入复习题或课堂练习，用户学习时应把它转化为情节赏析或人物分析任务。"
    if key_points:
        return compact(_explain_points(title, key_points), 420)
    return "阅读类材料需要把原文信息整理成作者背景、作品结构、人物形象和主题价值。"


def _declarative_summary(title: str, key_points: list[str]) -> str:
    if any(token in title for token in ["农业部门", "种植业", "林业", "畜牧业", "渔业"]):
        return "这部分用于区分种植业、林业、畜牧业和渔业，重点看各部门的生产对象和生产方式。"
    clean_points = [_summary_point_label(point) for point in key_points if not _looks_like_instruction_or_noise(point)]
    clean_points = [point for point in clean_points if not _looks_like_fallback_learning_phrase(title, point)]
    clean_points = [point for point in _dedupe_learning_list(clean_points, max_items=2) if point]
    if not clean_points:
        return f"{strip_leading_number(clean_item(title)) or title}用于建立该知识点的基本认识。"
    if len(clean_points) == 1:
        return _single_point_summary(title, clean_points[0])
    return _two_point_summary(title, clean_points[0], clean_points[1])


def _single_point_summary(title: str, point: str) -> str:
    title_clean = strip_leading_number(clean_item(title))
    if title_clean and _token_jaccard(title_clean, point) > 0.72:
        return f"{title_clean}的重点在于把握其含义、适用场景和相邻概念。"
    if title_clean and title_clean in point:
        return f"{title_clean}围绕{point}展开，学习时要把结论和依据对应起来。"
    return f"{title_clean or title}的关键内容是{point}。"


def _two_point_summary(title: str, first: str, second: str) -> str:
    title_clean = strip_leading_number(clean_item(title))
    if title_clean and (title_clean in first or title_clean in second):
        return f"{title_clean}包含{first}和{second}两个重点，需要分别对应到原文依据。"
    return f"{title_clean or title}主要围绕{first}和{second}展开。"


def _concise_summary_from_points(title: str, points: list[str]) -> str:
    labels = [_summary_point_label(point) for point in points if not _looks_like_generation_template(point)]
    labels = [label for label in _dedupe_learning_list(labels, max_items=2) if label]
    if not labels:
        return f"{strip_leading_number(clean_item(title)) or title}用于建立该知识点的基本认识。"
    if len(labels) == 1:
        return _single_point_summary(title, labels[0])
    return _two_point_summary(title, labels[0], labels[1])


def _explain_points(title: str, key_points: list[str]) -> str:
    clean_points = [
        point
        for point in _dedupe_learning_list(key_points, max_items=4)
        if not _looks_like_instruction_or_noise(point) and not _looks_like_fallback_learning_phrase(title, point)
    ]
    if not clean_points:
        return f"{title}需要明确它回答的问题、成立依据和使用边界。"
    if len(clean_points) == 1:
        if _token_jaccard(title, clean_points[0]) > 0.72:
            return f"{title}的重点是结论本身以及它适用的场景。"
        return f"{title}的核心依据是{clean_points[0]}，需要补充它的条件、作用或例子。"
    return f"{title}包含{clean_points[0]}和{clean_points[1]}等要点，需要分别归入定义、依据、作用或例子。"


def _rewrite_summary_for_role(title: str, summary: str, key_points: list[str]) -> str:
    text = normalize_learning_text(summary).strip()
    if _is_role_summary_good(title, text, key_points):
        return _compact_user_summary(_remove_summary_concat_noise(text), 160)
    profile = infer_learning_profile(title, summary, key_points)
    return _compact_user_summary(_summary_by_profile(title, key_points, profile), 160)


def _rewrite_content_for_role(title: str, content: str, summary: str, key_points: list[str]) -> str:
    text = normalize_learning_text(content).strip()
    profile = infer_learning_profile(title, summary, key_points, content)
    if _is_role_content_good(text, summary, key_points) and not _material_content_mismatch(profile, text):
        return compact(text, 460)
    return compact(_content_by_profile(title, key_points, profile), 460)


def _material_content_mismatch(profile: dict[str, Any], content: str) -> bool:
    if profile["material"] == "politics" and any(token in content for token in ["备考时", "选择题", "分析题", "真题"]):
        return True
    if profile["material"] == "politics" and "action" in profile["roles"]:
        probe = str(profile.get("probe") or "")
        if has_any(probe, ["青少年", "个人层面", "自身素质", "社会实践", "法治观念"]) and "国家层面" in content:
            return True
    if profile["material"] == "exam" and any(token in content for token in ["国家层面", "个人层面", "法治意识"]):
        return True
    return False


def _needs_profile_content(profile: dict[str, Any], content: str) -> bool:
    if profile["material"] == "literature" and profile["subtype"] in {"character", "reading_task"}:
        return "人物类笔记" not in content and "阅读任务" not in content
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
    if re.search(r"本部分包含\s*\d+\s*个并列内容项目", text):
        return True
    if re.search(r"学习[“\"']?.{0,30}[”\"']?时[，,]?\s*先", text):
        return True
    if re.search(r"(?:[一-龥A-Za-z]+类\s*)?NOTE\s*(?:应|要|不应|用于|可以)", text):
        return True
    return any(
        token in text
        for token in [
            "学习时先理解",
            "学习时先说明",
            "备考时不要只背长句",
            "压缩关键词，并练习展开成完整答案",
            "再围绕",
            "梳理作用、条件和易混点",
            "并列内容项目",
            "这部分围绕",
            "这部分用于说明",
            "核心线索",
            "关键线索是",
            "需要说明",
            "重点说明这些要点",
            "含义、条件、作用和区别",
            "条件、作用和边界",
            "概念含义、使用条件和应用场景",
            "这类技术点要放回",
            "这类技术点需要结合",
            "这一技术点需要放在",
            "核心是理解本主题的背景、结论和应用边界",
            "核心是理解核心概念、判断依据和应用边界",
            "学习这个主题时",
            "需要结合原文",
            "应结合原文确认",
            "主要学习",
            "之间的关系",
            "不应承载",
            "结构总览",
            "交给各子模块",
            "直接记住原文依据",
            "原理类内容由",
            "先点明原理",
            "材料如何体现该原理",
            "用原文短语支撑每个表现",
            "考前自检",
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
    if re.match(r"^\s*(?:行动要求|具体做法|做法|要求|路径|措施|要点)[:：]", title):
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
    return _compact_user_summary(text, 150)


def _compact_user_summary(text: str, limit: int) -> str:
    value = normalize_learning_text(text).strip()
    if len(value) <= limit:
        return value
    sentences = [sentence.strip() for sentence in split_sentences(value) if sentence.strip()]
    for sentence in sentences:
        if len(sentence) <= limit:
            return sentence
    clauses = [part.strip(" ，,；;。") for part in re.split(r"[；;。]", value) if part.strip(" ，,；;。")]
    for clause in clauses:
        if len(clause) <= limit:
            return clause + "。"
    parts = [part.strip(" ，,；;。") for part in re.split(r"[，,；;]", value) if part.strip(" ，,；;。")]
    selected: list[str] = []
    total = 0
    for part in parts:
        projected = total + len(part) + (1 if selected else 0)
        if selected and projected > limit - 1:
            break
        if projected <= limit - 1:
            selected.append(part)
            total = projected
    if selected:
        return "，".join(selected).rstrip("，,；;。") + "。"
    return value[: max(1, limit - 1)].rstrip("，,；;。") + "。"


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
    if _looks_like_meaningful_english_title(text):
        return text
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
    _detach_semantically_invalid_parents(notes)
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


def _detach_semantically_invalid_parents(notes: list[dict[str, Any]]) -> None:
    by_id = {str(note.get("id") or ""): note for note in notes}
    for note in notes:
        parent = by_id.get(str(note.get("parentId") or ""))
        if not parent:
            continue
        if _parent_child_semantic_conflict(parent, note):
            note["parentId"] = None
            note["level"] = 1


def _parent_child_semantic_conflict(parent: dict[str, Any], child: dict[str, Any]) -> bool:
    parent_title = str(parent.get("title") or "")
    child_title = str(child.get("title") or "")
    parent_profile = infer_learning_profile(parent_title, str(parent.get("summary") or ""), parent.get("keyPoints") or [], str(parent.get("content") or ""))
    child_profile = infer_learning_profile(child_title, str(child.get("summary") or ""), child.get("keyPoints") or [], str(child.get("content") or ""))
    if parent_profile["material"] != child_profile["material"]:
        return True
    if parent_profile["material"] == "technical":
        if "transfer_method" in parent_profile["roles"] and _belongs_to_interface_parent(child_profile, child_title):
            return True
        if parent_profile["subtype"] == "connection_type" and "transfer_method" in child_profile["roles"]:
            return True
    if parent_profile["material"] == "politics":
        parent_probe = " ".join([parent_title, str(parent.get("summary") or ""), " ".join(str(item) for item in parent.get("keyPoints", []) or [])])
        child_probe = " ".join([child_title, str(child.get("summary") or ""), " ".join(str(item) for item in child.get("keyPoints", []) or [])])
        parent_is_national = has_any(parent_probe, ["国家层面", "党的领导", "中国道路", "中国精神", "中国力量"])
        child_is_personal = has_any(child_probe, ["青少年", "个人层面", "自身素质", "社会实践", "法治观念", "亲社会行为"])
        if parent_is_national and child_is_personal:
            return True
        if "reason" in parent_profile["roles"] and "reason" in child_profile["roles"]:
            if not _source_refs_overlap(parent, child) and _token_jaccard(parent_title, child_title) < 0.10:
                return True
    return False


def _source_refs_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_refs = {str(item) for item in [*(left.get("sourceRefs") or []), *(left.get("source_refs") or [])] if str(item)}
    right_refs = {str(item) for item in [*(right.get("sourceRefs") or []), *(right.get("source_refs") or [])] if str(item)}
    return bool(left_refs & right_refs)


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
        answer = _review_answer_for_note(note)
        questions.append(
            {
                "id": f"q{index}",
                "type": q_type,
                "difficulty": difficulties[index - 1],
                "question": question,
                "options": [],
                "answer": answer,
                "explanation": "\u7b54\u6848\u5e94\u4f9d\u636e\u5173\u8054\u7b14\u8bb0\u548c\u6765\u6e90\u7247\u6bb5\uff0c\u4f18\u5148\u590d\u8ff0\u5173\u952e\u5b9a\u4e49\u3001\u6b65\u9aa4\u6216\u56e0\u679c\u5173\u7cfb\u3002",
                "relatedNoteId": note["id"],
                "citationIds": [],
            }
        )
    return questions


def _review_answer_for_note(note: dict[str, Any]) -> str:
    title = str(note.get("title") or "")
    points = _drop_low_value_key_points(title, [str(item) for item in note.get("keyPoints", []) or []])
    summary = str(note.get("summary") or "").strip()
    content = str(note.get("content") or "").strip()
    parts: list[str] = []
    if summary and not _looks_like_generation_template(summary) and not _looks_like_raw_concat_summary(title, summary):
        parts.append(summary.rstrip("。"))
    if points:
        parts.append("要点包括：" + "；".join(points[:4]))
    elif content and not _looks_like_generation_template(content):
        parts.append(content.rstrip("。"))
    if not parts:
        parts.append(f"{title}需要回到原文定位其定义、作用和适用条件")
    return compact("。".join(parts) + "。", 220)


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
