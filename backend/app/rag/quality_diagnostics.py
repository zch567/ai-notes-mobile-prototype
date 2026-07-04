from __future__ import annotations

from typing import Any

from .content_quality import assess_content_quality


def attach_quality_diagnostics(result: dict[str, Any]) -> dict[str, Any]:
    """Attach user-facing quality and asset diagnostics to an AgentResult."""
    meta = result.setdefault("_meta", {})
    if isinstance(meta, dict) and "contentQuality" not in meta:
        meta["contentQuality"] = assess_content_quality(result)
    result["assetMeta"] = build_asset_meta(result)
    result["qualityDiagnostics"] = build_quality_diagnostics(result)
    return result


def build_asset_meta(result: dict[str, Any]) -> dict[str, Any]:
    meta = result.get("_meta") if isinstance(result.get("_meta"), dict) else {}
    sources = _list(result.get("sources"))
    notes = _list(result.get("notes"))
    citations = _list(result.get("citations"))
    mind_map = result.get("mindMap") if isinstance(result.get("mindMap"), dict) else {}
    review = result.get("review") if isinstance(result.get("review"), dict) else {}
    file_names = sorted(
        {
            str(source.get("fileName") or source.get("title") or "")
            for source in sources
            if isinstance(source, dict) and str(source.get("fileName") or source.get("title") or "").strip()
        }
    )
    source_types = sorted(
        {
            str(source.get("sourceType") or "")
            for source in sources
            if isinstance(source, dict) and str(source.get("sourceType") or "").strip()
        }
    )
    return {
        "assetVersion": "learning-asset-v1",
        "resultId": str(result.get("id") or ""),
        "topic": str(result.get("topic") or ""),
        "generatedAt": meta.get("generatedAt") or "",
        "inputFile": meta.get("inputFile") or "",
        "fileNames": file_names,
        "sourceTypes": source_types,
        "pipeline": meta.get("pipeline") or meta.get("agentMode") or "",
        "parser": meta.get("parser") or "",
        "learningMode": result.get("learningScene") or result.get("learningMode") or "auto",
        "chunkCount": int(_number(meta.get("chunkCount"), len(sources))),
        "noteCount": len(notes),
        "sourceCount": len(sources),
        "citationCount": len(citations),
        "mindMapNodeCount": len(_list(mind_map.get("nodes"))),
        "mindMapEdgeCount": len(_list(mind_map.get("edges"))),
        "reviewQuestionCount": len(_list(review.get("questions"))),
        "stageIds": [str(stage.get("id") or "") for stage in _list(result.get("agentStages")) if isinstance(stage, dict)],
    }


def build_quality_diagnostics(result: dict[str, Any]) -> dict[str, Any]:
    notes = _list(result.get("notes"))
    citations = _list(result.get("citations"))
    sources = _list(result.get("sources"))
    mind_map = result.get("mindMap") if isinstance(result.get("mindMap"), dict) else {}
    review = result.get("review") if isinstance(result.get("review"), dict) else {}
    meta = result.get("_meta") if isinstance(result.get("_meta"), dict) else {}
    content_quality = meta.get("contentQuality") if isinstance(meta.get("contentQuality"), dict) else {}
    content_metrics = content_quality.get("metrics") if isinstance(content_quality.get("metrics"), dict) else {}
    citation_metrics = result.get("citationDiagnostics") if isinstance(result.get("citationDiagnostics"), dict) else {}

    asset_score = _asset_score(notes, sources, citations, mind_map, review, citation_metrics)
    citation_score = _citation_score(citation_metrics, notes)
    structure_score = _structure_score(content_quality, content_metrics, notes)
    review_score = _review_score(review, notes)
    multi_agent_score = _multi_agent_score(result, meta)
    raw_overall = round(
        asset_score * 0.22
        + citation_score * 0.24
        + structure_score * 0.30
        + review_score * 0.12
        + multi_agent_score * 0.12,
        1,
    )
    overall = _cap_overall_score(raw_overall, content_quality, content_metrics, citation_metrics)
    warnings = _quality_warnings(result, content_quality, content_metrics, citation_metrics)
    diagnostics = {
        "overallScore": overall,
        "assetCompleteness": round(asset_score, 1),
        "citationScore": round(citation_score, 1),
        "structureScore": round(structure_score, 1),
        "reviewScore": round(review_score, 1),
        "multiAgentScore": round(multi_agent_score, 1),
        "passed": overall >= 85 and not _has_blocking_quality_issue(content_quality, citation_metrics),
        "summaryText": _summary_text(overall, notes, review, citation_metrics),
        "warnings": warnings,
        "dimensions": [
            {"id": "asset", "label": "学习资产完整度", "score": round(asset_score, 1)},
            {"id": "citation", "label": "可信引用审计", "score": round(citation_score, 1)},
            {"id": "structure", "label": "概要与要点质量", "score": round(structure_score, 1)},
            {"id": "review", "label": "复习可用性", "score": round(review_score, 1)},
            {"id": "multiAgent", "label": "多 Agent 链路", "score": round(multi_agent_score, 1)},
        ],
        "keyMetrics": {
            "noteCitationCoverage": _number(citation_metrics.get("noteCitationCoverage")),
            "quoteInSourceRate": _number(citation_metrics.get("quoteInSourceRate")),
            "averageConfidence": _number(citation_metrics.get("averageConfidence")),
            "rawConcatSummaryRate": _number(content_metrics.get("rawConcatSummaryRate")),
            "weakKeyPointRate": _number(content_metrics.get("weakKeyPointRate")),
            "weakTeachingValueRate": _number(content_metrics.get("weakTeachingValueRate")),
            "citationDisplayCoverage": _number(content_metrics.get("citationDisplayCoverage")),
        },
    }
    return diagnostics


