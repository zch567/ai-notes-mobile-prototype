from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ..provider_config import create_provider
from ..providers import ModelLog
from .schemas import SourceChunk
from .text_utils import compact


POLISH_MODULE = "M8_NOTE_POLISH"


def polish_result_with_provider(
    result: dict[str, Any],
    chunks: list[SourceChunk],
    *,
    provider_name: str | None = None,
    max_notes: int = 18,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Use an LLM to improve user-facing note text without changing source links."""
    provider = create_provider(provider_name)
    payload = _build_polish_payload(result, chunks, max_notes=max_notes)
    output, log = provider.generate_module_json(
        POLISH_MODULE,
        _polish_prompt(),
        payload,
        max_tokens=8192,
    )
    polished = apply_polish_result(result, output, chunks)
    return polished, {"modelLog": asdict(log), "module": POLISH_MODULE}


def apply_polish_result(
    result: dict[str, Any],
    polish: dict[str, Any],
    chunks: list[SourceChunk],
) -> dict[str, Any]:
    """Apply validated LLM note edits while preserving ids and source refs."""
    if not isinstance(polish, dict):
        return result
    notes_patch = polish.get("notes")
    if not isinstance(notes_patch, list):
        return result

    valid_chunk_ids = {chunk.id for chunk in chunks}
    current_notes = list(result.get("notes") or [])
    by_id = {str(note.get("id")): note for note in current_notes if note.get("id")}
    applied = 0
    for patch in notes_patch:
        if not isinstance(patch, dict):
            continue
        note_id = str(patch.get("id") or "")
        note = by_id.get(note_id)
        if not note:
            continue

        requested_refs = _string_list(patch.get("sourceRefs") or patch.get("source_refs"))
        existing_refs = _string_list(note.get("sourceRefs") or note.get("source_refs"))
        if requested_refs and any(ref not in valid_chunk_ids for ref in requested_refs):
            continue
        if requested_refs and existing_refs and not set(requested_refs).issubset(set(existing_refs)):
            continue

        title = _clean_field(patch.get("title"), limit=56)
        summary = _clean_field(patch.get("summary"), limit=260)
        content = _clean_field(patch.get("content"), limit=620)
        key_points = [_clean_field(item, limit=160) for item in _string_list(patch.get("keyPoints") or patch.get("key_points"))]
        key_points = [item for item in key_points if item]

        if title:
            note["title"] = title
        if summary:
            note["summary"] = summary
        if content:
            note["content"] = content
        if key_points:
            note["keyPoints"] = _dedupe(key_points)[:8]

        level = _int(patch.get("level"))
        if level is not None and 1 <= level <= 4:
            note["level"] = level
        parent_id = patch.get("parentId")
        if parent_id is None or parent_id == "" or str(parent_id) in by_id:
            note["parentId"] = str(parent_id) if parent_id else None

        note["citationIds"] = []
        note["sourceRefs"] = existing_refs
        note["source_refs"] = existing_refs
        note["blocks"] = _blocks_from_polished_note(note)
        applied += 1

    if applied:
        result["_meta"] = dict(result.get("_meta") or {})
        result["_meta"]["llmPolish"] = {
            "provider": "lanxin",
            "module": POLISH_MODULE,
            "appliedNotes": applied,
            "preservedSourceRefs": True,
            "citationsRebuiltByBackend": True,
        }
        _update_mindmap_text(result)
        _update_review_answers(result)
    return result


def _build_polish_payload(result: dict[str, Any], chunks: list[SourceChunk], *, max_notes: int) -> dict[str, Any]:
    source_by_id = {chunk.id: chunk for chunk in chunks}
    notes = []
    for note in (result.get("notes") or [])[:max_notes]:
        refs = _string_list(note.get("sourceRefs") or note.get("source_refs"))
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
        "topic": result.get("topic"),
        "documentSummary": result.get("summary"),
        "task": "polish_user_facing_learning_notes_without_changing_source_ids",
        "notes": notes,
        "constraints": {
            "doNotInventFacts": True,
            "doNotChangeNoteIds": True,
            "doNotAddSourceRefs": True,
            "doNotReturnCitations": True,
            "backendWillRebuildCitations": True,
            "summary": "one concise explanatory sentence; do not duplicate keyPoints",
            "keyPoints": "deduplicated complete bullet points; no broken clauses",
            "content": "supplementary explanation only; omit repeated lists",
        },
        "outputSchema": {
            "notes": [
                {
                    "id": "existing note id",
                    "title": "short natural title",
                    "summary": "one sentence",
                    "content": "non-repeating explanation",
                    "keyPoints": ["complete point"],
                    "level": 1,
                    "parentId": "existing parent id or null",
                    "sourceRefs": ["unchanged existing source ids"],
                }
            ]
        },
    }


def _polish_prompt() -> str:
    return (
        "你是学习笔记后端的文本整理模块。只返回严格 JSON。"
        "你的任务是把已有 NOTE 改成适合用户学习的表达，但不得改变事实和引用来源。"
        "必须遵守：1) 不新增 note id；2) 不新增 sourceRefs；3) 不输出 citations；"
        "4) summary 只写一句解释，不复制 keyPoints；5) keyPoints 必须完整、去重、无断句；"
        "6) content 只补充机制/上下文/例子，不重复 summary 和 keyPoints；"
        "7) classroom prompt 或材料句不要作为标题，改成概念化标题。"
    )


def _blocks_from_polished_note(note: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    summary = str(note.get("summary") or "").strip()
    if summary:
        blocks.append({"type": "summary", "title": "概要", "content": summary})
    key_points = _string_list(note.get("keyPoints"))
    if key_points:
        blocks.append(
            {
                "type": "outline",
                "title": "要点",
                "items": key_points,
                "structuredItems": [{"text": item, "children": []} for item in key_points],
            }
        )
    content = str(note.get("content") or "").strip()
    if content and content != summary:
        blocks.append({"type": "explanation", "title": "说明", "content": content})
    return blocks


def _update_mindmap_text(result: dict[str, Any]) -> None:
    notes = {str(note.get("id")): note for note in result.get("notes") or []}
    mind_map = result.get("mindMap") or {}
    for node in mind_map.get("nodes") or []:
        note_id = str(node.get("relatedNoteId") or "")
        note = notes.get(note_id)
        if not note:
            continue
        node["label"] = compact(str(note.get("title") or node.get("label") or ""), 22)
        node["desc"] = compact(str(note.get("summary") or note.get("content") or ""), 60)
        node["detail"] = str(note.get("content") or note.get("summary") or "")


def _update_review_answers(result: dict[str, Any]) -> None:
    notes = {str(note.get("id")): note for note in result.get("notes") or []}
    review = result.get("review") or {}
    for question in review.get("questions") or []:
        note = notes.get(str(question.get("relatedNoteId") or ""))
        if not note:
            continue
        question["answer"] = compact(str(note.get("summary") or note.get("content") or ""), 180)
        question["citationIds"] = []


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _clean_field(value: Any, *, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    return compact(text, limit)


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = "".join(item.split()).lower()
        if key and key not in seen:
            result.append(item)
            seen.add(key)
    return result


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
