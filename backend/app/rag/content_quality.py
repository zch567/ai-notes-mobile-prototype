from __future__ import annotations

import re
from collections import Counter
from typing import Any


TEMPLATE_SUMMARY_PATTERNS = [
    "并列内容项目",
    "围绕核心概念与关键要点展开",
    "学习时应先把握整体关系",
    "学习时先说明",
    "备考时不要只背长句",
    "压缩关键词，并练习展开成完整答案",
    "重点说明其在",
    "中的位置和理解边界",
    "所表达的概念或结论",
    "核心是理解核心概念与关键要点",
    "这部分可按",
    "这部分围绕",
    "这部分用于说明",
    "核心线索",
    "关键线索是",
    "需要说明",
    "重点说明这些要点",
    "含义、条件、作用和区别",
    "条件、作用和边界",
    "含义、条件、作用或例子",
    "概念含义、使用条件和应用场景",
    "这类技术点要放回",
    "这类技术点需要结合",
    "这一技术点需要放在",
    "主要学习",
    "之间的关系",
    "需要结合原文",
    "应结合原文确认",
    "主要涉及",
]

LOW_INFO_SUMMARY_PATTERNS = [
    "核心概念与关键要点",
    "关键要点理解",
    "几个要点理解",
    "说明本部分的核心概念",
    "本资料中的核心学习点",
    "需要结合定义、作用和适用场景来理解",
    "应结合上下文判断其定义、作用和适用场景",
    "建立基本认识",
]

INTERNAL_PROCESS_PATTERNS = [
    "不应承载",
    "结构总览",
    "交给各子模块",
    "该组并列项目中的一个子项",
    "并列项目中的一个子项",
    "总起模块",
    "直接记住原文依据",
    "原理类内容由",
    "先点明原理",
    "材料如何体现该原理",
    "用原文短语支撑每个表现",
    "考前自检",
]

ACTIVITY_PATTERNS = [
    "同学们",
    "请同学们",
    "通过本节课学习",
    "采访身边的人",
    "想一想",
    "思考",
    "你对",
    "为何会产生",
    "基础型作业",
    "发展型作业",
    "完成课时练习",
    "请以",
    "请说出",
    "你还爱读",
    "哪些精彩的故事",
]

VISUAL_LABEL_PATTERNS = [
    "主存工作时间",
    "CPU不执行程序",
    "DMA不工作",
    "DMA工作",
    "CPU控制并使用主存",
    "DMA控制并使用主存",
    "DMA传送速率高总线",
    "DMA接口组成线",
    "接口CPU主存",
    "设备设备设备DMA",
    "DMA响应",
    "DMA请求",
    "数据线",
    "ACC",
    "NANKAI UNIVERSITY",
    "©LXD",
]

BROKEN_FRAGMENT_PATTERNS = [
    r"DMA\s*传送速\s*率高",
    r"DMA\s*接口组成\s*线",
    r"起总线竞争",
    r"CPU在一个工作周期内访$",
    r"问一次存储器即可不需要\s*申请建立和归还\s*总线",
    r"DMA方式是以数据块为单位进行传送\s*，当$",
    r"控制电[；;、]?\s*路",
    r"字装配\s*/\s*[、；;]?\s*拆卸",
    r"主存和[、；;]\s*服务",
    r"原程序为设备",
    r"(^|[；;、\s])存的利用率，使用广泛",
    r"控[、；;\s]+制权",
    r"中断方[、；;\s]+式高",
    r"理时，将所选设备",
    r"设备地址\s*寄",
    r"(^|[；;、\s])控制逻($|[；;、\s])",
    r"接口nCPU",
    r"设备设备设备DMA",
    r"DMA操[、\s]+作",
    r"通过说明",
    r"预处理之后",
    r"对应输入情况",
    r"对应输出情况",
    r"经处理完毕",
    r"便通过\s*DMA",
    r"请\s*CPU",
    r"设备信[、\s]*息",
    r"与接口[、\s]*相连",
    r"打印机\s*t",
    r"每\d+\s*s请求DMA",
    r"s\s*一次DMA传送",
    r"^理，这由",
    r"^性和多路型",
]

LOW_QUALITY_CONTENT_PATTERNS = [
    r"^.{0,12}线$",
    r"^\d+[.、]\s*DMA\s*接口功能",
    r"结构拆解[:：]",
    r"要点介绍[:：].*结构拆解[:：]",
    r"^(C1、C2控制下的多路转换器|在逻辑上只允许连接一个设备|2\.\s*DMA接口与系统的连接方式|3\.\s*DMA方式与程序中断方式的比较)",
    r"设备地址寄存器$",
    r"备考时不要只背长句",
    r"学习时先说明.+再围绕",
]

QUESTION_TITLE_PREFIXES = ("如何", "怎样", "为什么", "什么是")


def _u(value: str) -> str:
    try:
        return value.encode("ascii").decode("unicode_escape")
    except UnicodeEncodeError:
        return value


