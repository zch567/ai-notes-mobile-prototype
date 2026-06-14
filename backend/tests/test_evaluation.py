from app.evaluation import compare_results, evaluate_result


def result(provider: str, confidence: float, note_content: str) -> dict:
    return {
        "id": f"{provider}-1",
        "topic": "RAG",
        "summary": "摘要",
        "agentStages": [],
        "sources": [{"id": "s1", "title": "来源", "text": "RAG 使用检索结果约束生成并提供引用。"}],
        "notes": [{"id": "n1", "title": "RAG", "content": note_content, "citationIds": ["s1"]}],
        "citations": [{"id": "c1", "sourceId": "s1", "noteId": "n1"}],
        "mindMap": {"nodes": [], "edges": []},
        "review": {"questions": [], "masteryScore": 0, "weakPoints": [], "recommendations": []},
        "citationDiagnostics": {
            "noteCitationCoverage": 1,
            "citationSourceValidity": 1,
            "citationNoteValidity": 1,
            "quoteInSourceRate": 1,
            "averageConfidence": confidence,
            "noteTitleUniqueness": 1,
            "noteContentUniqueness": 1,
        },
        "_meta": {"modelLog": {"provider": provider, "model": f"{provider}-model", "fallbackUsed": False}},
    }


def test_evaluation_reports_provider_and_grounding_metrics():
    metrics = evaluate_result(result("lanxin", 0.9, "RAG 使用检索结果约束生成。"), 120)

    assert metrics["contractValid"] is True
    assert metrics["provider"] == "lanxin"
    assert metrics["averageNoteSourceSupport"] > 0
    assert metrics["qualityScore"] > 0


def test_comparison_delta_is_lanxin_minus_offline():
    comparison = compare_results(
        result("offline", 0.5, "简短说明"),
        result("lanxin", 0.9, "RAG 使用检索结果约束生成并提供引用。"),
        offline_latency_ms=10,
        lanxin_latency_ms=100,
    )

    assert comparison["deltaLanxinMinusOffline"]["latencyMs"] == 90
    assert comparison["lanxin"]["provider"] == "lanxin"
