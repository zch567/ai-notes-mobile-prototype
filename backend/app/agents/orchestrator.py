from __future__ import annotations

import uuid
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..provider_config import create_provider
from ..providers import ModelLog
from ..prompts import PromptRegistry
from ..rag.learning_notes import enrich_learning_notes
from ..rag.retrieval import HybridRetriever
from ..rag.schemas import SourceChunk
from ..rag.text_utils import compact, extract_keywords, tokenize


MODULE_SEQUENCE = ("M2", "M3", "M4", "M6")
AGENT_MODULES = [
    "M1_parse_clean",
    "M2_topic_summary",
    "M3_structured_notes",
    "M4_mindmap",
    "M5_programmatic_citation_grounding",
    "M6_review_generation",
    "M7_note_chat_api",
]
PROMPT_MAX_CHUNKS = 48
PROMPT_TEXT_BUDGET = 18000


class ModuleAgentOrchestrator:
    def __init__(self, registry: PromptRegistry | None = None) -> None:
        self.registry = registry or PromptRegistry.load_default()

    def generate(
        self,
        chunks: list[SourceChunk],
        *,
        input_path: Path | None = None,
        provider_name: str | None = None,
        strict: bool = False,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        prompt_context = _select_context(
            chunks,
            max_chunks=PROMPT_MAX_CHUNKS,
            text_budget=PROMPT_TEXT_BUDGET,
        )
        prompt_chunks = normalize_chunks_for_prompt(prompt_context)
        outputs: dict[str, dict[str, Any]] = {}
        logs: list[dict[str, Any]] = []

        for module in MODULE_SEQUENCE:
            provider = create_provider("lanxin" if module == "M6" else provider_name)
            prompt = self.registry.get(module)
            payload = build_payload(module, prompt_chunks, outputs)
            output, log = provider.generate_module_json(module, prompt, payload, max_tokens=_module_max_tokens(module))
            log_data = asdict(log)
            logs.append(log_data)
            outputs[module] = output if isinstance(output, dict) else {}

        draft = build_agent_result_from_modules(
            outputs,
            chunks,
            input_path=input_path,
            prompt_source=self.registry.source,
        )
        return draft, {
            "agentMode": "modular",
            "agentModules": AGENT_MODULES,
            "promptSource": self.registry.source,
            "modelLogs": logs,
            "modelLog": logs[-1] if logs else None,
            "promptContext": {
                "chunkCount": len(prompt_context),
                "sourceIds": [chunk.id for chunk in prompt_context],
                "textBudget": PROMPT_TEXT_BUDGET,
            },
        }

    def chat(
        self,
        *,
        question: str,
        result: dict[str, Any],
        chunks: list[SourceChunk],
        provider_name: str | None = None,
        strict: bool = False,
        top_k: int = 3,
    ) -> dict[str, Any]:
        provider = create_provider(provider_name)
        retriever = HybridRetriever(chunks)
        hits = retriever.retrieve(question, top_k=top_k)
        payload = {
            "user_query": question,
            "question": question,
            "topic": result.get("topic"),
            "summary": result.get("summary"),
            "notes": _compact_notes_for_prompt(result.get("notes", [])),
            "current_structured_notes": {"notes": _compact_notes_for_prompt(result.get("notes", []))},
            "mindmap": result.get("mindMap") or {},
            "citations": result.get("citations", [])[:20],
            "retrieved_sources": [hit.to_dict() for hit in hits],
        }
        output, log = provider.generate_module_json("M7", self.registry.get("M7"), payload, max_tokens=2048)
        response = output if isinstance(output, dict) else {}
        if not response.get("answer") and response.get("chat_response"):
            response["answer"] = str(response.get("chat_response") or "")
        response.setdefault("answer", "Current material does not contain enough evidence.")
        response.setdefault("used_citations", [])
        response.setdefault("related_notes", [])
        response.setdefault("is_fully_supported_by_sources", False)
        response.setdefault("unsupported_parts", [])
        response.setdefault("follow_up_suggestions", [])
        response["_meta"] = {
            "agentMode": "modular-chat",
            "agentModule": "M7_note_chat",
            "promptSource": self.registry.source,
            "modelLog": asdict(log),
            "retrievedSourceIds": [hit.chunk.id for hit in hits],
        }
        return response

    def regenerate_review(
        self,
        *,
        result: dict[str, Any],
        review_history: list[dict[str, Any]],
        provider_name: str | None = None,
        strict: bool = False,
        question_count: int = 5,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        provider = create_provider(provider_name or "lanxin")
        notes = result.get("notes", [])
        history_summary = summarize_review_history(review_history, current_review=result.get("review") or {})
        payload = build_review_generation_payload(
            notes,
            topic=result.get("topic"),
            summary=result.get("summary"),
            history_summary=history_summary,
            question_count=question_count,
        )
        output, log = provider.generate_module_json("M6", self.registry.get("M6"), payload, max_tokens=_module_max_tokens("M6"))
        review = normalize_review(output.get("review") if isinstance(output, dict) and isinstance(output.get("review"), dict) else output, notes)
        review.setdefault("_meta", {})["regenerated"] = True
        review["_meta"]["historyAware"] = True
        review["_meta"]["strategy"] = payload["adaptive_review_strategy"]
        return review, {
            "agentMode": "modular-review-regeneration",
            "agentModule": "M6_review_generation",
            "promptSource": self.registry.source,
            "modelLog": asdict(log),
            "historySummary": history_summary,
            "strategy": payload["adaptive_review_strategy"],
        }


def _module_max_tokens(module: str) -> int:
    limits = {"M2": 4096, "M3": 8192, "M4": 6144, "M6": 4096}
    return limits.get(module.upper(), 4096)


def normalize_chunks_for_prompt(chunks: list[SourceChunk]) -> list[dict[str, Any]]:
    normalized = []
    for index, chunk in enumerate(chunks, start=1):
        normalized.append(
            {
                "source_id": chunk.id,
                "source_type": chunk.sourceType,
                "file_name": chunk.fileName,
                "page": chunk.page or "",
                "slide": chunk.slide or "",
                "paragraph": chunk.paragraphStart or "",
                "heading": chunk.heading or chunk.title,
                "source_ref": chunk.sourceRef,
                "source_refs": [value for value in (chunk.id, chunk.sourceRef) if value],
                "citation_hint": "Use source_id exactly in note.source_refs when this chunk supports a note.",
                "text": compact(chunk.text, 1200),
                "char_start": chunk.charStart,
                "char_end": chunk.charEnd,
                "chunk_index": chunk.chunkIndex or index,
            }
        )
    return normalized


def build_payload(
    module: str,
    chunks: list[dict[str, Any]],
    outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    language_policy = _output_language_policy()
    if module == "M2":
        return {
            "chunks": chunks,
            **language_policy,
            **_source_ref_policy(chunks),
            "storm_policy": _storm_policy(),
            "seed_research_questions": _seed_research_questions_from_chunks(chunks),
        }
    if module == "M3":
        m2 = outputs.get("M2", {})
        return {
            "chunks": chunks,
            **language_policy,
            **_source_ref_policy(chunks),
            "topic": m2.get("topic"),
            "summary": m2.get("summary"),
            "core_points": m2.get("core_points", []),
            "report_plan": _build_report_plan(m2, outputs.get("M3", {}).get("notes", [])),
            "semantic_note_contract": _semantic_note_contract(),
        }
    if module == "M4":
        return {
            **language_policy,
            "topic": outputs.get("M2", {}).get("topic"),
            "notes": _compact_notes_for_prompt(outputs.get("M3", {}).get("notes", [])),
            "report_plan": _build_report_plan(outputs.get("M2", {}), outputs.get("M3", {}).get("notes", [])),
            "mindmap_schema": {
                "nodes": [
                    {
                        "id": "root|node-id",
                        "label": "concept label",
                        "detail": "what this node explains",
                        "related_note_id": "note id when available",
                        "source_refs": ["exact source ids"],
                    }
                ],
                "edges": [
                    {
                        "from": "source node id",
                        "to": "target node id",
                        "type": "hierarchy|prerequisite|component|mechanism|training-flow|evolution|application|contrast|evidence|solution",
                        "label": "short Chinese relation label",
                        "reason": "why the two modules are connected",
                        "confidence": 0.0,
                        "source_refs": ["exact source ids"],
                    }
                ],
            },
            "allowed_edge_types": [
                "hierarchy",
                "prerequisite",
                "component",
                "mechanism",
                "training-flow",
                "evolution",
                "application",
                "contrast",
                "evidence",
                "solution",
            ],
            "logic_relation_policy": (
                "Make edge types explicit. Prefer concept dependencies and module logic over a flat root star. "
                "Connect input representation to attention as prerequisite, architecture to encoder/decoder/modules as component, "
                "self-attention to multi-head attention as mechanism, training objective to loss/optimizer as training-flow, "
                "advantages to derived models/applications as evolution/application, and challenges to future directions as solution. "
                "Every non-hierarchy relation must cite source_refs or be omitted."
            ),
        }
    if module == "M6":
        return build_review_generation_payload(outputs.get("M3", {}).get("notes", []), **language_policy)
    return {"chunks": chunks}


def build_review_generation_payload(
    notes: Any,
    *,
    topic: Any = None,
    summary: Any = None,
    history_summary: dict[str, Any] | None = None,
    question_count: int = 5,
    **language_policy: Any,
) -> dict[str, Any]:
    compact_notes = _compact_notes_for_prompt(notes)
    history = history_summary or {
        "attemptCount": 0,
        "previousQuestionStems": [],
        "weakPoints": [],
        "reviewSuggestions": [],
        "masteryTrend": [],
    }
    adaptive_strategy = _adaptive_review_strategy(history, question_count)
    return {
        **language_policy,
        "topic": topic,
        "summary": summary,
        "notes": compact_notes,
        "review_history_summary": history,
        "adaptive_review_strategy": adaptive_strategy,
        "user_requirement": (
            f"Generate exactly {question_count} choice questions. Prefer 3 single_choice and 2 multiple_choice when question_count is 5. "
            "Each question must have 4 options. single_choice has exactly 1 correct answer; "
            "multiple_choice has at least 2 correct answers. If the material is insufficient for multiple_choice, use single_choice. "
            "At least 60% of questions must be application, scenario, transfer, comparison, error-diagnosis, or procedure-use questions. "
            "Do not merely ask definitions such as 'what is X' unless needed for a known weak point. "
            "Avoid repeating previousQuestionStems or the same option pattern from review_history_summary. "
            "Use weakPoints and wrongQuestionExplanations to decide what to retest, and raise difficulty when masteryTrend is high."
        ),
        "review_schema": {
            "quiz": [
                {
                    "question_id": "1",
                    "question_type": "single_choice|multiple_choice",
                    "skill": "application|error_diagnosis|comparison|procedure|concept_check",
                    "difficulty": "easy|medium|hard",
                    "question": "scenario/application question stem",
                    "options": ["A. option", "B. option", "C. option", "D. option"],
                    "answer": "single: correct option letter/text; multiple: array or comma-separated letters/text",
                    "explanation": "explain how to apply the note, not only repeat a definition",
                    "related_note_id": "matching note_id from notes",
                }
            ]
        },
        "citations": [],
        "grounding_policy": "citations_are_rebuilt_by_backend_M5",
    }


def summarize_review_history(review_history: list[dict[str, Any]], *, current_review: dict[str, Any] | None = None) -> dict[str, Any]:
    sessions = [item for item in review_history if isinstance(item, dict)][-8:]
    mastery_trend = [_float(item.get("masteryScore"), -1) for item in sessions]
    mastery_trend = [value for value in mastery_trend if value >= 0]
    previous_questions: list[str] = []
    wrong_points: list[str] = []
    suggestions: list[str] = []
    wrong_examples: list[dict[str, str]] = []

    for session in sessions:
        for question in session.get("questionResults") or []:
            if not isinstance(question, dict):
                continue
            stem = _string(question.get("question"), "")
            if stem:
                previous_questions.append(stem)
            if not question.get("isCorrect"):
                wrong_examples.append(
                    {
                        "question": compact(stem, 120),
                        "userAnswer": compact(str(question.get("userAnswer") or ""), 80),
                        "correctAnswer": compact(str(question.get("correctAnswer") or ""), 80),
                    }
                )
        wrong_points.extend(_string_list(session.get("weakPoints")))
        suggestions.extend(_string_list(session.get("reviewSuggestions")))
        for explanation in session.get("wrongQuestionExplanations") or []:
            if isinstance(explanation, dict):
                point = _string(explanation.get("knowledgePoint"), "")
                if point:
                    wrong_points.append(point)
                remediation = _string(explanation.get("remediation") or explanation.get("mistakeReason"), "")
                if remediation:
                    suggestions.append(remediation)

    current_questions = []
    if isinstance(current_review, dict):
        for question in current_review.get("questions") or []:
            if isinstance(question, dict):
                stem = _string(question.get("question"), "")
                if stem:
                    current_questions.append(stem)

    dedup_previous = list(dict.fromkeys(previous_questions + current_questions))
    dedup_weak = list(dict.fromkeys(wrong_points))
    dedup_suggestions = list(dict.fromkeys(suggestions))

    return {
        "attemptCount": len(sessions),
        "masteryTrend": mastery_trend[-6:],
        "averageMasteryScore": round(sum(mastery_trend) / len(mastery_trend), 1) if mastery_trend else None,
        "weakPoints": dedup_weak[:8],
        "wrongExamples": wrong_examples[-8:],
        "reviewSuggestions": dedup_suggestions[:8],
        "previousQuestionStems": dedup_previous[-16:],
        "antiRepetitionPolicy": "Do not reuse these stems, same correct option pattern, or a pure synonym of them.",
    }


def _adaptive_review_strategy(history: dict[str, Any], question_count: int) -> dict[str, Any]:
    mastery = history.get("averageMasteryScore")
    weak_points = history.get("weakPoints") or []
    try:
        mastery_number = float(mastery) if mastery is not None else None
    except (TypeError, ValueError):
        mastery_number = None
    if mastery_number is not None and mastery_number >= 80:
        difficulty = "medium-to-hard"
        focus = "transfer and error-diagnosis questions that require applying notes to new cases"
    elif mastery_number is not None and mastery_number < 60:
        difficulty = "easy-to-medium"
        focus = "weak-point repair through concrete scenarios with one concept boundary per question"
    else:
        difficulty = "medium"
        focus = "balanced application, comparison, and concept-check questions"

    application_count = max(3, round(question_count * 0.6))
    concept_count = max(0, question_count - application_count)
    return {
        "difficulty": difficulty,
        "focus": focus,
        "targetWeakPoints": weak_points[:5],
        "questionMix": {
            "applicationScenario": application_count,
            "conceptCheck": concept_count,
            "includeErrorDiagnosis": True,
            "includeComparison": True,
        },
    }


def build_agent_result_from_modules(
    outputs: dict[str, dict[str, Any]],
    chunks: list[SourceChunk],
    *,
    input_path: Path | None,
    prompt_source: str,
) -> dict[str, Any]:
    m2 = outputs.get("M2", {})
    m3 = outputs.get("M3", {})
    m4 = outputs.get("M4", {})
    m6 = outputs.get("M6", {})

    notes = flatten_notes(m3.get("notes", []))
    if not notes:
        notes = fallback_notes(chunks)
    notes = enrich_learning_notes(notes, chunks)

    topic = _string(m2.get("topic"), _infer_topic(chunks))
    summary = _string(m2.get("summary"), _string(m3.get("global_summary"), ""))
    if not summary:
        summary = compact(" ".join(chunk.text for chunk in chunks[:4]), 260)

    report_plan = _build_report_plan(m2, notes)
    mind_map = convert_mindmap(m4.get("mindmap") or m4.get("mindMap"), topic, notes, report_plan=report_plan)
    review = normalize_review(m6.get("review") or m6, notes)

    return {
        "id": f"agent-{uuid.uuid4().hex[:8]}",
        "topic": topic,
        "summary": summary,
        "keywords": _string_list(m2.get("keywords")) or extract_keywords(" ".join(chunk.text for chunk in chunks), limit=8),
        "learningScene": m2.get("learning_scene") or m2.get("learningScene") or "",
        "outline": normalize_core_points(m2.get("core_points", [])) or report_plan,
        "agentStages": [
            {"id": "M1", "label": "Input Parsing and Cleaning", "text": f"Parsed and chunked {len(chunks)} source chunks."},
            {"id": "M2", "label": "Topic and Summary", "text": "Generated topic, summary, keywords, and core points."},
            {"id": "M3", "label": "Structured Notes", "text": f"Generated {len(notes)} structured notes."},
            {"id": "M4", "label": "Mind Map", "text": f"Generated {len(mind_map.get('nodes', []))} mind-map nodes."},
            {"id": "M5", "label": "Citation Grounding", "text": "Backend retrieval rebuilt source links, quotes, and citation diagnostics."},
            {"id": "M6", "label": "Review Generation", "text": f"Generated {len(review.get('questions', []))} review questions."},
            {"id": "M7", "label": "Note Chat", "text": "Question answering is available through /api/agent/chat using the saved result and chunks."},
        ],
        "sources": [],
        "notes": notes,
        "citations": [],
        "mindMap": mind_map,
        "review": review,
        "warnings": _string_list(m3.get("possible_risks")) + _string_list(m2.get("missing_information")),
        "reportPlan": report_plan,
        "_meta": {
            "inputFile": str(input_path) if input_path else "",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "chunkCount": len(chunks),
            "promptSource": prompt_source,
            "agentMode": "modular",
            "agentModules": AGENT_MODULES,
        },
    }


def flatten_notes(raw_notes: Any) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    used: set[str] = set()

    def visit(items: Any, parent_id: str | None = None, level_offset: int = 0) -> None:
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            index = len(flattened) + 1
            note_id = _string(item.get("id") or item.get("note_id") or item.get("node_id"), f"note-{index}")
            if note_id in used:
                note_id = f"note-{index}"
            used.add(note_id)
            level = _int(item.get("level"), 1) + level_offset
            note = {
                "id": note_id,
                "title": _string(item.get("title"), f"Note {index}"),
                "content": _string(item.get("content"), ""),
                "summary": _string(item.get("summary"), ""),
                "keyPoints": _string_list(item.get("keyPoints") or item.get("key_points")),
                "examples": item.get("examples") if isinstance(item.get("examples"), list) else [],
                "relations": item.get("relations") if isinstance(item.get("relations"), list) else [],
                "blocks": item.get("blocks") if isinstance(item.get("blocks"), list) else [],
                "level": max(1, level),
                "parentId": parent_id,
                "noteType": item.get("note_type") or item.get("type") or "",
                "source_refs": _string_list(item.get("source_refs") or item.get("sourceRefs")),
                "citationIds": [],
            }
            flattened.append(note)
            visit(item.get("children"), note_id, 0)

    visit(raw_notes)
    return flattened


def fallback_notes(chunks: list[SourceChunk]) -> list[dict[str, Any]]:
    notes = []
    for index, chunk in enumerate(chunks[:5], start=1):
        notes.append(
            {
                "id": f"note-{index}",
                "title": chunk.heading or chunk.title or f"Note {index}",
                "content": compact(chunk.text, 360),
                "summary": compact(chunk.text, 220),
                "sourceRefs": [chunk.id],
                "level": 1,
                "parentId": None,
                "noteType": "fallback",
                "source_refs": [chunk.id],
                "citationIds": [],
            }
        )
    return notes


def convert_mindmap(raw: Any, topic: str, notes: list[dict[str, Any]], report_plan: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if isinstance(raw, dict) and isinstance(raw.get("nodes"), list):
        mapped = {
            "nodes": [_frontend_node(node, index, notes) for index, node in enumerate(raw.get("nodes", []))],
            "edges": [_frontend_edge(edge) for edge in raw.get("edges", []) if isinstance(edge, dict)],
        }
        mapped = _enrich_logical_mindmap_edges(mapped, notes, report_plan)
        return mapped if _has_meaningful_mindmap(mapped) or not _is_empty_root_mindmap(mapped) else fallback_mindmap(topic, notes, report_plan=report_plan)

    root = _extract_mindmap_root(raw)
    if isinstance(root, dict):
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        layout = _layout_points(64)

        def visit(node: dict[str, Any], parent: str | None = None) -> None:
            index = len(nodes)
            node_id = _string(node.get("id") or node.get("node_id"), "root" if parent is None else f"node-{index + 1}")
            related_note_id = _string(node.get("relatedNoteId") or node.get("related_note_id"), "")
            x, y = layout[index % len(layout)]
            note = _note_by_id(notes, related_note_id)
            nodes.append(
                {
                    "id": node_id,
                    "label": _string(node.get("label") or node.get("title"), topic if parent is None else f"Node {index + 1}"),
                    "desc": compact(_string(node.get("desc") or (note or {}).get("content"), ""), 60),
                    "detail": _string(node.get("detail") or (note or {}).get("content"), ""),
                    "relatedNoteId": related_note_id,
                    "source_refs": _string_list(node.get("source_refs") or node.get("sourceRefs")),
                    "x": x,
                    "y": y,
                    "line": "#2563eb" if parent is None else "#64748b",
                    "fill": "#ffffff" if parent is None else "#eff6ff",
                }
            )
            if parent:
                edges.append(_frontend_edge({
                    "from": parent,
                    "to": node_id,
                    "type": node.get("edge_type") or node.get("relation_type") or node.get("relation") or "hierarchy",
                    "label": node.get("edge_label") or node.get("relation_label") or "belongs to",
                    "reason": node.get("reason") or node.get("relation_reason") or "Tree parent-child relation returned by M4.",
                    "confidence": node.get("confidence") or 0.72,
                    "source_refs": node.get("source_refs") or node.get("sourceRefs") or [],
                }))
            children = _extract_children(node)
            for child in children:
                if isinstance(child, dict):
                    visit(child, node_id)

        visit(root)
        mapped = _enrich_logical_mindmap_edges({"nodes": nodes, "edges": edges}, notes, report_plan)
        return mapped if _has_meaningful_mindmap(mapped) else fallback_mindmap(topic, notes, report_plan=report_plan)

    return fallback_mindmap(topic, notes, report_plan=report_plan)


def fallback_mindmap(topic: str, notes: list[dict[str, Any]], report_plan: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    groups = _semantic_note_groups(notes, report_plan=report_plan)
    nodes = [
        {
            "id": "root",
            "label": topic,
            "desc": "\u4e2d\u5fc3\u4e3b\u9898",
            "detail": topic,
            "x": 50,
            "y": 12,
            "line": "#2563eb",
            "fill": "#ffffff",
        }
    ]
    edges: list[dict[str, str]] = []
    group_positions = _group_layout(len(groups))

    for group_index, group in enumerate(groups, start=1):
        group_id = f"group-{group_index}"
        gx, gy = group_positions[group_index - 1]
        nodes.append(
            {
                "id": group_id,
                "label": group["label"],
                "desc": compact(group["desc"], 24),
                "detail": group["desc"],
                "x": gx,
                "y": gy,
                "line": "#0f766e" if group_index % 2 else "#7c3aed",
                "fill": "#f0fdfa" if group_index % 2 else "#f5f3ff",
            }
        )
        edges.append(_typed_edge("root", group_id, "hierarchy", "module", "Report-plan module grouping.", source_refs=[]))
        child_y_start = gy + 13
        for note_index, note in enumerate(group["notes"][:5], start=1):
            node_id = f"mind-{note['id']}"
            nodes.append(
                {
                    "id": node_id,
                    "label": compact(note["title"], 22),
                    "desc": compact(note.get("content", ""), 28),
                    "detail": note.get("content", ""),
                    "relatedNoteId": note["id"],
                    "x": gx,
                    "y": min(92, child_y_start + (note_index - 1) * 9),
                    "line": "#64748b",
                    "fill": "#eff6ff",
                }
            )
            edges.append(_typed_edge(group_id, node_id, "component", "contains", "The note belongs to this learning module.", source_refs=_source_refs_from_note(note)))

    if not groups:
        layout = _layout_points(len(notes))
        for index, note in enumerate(notes[:8], start=1):
            x, y = layout[(index - 1) % len(layout)]
            node_id = f"mind-{note['id']}"
            nodes.append(
                {
                    "id": node_id,
                    "label": compact(note["title"], 22),
                    "desc": compact(note.get("content", ""), 28),
                    "detail": note.get("content", ""),
                    "relatedNoteId": note["id"],
                    "x": x,
                    "y": y,
                    "line": "#64748b",
                    "fill": "#eff6ff",
                }
            )
            edges.append(_typed_edge("root", node_id, "hierarchy", "topic", "Fallback topic-to-note relation.", source_refs=_source_refs_from_note(note)))
    return {"nodes": nodes, "edges": edges}


def _extract_mindmap_root(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    for key in ("root", "mindmap", "mindMap", "mind_map", "tree"):
        value = raw.get(key)
        if isinstance(value, dict):
            if isinstance(value.get("root"), dict):
                return value["root"]
            children = _extract_children(value)
            if children or value.get("title") or value.get("label"):
                return value
    branches = raw.get("branches") or raw.get("subtopics") or raw.get("children")
    if isinstance(branches, list):
        return {"id": "root", "title": "\u77e5\u8bc6\u7ed3\u6784", "children": branches}
    return None


def _extract_children(node: dict[str, Any]) -> list[Any]:
    for key in ("children", "branches", "subtopics", "items", "nodes"):
        value = node.get(key)
        if isinstance(value, list):
            return value
    return []


def _has_meaningful_mindmap(mind_map: dict[str, Any]) -> bool:
    return len(mind_map.get("nodes", [])) > 1 and bool(mind_map.get("edges"))


def _is_empty_root_mindmap(mind_map: dict[str, Any]) -> bool:
    nodes = mind_map.get("nodes", [])
    if len(nodes) != 1 or mind_map.get("edges"):
        return False
    node_id = str(nodes[0].get("id", "")).lower()
    return node_id in {"root", "center"}


def _semantic_note_groups(notes: list[dict[str, Any]], report_plan: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    planned = _groups_from_report_plan(notes, report_plan or [])
    if planned:
        return planned
    rules = [
        ("\u8d1d\u53f6\u65af\u57fa\u7840", "\u8d1d\u53f6\u65af\u5b9a\u7406\u4e0e\u6982\u7387\u5206\u7c7b\u7684\u57fa\u7840\u6982\u5ff5", ("\u8d1d\u53f6\u65af\u5b9a\u7406", "\u57fa\u672c\u5f62\u5f0f", "\u5148\u9a8c", "\u540e\u9a8c")),
        ("\u6734\u7d20\u8d1d\u53f6\u65af\u5206\u7c7b\u5668", "\u4ece\u6761\u4ef6\u72ec\u7acb\u5047\u8bbe\u5230\u5224\u51b3\u3001\u4f30\u8ba1\u548c\u8bad\u7ec3\u9884\u6d4b\u6d41\u7a0b", ("\u6734\u7d20\u8d1d\u53f6\u65af", "\u5224\u51b3\u51fd\u6570", "\u6982\u7387\u4f30\u8ba1", "\u96f6\u6982\u7387", "\u8bad\u7ec3", "\u9884\u6d4b")),
        ("\u53c2\u6570\u4f30\u8ba1\u4e0e\u9690\u53d8\u91cf\u4f18\u5316", "\u6700\u5927\u4f3c\u7136\u4f30\u8ba1\u548c EM \u7b97\u6cd5\u652f\u6491\u6a21\u578b\u53c2\u6570\u5b66\u4e60", ("\u6700\u5927\u4f3c\u7136", "MLE", "EM\u7b97\u6cd5", "EM \u7b97\u6cd5", "\u671f\u671b\u6700\u5927\u5316")),
        ("\u6982\u7387\u56fe\u6a21\u578b", "\u8d1d\u53f6\u65af\u4fe1\u5ff5\u7f51\u63cf\u8ff0\u53d8\u91cf\u4f9d\u8d56\u7ed3\u6784\u53ca\u5b66\u4e60\u65b9\u6cd5", ("\u8d1d\u53f6\u65af\u4fe1\u5ff5\u7f51", "\u4fe1\u5ff5\u7f51", "\u7ed3\u6784", "\u5b66\u4e60\u65b9\u6cd5")),
        ("\u5e94\u7528\u573a\u666f", "\u5c06\u6734\u7d20\u8d1d\u53f6\u65af\u5e94\u7528\u4e8e\u6587\u672c\u60c5\u611f\u5206\u7c7b\u7b49\u4efb\u52a1", ("\u6587\u672c\u60c5\u611f", "\u60c5\u611f\u5206\u7c7b", "\u5e94\u7528")),
    ]
    groups = [{"label": label, "desc": desc, "notes": []} for label, desc, _ in rules]
    assigned: set[str] = set()
    for note in notes:
        haystack = f"{note.get('title', '')} {note.get('content', '')}"
        for index, (_label, _desc, keywords) in enumerate(rules):
            if any(keyword in haystack for keyword in keywords):
                groups[index]["notes"].append(note)
                assigned.add(note["id"])
                break
    leftovers = [note for note in notes if note.get("id") not in assigned]
    if leftovers:
        groups.append({"label": "\u8865\u5145\u77e5\u8bc6\u70b9", "desc": "\u5176\u4ed6\u76f8\u5173\u6982\u5ff5\u548c\u8bfe\u7a0b\u7ec6\u8282", "notes": leftovers})
    return [group for group in groups if group["notes"]]


def _groups_from_report_plan(notes: list[dict[str, Any]], report_plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not report_plan or not notes:
        return []
    groups = [
        {
            "label": compact(_string(item.get("title"), f"学习问题 {index}"), 18),
            "desc": _string(item.get("brief"), "围绕该学习问题组织证据、概念和应用。"),
            "notes": [],
        }
        for index, item in enumerate(report_plan[:6], start=1)
        if isinstance(item, dict)
    ]
    if not groups:
        return []
    assigned: set[str] = set()
    group_tokens = [set(tokenize(f"{group['label']} {group['desc']}")) for group in groups]
    for note in notes:
        note_tokens = set(tokenize(f"{note.get('title', '')} {note.get('content', '')}"))
        if not note_tokens:
            continue
        scores = [len(note_tokens & tokens) for tokens in group_tokens]
        best_index = max(range(len(groups)), key=lambda index: scores[index])
        if scores[best_index] > 0:
            groups[best_index]["notes"].append(note)
            assigned.add(str(note.get("id")))
    leftovers = [note for note in notes if str(note.get("id")) not in assigned]
    for index, note in enumerate(leftovers):
        groups[index % len(groups)]["notes"].append(note)
    return [group for group in groups if group["notes"]]


def _group_layout(count: int) -> list[tuple[int, int]]:
    layouts = {
        1: [(50, 30)],
        2: [(30, 30), (70, 30)],
        3: [(18, 30), (50, 30), (82, 30)],
        4: [(14, 30), (38, 30), (62, 30), (86, 30)],
        5: [(10, 30), (30, 30), (50, 30), (70, 30), (90, 30)],
    }
    if count <= 5:
        return layouts[count]
    base = layouts[5]
    return base + [(10 + (index % 5) * 20, 62) for index in range(count - 5)]

def normalize_review(raw: dict[str, Any], notes: list[dict[str, Any]]) -> dict[str, Any]:
    questions = []
    raw_questions = raw.get("questions") or raw.get("quiz") if isinstance(raw, dict) else []
    for index, item in enumerate(raw_questions if isinstance(raw_questions, list) else [], start=1):
        if not isinstance(item, dict):
            continue
        related_note_id = _string(item.get("relatedNoteId") or item.get("related_note_id"), "")
        if related_note_id and not _note_by_id(notes, related_note_id):
            related_note_id = ""
        question_type = _normalize_question_type(item.get("type") or item.get("question_type"))
        options = _review_options(item.get("options"))
        if question_type in {"single-choice", "multiple-choice"}:
            options = _ensure_single_choice_options(options, notes, index)
        if question_type == "multiple-choice":
            answer_items = _normalize_multiple_choice_answer(item.get("answer"), options)
            if len(answer_items) >= 2:
                answer = "; ".join(answer_items)
            else:
                question_type = "single-choice"
                answer = _normalize_single_choice_answer(item.get("answer"), options)
        else:
            question_type = "single-choice"
            answer = _normalize_single_choice_answer(item.get("answer"), options)
        questions.append(
            {
                "id": _string(item.get("id") or item.get("question_id"), f"q{index}"),
                "type": question_type,
                "difficulty": item.get("difficulty") or "medium",
                "skill": _string(item.get("skill") or item.get("question_skill"), "application" if index > 2 else "concept_check"),
                "question": _string(item.get("question"), f"Review note {index}."),
                "options": options,
                "answer": answer,
                "explanation": _string(item.get("explanation"), ""),
                "relatedNoteId": related_note_id or (notes[min(index - 1, len(notes) - 1)]["id"] if notes else ""),
                "citationIds": [],
            }
        )
    if not questions:
        questions = fallback_questions(notes)

    recommendations = _string_list(raw.get("recommendations") if isinstance(raw, dict) else [])
    suggestions = raw.get("suggestions") if isinstance(raw, dict) else []
    if isinstance(suggestions, list):
        recommendations.extend(
            str(item.get("content"))
            for item in suggestions
            if isinstance(item, dict) and item.get("content")
        )
    return {
        "questions": questions,
        "masteryScore": _float(raw.get("masteryScore") or raw.get("mastery_score"), 0) if isinstance(raw, dict) else 0,
        "weakPoints": _string_list(raw.get("weakPoints") or raw.get("weak_points")) if isinstance(raw, dict) else [],
        "recommendations": recommendations
        or ["Review notes through their grounded source quotes.", "Use generated questions for self-testing."],
    }


def fallback_questions(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    questions = []
    usable_notes = notes[:5] or [{"id": "n1", "title": "Core concept", "summary": "Core content from the review material"}]
    supports_multiple_choice = len(notes) >= 4
    for index in range(1, 6):
        note = usable_notes[(index - 1) % len(usable_notes)]
        options, answer = _fallback_single_choice_options(note, notes or usable_notes, index)
        question_type = "multiple-choice" if supports_multiple_choice and index in {4, 5} else "single-choice"
        if question_type == "multiple-choice":
            multi_answers = _fallback_multiple_choice_answers(options)
            if len(multi_answers) >= 2:
                answer = "; ".join(multi_answers)
            else:
                question_type = "single-choice"
        questions.append(
            {
                "id": f"q{index}",
                "type": question_type,
                "difficulty": "medium",
                "skill": "application" if index in {2, 3, 4} else ("error_diagnosis" if index == 5 else "concept_check"),
                "question": _fallback_application_question(note, index, question_type),
                "options": options,
                "answer": answer,
                "explanation": "先判断场景或错误原因，再用关联笔记和来源证据选择匹配选项。",
                "question": f"Which statements match the review points for \"{note['title']}\"?" if question_type == "multiple-choice" else f"Which option best summarizes \"{note['title']}\"?",
                "options": options,
                "answer": answer,
                "explanation": "Use the related note summary and source evidence to choose the matching option(s).",
                "relatedNoteId": note["id"],
                "citationIds": [],
            }
        )
    return questions


def _fallback_application_question(note: dict[str, Any], index: int, question_type: str) -> str:
    title = note.get("title") or "该知识点"
    if question_type == "multiple-choice":
        return f"在新的学习或解题场景中，哪些做法能正确应用「{title}」？"
    templates = [
        f"如果遇到一个需要使用「{title}」判断的具体题目，第一步最应该关注什么？",
        f"下面哪个场景最适合用「{title}」来解释或处理？",
        f"学习者把「{title}」用错时，最可能忽略哪一点？",
        f"把「{title}」迁移到新材料时，哪个判断最可靠？",
        f"针对「{title}」的错题订正，哪种做法最有效？",
    ]
    return templates[(index - 1) % len(templates)]


def _normalize_question_type(value: Any) -> str:
    raw = str(value or "short_answer").strip().lower().replace("_", "-")
    aliases = {
        "single-choice": "single-choice",
        "singlechoice": "single-choice",
        "choice": "single-choice",
        "multiple-choice": "multiple-choice",
        "multiplechoice": "multiple-choice",
        "multi-choice": "multiple-choice",
        "judgement": "judgement",
        "judgment": "judgement",
        "true-false": "judgement",
        "short-answer": "short-answer",
        "concept-explanation": "concept-explanation",
        "application": "application",
        "procedure": "application",
        "cause-effect": "application",
        "comparison": "application",
    }
    return aliases.get(raw, raw or "short-answer")


def _review_options(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    options: list[str] = []
    for index, option in enumerate(raw):
        label = chr(ord("A") + index)
        if isinstance(option, dict):
            option_label = _string(option.get("label") or option.get("key") or option.get("id"), label)
            text = _string(option.get("text") or option.get("content") or option.get("value"), "")
            value = f"{option_label}. {text}" if text and not text.startswith(f"{option_label}.") else text
        else:
            value = str(option).strip()
        if value:
            options.append(value)
    return options


def _ensure_single_choice_options(options: list[str], notes: list[dict[str, Any]], index: int) -> list[str]:
    if len(options) >= 4:
        return options[:4]
    note = notes[min(index - 1, len(notes) - 1)] if notes else {}
    fallback_options, _answer = _fallback_single_choice_options(note, notes, index)
    merged = []
    seen: set[str] = set()
    for option in [*options, *fallback_options]:
        key = option.strip().lower()
        if key and key not in seen:
            seen.add(key)
            merged.append(option)
        if len(merged) >= 4:
            break
    return merged


def _normalize_single_choice_answer(raw: Any, options: list[str]) -> str:
    answer = str(raw or "").strip()
    if not answer:
        return options[0] if options else ""
    normalized = answer.rstrip(".、:：").upper()
    if normalized in {"A", "B", "C", "D"}:
        offset = ord(normalized) - ord("A")
        if 0 <= offset < len(options):
            return options[offset]
    for option in options:
        if answer == option or answer in option or option in answer:
            return option
    return answer


def _normalize_multiple_choice_answer(raw: Any, options: list[str]) -> list[str]:
    raw_values = raw if isinstance(raw, list) else [raw]
    answers: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        for part in str(value or "").replace("；", ";").replace("，", ",").replace(";", ",").split(","):
            normalized = _normalize_single_choice_answer(part, options)
            key = normalized.strip().lower()
            if normalized and key not in seen:
                seen.add(key)
                answers.append(normalized)
    return answers


def _fallback_multiple_choice_answers(options: list[str]) -> list[str]:
    return options[:2] if len(options) >= 2 else []


def _fallback_single_choice_options(note: dict[str, Any], notes: list[dict[str, Any]], index: int) -> tuple[list[str], str]:
    correct_text = compact(str(note.get("summary") or note.get("content") or note.get("title") or "该笔记的核心内容"), 80)
    distractors = [
        compact(str(other.get("summary") or other.get("content") or other.get("title") or ""), 80)
        for other in notes
        if other is not note
    ]
    distractors = [item for item in distractors if item and item != correct_text]
    while len(distractors) < 3:
        distractors.append([
            "只需记住资料标题，不需要理解具体内容。",
            "该知识点与当前笔记没有直接关系。",
            "复习时可以忽略来源片段和关键定义。",
        ][len(distractors) % 3])
    raw_options = [correct_text, *distractors[:3]]
    shift = (index - 1) % 4
    rotated = raw_options[shift:] + raw_options[:shift]
    options = [f"{chr(ord('A') + option_index)}. {text}" for option_index, text in enumerate(rotated)]
    answer = options[rotated.index(correct_text)]
    return options, answer


def normalize_core_points(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    outline = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        outline.append(
            {
                "id": _string(item.get("point_id") or item.get("id"), f"point-{index}"),
                "title": _string(item.get("title"), f"Point {index}"),
                "brief": _string(item.get("brief") or item.get("content"), ""),
                "sourceRefs": _string_list(item.get("source_refs") or item.get("sourceRefs")),
            }
        )
    return outline


def _compact_notes_for_prompt(notes: Any) -> list[dict[str, Any]]:
    compacted = []
    if not isinstance(notes, list):
        return compacted
    for item in notes[:10]:
        if not isinstance(item, dict):
            continue
        note = {
            "note_id": item.get("note_id") or item.get("id"),
            "title": item.get("title"),
            "note_type": item.get("note_type") or item.get("noteType"),
            "source_refs": item.get("source_refs") or item.get("sourceRefs") or [],
            "content": compact(str(item.get("content") or item.get("summary") or ""), 360),
            "summary": compact(str(item.get("summary") or item.get("content") or ""), 220),
            "keyPoints": item.get("keyPoints") or item.get("key_points") or [],
            "blocks": item.get("blocks") or [],
        }
        children = item.get("children")
        if isinstance(children, list) and children:
            note["children"] = _compact_notes_for_prompt(children[:5])
        compacted.append(note)
    return compacted


def _select_context(
    chunks: list[SourceChunk],
    *,
    limit: int | None = None,
    max_chunks: int | None = None,
    text_budget: int | None = None,
) -> list[SourceChunk]:
    chunk_limit = max_chunks or limit or len(chunks)
    if not chunks or chunk_limit <= 0:
        return []
    budget = text_budget or sum(_prompt_text_len(chunk) for chunk in chunks)
    if len(chunks) <= chunk_limit and sum(_prompt_text_len(chunk) for chunk in chunks) <= budget:
        return chunks

    candidates = [chunk for chunk in chunks if not _looks_like_toc(chunk)] or chunks
    selected: list[SourceChunk] = []
    seen: set[str] = set()
    used_budget = 0

    def try_add(chunk: SourceChunk) -> bool:
        nonlocal used_budget
        if chunk.id in seen or len(selected) >= chunk_limit:
            return False
        cost = _prompt_text_len(chunk)
        if selected and used_budget + cost > budget:
            return False
        selected.append(chunk)
        seen.add(chunk.id)
        used_budget += cost
        return True

    try_add(candidates[0])
    spread_limit = max(1, chunk_limit - len(selected))
    positions = [round(index * (len(candidates) - 1) / max(1, spread_limit - 1)) for index in range(spread_limit)]
    for position in positions:
        try_add(candidates[position])
    for chunk in candidates:
        if len(selected) >= chunk_limit:
            break
        try_add(chunk)
    if not selected:
        return [chunks[0]]
    return sorted(selected, key=lambda chunk: chunk.chunkIndex)




def _semantic_note_contract() -> dict[str, Any]:
    return {
        "goal": "Lanxin should generate semantically structured notes; backend only normalizes and validates the contract.",
        "note_fields": ["note_id", "title", "summary", "content", "source_refs", "blocks", "children"],
        "outline_block_schema": {
            "type": "outline",
            "title": "????",
            "structuredItems": [{"text": "one complete knowledge point", "children": ["subpoint when the source is total-branch"]}],
        },
        "rules": [
            "Do not split one concept only because it spans multiple source lines.",
            "Do not turn examples or isolated tokens into top-level knowledge points.",
            "Use children for total-branch lists such as problems/effects/features/capabilities.",
            "Stop extracting when the section's main semantic content ends; do not force a fixed bullet count.",
        ],
    }

def _storm_policy() -> dict[str, str]:
    return {
        "goal": "Build a question-driven learning report before writing notes, inspired by STORM-style synthesis.",
        "requirements": "Identify learning questions, perspectives, evidence gaps, and a report outline. Keep every point grounded in source_refs.",
    }


def _seed_research_questions_from_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seeds = []
    for index, chunk in enumerate(chunks[:8], start=1):
        heading = str(chunk.get("heading") or chunk.get("source_ref") or f"学习问题 {index}")
        seeds.append(
            {
                "id": f"rq-{index}",
                "question": f"{heading} 解决了什么核心学习问题？",
                "perspective": _perspective_for_heading(heading),
                "source_refs": [chunk.get("source_id")],
            }
        )
    return seeds


def _build_report_plan(m2: dict[str, Any], notes: Any) -> list[dict[str, Any]]:
    raw = m2.get("report_plan") or m2.get("reportPlan") or m2.get("outline") or m2.get("core_points") or []
    plan = normalize_core_points(raw)
    if plan:
        return plan[:8]
    compact_notes = _compact_notes_for_prompt(notes)
    if compact_notes:
        return [
            {
                "id": f"report-{index}",
                "title": _string(note.get("title"), f"学习问题 {index}"),
                "brief": f"\u56f4\u7ed5\u201c{_string(note.get('title'), f'\u5b66\u4e60\u95ee\u9898 {index}')}\u201d\u68b3\u7406\u6982\u5ff5\u3001\u8bc1\u636e\u548c\u5e94\u7528\u3002",
                "sourceRefs": _string_list(note.get("source_refs")),
            }
            for index, note in enumerate(compact_notes[:8], start=1)
        ]
    return []


def _perspective_for_heading(heading: str) -> str:
    value = heading.lower()
    if any(term in value for term in ("应用", "案例", "场景", "application", "case")):
        return "应用视角"
    if any(term in value for term in ("方法", "算法", "流程", "method", "algorithm")):
        return "方法视角"
    if any(term in value for term in ("评估", "指标", "实验", "evaluation")):
        return "验证视角"
    return "概念视角"


def _source_ref_policy(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "source_ref_policy": (
            "Every core point and note must include exact chunks[].source_id values in source_refs. "
            "Do not invent source ids; omit unsupported claims."
        ),
        "available_source_ids": [
            {
                "source_id": chunk.get("source_id"),
                "source_ref": chunk.get("source_ref"),
                "heading": chunk.get("heading"),
                "page": chunk.get("page"),
                "slide": chunk.get("slide"),
            }
            for chunk in chunks
        ],
    }


def _output_language_policy() -> dict[str, str]:
    return {
        "output_language": "zh-CN",
        "language_policy": "All user-facing fields must be written in Simplified Chinese. Keep technical terms bilingual only when the source commonly uses English abbreviations, for example EM算法 or MLE.",
    }


def _prompt_text_len(chunk: SourceChunk) -> int:
    return len(compact(chunk.text, 1200))


def _looks_like_toc(chunk: SourceChunk) -> bool:
    heading = (chunk.heading or chunk.title or "").strip().lower()
    text = " ".join((chunk.text or "").strip().lower().split())
    if heading in {"目录", "目錄", "contents", "table of contents"}:
        return True
    if not text:
        return False
    lines = [line.strip() for line in chunk.text.splitlines() if line.strip()]
    toc_markers = sum(1 for line in lines if re.match(r"^(\d+(?:\.\d+)*|第.+[章节])\s+.+\s+\d+$", line))
    if toc_markers >= 3:
        return True
    return text.startswith(("目录 ", "目錄 ", "contents ", "table of contents "))


def _frontend_node(node: dict[str, Any], index: int, notes: list[dict[str, Any]]) -> dict[str, Any]:
    related_note_id = _string(node.get("relatedNoteId") or node.get("related_note_id"), "")
    note = _note_by_id(notes, related_note_id)
    return {
        **node,
        "id": _string(node.get("id") or node.get("node_id"), f"node-{index + 1}"),
        "label": _string(node.get("label") or node.get("title"), f"Node {index + 1}"),
        "desc": _string(node.get("desc") or (note or {}).get("content"), ""),
        "detail": _string(node.get("detail") or (note or {}).get("content"), ""),
        "relatedNoteId": related_note_id,
        "x": _float(node.get("x"), 50),
        "y": _float(node.get("y"), 50),
        "line": _string(node.get("line"), "#64748b"),
        "fill": _string(node.get("fill"), "#eff6ff"),
    }


def _frontend_edge(edge: dict[str, Any]) -> dict[str, Any]:
    edge_type = _normalize_edge_type(edge.get("type") or edge.get("relation_type") or edge.get("relation"))
    return {
        **edge,
        "from": _string(edge.get("from") or edge.get("source"), ""),
        "to": _string(edge.get("to") or edge.get("target"), ""),
        "type": edge_type,
        "label": _string(edge.get("label") or edge.get("edge_label") or edge.get("relation_label"), _edge_label(edge_type)),
        "reason": _string(edge.get("reason") or edge.get("description") or edge.get("relation_reason"), ""),
        "confidence": _float(edge.get("confidence"), 0.68),
        "source_refs": _string_list(edge.get("source_refs") or edge.get("sourceRefs")),
    }


def _typed_edge(
    from_id: str,
    to_id: str,
    edge_type: str,
    label: str | None = None,
    reason: str = "",
    *,
    confidence: float = 0.78,
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    normalized_type = _normalize_edge_type(edge_type)
    return {
        "from": from_id,
        "to": to_id,
        "type": normalized_type,
        "label": label or _edge_label(normalized_type),
        "reason": reason,
        "confidence": confidence,
        "source_refs": source_refs or [],
    }


def _normalize_edge_type(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("_", "-")
    aliases = {
        "dependency": "prerequisite",
        "depends-on": "prerequisite",
        "part-of": "component",
        "contains": "component",
        "method": "mechanism",
        "core-mechanism": "mechanism",
        "flow": "training-flow",
        "workflow": "training-flow",
        "train": "training-flow",
        "derived": "evolution",
        "extension": "evolution",
        "challenge": "contrast",
        "compare": "contrast",
        "support": "evidence",
    }
    raw = aliases.get(raw, raw)
    allowed = {
        "hierarchy",
        "prerequisite",
        "component",
        "mechanism",
        "training-flow",
        "evolution",
        "application",
        "contrast",
        "evidence",
        "solution",
    }
    return raw if raw in allowed else "hierarchy"


def _edge_label(edge_type: str) -> str:
    labels = {
        "hierarchy": "\u5f52\u5c5e",
        "prerequisite": "\u5148\u4fee",
        "component": "\u7ec4\u6210",
        "mechanism": "\u673a\u5236",
        "training-flow": "\u8bad\u7ec3\u6d41",
        "evolution": "\u6f14\u8fdb",
        "application": "\u5e94\u7528",
        "contrast": "\u5bf9\u6bd4",
        "evidence": "\u8bc1\u636e",
        "solution": "\u89e3\u51b3",
    }
    return labels.get(edge_type, "\u5173\u7cfb")


def _enrich_logical_mindmap_edges(
    mind_map: dict[str, Any],
    notes: list[dict[str, Any]],
    report_plan: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    nodes = [node for node in mind_map.get("nodes", []) if isinstance(node, dict) and node.get("id")]
    if not nodes:
        return mind_map
    node_ids = {str(node.get("id")) for node in nodes}
    root_id = _mindmap_root_id(nodes)
    note_by_id = {str(note.get("id")): note for note in notes}
    existing: dict[tuple[str, str], dict[str, Any]] = {}
    for edge in mind_map.get("edges", []):
        if not isinstance(edge, dict):
            continue
        normalized = _frontend_edge(edge)
        if normalized["from"] in node_ids and normalized["to"] in node_ids and normalized["from"] != normalized["to"]:
            key = (normalized["from"], normalized["to"])
            existing[key] = normalized

    roles = {str(node.get("id")): _mindmap_node_roles(node, note_by_id) for node in nodes}

    def first(role: str) -> str | None:
        for node in nodes:
            node_id = str(node.get("id"))
            if role in roles.get(node_id, set()):
                return node_id
        return None

    def add(from_id: str | None, to_id: str | None, edge_type: str, label: str, reason: str, confidence: float = 0.82) -> None:
        if not from_id or not to_id or from_id == to_id or from_id not in node_ids or to_id not in node_ids:
            return
        key = (from_id, to_id)
        source_refs = _merge_source_refs(_node_source_refs(from_id, nodes), _node_source_refs(to_id, nodes))
        edge = existing.get(key)
        if edge:
            if edge.get("type") == "hierarchy" and edge_type != "hierarchy":
                edge.update(_typed_edge(from_id, to_id, edge_type, label, reason, confidence=confidence, source_refs=source_refs))
            elif not edge.get("reason"):
                edge["reason"] = reason
            return
        existing[key] = _typed_edge(from_id, to_id, edge_type, label, reason, confidence=confidence, source_refs=source_refs)

    background = first("background")
    architecture = first("architecture")
    input_repr = first("input")
    attention = first("attention")
    sublayer = first("sublayer")
    decoder = first("decoder")
    training = first("training")
    advantage = first("advantage")
    derivative = first("derivative")
    llm = first("llm")
    challenge = first("challenge")
    future = first("future")

    add(background, architecture, "prerequisite", None, "The background explains why the architecture is needed.", 0.86)
    add(architecture, input_repr, "component", None, "Embedding and positional encoding are input-side components of the architecture.", 0.88)
    add(architecture, attention, "component", None, "Attention is the core module inside Transformer.", 0.9)
    add(input_repr, attention, "prerequisite", None, "Attention operates on token vectors with position information.", 0.88)
    add(attention, sublayer, "mechanism", None, "Attention output is refined by feed-forward, residual, and normalization sublayers.", 0.82)
    add(architecture, decoder, "component", None, "Masked attention is a Decoder-side design.", 0.84)
    add(decoder, training, "training-flow", None, "Decoder generation behavior is optimized during supervised training.", 0.78)
    add(attention, advantage, "evidence", None, "Attention explains parallelism and long-distance dependency advantages.", 0.82)
    add(advantage, derivative, "evolution", None, "Transformer advantages enabled derived model families.", 0.86)
    add(derivative, llm, "application", None, "Large language models are built on Transformer-derived architectures.", 0.86)
    add(challenge, future, "solution", None, "Future directions respond to complexity, inference cost, hallucination, and long-context challenges.", 0.82)
    add(advantage, challenge, "contrast", None, "Advantages and challenges describe the benefit-cost boundary of Transformer.", 0.78)

    for node in nodes:
        node_id = str(node.get("id"))
        if node_id == root_id:
            continue
        has_incoming = any(edge["to"] == node_id for edge in existing.values())
        if not has_incoming:
            add(root_id, node_id, "hierarchy", "topic", "Top-level topic relation.", 0.66)

    enriched = list(existing.values())
    root_edges = [edge for edge in enriched if edge["from"] == root_id]
    non_root_edges = [edge for edge in enriched if edge["from"] != root_id]
    if non_root_edges and len(root_edges) > max(3, len(nodes) // 2):
        logical_targets = {edge["to"] for edge in non_root_edges if edge.get("type") != "hierarchy"}
        enriched = [edge for edge in enriched if not (edge["from"] == root_id and edge["to"] in logical_targets)]

    for edge in enriched:
        edge["label"] = _edge_label(_normalize_edge_type(edge.get("type")))
    return {"nodes": nodes, "edges": enriched}


def _mindmap_root_id(nodes: list[dict[str, Any]]) -> str:
    for node in nodes:
        node_id = str(node.get("id") or "")
        if node_id.lower() in {"root", "center"}:
            return node_id
    return str(nodes[0].get("id"))


def _mindmap_node_roles(node: dict[str, Any], note_by_id: dict[str, dict[str, Any]]) -> set[str]:
    note = note_by_id.get(str(node.get("relatedNoteId") or node.get("related_note_id") or ""), {})
    text = " ".join(
        str(value or "")
        for value in (
            node.get("label"),
            node.get("desc"),
            node.get("detail"),
            note.get("title"),
            note.get("content"),
            note.get("summary"),
        )
    ).lower()
    roles: set[str] = set()
    role_keywords = {
        "background": ("background", "rnn", "lstm", "gru", "before", "\u80cc\u666f", "\u63d0\u51fa\u80cc\u666f"),
        "architecture": ("architecture", "encoder", "decoder", "\u6574\u4f53", "\u67b6\u6784", "\u7ed3\u6784", "\u6574\u4f53\u67b6\u6784", "\u6574\u4f53\u7ed3\u6784"),
        "input": ("embedding", "positional", "\u4f4d\u7f6e", "\u7f16\u7801", "\u4f4d\u7f6e\u7f16\u7801", "\u8bcd\u5411\u91cf", "\u8f93\u5165", "\u8f93\u5165\u5904\u7406"),
        "attention": ("self-attention", "multi-head", "attention", "\u6ce8\u610f\u529b", "\u81ea\u6ce8\u610f\u529b", "\u591a\u5934\u6ce8\u610f\u529b", "\u6838\u5fc3\u673a\u5236", "qkv"),
        "sublayer": ("feed forward", "\u524d\u9988", "\u6b8b\u5dee", "\u5f52\u4e00\u5316", "\u5c42\u5f52\u4e00\u5316", "\u5b50\u5c42", "normalization", "add & norm"),
        "decoder": ("masked", "mask", "masked attention", "decoder", "\u89e3\u7801\u5668"),
        "training": ("\u8bad\u7ec3", "\u8bad\u7ec3\u8fc7\u7a0b", "loss", "\u635f\u5931", "adam", "\u76d1\u7763\u5b66\u4e60", "training"),
        "advantage": ("\u4f18\u52bf", "\u6838\u5fc3\u4f18\u52bf", "\u5e76\u884c", "\u957f\u8ddd\u79bb", "\u6269\u5c55", "\u9884\u8bad\u7ec3", "advantage"),
        "derivative": ("\u884d\u751f", "\u884d\u751f\u6a21\u578b", "bert", "gpt", "t5", "vit", "derived"),
        "llm": ("\u5927\u8bed\u8a00", "\u5927\u8bed\u8a00\u6a21\u578b", "llm", "large language", "gpt", "gemini", "claude"),
        "challenge": ("\u6311\u6218", "\u590d\u6742\u5ea6", "\u63a8\u7406\u6210\u672c", "\u5e7b\u89c9", "\u957f\u6587\u672c", "challenge"),
        "future": ("\u672a\u6765", "\u53d1\u5c55\u65b9\u5411", "\u4f18\u5316", "\u7a00\u758f", "\u9ad8\u6548", "future"),
    }
    for role, keywords in role_keywords.items():
        if any(keyword in text for keyword in keywords):
            roles.add(role)
    return roles


def _node_source_refs(node_id: str, nodes: list[dict[str, Any]]) -> list[str]:
    node = next((item for item in nodes if str(item.get("id")) == node_id), {})
    return _string_list(node.get("source_refs") or node.get("sourceRefs"))


def _source_refs_from_note(note: dict[str, Any]) -> list[str]:
    return _string_list(note.get("source_refs") or note.get("sourceRefs") or note.get("citationIds"))


def _merge_source_refs(*groups: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for group in groups:
        for item in group:
            if item and item not in seen:
                seen.add(item)
                merged.append(item)
    return merged[:8]


def _layout_points(count: int) -> list[tuple[int, int]]:
    base = [(50, 45), (20, 20), (50, 15), (80, 20), (18, 55), (82, 55), (25, 82), (50, 86), (75, 82)]
    return base if count <= len(base) else base * (count // len(base) + 1)


def _note_by_id(notes: list[dict[str, Any]], note_id: str) -> dict[str, Any] | None:
    if not note_id:
        return None
    return next((note for note in notes if note.get("id") == note_id), None)


def _infer_topic(chunks: list[SourceChunk]) -> str:
    if not chunks:
        return "Learning Material"
    keywords = extract_keywords(" ".join(chunk.text for chunk in chunks[:6]), limit=3)
    return keywords[0] if keywords else Path(chunks[0].fileName).stem


def _string(value: Any, fallback: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