def assess_content_quality(result: dict[str, Any]) -> dict[str, Any]:
    notes = list(result.get("notes") or [])
    total = max(1, len(notes))
    all_points = [str(point) for note in notes for point in note.get("keyPoints", []) or []]

    template_notes = [note for note in notes if is_template_summary(str(note.get("summary") or ""))]
    low_info_summaries = [note for note in notes if is_low_info_summary(str(note.get("summary") or ""))]
    empty_content = [note for note in notes if not str(note.get("content") or "").strip()]
    low_quality_content = [note for note in notes if is_low_quality_content(str(note.get("content") or ""))]
    activity_notes = [note for note in notes if is_activity_note(note)]
    visual_label_points = [point for point in all_points if is_visual_label(point)]
    page_ref_points = [point for point in all_points if is_page_reference_point(point)]
    long_points = [point for point in all_points if len(point) > 96]
    weak_points = [point for point in all_points if is_weak_key_point(point)]
    over_fragmented_notes = [note for note in notes if has_over_fragmented_key_points(note)]
    fragment_titles = [note for note in notes if is_fragment_title(str(note.get("title") or ""))]
    numbering_breaks = [note for note in notes if has_numbering_break(note)]
    field_repetition = [note for note in notes if field_repetition_score(note) > 0.72]
    broken_fragments = [note for note in notes if note_has_broken_fragment(note)]
    truncated_sentences = [note for note in notes if has_truncated_sentence(note)]
    raw_concat_summaries = [note for note in notes if has_raw_concat_summary(note)]
    title_summary_mismatch = [note for note in notes if has_title_summary_mismatch(note)]
    generic_template_mismatch = [note for note in notes if has_generic_template_mismatch(note)]
    transition_fragments = [note for note in notes if has_transition_fragment(note)]
    internal_process_notes = [note for note in notes if has_internal_process_language(note)]
    weak_explanations = [note for note in notes if not has_learning_explanation(note)]
    template_contents = [note for note in notes if has_template_content(note)]
    semantic_repetition = [note for note in notes if semantic_field_repetition_score(note) > 0.62]
    weak_teaching_value = [note for note in notes if has_weak_teaching_value(note)]
    weak_learning_actions = [note for note in notes if not has_learning_actionability(note)]
    weak_evidence = [note for note in notes if not has_relevant_evidence(note)]
    learning_role_gap = has_learning_role_gap(notes)
    duplicate_titles = duplicate_title_clusters(notes)
    citation_display = [note for note in notes if readable_source_excerpts(note)]

    metrics = {
        "noteCount": len(notes),
        "templateSummaryRate": round(len(template_notes) / total, 4),
        "lowInfoSummaryRate": round(len(low_info_summaries) / total, 4),
        "emptyContentRate": round(len(empty_content) / total, 4),
        "lowQualityContentRate": round(len(low_quality_content) / total, 4),
        "activityNoteRate": round(len(activity_notes) / total, 4),
        "visualLabelPointRate": round(len(visual_label_points) / max(1, len(all_points)), 4),
        "pageReferencePointRate": round(len(page_ref_points) / max(1, len(all_points)), 4),
        "longKeyPointRate": round(len(long_points) / max(1, len(all_points)), 4),
        "weakKeyPointRate": round(len(weak_points) / max(1, len(all_points)), 4),
        "overFragmentedKeyPointRate": round(len(over_fragmented_notes) / total, 4),
        "fragmentTitleRate": round(len(fragment_titles) / total, 4),
        "numberingBreakRate": round(len(numbering_breaks) / total, 4),
        "brokenFragmentRate": round(len(broken_fragments) / total, 4),
        "truncatedSentenceRate": round(len(truncated_sentences) / total, 4),
        "rawConcatSummaryRate": round(len(raw_concat_summaries) / total, 4),
        "titleSummaryMismatchRate": round(len(title_summary_mismatch) / total, 4),
        "genericTemplateMismatchRate": round(len(generic_template_mismatch) / total, 4),
        "transitionFragmentRate": round(len(transition_fragments) / total, 4),
        "internalProcessLanguageRate": round(len(internal_process_notes) / total, 4),
        "weakExplanationRate": round(len(weak_explanations) / total, 4),
        "templateContentRate": round(len(template_contents) / total, 4),
        "semanticFieldRepetitionRate": round(len(semantic_repetition) / total, 4),
        "weakTeachingValueRate": round(len(weak_teaching_value) / total, 4),
        "weakLearningActionabilityRate": round(len(weak_learning_actions) / total, 4),
        "weakEvidenceRelevanceRate": round(len(weak_evidence) / total, 4),
        "learningRoleCoverage": 0.0 if learning_role_gap else 1.0,
        "fieldRepetitionRate": round(len(field_repetition) / total, 4),
        "duplicateTitleClusterRate": round(len(duplicate_titles) / total, 4),
        "citationDisplayCoverage": round(len(citation_display) / total, 4),
    }
    failed = []
    if metrics["templateSummaryRate"] > 0.05:
        failed.append("template-summary-high")
    if metrics["lowInfoSummaryRate"] > 0.05:
        failed.append("low-info-summary-high")
    if metrics["emptyContentRate"] > 0.10:
        failed.append("empty-content-high")
    if metrics["lowQualityContentRate"] > 0.05:
        failed.append("low-quality-content-high")
    if metrics["activityNoteRate"] > 0.05:
        failed.append("activity-note-high")
    if metrics["visualLabelPointRate"] > 0.02:
        failed.append("visual-label-point-high")
    if metrics["pageReferencePointRate"] > 0:
        failed.append("page-reference-point-present")
    if metrics["longKeyPointRate"] > 0.03:
        failed.append("long-key-point-high")
    if metrics["weakKeyPointRate"] > 0.03:
        failed.append("weak-key-point-high")
    if metrics["overFragmentedKeyPointRate"] > 0.10:
        failed.append("over-fragmented-key-point-high")
    if metrics["fragmentTitleRate"] > 0:
        failed.append("fragment-title-present")
    if metrics["numberingBreakRate"] > 0.05:
        failed.append("numbering-break-high")
    if metrics["brokenFragmentRate"] > 0:
        failed.append("broken-fragment-present")
    if metrics["truncatedSentenceRate"] > 0.05:
        failed.append("truncated-sentence-high")
    if metrics["rawConcatSummaryRate"] > 0:
        failed.append("raw-concat-summary-present")
    if metrics["titleSummaryMismatchRate"] > 0:
        failed.append("title-summary-mismatch-present")
    if metrics["genericTemplateMismatchRate"] > 0:
        failed.append("generic-template-mismatch-present")
    if metrics["transitionFragmentRate"] > 0:
        failed.append("transition-fragment-present")
    if metrics["internalProcessLanguageRate"] > 0:
        failed.append("internal-process-language-present")
    if metrics["weakExplanationRate"] > 0.20:
        failed.append("weak-explanation-high")
    if metrics["templateContentRate"] > 0:
        failed.append("template-content-present")
    if metrics["semanticFieldRepetitionRate"] > 0.10:
        failed.append("semantic-field-repetition-high")
    if metrics["weakTeachingValueRate"] > 0.15:
        failed.append("weak-teaching-value-high")
    if metrics["weakLearningActionabilityRate"] > 0.35:
        failed.append("weak-learning-actionability-high")
    if metrics["weakEvidenceRelevanceRate"] > 0.25:
        failed.append("weak-evidence-relevance-high")
    if learning_role_gap:
        failed.append("learning-role-coverage-low")
    if metrics["fieldRepetitionRate"] > 0.18:
        failed.append("field-repetition-high")
    if metrics["duplicateTitleClusterRate"] > 0.05:
        failed.append("duplicate-title-high")
    if metrics["citationDisplayCoverage"] < 0.8 and notes:
        failed.append("citation-display-low")
    return {
        "passed": not failed,
        "failedChecks": failed,
        "metrics": metrics,
        "samples": {
            "templateSummaryNoteIds": [str(note.get("id")) for note in template_notes[:5]],
            "lowInfoSummaryNoteIds": [str(note.get("id")) for note in low_info_summaries[:5]],
            "emptyContentNoteIds": [str(note.get("id")) for note in empty_content[:5]],
            "lowQualityContentNoteIds": [str(note.get("id")) for note in low_quality_content[:5]],
            "activityNoteIds": [str(note.get("id")) for note in activity_notes[:5]],
            "numberingBreakNoteIds": [str(note.get("id")) for note in numbering_breaks[:5]],
            "brokenFragmentNoteIds": [str(note.get("id")) for note in broken_fragments[:5]],
            "truncatedSentenceNoteIds": [str(note.get("id")) for note in truncated_sentences[:5]],
            "weakExplanationNoteIds": [str(note.get("id")) for note in weak_explanations[:5]],
            "templateContentNoteIds": [str(note.get("id")) for note in template_contents[:5]],
            "semanticRepetitionNoteIds": [str(note.get("id")) for note in semantic_repetition[:5]],
            "weakTeachingValueNoteIds": [str(note.get("id")) for note in weak_teaching_value[:5]],
            "weakLearningActionabilityNoteIds": [str(note.get("id")) for note in weak_learning_actions[:5]],
            "weakEvidenceNoteIds": [str(note.get("id")) for note in weak_evidence[:5]],
            "learningRoleGap": learning_role_gap,
            "fragmentTitleNoteIds": [str(note.get("id")) for note in fragment_titles[:5]],
            "duplicateTitleGroups": duplicate_titles[:5],
            "visualLabelPoints": visual_label_points[:8],
            "pageReferencePoints": page_ref_points[:8],
            "longKeyPoints": long_points[:5],
            "weakKeyPoints": weak_points[:8],
            "overFragmentedKeyPointNoteIds": [str(note.get("id")) for note in over_fragmented_notes[:5]],
            "rawConcatSummaryNoteIds": [str(note.get("id")) for note in raw_concat_summaries[:5]],
            "titleSummaryMismatchNoteIds": [str(note.get("id")) for note in title_summary_mismatch[:5]],
            "genericTemplateMismatchNoteIds": [str(note.get("id")) for note in generic_template_mismatch[:5]],
            "transitionFragmentNoteIds": [str(note.get("id")) for note in transition_fragments[:5]],
            "internalProcessLanguageNoteIds": [str(note.get("id")) for note in internal_process_notes[:5]],
        },
    }


