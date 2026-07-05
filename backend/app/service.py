from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .adapters import RagPipelineAdapter, SidecarCapabilityAdapter
from .agents import ModuleAgentOrchestrator
from .config import settings
from .contracts import ReviewAnswerItem, RunAgentRequest
from .errors import BadRequestError, NotFoundError, ProviderError, ValidationError
from .normalization import normalize_agent_result, raw_contract_report
from .ocr import create_lanxin_ocr_client
from .provider_config import create_provider
from .rag.fingerprint import corpus_hash
from .rag.io_utils import load_chunks
from .rag.llm_polish import polish_result_with_provider
from .rag.llm_quality_review import quality_improvement_loop
from .rag.parsing import detect_ocr_need
from .rag.quality_diagnostics import attach_quality_diagnostics

ProgressCallback = Callable[[dict[str, Any]], None]


class AgentService:
    def __init__(self) -> None:
        self.rag = RagPipelineAdapter()
        self.legacy = SidecarCapabilityAdapter()
        self.agent = ModuleAgentOrchestrator()
        self._retriever_cache: dict[str, Any] = {}

    def run(self, request: RunAgentRequest, progress: ProgressCallback | None = None) -> dict[str, Any]:
        _report_progress(
            progress,
            "prepare",
            5,
            "准备材料",
            "正在整理输入内容和上传文件信息，准备交给后端处理。",
        )
        input_path = self._resolve_input(request)
        pipeline = request.pipeline or settings.default_pipeline
        ocr_text_dir = self._optional_safe_path(request.ocrTextDir)
        office_ocr_dir = self._optional_safe_path(request.officeOcrDir)
        ocr_client = None
        ocr_error = ""
        ocr_decision: dict[str, Any] = {
            "enabled": False,
            "reason": "sidecar-ocr-mode" if (ocr_text_dir or office_ocr_dir) else "not-evaluated",
            "signals": [],
        }

        _report_progress(
            progress,
            "parse",
            18,
            "解析资料",
            "后端正在抽取文本、拆分片段，并保留可追溯的来源位置。",
        )
        if ocr_text_dir or office_ocr_dir:
            chunks = self.legacy.parse_with_sidecars(
                input_path,
                ocr_text_dir=ocr_text_dir,
                office_ocr_dir=office_ocr_dir,
            )
            parser_name = "week2-sidecar-parser"
        else:
            ocr_decision = self._resolve_ocr_decision(input_path, request.enableOcr)
            if ocr_decision.get("enabled"):
                try:
                    ocr_client = create_lanxin_ocr_client()
                except Exception as exc:
                    ocr_error = str(exc)
                    if request.enableOcr is True and request.strictProvider:
                        raise ProviderError(f"Lanxin OCR failed to initialize: {exc}") from exc
                    ocr_decision = {**ocr_decision, "enabled": False, "error": ocr_error}
            chunks = self.rag.parse(input_path, ocr_client=ocr_client)
            parser_name = "structure-aware-parser"
        if not chunks:
            raise BadRequestError(f"No text extracted from {input_path}")
        _report_progress(
            progress,
            "parse",
            30,
            "解析资料",
            f"已解析出 {len(chunks)} 个来源片段，正在准备生成学习内容。",
        )

        model_log: dict[str, Any] | None = None
        agent_meta: dict[str, Any] = {}
        _report_progress(
            progress,
            "generate",
            42,
            "正在调用大模型生成笔记",
            "后端正在调用已配置的大模型，围绕主题、摘要和核心知识点生成结构化笔记。",
        )
        if pipeline == "hybrid":
            draft, agent_meta = self.agent.generate(
                chunks,
                input_path=input_path,
                provider_name=request.provider,
                strict=request.strictProvider,
            )
            _report_progress(
                progress,
                "ground",
                68,
                "绑定引用",
                "正在把生成内容和来源片段对齐，重建引用关系。",
            )
            result = self.rag.ground(draft, chunks, request.topK)
            model_log = agent_meta.get("modelLog")
        elif pipeline == "rag-only":
            result = self.rag.build_deterministic_result(chunks, input_path)
            if request.provider:
                try:
                    result, polish_meta = polish_result_with_provider(
                        result,
                        chunks,
                        provider_name=request.provider,
                    )
                    agent_meta["llmPolish"] = polish_meta
                    model_log = polish_meta.get("modelLog")
                except Exception as exc:
                    if request.strictProvider:
                        raise ProviderError(f"Provider note polish failed: {exc}") from exc
                    result.setdefault("warnings", []).append(f"Provider note polish fallback used: {exc}")
                _report_progress(
                    progress,
                    "ground",
                    68,
                    "绑定引用",
                    "正在把生成内容和来源片段对齐，重建引用关系。",
                )
                result = self.rag.ground(result, chunks, request.topK)
        else:
            raise BadRequestError("pipeline must be 'hybrid' or 'rag-only'")

        _report_progress(
            progress,
            "compose",
            84,
            "组织学习资产",
            "正在组合笔记、导图、引用和复习题。",
        )
        result.setdefault("_meta", {}).update(
            {
                "pipeline": pipeline,
                "parser": parser_name,
                "contract": "AgentResult",
                "contractVersion": "1.0",
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "requestedProvider": request.provider or "configured",
                "ocr": {
                    "enabled": bool(ocr_client),
                    "mode": "auto" if request.enableOcr is None else ("forced" if request.enableOcr else "disabled"),
                    "provider": "lanxin-ocr" if ocr_client else "",
                    "decision": ocr_decision,
                    "stats": ocr_client.stats.to_dict() if ocr_client else {},
                    "error": ocr_error,
                },
            }
        )
        result["_meta"].update({key: value for key, value in agent_meta.items() if value is not None})
        if model_log:
            result["_meta"]["modelLog"] = model_log

        attach_quality_diagnostics(result)
        if request.enableQualityReview:
            try:
                result, review_meta = quality_improvement_loop(
                    result,
                    chunks,
                    provider_name=request.provider,
                    threshold=request.qualityReviewThreshold,
                    top_k=request.topK,
                    max_rounds=3,
                )
                result.setdefault("_meta", {})["qualityReview"] = review_meta
                result["_meta"]["qualityReview"]["finalGroundingApplied"] = not review_meta.get("skipped")
            except Exception as exc:
                if request.strictProvider:
                    raise ProviderError(f"Provider quality review failed: {exc}") from exc
                result.setdefault("warnings", []).append(f"Provider quality review fallback used: {exc}")
                result.setdefault("_meta", {})["qualityReview"] = {
                    "skipped": True,
                    "reason": "provider-error",
                    "error": str(exc),
                }
        normalized = normalize_agent_result(result)
        result_id = normalized["id"] or f"agent-{uuid.uuid4().hex[:8]}"
        normalized["id"] = result_id
        _report_progress(
            progress,
            "finalize",
            94,
            "保存结果",
            "正在保存完整 AgentResult，完成后可回到 AI 页查看结果。",
        )
        self._persist(result_id, normalized, chunks)
        return normalized

    def validate(self, result: dict[str, Any]) -> dict[str, Any]:
        try:
            return raw_contract_report(result)
        except Exception as exc:
            raise ValidationError(str(exc)) from exc

    def query(
        self,
        *,
        query: str,
        chunks_path: str | None,
        result_id: str | None,
        top_k: int,
        provider_name: str | None = None,
    ) -> dict[str, Any]:
        if chunks_path:
            path = self._safe_input_path(chunks_path)
        elif result_id:
            path = self._safe_result_dir(result_id) / "chunks.json"
        else:
            raise BadRequestError("chunksPath or resultId is required")
        if not path.exists():
            raise NotFoundError(f"Chunks not found: {path}")
        hits = self._retriever_for(path).retrieve(query, top_k=top_k)
        return {"hits": [hit.to_dict() for hit in hits]}

    def chat(
        self,
        *,
        question: str,
        result_id: str,
        provider_name: str | None,
        strict: bool,
        top_k: int,
    ) -> dict[str, Any]:
        result_dir = self._safe_result_dir(result_id)
        result_path = result_dir / "result.json"
        chunks_path = result_dir / "chunks.json"
        if not result_path.exists():
            raise NotFoundError(result_id)
        if not chunks_path.exists():
            raise NotFoundError(f"chunks for result {result_id}")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        chunks = load_chunks(chunks_path)
        return self.agent.chat(
            question=question,
            result=result,
            chunks=chunks,
            provider_name=provider_name,
            strict=strict,
            top_k=top_k,
        )

    def submit_review_answers(
        self,
        *,
        result_id: str,
        answers: list[ReviewAnswerItem],
        provider_name: str | None,
        strict: bool,
    ) -> dict[str, Any]:
        result_dir = self._safe_result_dir(result_id)
        result_path = result_dir / "result.json"
        chunks_path = result_dir / "chunks.json"
        if not result_path.exists():
            raise NotFoundError(result_id)
        if not chunks_path.exists():
            raise NotFoundError(f"chunks for result {result_id}")

        result = json.loads(result_path.read_text(encoding="utf-8"))
        chunks = load_chunks(chunks_path)
        evaluation = _evaluate_review_answers(result, answers)
        payload = _review_assessment_payload(result, chunks, evaluation)
        prompt = _review_assessment_prompt()
        try:
            provider = create_provider(provider_name)
            output, log = provider.generate_module_json("M7_review_assessment", prompt, payload, max_tokens=3072)
            assessment = _normalize_review_assessment(output, evaluation)
            assessment.setdefault("_meta", {})["modelLog"] = log.__dict__ if hasattr(log, "__dict__") else dict(log)
            return assessment
        except Exception as exc:
            if strict:
                raise ProviderError(f"Provider review assessment failed: {exc}") from exc
            assessment = _fallback_review_assessment(evaluation)
            assessment.setdefault("_meta", {})["fallbackUsed"] = True
            assessment["_meta"]["error"] = str(exc)
            return assessment

    def regenerate_review_questions(
        self,
        *,
        result_id: str,
        review_history: list[dict[str, Any]],
        provider_name: str | None,
        strict: bool,
        question_count: int,
    ) -> dict[str, Any]:
        result_dir = self._safe_result_dir(result_id)
        result_path = result_dir / "result.json"
        chunks_path = result_dir / "chunks.json"
        if not result_path.exists():
            raise NotFoundError(result_id)
        if not chunks_path.exists():
            raise NotFoundError(f"chunks for result {result_id}")

        result = json.loads(result_path.read_text(encoding="utf-8"))
        chunks = load_chunks(chunks_path)
        try:
            review, meta = self.agent.regenerate_review(
                result=result,
                review_history=review_history,
                provider_name=provider_name,
                strict=strict,
                question_count=question_count,
            )
        except Exception as exc:
            if strict:
                raise ProviderError(f"Provider review regeneration failed: {exc}") from exc
            review = _fallback_regenerated_review(result, review_history)
            meta = {"fallbackUsed": True, "error": str(exc)}

        result["review"] = review
        result.setdefault("_meta", {})["reviewRegeneration"] = meta
        grounded = self.rag.ground(result, chunks, top_k=2)
        grounded["id"] = result_id
        grounded.setdefault("_meta", {}).update(result.get("_meta") or {})
        attach_quality_diagnostics(grounded)
        normalized = normalize_agent_result(grounded)
        normalized["id"] = result_id
        self._persist(result_id, normalized, chunks)
        return normalized

    def get_result(self, result_id: str) -> dict[str, Any]:
        path = self._safe_result_dir(result_id) / "result.json"
        if not path.exists():
            raise NotFoundError(result_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def _persist(self, result_id: str, result: dict[str, Any], chunks: list[Any]) -> None:
        self._cleanup_runtime_outputs()
        run_dir = settings.output_dir / result_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "chunks.json").write_text(
            json.dumps([chunk.to_dict() for chunk in chunks], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _resolve_input(self, request: RunAgentRequest) -> Path:
        if request.filePath:
            return self._safe_input_path(request.filePath)
        input_dir = settings.output_dir / "_inputs"
        input_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(request.fileName).suffix.lower()
        if suffix not in {".txt", ".md", ".markdown"}:
            suffix = ".md"
        path = input_dir / f"input-{uuid.uuid4().hex[:12]}{suffix}"
        path.write_text(request.sourceText or "", encoding="utf-8")
        return path

    def _safe_input_path(self, value: str) -> Path:
        path = Path(value).expanduser().resolve()
        if path != settings.allowed_input_root and settings.allowed_input_root not in path.parents:
            raise BadRequestError(f"Path is outside BACKEND_ALLOWED_INPUT_ROOT: {path}")
        if not path.exists():
            raise NotFoundError(str(path))
        return path

    def _optional_safe_path(self, value: str | None) -> Path | None:
        return self._safe_input_path(value) if value else None

    def _safe_result_dir(self, result_id: str) -> Path:
        if not result_id or result_id in {".", ".."} or "/" in result_id or "\\" in result_id:
            raise BadRequestError("Invalid resultId")
        path = (settings.output_dir / result_id).resolve()
        output_root = settings.output_dir.resolve()
        if output_root not in path.parents:
            raise BadRequestError("Invalid resultId")
        return path

    def _retriever_for(self, chunks_path: Path):
        from .rag.retrieval import HybridRetriever

        resolved = chunks_path.resolve()
        chunks = load_chunks(resolved)
        key = corpus_hash(chunks)
        cached = self._retriever_cache.get(key)
        if cached:
            return cached
        retriever = HybridRetriever(chunks)
        self._retriever_cache[key] = retriever
        if len(self._retriever_cache) > 32:
            oldest = next(iter(self._retriever_cache))
            self._retriever_cache.pop(oldest, None)
        return retriever

    def _resolve_ocr_decision(self, input_path: Path, requested: bool | None) -> dict[str, Any]:
        if requested is False:
            return {"enabled": False, "reason": "disabled-by-request", "signals": []}
        if requested is True:
            return {"enabled": True, "reason": "forced-by-request", "signals": []}
        return detect_ocr_need(input_path)

    def _cleanup_runtime_outputs(self, *, keep: int = 80) -> None:
        output_root = settings.output_dir
        if not output_root.exists():
            return
        run_dirs = [
            item for item in output_root.iterdir()
            if item.is_dir() and item.name.startswith(("agent-", "rag-")) and (item / "result.json").exists()
        ]
        run_dirs.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        for stale in run_dirs[keep:]:
            shutil.rmtree(stale, ignore_errors=True)


def _report_progress(
    progress: ProgressCallback | None,
    stage_id: str,
    percent: int,
    label: str,
    text: str,
) -> None:
    if not progress:
        return
    try:
        progress(
            {
                "stageId": stage_id,
                "progress": percent,
                "label": label,
                "text": text,
            }
        )
    except Exception:
        return


def _evaluate_review_answers(result: dict[str, Any], answers: list[ReviewAnswerItem]) -> dict[str, Any]:
    questions = (result.get("review") or {}).get("questions") or []
    by_id = {str(question.get("id") or question.get("question_id") or ""): question for question in questions if isinstance(question, dict)}
    note_by_id = {str(note.get("id") or ""): note for note in result.get("notes", []) if isinstance(note, dict)}
    answer_items = []
    for answer in answers:
        question_id = str(answer.questionId or "")
        question = by_id.get(question_id)
        if not question:
            raise BadRequestError(f"Unknown review questionId: {question_id}")
        question_type = str(question.get("type") or "").replace("_", "-")
        if question_type not in {"single-choice", "multiple-choice"}:
            raise BadRequestError(f"Only choice answers are supported: {question_id}")
        options = [str(item) for item in question.get("options") or []]
        correct_answer = _normalize_review_answer(question.get("answer"), options, question_type)
        user_answer = _normalize_review_answer(answer.answer, options, question_type)
        related_note_id = str(question.get("relatedNoteId") or question.get("related_note_id") or "")
        note = note_by_id.get(related_note_id, {})
        answer_items.append(
            {
                "questionId": question_id,
                "question": str(question.get("question") or ""),
                "options": options,
                "userAnswer": user_answer,
                "rawUserAnswer": str(answer.answer or ""),
                "correctAnswer": correct_answer,
                "isCorrect": _review_answer_equal(user_answer, correct_answer, question_type),
                "explanation": str(question.get("explanation") or ""),
                "relatedNoteId": related_note_id,
                "relatedNoteTitle": str(note.get("title") or ""),
                "relatedNoteSummary": str(note.get("summary") or note.get("content") or ""),
                "citationIds": [str(item) for item in question.get("citationIds") or []],
            }
        )
    correct_count = sum(1 for item in answer_items if item["isCorrect"])
    total_count = len(answer_items)
    return {
        "resultId": str(result.get("id") or ""),
        "topic": str(result.get("topic") or ""),
        "summary": str(result.get("summary") or ""),
        "correctCount": correct_count,
        "totalCount": total_count,
        "masteryScore": round(correct_count / max(1, total_count) * 100, 1),
        "questionResults": answer_items,
        "wrongItems": [item for item in answer_items if not item["isCorrect"]],
    }


def _review_assessment_payload(result: dict[str, Any], chunks: list[Any], evaluation: dict[str, Any]) -> dict[str, Any]:
    source_by_id = {chunk.id: chunk for chunk in chunks}
    wrong_with_sources = []
    for item in evaluation["wrongItems"]:
        sources = []
        for source_id in item.get("citationIds") or []:
            chunk = source_by_id.get(source_id)
            if chunk:
                sources.append({"source_id": chunk.id, "source_ref": chunk.sourceRef, "text": chunk.text[:900]})
        wrong_with_sources.append({**item, "sources": sources})
    return {
        "topic": evaluation["topic"],
        "summary": evaluation["summary"],
        "mastery_score": evaluation["masteryScore"],
        "question_results": evaluation["questionResults"],
        "wrong_questions": wrong_with_sources,
        "notes": [
            {
                "id": note.get("id"),
                "title": note.get("title"),
                "summary": note.get("summary") or note.get("content"),
            }
            for note in result.get("notes", [])[:12]
            if isinstance(note, dict)
        ],
        "output_schema": {
            "wrongQuestionExplanations": [
                {
                    "questionId": "q1",
                    "mistakeReason": "为什么错",
                    "correctThinking": "正确思路",
                    "knowledgePoint": "对应知识点",
                    "remediation": "如何补救",
                }
            ],
            "weakPoints": ["知识点"],
            "reviewSuggestions": ["具体复习动作"],
        },
    }


def _review_assessment_prompt() -> str:
    return (
        "你是模块 M7 学习评估与个性化复习建议。请只根据输入的复习题、用户答案、标准答案、"
        "关联笔记和来源片段进行错题解析。不要编造资料外知识。返回严格 JSON，字段包括："
        "wrongQuestionExplanations、weakPoints、reviewSuggestions。"
        "wrongQuestionExplanations 每项必须包含 questionId、mistakeReason、correctThinking、"
        "knowledgePoint、remediation。reviewSuggestions 必须具体说明复习什么、为什么复习、怎么复习。"
    )


def _normalize_review_assessment(output: dict[str, Any], evaluation: dict[str, Any]) -> dict[str, Any]:
    data = output if isinstance(output, dict) else {}
    explanations = data.get("wrongQuestionExplanations") or data.get("wrong_question_explanations") or data.get("analysis") or []
    suggestions = data.get("reviewSuggestions") or data.get("review_suggestions") or data.get("suggestions") or []
    weak_points = data.get("weakPoints") or data.get("weak_points") or []
    return {
        "resultId": evaluation["resultId"],
        "masteryScore": evaluation["masteryScore"],
        "correctCount": evaluation["correctCount"],
        "totalCount": evaluation["totalCount"],
        "questionResults": [
            {
                "questionId": item["questionId"],
                "question": item["question"],
                "userAnswer": item["userAnswer"],
                "correctAnswer": item["correctAnswer"],
                "isCorrect": item["isCorrect"],
                "explanation": item["explanation"],
                "relatedNoteId": item["relatedNoteId"],
            }
            for item in evaluation["questionResults"]
        ],
        "wrongQuestionExplanations": _list_of_dicts(explanations) or _fallback_wrong_explanations(evaluation),
        "weakPoints": _string_list(weak_points) or _fallback_weak_points(evaluation),
        "reviewSuggestions": _string_list(suggestions) or _fallback_review_suggestions(evaluation),
    }


def _fallback_review_assessment(evaluation: dict[str, Any]) -> dict[str, Any]:
    return _normalize_review_assessment({}, evaluation)


def _fallback_wrong_explanations(evaluation: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "questionId": item["questionId"],
            "mistakeReason": "用户答案与标准答案不一致，需要回到关联笔记核对概念边界。",
            "correctThinking": item.get("explanation") or "先定位题干考察点，再用关联笔记判断正确选项。",
            "knowledgePoint": item.get("relatedNoteTitle") or item.get("relatedNoteId") or "关联知识点",
            "remediation": "重读关联笔记，总结正确选项成立的关键词，并对比其他选项为什么不成立。",
        }
        for item in evaluation["wrongItems"]
    ]


def _fallback_weak_points(evaluation: dict[str, Any]) -> list[str]:
    points = [item.get("relatedNoteTitle") or item.get("relatedNoteId") for item in evaluation["wrongItems"]]
    return [str(item) for item in points if item] or []


def _fallback_review_suggestions(evaluation: dict[str, Any]) -> list[str]:
    if not evaluation["wrongItems"]:
        return ["本次单选题全部答对，可继续用简答题复述核心概念，检查是否真正理解。"]
    return [
        "优先回看错题关联笔记，逐题写出正确选项成立的依据。",
        "把错误选项和正确选项放在一起比较，标出概念边界、条件和关键词。",
        "完成订正后再次闭卷作答同类单选题，确认不再依赖选项提示。",
    ]


def _fallback_regenerated_review(result: dict[str, Any], review_history: list[dict[str, Any]]) -> dict[str, Any]:
    from .agents.orchestrator import fallback_questions, summarize_review_history

    notes = result.get("notes") if isinstance(result.get("notes"), list) else []
    review = {
        "questions": fallback_questions(notes),
        "masteryScore": 0,
        "weakPoints": summarize_review_history(review_history, current_review=result.get("review") or {}).get("weakPoints") or [],
        "recommendations": [
            "根据上一轮错题优先复习薄弱知识点，再完成新一轮应用题。",
            "新题会尽量避开上一轮题干，并改用场景应用、比较和错因诊断角度。",
        ],
    }
    review.setdefault("_meta", {})["fallbackUsed"] = True
    return review


def _normalize_choice_answer(answer: str, options: list[str]) -> str:
    value = str(answer or "").strip()
    if not value:
        return ""
    label = value.rstrip(".、:：").upper()
    if label in {"A", "B", "C", "D"}:
        index = ord(label) - ord("A")
        if 0 <= index < len(options):
            return options[index]
    for option in options:
        if value == option or value in option or option in value:
            return option
    return value


def _normalize_multi_choice_answer(answer: Any, options: list[str]) -> list[str]:
    raw_values = answer if isinstance(answer, list) else [answer]
    normalized: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        for part in str(value or "").replace("；", ";").replace("，", ",").replace(";", ",").split(","):
            item = _normalize_choice_answer(part, options)
            key = _choice_key(item)
            if item and key and key not in seen:
                seen.add(key)
                normalized.append(item)
    return normalized


def _choice_equal(left: str, right: str) -> bool:
    return bool(_choice_key(left)) and _choice_key(left) == _choice_key(right)


def _choice_set_equal(left: list[str], right: list[str]) -> bool:
    left_keys = {_choice_key(item) for item in left if _choice_key(item)}
    right_keys = {_choice_key(item) for item in right if _choice_key(item)}
    return bool(left_keys) and left_keys == right_keys


def _choice_key(value: str) -> str:
    def clean(value: str) -> str:
        return "".join(ch.lower() for ch in str(value or "") if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")

    return clean(value)
def _normalize_review_answer(raw: Any, options: list[str], question_type: str) -> str:
    if question_type == "multiple-choice":
        raw_values = raw if isinstance(raw, list) else str(raw or "").replace("；", ";").replace("，", ",").split(",")
        answers: list[str] = []
        seen: set[str] = set()
        for item in raw_values:
            normalized = _normalize_choice_answer(str(item), options)
            key = _clean_answer_key(normalized)
            if key and key not in seen:
                seen.add(key)
                answers.append(normalized)
        return "; ".join(answers)
    return _normalize_choice_answer(str(raw or ""), options)


def _review_answer_equal(left: str, right: str, question_type: str) -> bool:
    if question_type == "multiple-choice":
        return _answer_set(left) == _answer_set(right) and bool(_answer_set(right))
    return _choice_equal(left, right)


def _answer_set(value: str) -> set[str]:
    return {
        _clean_answer_key(item)
        for item in str(value or "").replace("；", ";").replace("，", ",").split(";")
        if _clean_answer_key(item)
    }


def _choice_equal(left: str, right: str) -> bool:
    return bool(_clean_answer_key(left)) and _clean_answer_key(left) == _clean_answer_key(right)


def _clean_answer_key(value: str) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, dict):
            text = item.get("suggestion") or item.get("text") or item.get("content") or item.get("knowledgePoint")
        else:
            text = item
        if str(text or "").strip():
            result.append(str(text).strip())
    return result


def _diagnostic_score(result: dict[str, Any]) -> float:
    diagnostics = result.get("qualityDiagnostics") if isinstance(result.get("qualityDiagnostics"), dict) else {}
    try:
        return float(diagnostics.get("overallScore") or 0)
    except (TypeError, ValueError):
        return 0.0
