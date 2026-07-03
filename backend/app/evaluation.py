from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .normalization import contract_report
from .rag.text_utils import tokenize


def evaluate_result(result: dict[str, Any], latency_ms: int) -> dict[str, Any]:
    diagnostics = result.get("citationDiagnostics") or {}
    sources = result.get("sources") or []
    notes = result.get("notes") or []
    questions = (result.get("review") or {}).get("questions") or []
    cited_ids = {
        source_id
        for note in notes
        for source_id in note.get("citationIds", [])
    }
    meta = result.get("_meta") or {}
    model_log = meta.get("modelLog") or {}
    support_values = [_note_support(note, sources) for note in notes]
    metrics = {
        "contractValid": contract_report(result)["valid"],
        "latencyMs": latency_ms,
        "provider": model_log.get("provider") or meta.get("provider") or "offline",
        "model": model_log.get("model") or meta.get("provider") or "deterministic",
        "fallbackUsed": bool(model_log.get("fallbackUsed", False)),
        "noteCount": len(notes),
        "questionCount": len(questions),
        "citationCount": len(result.get("citations") or []),
        "sourceCoverage": round(len(cited_ids) / max(1, len(sources)), 4),
        "noteCitationCoverage": _number(diagnostics.get("noteCitationCoverage")),
        "citationSourceValidity": _number(diagnostics.get("citationSourceValidity")),
        "citationNoteValidity": _number(diagnostics.get("citationNoteValidity")),
        "quoteInSourceRate": _number(diagnostics.get("quoteInSourceRate")),
        "averageConfidence": _number(diagnostics.get("averageConfidence")),
        "noteTitleUniqueness": _number(diagnostics.get("noteTitleUniqueness")),
        "noteContentUniqueness": _number(diagnostics.get("noteContentUniqueness")),
        "averageNoteSourceSupport": round(sum(support_values) / max(1, len(support_values)), 4),
        "averageNoteSupportScore": _number(diagnostics.get("averageNoteSupportScore")),
        "lowSupportNoteRate": _number(diagnostics.get("lowSupportNoteRate")),
        "explicitRefResolutionRate": _number(diagnostics.get("explicitRefResolutionRate", 1)),
        "generatedNoteChars": sum(len(str(note.get("content", ""))) for note in notes),
    }
    metrics["qualityScore"] = _quality_score(metrics)
    metrics["ragGroundingScore"] = _rag_grounding_score(metrics)
    return metrics


def compare_results(
    offline_result: dict[str, Any],
    lanxin_result: dict[str, Any],
    *,
    offline_latency_ms: int,
    lanxin_latency_ms: int,
) -> dict[str, Any]:
    offline = evaluate_result(offline_result, offline_latency_ms)
    lanxin = evaluate_result(lanxin_result, lanxin_latency_ms)
    compared = [
        "qualityScore",
        "sourceCoverage",
        "noteCitationCoverage",
        "quoteInSourceRate",
        "averageConfidence",
        "averageNoteSourceSupport",
        "averageNoteSupportScore",
        "lowSupportNoteRate",
        "explicitRefResolutionRate",
        "generatedNoteChars",
        "latencyMs",
    ]
    deltas = {
        key: round(float(lanxin[key]) - float(offline[key]), 4)
        for key in compared
    }
    winner = "lanxin" if lanxin["qualityScore"] > offline["qualityScore"] else (
        "offline" if offline["qualityScore"] > lanxin["qualityScore"] else "tie"
    )
    return {
        "method": "same Week03 chunks and citation grounding; generation differs",
        "scoreNotice": "qualityScore is a reproducible heuristic, not a human semantic-quality score",
        "offline": offline,
        "lanxin": lanxin,
        "deltaLanxinMinusOffline": deltas,
        "qualityWinner": winner,
    }