def is_template_summary(summary: str) -> bool:
    return any(pattern in summary for pattern in TEMPLATE_SUMMARY_PATTERNS)


def is_low_info_summary(summary: str) -> bool:
    text = normalize_key(summary)
    if len(text) < 12:
        return True
    if "重点说明" in summary and len(semantic_tokens(summary)) < 10:
        return True
    return any(normalize_key(pattern) in text for pattern in LOW_INFO_SUMMARY_PATTERNS)


def is_weak_key_point(point: str) -> bool:
    text = str(point).strip()
    compacted = normalize_key(text)
    if len(compacted) < 4 or len(text) > 72:
        return True
    if looks_like_transition_fragment(text):
        return True
    if any(pattern in text for pattern in TEMPLATE_SUMMARY_PATTERNS + INTERNAL_PROCESS_PATTERNS):
        return True
    if any(pattern in text for pattern in LOW_INFO_SUMMARY_PATTERNS):
        return True
    if "再回到原文确认它的条件、作用和边界" in text:
        return True
    if any(re.search(pattern, text) for pattern in BROKEN_FRAGMENT_PATTERNS):
        return True
    if re.search(r"(和|或|但|因为|由于|以及|、|，|；|：|/)$", text):
        return True
    if re.search(r"(控[、；;\s]+制|方[、；;\s]+式|主[、；;\s]+存|电[、；;\s]+路|字装配\s*/|装配\s*/)", text):
        return True
    if len(re.findall(r"[，、；]", text)) >= 4:
        return True
    if re.search(r"。.*。|；.*；", text):
        return True
    cleaned = re.sub(r"^\s*(?:[（(][一二三四五六七八九十\d]+[）)]|[①②③④⑤⑥⑦⑧⑨]|\d+[.、])\s*", "", text).strip()
    if len(cleaned) <= 14 and any(token in cleaned for token in ["根本原因", "重要原因", "原理内容", "方法论意义", "物质范畴", "意识范畴", "易混淆概念辨析"]):
        return True
    return False


