from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..provider_config import create_provider
from ..providers import ModelLog
from ..prompts import PromptRegistry
from ..rag.retrieval import HybridRetriever
from ..rag.schemas import SourceChunk
from ..rag.text_utils import compact, extract_keywords


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
        provider = create_provider(provider_name)
        prompt_chunks = normalize_chunks_for_prompt(_select_context(chunks, limit=8))
        outputs: dict[str, dict[str, Any]] = {}
        logs: list[dict[str, Any]] = []

        for module in MODULE_SEQUENCE:
            prompt = self.registry.get(module)
            payload = build_payload(module, prompt_chunks, outputs)
            output, log = provider.generate_module_json(module, prompt, payload)
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
            "question": question,
            "topic": result.get("topic"),
            "summary": result.get("summary"),
            "notes": _compact_notes_for_prompt(result.get("notes", [])),
            "mindmap": result.get("mindMap") or {},
            "citations": result.get("citations", [])[:20],
            "retrieved_sources": [hit.to_dict() for hit in hits],
        }
        output, log = provider.generate_module_json("M7", self.registry.get("M7"), payload, max_tokens=2048)
        response = output if isinstance(output, dict) else {}
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
    if module == "M2":
        return {"chunks": chunks}
    if module == "M3":
        m2 = outputs.get("M2", {})
        return {
            "chunks": chunks,
            "topic": m2.get("topic"),
            "summary": m2.get("summary"),
            "core_points": m2.get("core_points", []),
        }
    if module == "M4":
        return {
            "topic": outputs.get("M2", {}).get("topic"),
            "notes": _compact_notes_for_prompt(outputs.get("M3", {}).get("notes", [])),
        }
    if module == "M6":
        return {
            "notes": _compact_notes_for_prompt(outputs.get("M3", {}).get("notes", [])),
            "citations": [],
            "grounding_policy": "citations_are_rebuilt_by_backend_M5",
        }
    return {"chunks": chunks}


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

    topic = _string(m2.get("topic"), _infer_topic(chunks))
    summary = _string(m2.get("summary"), _string(m3.get("global_summary"), ""))
    if not summary:
        summary = compact(" ".join(chunk.text for chunk in chunks[:4]), 260)

    mind_map = convert_mindmap(m4.get("mindmap") or m4.get("mindMap"), topic, notes)
    review = normalize_review(m6.get("review") or {}, notes)

    return {
        "id": f"agent-{uuid.uuid4().hex[:8]}",
        "topic": topic,
        "summary": summary,
        "keywords": _string_list(m2.get("keywords")) or extract_keywords(" ".join(chunk.text for chunk in chunks), limit=8),
        "learningScene": m2.get("learning_scene") or m2.get("learningScene") or "",
        "outline": normalize_core_points(m2.get("core_points", [])),
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
                "level": 1,
                "parentId": None,
                "noteType": "fallback",
                "source_refs": [chunk.id],
                "citationIds": [],
            }
        )
    return notes


def convert_mindmap(raw: Any, topic: str, notes: list[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(raw, dict) and isinstance(raw.get("nodes"), list):
        return {
            "nodes": [_frontend_node(node, index, notes) for index, node in enumerate(raw.get("nodes", []))],
            "edges": [_frontend_edge(edge) for edge in raw.get("edges", []) if isinstance(edge, dict)],
        }

    root = raw.get("root") if isinstance(raw, dict) else None
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
                edges.append({"from": parent, "to": node_id})
            children = node.get("children")
            if isinstance(children, list):
                for child in children:
                    if isinstance(child, dict):
                        visit(child, node_id)

        visit(root)
        return {"nodes": nodes, "edges": edges}

    return fallback_mindmap(topic, notes)


def fallback_mindmap(topic: str, notes: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = [
        {
            "id": "root",
            "label": topic,
            "desc": "Topic",
            "detail": topic,
            "x": 50,
            "y": 45,
            "line": "#2563eb",
            "fill": "#ffffff",
        }
    ]
    edges = []
    layout = _layout_points(len(notes))
    for index, note in enumerate(notes[:8], start=1):
        x, y = layout[(index - 1) % len(layout)]
        nodes.append(
            {
                "id": f"mind-{note['id']}",
                "label": compact(note["title"], 24),
                "desc": compact(note.get("content", ""), 60),
                "detail": note.get("content", ""),
                "relatedNoteId": note["id"],
                "x": x,
                "y": y,
                "line": "#64748b",
                "fill": "#eff6ff",
            }
        )
        edges.append({"from": "root", "to": f"mind-{note['id']}"})
    return {"nodes": nodes, "edges": edges}


def normalize_review(raw: dict[str, Any], notes: list[dict[str, Any]]) -> dict[str, Any]:
    questions = []
    raw_questions = raw.get("questions") if isinstance(raw, dict) else []
    for index, item in enumerate(raw_questions if isinstance(raw_questions, list) else [], start=1):
        if not isinstance(item, dict):
            continue
        related_note_id = _string(item.get("relatedNoteId") or item.get("related_note_id"), "")
        if related_note_id and not _note_by_id(notes, related_note_id):
            related_note_id = ""
        questions.append(
            {
                "id": _string(item.get("id") or item.get("question_id"), f"q{index}"),
                "type": _string(item.get("type") or item.get("question_type"), "short_answer"),
                "difficulty": item.get("difficulty") or "medium",
                "question": _string(item.get("question"), f"Review note {index}."),
                "options": _string_list(item.get("options")),
                "answer": _string(item.get("answer"), ""),
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
    for index, note in enumerate(notes[:5], start=1):
        questions.append(
            {
                "id": f"q{index}",
                "type": "short_answer",
                "difficulty": "medium",
                "question": f"Explain the key idea of {note['title']}.",
                "options": [],
                "answer": compact(note.get("content", ""), 140),
                "explanation": "Answer using the related note and its grounded citation.",
                "relatedNoteId": note["id"],
                "citationIds": [],
            }
        )
    return questions


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
            "content": compact(str(item.get("content") or ""), 360),
        }
        children = item.get("children")
        if isinstance(children, list) and children:
            note["children"] = _compact_notes_for_prompt(children[:5])
        compacted.append(note)
    return compacted


def _select_context(chunks: list[SourceChunk], *, limit: int) -> list[SourceChunk]:
    if len(chunks) <= limit:
        return chunks
    positions = [round(index * (len(chunks) - 1) / (limit - 1)) for index in range(limit)]
    selected = []
    seen = set()
    for position in positions:
        chunk = chunks[position]
        if chunk.id not in seen:
            selected.append(chunk)
            seen.add(chunk.id)
    for chunk in chunks:
        if len(selected) >= limit:
            break
        if chunk.id not in seen:
            selected.append(chunk)
            seen.add(chunk.id)
    return selected


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
    return {
        **edge,
        "from": _string(edge.get("from") or edge.get("source"), ""),
        "to": _string(edge.get("to") or edge.get("target"), ""),
    }


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
