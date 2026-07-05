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
    mind_map_nodes = [_node(item, index) for index, item in enumerate(_list(mind_map.get("nodes")))]
    mind_map_edges = [_edge(item) for item in _list(mind_map.get("edges"))]
    mind_map_nodes, mind_map_edges = _normalize_mind_map_graph(mind_map_nodes, mind_map_edges, result["topic"])
    result["mindMap"] = {
        **mind_map,
        "nodes": mind_map_nodes,
        "edges": mind_map_edges,
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


def _normalize_mind_map_graph(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], topic: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not nodes:
        return nodes, edges

    root_id = _mind_map_root_id(nodes)
    duplicate_ids = {
        str(node.get("id"))
        for node in nodes
        if str(node.get("id")) != root_id and _is_core_summary_node(node, topic)
    }
    normalized_nodes = []
    for node in nodes:
        node_id = str(node.get("id"))
        if node_id in duplicate_ids:
            continue
        if node_id == root_id and _is_core_summary_node(node, topic) and topic:
            node = {
                **node,
                "label": topic,
                "desc": node.get("desc") or "中心主题",
                "detail": node.get("detail") or topic,
            }
        normalized_nodes.append(node)

    valid_ids = {str(node.get("id")) for node in normalized_nodes}
    normalized_edges: list[dict[str, Any]] = []
    edge_keys: set[tuple[str, str, str, str]] = set()
    for edge in edges:
        source = str(edge.get("from") or "")
        target = str(edge.get("to") or "")
        if target in duplicate_ids:
            continue
        if source in duplicate_ids:
            source = root_id
        if not source or not target or source == target or source not in valid_ids or target not in valid_ids:
            continue
        key = (source, target, str(edge.get("type") or "hierarchy"), str(edge.get("label") or ""))
        if key in edge_keys:
            continue
        edge_keys.add(key)
        normalized_edges.append({**edge, "from": source, "to": target})

    return normalized_nodes, normalized_edges


def _mind_map_root_id(nodes: list[dict[str, Any]]) -> str:
    for node in nodes:
        node_id = str(node.get("id") or "")
        if node_id.lower() in {"root", "center"}:
            return node_id
    return str(nodes[0].get("id") or "")


def _is_core_summary_node(node: dict[str, Any], topic: str) -> bool:
    if node.get("relatedNoteId") or node.get("related_note_id"):
        return False
    label = _semantic_label(node.get("label"))
    topic_label = _semantic_label(topic)
    core_labels = {
        "中心主题",
        "本章核心考点总结",
        "本节核心考点总结",
        "章节核心考点总结",
        "核心考点总结",
        "核心知识点总结",
    }
    return label in core_labels or bool(topic_label and label == topic_label)


def _semantic_label(value: Any) -> str:
    return "".join(ch for ch in str(value or "").strip() if ch not in " \t\r\n：:，,。.-_")


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