def has_over_fragmented_key_points(note: dict[str, Any]) -> bool:
    points = [str(item).strip() for item in note.get("keyPoints", []) or [] if str(item).strip()]
    if len(points) < 5:
        return False
    short_count = sum(len(normalize_key(point)) <= 8 for point in points)
    label_count = sum(bool(re.match(r"^(?:[（(]\d+[）)]|[①②③④⑤⑥⑦⑧⑨]|\d+[.、])\s*[^，。；]{0,16}$", point)) for point in points)
    if label_count >= 3 and all(is_parallel_numbered_learning_point(point) for point in points[:5]):
        return False
    return short_count >= 3 or label_count >= 3


def is_parallel_numbered_learning_point(point: str) -> bool:
    text = str(point).strip()
    if not re.match(r"^(?:[（(]\d+[）)]|[①②③④⑤⑥⑦⑧⑨])", text):
        return True
    body = re.sub(r"^(?:[（(]\d+[）)]|[①②③④⑤⑥⑦⑧⑨])\s*", "", text).strip()
    if len(body) < 6:
        return False
    return any(token in body for token in ["道路", "理论", "制度", "文化", "中国人", "中国梦", "精神", "力量", "理想", "责任"])


def has_raw_concat_summary(note: dict[str, Any]) -> bool:
    summary = str(note.get("summary") or "")
    title = str(note.get("title") or "")
    if len(summary) > 150:
        return True
    if summary.startswith("根本原因包括") and "重要原因" in summary and len(summary) <= 120:
        return False
    if summary.count("、") >= 4 or summary.count("，") >= 5:
        return True
    if title and summary.startswith(title) and ("主要包括" in summary or "重点说明" in summary or "包括" in summary[: len(title) + 16] or "包含" in summary[: len(title) + 16] or "说明" in summary[: len(title) + 12]):
        return True
    if title and summary.startswith(title) and "主要涉及" in summary[: len(title) + 16]:
        return True
    if "说明" in summary and summary.count("说明") >= 2:
        return True
    if re.search(r"(.{8,40})(?:说明|主要包括)\1", summary):
        return True
    if looks_like_transition_fragment(summary):
        return True
    return False


def has_title_summary_mismatch(note: dict[str, Any]) -> bool:
    title = str(note.get("title") or "")
    summary = str(note.get("summary") or "")
    if "中断机构" in title and any(token in summary for token in ["字计数器溢出", "通过说明", "数据缓冲寄存器"]):
        return True
    if "数据传送过程" in title and looks_like_transition_fragment(summary):
        return True
    if component_title_summary_mismatch(title, summary):
        return True
    return False


def has_generic_template_mismatch(note: dict[str, Any]) -> bool:
    title = str(note.get("title") or "")
    content = str(note.get("content") or "")
    if "中断机构" in title and "地址类部件负责定位" in content:
        return True
    if "数据传送过程" in title and any(token in content for token in ["地址类部件负责定位", "缓冲类部件暂存数据"]):
        return True
    return False


def looks_like_transition_fragment(text: str) -> bool:
    value = str(text)
    compacted = normalize_key(value)
    return any(token in value for token in ["通过说明", "✓ 预处理之后", "预处理之后", "（对应输入情况", "对应输入情况", "对应输出情况", "经处理完毕", "便通过DMA", "请CPU", "请 CPU"]) or compacted.endswith("便通过dma")


