from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..agents.orchestrator import (
    build_agent_result_from_modules,
    build_payload,
    normalize_chunks_for_prompt,
)
from ..provider_config import create_provider
from ..prompts import PromptRegistry
from .grounding import ground_result
from .llm_polish import apply_polish_result
from .quality_diagnostics import attach_quality_diagnostics
from .schemas import SourceChunk
from .text_utils import compact


REVIEW_MODULE = "M8_QUALITY_REVIEW"
REGENERATE_MODULE = "M8_QUALITY_GUIDED_REWRITE"


def review_and_rewrite_if_needed(
    result: dict[str, Any],
    chunks: list[SourceChunk],
    *,
    provider_name: str | None,
    threshold: float = 85,
    max_notes: int = 18,
) -> tuple[dict[str, Any], dict[str, Any]]:
    diagnostics = result.get("qualityDiagnostics") if isinstance(result.get("qualityDiagnostics"), dict) else {}
    score = _number(diagnostics.get("overallScore"))
    if score >= threshold:
        return result, {"skipped": True, "reason": "score-above-threshold", "threshold": threshold, "score": score}

    provider = create_provider(provider_name)
    review_payload = _build_review_payload(result, max_notes=max_notes)
    review_output, review_log = provider.generate_module_json(
        REVIEW_MODULE,
        _review_prompt(),
        review_payload,
        max_tokens=4096,
    )
    rewrite_payload = _build_rewrite_payload(result, chunks, review_output, max_notes=max_notes)
    rewrite_output, rewrite_log = provider.generate_module_json(
        REGENERATE_MODULE,
        _rewrite_prompt(),
        rewrite_payload,
        max_tokens=8192,
    )
    rewritten = apply_polish_result(result, rewrite_output, chunks)
    return rewritten, {
        "skipped": False,
        "threshold": threshold,
        "initialScore": score,
        "review": _safe_review_summary(review_output),
        "reviewModelLog": asdict(review_log),
        "rewriteModelLog": asdict(rewrite_log),
        "preservedSourceRefs": True,
        "citationsRebuiltByBackend": True,
    }


def quality_improvement_loop(
    result: dict[str, Any],
    chunks: list[SourceChunk],
    *,
    provider_name: str | None,
    threshold: float = 85,
    top_k: int = 2,
    max_rounds: int = 3,
    max_notes: int = 18,
) -> tuple[dict[str, Any], dict[str, Any]]:
    attach_quality_diagnostics(result)
    initial_score = _diagnostic_score(result)
    if initial_score >= threshold:
        return result, {
            "skipped": True,
            "reason": "score-above-threshold",
            "threshold": threshold,
            "initialScore": initial_score,
            "finalScore": initial_score,
            "rounds": [],
            "selectedRound": 0,
            "usedBestVersion": False,
        }

    provider = create_provider(provider_name)
    best_result = result
    best_score = initial_score
    rounds: list[dict[str, Any]] = []
    current = result

    for round_index in range(1, max(1, max_rounds) + 1):
        round_input_score = _diagnostic_score(current)
        repair_actions = _plan_repair_actions(current)
        review_payload = _build_review_payload(current, max_notes=max_notes)
        review_payload["improvementRound"] = round_index
        review_payload["previousScores"] = [item.get("afterScore") for item in rounds]
        review_payload["plannedRepairActions"] = repair_actions
        review_output, review_log = provider.generate_module_json(
            REVIEW_MODULE,
            _review_prompt(),
            review_payload,
            max_tokens=4096,
        )
        candidate, rewrite_log = _apply_repair_actions(
            current,
            chunks,
            provider,
            review_output,
            repair_actions,
            top_k=top_k,
            round_index=round_index,
            previous_rounds=rounds,
            max_notes=max_notes,
        )
        attach_quality_diagnostics(candidate)
        after_score = _diagnostic_score(candidate)
        selected = after_score > best_score
        if selected:
            best_result = candidate
            best_score = after_score
        round_meta = {
            "round": round_index,
            "beforeScore": round_input_score,
            "afterScore": after_score,
            "selected": selected,
            "actions": repair_actions,
            "review": _safe_review_summary(review_output),
            "reviewModelLog": asdict(review_log),
            "rewriteModelLog": asdict(rewrite_log) if rewrite_log else {},
        }
        rounds.append(round_meta)
        current = candidate
        if after_score >= threshold:
            best_result = candidate
            best_score = after_score
            break

    selected_round = 0
    for item in rounds:
        if item.get("selected"):
            selected_round = int(item.get("round") or 0)
    if best_score >= threshold:
        selected_round = int(rounds[-1].get("round") or selected_round) if rounds else selected_round
    return best_result, {
        "skipped": False,
        "threshold": threshold,
        "maxRounds": max_rounds,
        "initialScore": initial_score,
        "finalScore": best_score,
        "beforeScore": initial_score,
        "afterScore": best_score,
        "rounds": rounds,
        "selectedRound": selected_round,
        "usedBestVersion": best_score < threshold,
        "preservedSourceRefs": True,
        "citationsRebuiltByBackend": True,
    }