def _asset_score(
    notes: list[Any],
    sources: list[Any],
    citations: list[Any],
    mind_map: dict[str, Any],
    review: dict[str, Any],
    citation_metrics: dict[str, Any],
) -> float:
    note_score = min(1.0, len(notes) / 6)
    source_score = 1.0 if sources else 0.0
    citation_score = _number(citation_metrics.get("noteCitationCoverage"), 1.0 if citations else 0.0)
    node_score = min(1.0, len(_list(mind_map.get("nodes"))) / max(1, min(len(notes) + 1, 10)))
    question_score = min(1.0, len(_list(review.get("questions"))) / 5)
    return 100 * (
        note_score * 0.25
        + source_score * 0.15
        + citation_score * 0.25
        + node_score * 0.20
        + question_score * 0.15
    )


def _citation_score(citation_metrics: dict[str, Any], notes: list[Any]) -> float:
    if not citation_metrics and not notes:
        return 0.0
    note_coverage = _number(citation_metrics.get("noteCitationCoverage"))
    quote_rate = _number(citation_metrics.get("quoteInSourceRate"))
    confidence = _number(citation_metrics.get("averageConfidence"))
    support = _number(citation_metrics.get("averageNoteSupportScore"))
    explicit_resolution = _number(citation_metrics.get("explicitRefResolutionRate"), 1.0)
    low_support = _number(citation_metrics.get("lowSupportNoteRate"))
    score = (
        note_coverage * 0.30
        + quote_rate * 0.25
        + confidence * 0.15
        + support * 0.15
        + explicit_resolution * 0.10
        + (1 - min(1.0, low_support)) * 0.05
    )
    return max(0.0, min(100.0, score * 100))


def _structure_score(content_quality: dict[str, Any], metrics: dict[str, Any], notes: list[Any]) -> float:
    if not notes:
        return 0.0
    issue_weights = {
        "templateSummaryRate": 18,
        "lowInfoSummaryRate": 16,
        "rawConcatSummaryRate": 24,
        "titleSummaryMismatchRate": 20,
        "weakKeyPointRate": 18,
        "overFragmentedKeyPointRate": 12,
        "brokenFragmentRate": 24,
        "truncatedSentenceRate": 18,
        "semanticFieldRepetitionRate": 16,
        "weakTeachingValueRate": 12,
        "weakLearningActionabilityRate": 8,
        "weakEvidenceRelevanceRate": 8,
    }
    penalty = sum(_number(metrics.get(name)) * weight for name, weight in issue_weights.items())
    if content_quality and not content_quality.get("passed", True):
        penalty += 6
    return max(0.0, min(100.0, 100 - penalty))


def _cap_overall_score(
    overall: float,
    content_quality: dict[str, Any],
    content_metrics: dict[str, Any],
    citation_metrics: dict[str, Any],
) -> float:
    if not content_quality.get("passed", True):
        overall = min(overall, 79.0)
    hard_content_metrics = [
        "rawConcatSummaryRate",
        "templateContentRate",
        "fragmentTitleRate",
        "activityNoteRate",
        "weakKeyPointRate",
    ]
    if any(_number(content_metrics.get(name)) > 0 for name in hard_content_metrics):
        overall = min(overall, 74.0)
    if _number(content_metrics.get("weakLearningActionabilityRate")) > 0.35 or _number(content_metrics.get("learningRoleCoverage"), 1.0) < 1.0:
        overall = min(overall, 79.0)
    if _number(citation_metrics.get("noteCitationCoverage"), 1.0) < 0.8 or _number(citation_metrics.get("quoteInSourceRate"), 1.0) < 0.8:
        overall = min(overall, 74.0)
    return round(overall, 1)