def has_transition_fragment(note: dict[str, Any]) -> bool:
    fields = [
        str(note.get("title") or ""),
        str(note.get("summary") or ""),
        str(note.get("content") or ""),
        " ".join(str(item) for item in note.get("keyPoints", []) or []),
    ]
    return any(looks_like_transition_fragment(field) for field in fields)


def component_title_summary_mismatch(title: str, summary: str) -> bool:
    component_terms = ["字计数器", "数据缓冲寄存器", "主存地址寄存器", "控制逻辑", "中断机构"]
    title_terms = {term for term in component_terms if term in title}
    if not title_terms:
        return False
    first_clause = re.split(r"[，。；;]", summary, maxsplit=1)[0]
    foreign_terms = [term for term in component_terms if term in first_clause and term not in title_terms]
    return bool(foreign_terms and any(term in summary for term in title_terms))


def has_internal_process_language(note: dict[str, Any]) -> bool:
    text = " ".join(
        [
            str(note.get("title") or ""),
            str(note.get("summary") or ""),
            str(note.get("content") or ""),
            " ".join(str(item) for item in note.get("keyPoints", []) or []),
        ]
    )
    return any(pattern in text for pattern in INTERNAL_PROCESS_PATTERNS)


def is_low_quality_content(content: str) -> bool:
    text = content.strip()
    if not text:
        return True
    if len(normalize_key(text)) < 18:
        return True
    return any(re.search(pattern, text) for pattern in LOW_QUALITY_CONTENT_PATTERNS)


def is_activity_note(note: dict[str, Any]) -> bool:
    probe = " ".join(
        [
            str(note.get("title") or ""),
            str(note.get("summary") or ""),
            " ".join(str(item) for item in note.get("keyPoints", []) or []),
        ]
    )
    return any(pattern in probe for pattern in ACTIVITY_PATTERNS)


def is_visual_label(value: str) -> bool:
    text = re.sub(r"\s+", "", value)
    if text in {"t", "I/O", "设", "备", "ACC", "线", "+1", "…", "控制逻", "数据线"}:
        return True
    for pattern in VISUAL_LABEL_PATTERNS:
        compacted = pattern.replace(" ", "")
        if text == compacted:
            return True
        if len(text) <= len(compacted) + 4 and compacted in text:
            return True
    return False


def is_page_reference_point(value: str) -> bool:
    return bool(re.search(r"P\d+\s*[-－]\s*\d+", str(value)))


def is_fragment_title(title: str) -> bool:
    text = title.strip()
    compacted = re.sub(r"\s+", "", text)
    if not text:
        return True
    if re.match(r"^(理时|设备地址|控制逻|接口\d+|DMA接口（page_|DACK$)", text):
        return True
    if text.endswith("通过") and len(text) <= 42:
        return True
    if any(re.search(pattern, text) for pattern in BROKEN_FRAGMENT_PATTERNS):
        return True
    if looks_like_raw_sentence_title(text):
        return True
    if has_template_phrase(text):
        return True
    if compacted in {"控制逻", "数据线", "溢出信号", "+1"}:
        return True
    return False


def looks_like_raw_sentence_title(title: str) -> bool:
    text = str(title or "").strip()
    compacted = re.sub(r"\s+", "", text)
    if looks_like_meaningful_english_title(text):
        return False
    if len(compacted) > 36:
        return True
    if "..." in text or "…" in text:
        return True
    if len(re.findall(r"[，,；;。]", text)) >= 1 and len(compacted) > 18:
        return True
    return any(token in text for token in ["其中描述了", "它是一部", "讲述的是", "请以", "你还爱读", "请说出"])


def looks_like_meaningful_english_title(title: str) -> bool:
    text = str(title or "").strip()
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


def has_numbering_break(note: dict[str, Any]) -> bool:
    title = str(note.get("title") or "").strip()
    return bool(re.match(r"^[①②③④⑤⑥⑦⑧⑨]", title))


def note_has_broken_fragment(note: dict[str, Any]) -> bool:
    fields = [
        str(note.get("title") or ""),
        str(note.get("summary") or ""),
        str(note.get("content") or ""),
        " ".join(str(item) for item in note.get("keyPoints", []) or []),
    ]
    text = "\n".join(fields)
    return any(re.search(pattern, text) for pattern in BROKEN_FRAGMENT_PATTERNS)


def has_truncated_sentence(note: dict[str, Any]) -> bool:
    fields = [
        str(note.get("summary") or ""),
        str(note.get("content") or ""),
        " ".join(str(item) for item in note.get("keyPoints", []) or []),
    ]
    text = "\n".join(fields)
    return bool(
        re.search(r"(可以采。|预置信$|字装配\s*/$|DMA接$|有选择$|后处$|CPU停$|已$)", text)
        or re.search(r"(，但$|，通过$|，需要$|，将$|，由$)", text)
    )