def _plan_repair_actions(result: dict[str, Any]) -> list[str]:
    diagnostics = result.get("qualityDiagnostics") if isinstance(result.get("qualityDiagnostics"), dict) else {}
    metrics = diagnostics.get("keyMetrics") if isinstance(diagnostics.get("keyMetrics"), dict) else {}
    content_quality = (result.get("_meta") or {}).get("contentQuality") if isinstance(result.get("_meta"), dict) else {}
    failed = set(content_quality.get("failedChecks") or []) if isinstance(content_quality.get("failedChecks"), list) else set()
    notes = result.get("notes") if isinstance(result.get("notes"), list) else []
    review = result.get("review") if isinstance(result.get("review"), dict) else {}
    actions: list[str] = []

    def add(*items: str) -> None:
        for item in items:
            if item not in actions:
                actions.append(item)

    if _number(diagnostics.get("assetCompleteness"), 100) < 80 or len(notes) < 3:
        add("M2", "M3", "M4", "M6")
    if _number(diagnostics.get("structureScore"), 100) < 85 or failed & {
        "raw-concat-summary-present",
        "weak-key-point-high",
        "over-fragmented-key-point-high",
        "title-summary-mismatch-present",
        "template-content-present",
        "semantic-field-repetition-high",
        "weak-teaching-value-high",
    }:
        add("M3", "M4")
    if _number(diagnostics.get("reviewScore"), 100) < 85 or len(review.get("questions") or []) < 5:
        add("M6")
    if (
        _number(diagnostics.get("citationScore"), 100) < 85
        or _number(metrics.get("citationDisplayCoverage"), 1.0) < 0.8
        or _number(metrics.get("noteCitationCoverage"), 1.0) < 0.95
        or _number(metrics.get("quoteInSourceRate"), 1.0) < 0.95
    ):
        add("M5")
    if not actions:
        add("M3", "M5")
    if "M2" in actions and "M3" not in actions:
        add("M3")
    if "M3" in actions and "M4" not in actions:
        add("M4")
    return actions


def _apply_repair_actions(
    current: dict[str, Any],
    chunks: list[SourceChunk],
    provider: Any,
    review_output: dict[str, Any],
    actions: list[str],
    *,
    top_k: int,
    round_index: int,
    previous_rounds: list[dict[str, Any]],
    max_notes: int,
) -> tuple[dict[str, Any], Any]:
    if actions == ["M5"] or set(actions) == {"M5"}:
        return ground_result(current, chunks, top_k=max(top_k, 3)), None
    if any(action in actions for action in ["M2", "M3", "M4", "M6"]):
        candidate, log = _rerun_selected_modules(
            current,
            chunks,
            provider,
            review_output,
            actions,
            round_index=round_index,
        )
        return ground_result(candidate, chunks, top_k=max(top_k, 3)), log

    rewrite_payload = _build_rewrite_payload(current, chunks, review_output, max_notes=max_notes)
    rewrite_payload["improvementRound"] = round_index
    rewrite_payload["previousAttempts"] = _previous_attempts(previous_rounds)
    rewrite_output, rewrite_log = provider.generate_module_json(
        REGENERATE_MODULE,
        _rewrite_prompt(),
        rewrite_payload,
        max_tokens=8192,
    )
    candidate = apply_polish_result(current, rewrite_output, chunks)
    return ground_result(candidate, chunks, top_k=max(top_k, 3)), rewrite_log


