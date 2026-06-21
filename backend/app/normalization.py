from __future__ import annotations

import uuid
from typing import Any

from .contracts import AgentResult


def normalize_agent_result(raw: dict[str, Any]) -> dict[str, Any]:
    result = dict(raw or {})
    result["id"] = _string(result.get("id"), f"agent-{uuid.uuid4().hex[:8]}")
    result["topic"] = _string(result.get("topic"), "学习资料")
    result["summary"] = _string(result.get("summary"), "")
    result["agentStages"] = [_stage(item, index) for index, item in enumerate(_list(result.get("agentStages")))]
    result["sources"] = [_source(item, index) for index, item in enumerate(_list(result.get("sources")))]
    result["notes"] = [_note(item, index) for index, item in enumerate(_list(result.get("notes")))]
    result["citations"] = [_citation(item, index) for index, item in enumerate(_list(result.get("citations")))]

    mind_map = result.get("mindMap") if isinstance(result.get("mindMap"), dict) else {}
    result["mindMap"] = {
        **mind_map,
        "nodes": [_node(item, index) for index, item in enumerate(_list(mind_map.get("nodes")))],
        "edges": [_edge(item) for item in _list(mind_map.get("edges"))],
    }
    review = result.get("review") if isinstance(result.get("review"), dict) else {}
    result["review"] = {
        **review,
        "questions": [_question(item, index) for index, item in enumerate(_list(review.get("questions")))],
        "masteryScore": _number(review.get("masteryScore"), 0),
        "weakPoints": [str(item) for item in _list(review.get("weakPoints"))],
        "recommendations": [str(item) for item in _list(review.get("recommendations"))],
    }
    return AgentResult.model_validate(result).model_dump(by_alias=True)