def has_learning_explanation(note: dict[str, Any]) -> bool:
    content = str(note.get("content") or "")
    if len(normalize_key(content)) < 28:
        return False
    if re.match(r"^\s*(?:\d+[).、]|[①②③④⑤⑥⑦⑧⑨⑩])", content.strip()):
        return False
    tokens = [
        _u("\u5b66\u4e60"), _u("\u91cd\u70b9"), _u("\u533a\u5206"), _u("\u7406\u89e3"), _u("\u8bb0\u5fc6"),
        _u("\u7b54\u9898"), _u("\u9002\u5408"), _u("\u8d1f\u8d23"), _u("\u6bd4\u8f83"), _u("\u7ed3\u8bba"),
        _u("\u4f9d\u636e"), _u("\u6846\u67b6"), _u("\u4e3b\u4f53"), _u("\u9009\u62e9\u9898"), _u("\u5206\u6790\u9898"),
        _u("\u6613\u6df7"), _u("\u65b9\u6cd5\u8bba"), _u("\u804c\u8d23"), _u("\u63a7\u5236"), _u("\u52a8\u4f5c"),
        _u("\u7406\u6027"), _u("\u5b9e\u5e72"), _u("\u8ba4\u540c"), _u("\u5e95\u6c14"), _u("\u4fe1\u5fc3"),
        "复习", "备考", "关键词", "逐项回忆", "判断", "场景", "真题", "检查清单",
        "构成", "对应", "分成", "分层", "两层", "链条", "逻辑链", "边界", "条件", "路径",
        "能力建设", "行为约束", "限定词", "材料对应", "共同本质", "相互依存",
    ]
    return any(token in content for token in tokens)


def has_template_content(note: dict[str, Any]) -> bool:
    text = " ".join([str(note.get("summary") or ""), str(note.get("content") or "")])
    if has_template_phrase(text):
        return True
    if re.search(r"本部分包含\s*\d+\s*个并列内容项目", text):
        return True
    if re.search(r"学习[“\"']?.{0,30}[”\"']?时[，,]?\s*先", text):
        return True
    if re.search(r"(?:[\u4e00-\u9fffA-Za-z]+类\s*)?NOTE\s*(?:应|要|不应|用于|可以)", text):
        return True
    templates = [
        _u("\u5b66\u4e60\u65f6\u5148\u7406\u89e3"),
        _u("\u5b66\u4e60\u65f6\u5148\u8bf4\u660e"),
        _u("\u5907\u8003\u65f6\u4e0d\u8981\u53ea\u80cc\u957f\u53e5"),
        _u("\u538b\u7f29\u5173\u952e\u8bcd\uff0c\u5e76\u7ec3\u4e60\u5c55\u5f00\u6210\u5b8c\u6574\u7b54\u6848"),
        _u("\u518d\u56f4\u7ed5"),
        _u("\u68b3\u7406\u4f5c\u7528\u3001\u6761\u4ef6\u548c\u6613\u6df7\u70b9"),
        _u("\u6838\u5fc3\u662f\u7406\u89e3\u672c\u4e3b\u9898\u7684\u80cc\u666f\u3001\u7ed3\u8bba\u548c\u5e94\u7528\u8fb9\u754c"),
        _u("\u6838\u5fc3\u662f\u7406\u89e3\u6838\u5fc3\u6982\u5ff5\u3001\u5224\u65ad\u4f9d\u636e\u548c\u5e94\u7528\u8fb9\u754c"),
        _u("\u9700\u8981\u7ed3\u5408\u539f\u6587\u7406\u89e3\u5176\u542b\u4e49\u3001\u4f5c\u7528\u548c\u4f7f\u7528\u6761\u4ef6"),
        _u("\u5b66\u4e60\u8fd9\u4e2a\u4e3b\u9898\u65f6"),
        "并列内容项目",
        "应结合原文确认",
        _u("\u4e3b\u8981\u5b66\u4e60"),
        _u("\u4e4b\u95f4\u7684\u5173\u7cfb"),
        "直接记住原文依据",
        "原理类内容由",
        "先点明原理",
        "材料如何体现该原理",
        "用原文短语支撑每个表现",
        "考前自检",
    ]
    return any(item in text for item in templates) or has_internal_process_language(note)


def has_template_phrase(text: str) -> bool:
    value = str(text or "")
    return any(pattern in value for pattern in TEMPLATE_SUMMARY_PATTERNS)


def semantic_field_repetition_score(note: dict[str, Any]) -> float:
    values = [
        str(note.get("summary") or ""),
        str(note.get("content") or ""),
        " ".join(str(item) for item in note.get("keyPoints", []) or []),
    ]
    token_sets = [set(semantic_tokens(value)) for value in values if semantic_tokens(value)]
    if len(token_sets) < 2:
        return 0.0
    repeated = 0
    pairs = 0
    for index, left in enumerate(token_sets):
        for right in token_sets[index + 1 :]:
            pairs += 1
            score = len(left & right) / max(1, min(len(left), len(right)))
            if score > 0.72:
                repeated += 1
    return repeated / max(1, pairs)