def _rerun_selected_modules(
    current: dict[str, Any],
    chunks: list[SourceChunk],
    provider: Any,
    review_output: dict[str, Any],
    actions: list[str],
    *,
    round_index: int,
) -> tuple[dict[str, Any], Any]:
    registry = PromptRegistry.load_default()
    prompt_chunks = normalize_chunks_for_prompt(chunks)
    outputs = _outputs_from_current_result(current)
    last_log = None
    modules = [module for module in ["M2", "M3", "M4", "M6"] if module in actions]
    for module in modules:
        payload = build_payload(module, prompt_chunks, outputs)
        payload["qualityRepair"] = {
            "enabled": True,
            "round": round_index,
            "plannedActions": actions,
            "semanticReview": review_output,
            "policy": {
                "doNotOptimizeForMetricNames": True,
                "doNotMentionQualityScores": True,
                "preserveEvidenceGrounding": True,
                "focusOnLearnerValue": True,
                "ifAddingNotes": "only split genuinely distinct concepts supported by chunks",
                "ifAddingReviewQuestions": "cover the strongest notes and include usable explanations",
            },
        }
        output, log = provider.generate_module_json(module, registry.get(module), payload, max_tokens=_module_max_tokens(module))
        outputs[module] = output if isinstance(output, dict) else {}
        last_log = log
    candidate = build_agent_result_from_modules(
        outputs,
        chunks,
        input_path=Path(str((current.get("_meta") or {}).get("inputFile") or "")) if (current.get("_meta") or {}).get("inputFile") else None,
        prompt_source=registry.source,
    )
    candidate["id"] = current.get("id") or candidate.get("id")
    candidate.setdefault("_meta", {}).update({key: value for key, value in (current.get("_meta") or {}).items() if key not in {"contentQuality"}})
    candidate["_meta"]["qualityRepairActions"] = actions
    candidate["_meta"]["qualityRepairRound"] = round_index
    return candidate, last_log


def _outputs_from_current_result(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    notes = result.get("notes") if isinstance(result.get("notes"), list) else []
    return {
        "M2": {
            "topic": result.get("topic"),
            "summary": result.get("summary"),
            "keywords": result.get("keywords") or [],
            "core_points": result.get("outline") or result.get("reportPlan") or [],
            "learning_scene": result.get("learningScene") or "",
        },
        "M3": {
            "notes": notes,
            "global_summary": result.get("summary") or "",
            "possible_risks": result.get("warnings") or [],
        },
        "M4": {"mindmap": result.get("mindMap") or {}},
        "M6": {"review": result.get("review") or {}},
    }


def _module_max_tokens(module: str) -> int:
    return {"M2": 4096, "M3": 8192, "M4": 6144, "M6": 4096}.get(module.upper(), 4096)


def _previous_attempts(rounds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "round": item.get("round"),
            "beforeScore": item.get("beforeScore"),
            "afterScore": item.get("afterScore"),
            "selected": item.get("selected"),
            "actions": item.get("actions"),
        }
        for item in rounds
    ]


def _build_review_payload(result: dict[str, Any], *, max_notes: int) -> dict[str, Any]:
    diagnostics = result.get("qualityDiagnostics") if isinstance(result.get("qualityDiagnostics"), dict) else {}
    content_quality = (result.get("_meta") or {}).get("contentQuality") if isinstance(result.get("_meta"), dict) else {}
    notes = []
    for note in (result.get("notes") or [])[:max_notes]:
        notes.append(
            {
                "id": note.get("id"),
                "title": note.get("title"),
                "summary": note.get("summary"),
                "content": compact(str(note.get("content") or ""), 420),
                "keyPoints": note.get("keyPoints") or [],
                "sourceExcerpts": note.get("sourceExcerpts") or [],
            }
        )
    return {
        "task": "semantic_learning_quality_review",
        "topic": result.get("topic"),
        "documentSummary": result.get("summary"),
        "qualityDiagnostics": diagnostics,
        "contentQuality": content_quality,
        "notes": notes,
        "reviewPolicy": {
            "evaluateForLearners": True,
            "doNotOptimizeForMetricNames": True,
            "focus": [
                "whether each note teaches a useful concept",
                "whether key points are complete and reviewable",
                "whether summary, content and key points play different roles",
                "whether evidence supports the note",
                "whether the user can learn or answer questions from the output",
            ],
        },
        "outputSchema": {
            "overallVerdict": "short judgement",
            "priorityProblems": [
                {
                    "noteId": "existing note id or empty for global issue",
                    "problem": "learner-facing problem",
                    "cause": "likely cause in generation or organization",
                    "rewriteGuidance": "general rewrite guidance, not metric-specific",
                }
            ],
            "globalRewriteRules": ["general semantic rule"],
            "doNotDo": ["overfit to score labels"],
        },
    }


