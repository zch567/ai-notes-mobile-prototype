import pytest

from app.normalization import normalize_agent_result


def minimal_result():
    return {
        "topic": "主题",
        "summary": "摘要",
        "sources": [{"id": "s1", "title": "来源", "text": "原文"}],
        "notes": [{"id": "n1", "title": "笔记", "content": "正文", "citationIds": ["s1"]}],
        "citations": [{"id": "c1", "sourceId": "s1", "noteId": "n1"}],
    }


def test_minimal_backend_result_normalizes_to_contract():
    result = normalize_agent_result(minimal_result())
    assert result["id"]
    assert result["mindMap"] == {"nodes": [], "edges": []}
    assert result["review"]["masteryScore"] == 0


def test_invalid_source_link_is_rejected():
    raw = minimal_result()
    raw["notes"][0]["citationIds"] = ["missing"]
    with pytest.raises(ValueError):
        normalize_agent_result(raw)