def has_weak_teaching_value(note: dict[str, Any]) -> bool:
    title = str(note.get("title") or "")
    content = str(note.get("content") or "")
    points = [str(item) for item in note.get("keyPoints", []) or []]
    if has_template_content(note):
        return True
    if len(semantic_tokens(content)) < 8:
        return True
    probe = " ".join([title, content, *points])
    if any(token in probe for token in ["DMA", "CPU", _u("\u4e3b\u5b58"), _u("\u603b\u7ebf"), _u("\u63a5\u53e3")]):
        return not any(token in content for token in [_u("\u6761\u4ef6"), _u("\u52a8\u4f5c"), _u("\u7ed3\u679c"), _u("\u6bd4\u8f83"), _u("\u533a\u5206"), _u("\u804c\u8d23"), _u("\u63a7\u5236"), _u("\u6570\u636e\u6d41"), _u("\u63a7\u5236\u6d41"), "流程", "阶段", "并行关系", "优先级", "独占", "共享", "收尾", "场景", "适合"])
    if any(
        token in probe
        for token in [
            _u("\u4e2d\u56fd\u68a6"), _u("\u81ea\u4fe1\u4e2d\u56fd\u4eba"), _u("\u4e2d\u56fd\u7279\u8272\u793e\u4f1a\u4e3b\u4e49"), _u("\u9752\u5c11\u5e74"),
            "行动要求", "理想信念", "学习实践", "责任担当", "法治意识", "科学文化知识", "自身素质",
        ]
    ):
        return not any(
            token in content
            for token in [
                _u("\u7b54\u9898"), _u("\u4e3b\u4f53"), _u("\u56fd\u5bb6\u5c42\u9762"), _u("\u4e2a\u4eba\u5c42\u9762"),
                _u("\u884c\u52a8"), _u("\u4f9d\u636e"), _u("\u6846\u67b6"), "原因链条", "根本原因",
                "重要原因", "对应", "构成", "能力建设", "行为约束", "落实场景", "价值指向",
            ]
        )
    if any(token in probe for token in [_u("\u552f\u7269\u8bba"), _u("\u7269\u8d28"), _u("\u610f\u8bc6"), _u("\u539f\u7406"), _u("\u8003\u70b9")]):
        return not any(
            token in content
            for token in [
                _u("\u9009\u62e9\u9898"), _u("\u5206\u6790\u9898"), _u("\u6a21\u677f"), _u("\u6613\u6df7"),
                _u("\u5173\u952e\u8bcd"), _u("\u65b9\u6cd5\u8bba"), _u("\u771f\u9898"), "逻辑链",
                "原理内容", "易错边界", "题目判断", "限定词", "概念表述", "材料对应",
            ]
        )
    return False


def has_learning_actionability(note: dict[str, Any]) -> bool:
    if has_template_content(note):
        return False
    probe = " ".join([str(note.get("title") or ""), str(note.get("content") or ""), str(note.get("summary") or "")])
    return any(
        token in probe
        for token in [
            "学习时", "答题时", "复习时", "备考时", "重点", "区分", "比较", "记忆", "先", "再",
            "避免", "适合", "高频", "关键词", "逐项", "判断", "场景", "关注", "练习", "检查清单",
            "构成", "对应", "分成", "分层", "两层", "链条", "逻辑链", "边界", "条件", "路径",
            "主体", "目标", "落实", "能力建设", "行为约束", "限定词", "材料对应", "共同本质",
            "相互依存", "概念定义", "原理", "方法论", "易错",
        ]
    )


def has_relevant_evidence(note: dict[str, Any]) -> bool:
    excerpts = note.get("sourceExcerpts") or []
    if not excerpts:
        return False
    query = " ".join([str(note.get("title") or ""), " ".join(str(item) for item in note.get("keyPoints", []) or [])])
    query_tokens = set(simple_tokens(query))
    if not query_tokens:
        return True
    for item in excerpts[:2]:
        quote = str(item.get("quote") or "")
        if title_or_point_mentions_quote(note, quote):
            return True
        quote_tokens = set(simple_tokens(str(item.get("quote") or "")))
        if len(query_tokens & quote_tokens) / max(1, len(query_tokens)) >= 0.18:
            return True
    return False


def has_learning_role_gap(notes: list[dict[str, Any]]) -> bool:
    text = " ".join(
        " ".join(
            [
                str(note.get("title") or ""),
                str(note.get("summary") or ""),
                str(note.get("content") or ""),
                " ".join(str(item) for item in note.get("keyPoints", []) or []),
            ]
        )
        for note in notes
    )
    if any(token in text for token in ["DMA", "总线", "主存", "接口"]):
        return not all(token in text for token in ["区分", "适合", "总线控制权"])
    if any(token in text for token in ["中国梦", "自信中国人", "中国特色社会主义"]):
        has_state_path = any(token in text for token in ["国家层面", "领导核心", "道路方向", "精神支撑", "人民力量"])
        has_action_path = any(token in text for token in ["行动", "能力建设", "行为约束", "落实场景", "主体"])
        has_reason_path = any(token in text for token in ["原因链条", "根本原因", "重要原因", "依据"])
        return not (has_state_path and has_action_path and has_reason_path)
    if any(token in text for token in ["唯物论", "物质", "意识", "考点"]):
        has_concept_path = any(token in text for token in ["概念表述", "概念定义", "客观实在", "主观映象"])
        has_principle_path = any(token in text for token in ["原理", "逻辑链", "方法论", "意识对物质"])
        has_judgement_path = any(token in text for token in ["题目判断", "限定词", "易错", "选择题", "分析题"])
        return not (has_concept_path and has_principle_path and has_judgement_path)
    if any(token in text for token in ["水浒传", "宋江", "林冲", "梁山", "人物形象", "性格特点"]):
        return not all(token in text for token in ["人物", "情节", "主题"])
    return False