def write_comparison_report(comparison: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "comparison.json"
    report_path = output_dir / "comparison.md"
    json_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    offline = comparison["offline"]
    lanxin = comparison["lanxin"]
    delta = comparison["deltaLanxinMinusOffline"]
    rows = [
        ("综合启发式质量分", "qualityScore"),
        ("来源覆盖率", "sourceCoverage"),
        ("笔记引用覆盖率", "noteCitationCoverage"),
        ("引用原文命中率", "quoteInSourceRate"),
        ("平均引用置信度", "averageConfidence"),
        ("笔记-来源词项支持度", "averageNoteSourceSupport"),
        ("生成笔记字符数", "generatedNoteChars"),
        ("耗时 ms", "latencyMs"),
    ]
    lines = [
        "# 蓝心大模型 RAG 与离线 RAG 对比报告",
        "",
        "## 评估口径",
        "",
        "- 两条链路使用相同的 Week03 文档解析、分块、Retriever 与 Citation Grounding。",
        "- 差异仅在生成阶段：离线确定性生成器 vs 蓝心大模型。",
        "- 综合质量分是用于持续回归的启发式指标，不等同于人工语义质量评分。",
        "",
        "## 对比结果",
        "",
        "| 指标 | 离线 RAG | 蓝心 RAG | 蓝心-离线 |",
        "|---|---:|---:|---:|",
    ]
    for label, key in rows:
        lines.append(f"| {label} | {offline[key]} | {lanxin[key]} | {delta[key]} |")
    lines += [
        "",
        "## 结论",
        "",
        f"- 启发式质量指标胜出：`{comparison['qualityWinner']}`。",
        f"- 蓝心调用 Provider：`{lanxin['provider']}` / `{lanxin['model']}`，fallbackUsed=`{lanxin['fallbackUsed']}`。",
        f"- 蓝心相对离线耗时增加 `{delta['latencyMs']}` ms。",
        "- 内容表达质量仍建议补充人工盲评；自动指标主要覆盖契约、引用可靠性、信息量和可复现性。",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, report_path


def _note_support(note: dict[str, Any], sources: list[dict[str, Any]]) -> float:
    source_ids = set(note.get("citationIds") or [])
    source_text = " ".join(str(item.get("text", "")) for item in sources if item.get("id") in source_ids)
    note_tokens = set(tokenize(str(note.get("content", ""))))
    source_tokens = set(tokenize(source_text))
    return len(note_tokens & source_tokens) / max(1, len(note_tokens))


def _rag_grounding_score(metrics: dict[str, Any]) -> float:
    value = (
        float(metrics["quoteInSourceRate"]) * 0.20
        + float(metrics["noteCitationCoverage"]) * 0.15
        + float(metrics["citationSourceValidity"]) * 0.10
        + float(metrics["citationNoteValidity"]) * 0.10
        + float(metrics.get("averageNoteSupportScore") or metrics.get("averageNoteSourceSupport") or 0) * 0.20
        + float(metrics.get("explicitRefResolutionRate", 1)) * 0.10
        + (1 - min(1.0, float(metrics.get("lowSupportNoteRate", 0)))) * 0.15
    )
    return round(value, 4)


def _quality_score(metrics: dict[str, Any]) -> float:
    question_score = min(1.0, float(metrics["questionCount"]) / 5)
    information_score = min(1.0, float(metrics["generatedNoteChars"]) / 1200)
    value = (
        float(metrics["noteCitationCoverage"]) * 0.20
        + float(metrics["citationSourceValidity"]) * 0.10
        + float(metrics["quoteInSourceRate"]) * 0.15
        + float(metrics["averageConfidence"]) * 0.10
        + float(metrics["averageNoteSourceSupport"]) * 0.15
        + float(metrics["sourceCoverage"]) * 0.10
        + float(metrics["noteTitleUniqueness"]) * 0.05
        + question_score * 0.05
        + information_score * 0.10
    )
    return round(value, 4)


def _number(value: Any) -> float:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return 0.0