def _review_score(review: dict[str, Any], notes: list[Any]) -> float:
    questions = _list(review.get("questions"))
    if not notes:
        return 0.0
    question_score = min(1.0, len(questions) / 5)
    linked = sum(bool(question.get("citationIds")) for question in questions if isinstance(question, dict))
    link_score = linked / max(1, len(questions)) if questions else 0.0
    weak_points = min(1.0, len(_list(review.get("weakPoints"))) / 2)
    recommendations = min(1.0, len(_list(review.get("recommendations"))) / 2)
    return 100 * (question_score * 0.45 + link_score * 0.25 + weak_points * 0.15 + recommendations * 0.15)


def _multi_agent_score(result: dict[str, Any], meta: dict[str, Any]) -> float:
    stage_ids = {str(stage.get("id") or "") for stage in _list(result.get("agentStages")) if isinstance(stage, dict)}
    expected = {"M1", "M2", "M3", "M4", "M5", "M6"}
    if not any(stage_id.startswith("M") for stage_id in stage_ids):
        expected = {"parse", "chunk", "retrieve", "citation"}
    stage_score = len(stage_ids & expected) / max(1, len(expected))
    modules = _list(meta.get("agentModules"))
    module_score = min(1.0, len(modules) / 7) if modules else stage_score
    observability = 1.0 if meta.get("modelLog") or meta.get("modelLogs") or result.get("citationDiagnostics") else 0.7
    return 100 * (stage_score * 0.50 + module_score * 0.30 + observability * 0.20)


def _quality_warnings(
    result: dict[str, Any],
    content_quality: dict[str, Any],
    content_metrics: dict[str, Any],
    citation_metrics: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    failed = content_quality.get("failedChecks") if isinstance(content_quality.get("failedChecks"), list) else []
    labels = {
        "raw-concat-summary-present": "存在拼接式概要，需要重写为语义化总结。",
        "weak-key-point-high": "要点质量偏弱，需要补全为可复习的完整知识点。",
        "over-fragmented-key-point-high": "要点切分过细，需要合并同一概念下的碎片。",
        "title-summary-mismatch-present": "标题和概要存在错配，需要重新绑定主题。",
        "weak-teaching-value-high": "部分笔记学习指导不足，需要补充答题或理解方法。",
        "citation-display-low": "可读原文摘录覆盖不足，用户查证会受影响。",
    }
    for item in failed:
        text = labels.get(str(item))
        if text and text not in warnings:
            warnings.append(text)
    if _number(citation_metrics.get("noteCitationCoverage")) < 0.95:
        warnings.append("部分笔记没有引用回链，建议复核来源绑定。")
    if _number(citation_metrics.get("quoteInSourceRate")) < 0.95:
        warnings.append("部分 quote 未命中原文，建议检查引用抽取。")
    if _number(content_metrics.get("weakLearningActionabilityRate")) > 0.20:
        warnings.append("部分内容缺少学习动作建议，复习路径还不够明确。")
    if not result.get("notes"):
        warnings.append("未生成有效笔记。")
    return warnings[:6]


def _has_blocking_quality_issue(content_quality: dict[str, Any], citation_metrics: dict[str, Any]) -> bool:
    failed = set(content_quality.get("failedChecks") or []) if isinstance(content_quality.get("failedChecks"), list) else set()
    blocking = {
        "raw-concat-summary-present",
        "weak-key-point-high",
        "broken-fragment-present",
        "title-summary-mismatch-present",
        "generic-template-mismatch-present",
        "transition-fragment-present",
    }
    if failed & blocking:
        return True
    return _number(citation_metrics.get("noteCitationCoverage")) < 0.8 or _number(citation_metrics.get("quoteInSourceRate")) < 0.8


def _summary_text(overall: float, notes: list[Any], review: dict[str, Any], citation_metrics: dict[str, Any]) -> str:
    note_count = len(notes)
    question_count = len(_list(review.get("questions")))
    coverage = int(round(_number(citation_metrics.get("noteCitationCoverage")) * 100))
    quote = int(round(_number(citation_metrics.get("quoteInSourceRate")) * 100))
    return (
        f"本次生成质量评分 {int(round(overall))}，形成 {note_count} 条结构化笔记、"
        f"{question_count} 道复习题；引用覆盖率 {coverage}%，原文 quote 命中率 {quote}%。"
    )


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _number(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