def title_or_point_mentions_quote(note: dict[str, Any], quote: str) -> bool:
    title = str(note.get("title") or "")
    points = " ".join(str(item) for item in note.get("keyPoints", []) or [])
    probe = f"{title} {points}"
    if title and title in quote:
        return True
    title_key = normalize_title(title)
    quote_key = normalize_key(quote)
    if title_key and len(title_key) >= 4 and title_key in quote_key:
        return True
    evidence_pairs = [
        ("数据缓冲寄存器", "暂存每次传送的数据"),
        ("字计数器", "每传送一个字其值"),
        ("主存地址寄存器", "主存中的地址"),
        ("控制逻辑", "管理"),
        ("传送长度", "字计数器"),
        ("交替访问", "独立的地址"),
        ("交替访问", "硬件复杂"),
        ("DMA 与 CPU 交替访问", "硬件复杂"),
        ("传送期间并行工作", "DMA 传送过程"),
        ("传送期间并行工作", "向 CPU 申请 DMA"),
        ("并行工作", "CPU继续执行主程序"),
        ("并行工作", "DMA 传送过程"),
        ("后处理", "决定是否继续"),
        ("后处理", "错误诊断"),
        ("国家有认同", "国家有认同"),
        ("中国道路", "中国特色社会主义道路"),
        ("中国精神", "民族精神"),
        ("中国力量", "全国各族人民大团结"),
        ("青少年", "树立崇高远大理想"),
        ("青少年", "增强法治观念"),
        ("助力实现中国梦", "树立崇高远大理想"),
        ("助力实现中国梦", "增强法治观念"),
        ("自信中国人", "四个自信"),
        ("自信中国人", "道路自信"),
        ("如何做自信中国人", "理性平和"),
        ("如何做自信中国人", "道路自信"),
        ("物质", "客观实在性"),
        ("意识", "主观映象"),
        ("物质与意识", "意识对物质具有能动"),
        ("唯物论核心基本概念", "物质"),
    ]
    return any(left in probe and right in quote for left, right in evidence_pairs)


def simple_tokens(value: str) -> list[str]:
    text = normalize_key(value)
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{1,}|[0-9]+|[\u4e00-\u9fff]{2,}", text)
    tokens: list[str] = []
    for word in words:
        if re.fullmatch(r"[\u4e00-\u9fff]{2,}", word):
            tokens.extend(word[i : i + 2] for i in range(max(0, len(word) - 1)))
        else:
            tokens.append(word.lower())
    return [token for token in tokens if token not in {"这部", "部分", "说明", "核心", "理解", "内容"}]


def readable_source_excerpts(note: dict[str, Any]) -> bool:
    excerpts = note.get("sourceExcerpts") or []
    return any(len(str(item.get("quote") or "").strip()) >= 12 for item in excerpts if isinstance(item, dict))


def duplicate_title_clusters(notes: list[dict[str, Any]]) -> list[list[str]]:
    normalized = [normalize_title(str(note.get("title") or "")) for note in notes]
    counts = Counter(item for item in normalized if item)
    clusters: list[list[str]] = []
    for title, count in counts.items():
        if count > 1:
            clusters.append([title, str(count)])
    for idx, title in enumerate(normalized):
        if not title:
            continue
        for other in normalized[idx + 1 :]:
            if not other or title == other:
                continue
            if is_title_detail_pair(title, other):
                continue
            if len(title) >= 6 and len(other) >= 6 and (title in other or other in title):
                clusters.append([title, other])
                break
    return clusters


def normalize_title(value: str) -> str:
    value = re.sub(r"^\s*(?:\d+[.、]|\(\d+\)|[①②③④⑤⑥⑦⑧⑨])\s*", "", value)
    return normalize_key(value)


def is_title_detail_pair(left: str, right: str) -> bool:
    return left.startswith(right + "：") or right.startswith(left + "：")


def field_repetition_score(note: dict[str, Any]) -> float:
    values = [
        normalize_key(str(note.get("summary") or "")),
        normalize_key(str(note.get("content") or "")),
        normalize_key(" ".join(str(item) for item in note.get("keyPoints", []) or [])),
    ]
    values = [value for value in values if value]
    if len(values) < 2:
        return 0.0
    repeated = 0
    pairs = 0
    for idx, left in enumerate(values):
        for right in values[idx + 1 :]:
            pairs += 1
            if left in right or right in left or jaccard(left, right) > 0.72:
                repeated += 1
    return repeated / max(1, pairs)


def normalize_key(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def jaccard(left: str, right: str) -> float:
    a = set(left)
    b = set(right)
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def semantic_tokens(value: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}|[0-9]+|[\u4e00-\u9fff]{2,}", str(value))
    tokens: list[str] = []
    for word in words:
        if re.fullmatch(r"[\u4e00-\u9fff]{2,}", word):
            tokens.extend(word[index : index + 2] for index in range(max(1, len(word) - 1)))
        else:
            tokens.append(word.lower())
    stop = {"内容", "主要", "包括", "说明", "学习", "重点", "理解", "进行", "通过", "需要", "可以"}
    return [token for token in tokens if token not in stop]