def _build_rewrite_payload(
    result: dict[str, Any],
    chunks: list[SourceChunk],
    review_output: dict[str, Any],
    *,
    max_notes: int,
) -> dict[str, Any]:
    source_by_id = {chunk.id: chunk for chunk in chunks}
    notes = []
    for note in (result.get("notes") or [])[:max_notes]:
        refs = _string_list(note.get("sourceRefs") or note.get("source_refs") or note.get("citationIds"))
        evidence = []
        for ref in refs[:3]:
            chunk = source_by_id.get(ref)
            if chunk:
                evidence.append(
                    {
                        "sourceId": chunk.id,
                        "sourceRef": chunk.sourceRef,
                        "heading": chunk.heading,
                        "text": compact(chunk.text, 900),
                    }
                )
        notes.append(
            {
                "id": note.get("id"),
                "title": note.get("title"),
                "summary": note.get("summary"),
                "content": note.get("content"),
                "keyPoints": note.get("keyPoints") or [],
                "level": note.get("level") or 1,
                "parentId": note.get("parentId"),
                "sourceRefs": refs,
                "evidence": evidence,
            }
        )
    return {
        "task": "quality_guided_note_rewrite",
        "topic": result.get("topic"),
        "documentSummary": result.get("summary"),
        "semanticReview": review_output,
        "notes": notes,
        "rewriteContract": {
            "preserveNoteIds": True,
            "preserveSourceRefs": True,
            "doNotAddFactsOutsideEvidence": True,
            "doNotMentionQualityScoresOrDiagnostics": True,
            "doNotOptimizeAgainstMetricNames": True,
            "summaryRole": "one explanatory sentence that teaches the note's core idea",
            "keyPointRole": "3 to 6 complete, reviewable learning points",
            "contentRole": "explain mechanism, context, distinction, or answer pattern without repeating the list",
            "whenEvidenceIsWeak": "make the note narrower instead of inventing missing facts",
        },
        "outputSchema": {
            "notes": [
                {
                    "id": "existing note id",
                    "title": "clear concept title",
                    "summary": "one useful sentence",
                    "content": "non-repeating explanation",
                    "keyPoints": ["complete learning point"],
                    "level": 1,
                    "parentId": "existing parent id or null",
                    "sourceRefs": ["unchanged existing source ids"],
                }
            ]
        },
    }


def _review_prompt() -> str:
    return (
        "你是学习产品的质量审查专家。只返回严格 JSON。"
        "你要从真实用户学习效果出发审查笔记，而不是迎合某个评分器。"
        "请指出会影响理解、复习、答题和查证的问题，并给出通用语义改写建议。"
        "不要要求加入评分关键词，不要按 failedCheck 名称机械修补。"
    )


def _rewrite_prompt() -> str:
    return (
        "你是学习笔记重写模块。只返回严格 JSON。"
        "根据语义审查意见重写 NOTE，但必须只使用 evidence 中可支持的信息。"
        "保留所有 note id 和 sourceRefs，不新增来源，不输出 citations。"
        "目标是让用户真正学会：标题清楚，概要有解释价值，要点完整可复习，content 不重复列表。"
        "不要提及质量分数、评分项或诊断字段。"
    )


def _safe_review_summary(review_output: Any) -> dict[str, Any]:
    if not isinstance(review_output, dict):
        return {}
    problems = review_output.get("priorityProblems")
    rules = review_output.get("globalRewriteRules")
    return {
        "overallVerdict": str(review_output.get("overallVerdict") or "")[:300],
        "priorityProblemCount": len(problems) if isinstance(problems, list) else 0,
        "globalRewriteRules": rules[:8] if isinstance(rules, list) else [],
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _number(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _diagnostic_score(result: dict[str, Any]) -> float:
    diagnostics = result.get("qualityDiagnostics") if isinstance(result.get("qualityDiagnostics"), dict) else {}
    return _number(diagnostics.get("overallScore"))