def contract_report(raw: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_agent_result(raw)
    return {
        "valid": True,
        "contract": "AgentResult",
        "requiredTopLevelFields": [
            "id", "topic", "summary", "agentStages", "sources", "notes", "citations", "mindMap", "review"
        ],
        "sourceCount": len(normalized["sources"]),
        "noteCount": len(normalized["notes"]),
        "citationCount": len(normalized["citations"]),
        "questionCount": len(normalized["review"]["questions"]),
    }




def raw_contract_report(raw: dict[str, Any]) -> dict[str, Any]:
    required = ["id", "topic", "summary", "agentStages", "sources", "notes", "citations", "mindMap", "review"]
    if not isinstance(raw, dict):
        raise ValueError("AgentResult must be an object")
    missing = [field for field in required if field not in raw]
    if missing:
        raise ValueError(f"Missing required AgentResult fields: {', '.join(missing)}")

    result = AgentResult.model_validate(raw).model_dump(by_alias=True)
    if not result["sources"]:
        raise ValueError("AgentResult must include at least one source")
    if not result["notes"]:
        raise ValueError("AgentResult must include at least one note")
    if not result["agentStages"]:
        raise ValueError("AgentResult must include agentStages")
    if not result["mindMap"]["nodes"]:
        raise ValueError("AgentResult must include mindMap.nodes")
    return {
        "valid": True,
        "contract": "AgentResult",
        "requiredTopLevelFields": required,
        "sourceCount": len(result["sources"]),
        "noteCount": len(result["notes"]),
        "citationCount": len(result["citations"]),
        "questionCount": len(result["review"]["questions"]),
    }


def _stage(item: Any, index: int) -> dict[str, Any]:
    value = _dict(item)
    return {**value, "id": _string(value.get("id"), f"stage-{index + 1}"), "label": _string(value.get("label"), f"Stage {index + 1}"), "text": _string(value.get("text"), "")}


def _source(item: Any, index: int) -> dict[str, Any]:
    value = _dict(item)
    return {**value, "id": _string(value.get("id"), str(index + 1)), "title": _string(value.get("title"), f"Source {index + 1}"), "text": _string(value.get("text"), "")}


def _note(item: Any, index: int) -> dict[str, Any]:
    value = _dict(item)
    return {
        **value,
        "id": _string(value.get("id") or value.get("node_id"), f"note-{index + 1}"),
        "title": _string(value.get("title"), f"第 {index + 1} 节"),
        "content": _string(value.get("content"), ""),
        "summary": _string(value.get("summary"), ""),
        "keyPoints": [str(item) for item in _list(value.get("keyPoints") or value.get("key_points"))],
        "examples": _list(value.get("examples")),
        "relations": _list(value.get("relations")),
        "blocks": _list(value.get("blocks")),
        "sourceRefs": [str(link) for link in _list(value.get("sourceRefs") or value.get("source_refs"))],
        "citationIds": [str(link) for link in _list(value.get("citationIds") or value.get("refs") or value.get("source_refs"))],
    }


def _citation(item: Any, index: int) -> dict[str, Any]:
    value = _dict(item)
    citation_id = _string(value.get("id") or value.get("citation_id"), f"citation-{index + 1}")
    return {
        **value,
        "id": citation_id,
        "sourceId": _string(value.get("sourceId") or value.get("source_id"), citation_id),
        "noteId": _string(value.get("noteId") or value.get("related_note_id"), ""),
    }


def _node(item: Any, index: int) -> dict[str, Any]:
    value = _dict(item)
    return {
        **value,
        "id": _string(value.get("id") or value.get("node_id"), f"node-{index + 1}"),
        "label": _string(value.get("label") or value.get("title"), f"Node {index + 1}"),
        "desc": _string(value.get("desc") or value.get("description") or value.get("discription"), ""),
        "detail": _string(value.get("detail"), ""),
        "x": _number(value.get("x"), 50),
        "y": _number(value.get("y"), 50),
        "line": _string(value.get("line"), "#93c5fd"),
        "fill": _string(value.get("fill"), "#ffffff"),
    }


def _edge(item: Any) -> dict[str, Any]:
    value = _dict(item)
    edge_type = _edge_type(value.get("type") or value.get("relation_type") or value.get("relation"))
    return {
        **value,
        "from": _string(value.get("from") or value.get("source"), ""),
        "to": _string(value.get("to") or value.get("target"), ""),
        "type": edge_type,
        "label": _string(value.get("label") or value.get("edge_label") or value.get("relation_label"), _edge_label(edge_type)),
        "reason": _string(value.get("reason") or value.get("description") or value.get("relation_reason"), ""),
        "confidence": _number(value.get("confidence"), 0.68),
        "source_refs": [str(link) for link in _list(value.get("source_refs") or value.get("sourceRefs"))],
    }


def _edge_type(value: Any) -> str:
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
    allowed = {"hierarchy", "prerequisite", "component", "mechanism", "training-flow", "evolution", "application", "contrast", "evidence", "solution"}
    return raw if raw in allowed else "hierarchy"


def _edge_label(edge_type: str) -> str:
    return {
        "hierarchy": "??",
        "prerequisite": "??",
        "component": "??",
        "mechanism": "??",
        "training-flow": "???",
        "evolution": "??",
        "application": "??",
        "contrast": "??",
        "evidence": "??",
        "solution": "??",
    }.get(edge_type, "??")


def _question(item: Any, index: int) -> dict[str, Any]:
    value = _dict(item)
    return {
        **value,
        "id": _string(value.get("id") or value.get("question_id"), f"question-{index + 1}"),
        "type": _string(value.get("type") or value.get("question_type"), "single-choice"),
        "question": _string(value.get("question"), ""),
        "options": [str(option) for option in _list(value.get("options"))],
        "answer": _string(value.get("answer"), ""),
        "explanation": _string(value.get("explanation"), ""),
        "citationIds": [str(link) for link in _list(value.get("citationIds"))],
    }


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any, fallback: str) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _number(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
