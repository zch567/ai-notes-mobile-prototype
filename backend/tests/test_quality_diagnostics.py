from app.rag.quality_diagnostics import attach_quality_diagnostics


def test_quality_diagnostics_surfaces_summary_and_keypoint_failures():
    result = {
        "id": "agent-test",
        "topic": "DMA",
        "summary": "DMA 学习资料",
        "agentStages": [
            {"id": "M1", "label": "Parse", "text": "parsed"},
            {"id": "M2", "label": "Summary", "text": "summarized"},
            {"id": "M3", "label": "Notes", "text": "notes"},
            {"id": "M4", "label": "Mind Map", "text": "mindmap"},
            {"id": "M5", "label": "Grounding", "text": "grounded"},
            {"id": "M6", "label": "Review", "text": "review"},
        ],
        "sources": [{"id": "c1", "title": "DMA", "text": "DMA 数据传送过程包含预处理、数据传送、后处理。"}],
        "notes": [
            {
                "id": "note-1",
                "title": "DMA 数据传送过程",
                "summary": "DMA 数据传送过程包含✓ 预处理之后：当 I/O设备准备好发送的数据、CPU继续执行主程序、校验送入主存的数据是否正确等内容。",
                "content": "流程类内容可按触发条件、执行动作和结束信号理解。",
                "keyPoints": ["✓ 预处理之后：当 I/O设备准备好发送的数据", "经处理完毕（对应输出情况），便通过DMA"],
                "citationIds": ["c1"],
                "sourceExcerpts": [{"quote": "DMA 数据传送过程包含预处理、数据传送、后处理。"}],
            }
        ],
        "citations": [{"id": "citation-1", "sourceId": "c1", "noteId": "note-1"}],
        "mindMap": {"nodes": [{"id": "root", "label": "DMA"}, {"id": "note-1", "label": "DMA 数据传送过程"}], "edges": [{"from": "root", "to": "note-1"}]},
        "review": {"questions": [{"id": "q1", "question": "DMA 数据传送过程有哪些阶段？", "citationIds": ["c1"]}], "weakPoints": ["DMA 数据传送过程"], "recommendations": ["按阶段复述"]},
        "citationDiagnostics": {
            "noteCitationCoverage": 1,
            "quoteInSourceRate": 1,
            "averageConfidence": 0.9,
            "averageNoteSupportScore": 0.8,
            "explicitRefResolutionRate": 1,
            "lowSupportNoteRate": 0,
        },
        "_meta": {"chunkCount": 1, "agentModules": ["M1", "M2", "M3", "M4", "M5", "M6"]},
    }

    attach_quality_diagnostics(result)

    assert result["assetMeta"]["assetVersion"] == "learning-asset-v1"
    diagnostics = result["qualityDiagnostics"]
    assert diagnostics["passed"] is False
    assert diagnostics["structureScore"] < 100
    assert any("拼接式概要" in warning or "要点质量偏弱" in warning for warning in diagnostics["warnings"])
    assert diagnostics["keyMetrics"]["rawConcatSummaryRate"] > 0
    assert diagnostics["keyMetrics"]["weakKeyPointRate"] > 0


def test_quality_diagnostics_caps_score_when_content_quality_fails():
    result = {
        "id": "agent-score-cap",
        "topic": "水浒传",
        "summary": "水浒传阅读资料",
        "agentStages": [{"id": f"M{i}", "label": f"M{i}", "text": "ok"} for i in range(1, 7)],
        "sources": [{"id": "c1", "title": "水浒传", "text": "宋江为人仗义，善于用人。"}],
        "notes": [
            {
                "id": "note-1",
                "title": "性格特点：为人仗义、善于用人，但总希望被朝廷招安",
                "summary": "“性格特点：为人仗义、善于用人，但总希望被朝廷招安”需要说明概念含义、使用条件和应用场景。",
                "content": "性格特点的关键线索是宋江为人仗义，需要说明它的含义、条件、作用或例子。",
                "keyPoints": ["“性格特点：为人仗义、善于用人，但总希望被朝廷招安”需要说明概念含义、使用条件和应用场景"],
                "citationIds": ["c1"],
                "sourceExcerpts": [{"quote": "宋江为人仗义，善于用人。"}],
            }
        ],
        "citations": [{"id": "citation-1", "sourceId": "c1", "noteId": "note-1"}],
        "mindMap": {"nodes": [{"id": "root"}, {"id": "note-1"}], "edges": [{"from": "root", "to": "note-1"}]},
        "review": {"questions": [{"id": "q1", "question": "宋江性格如何？", "citationIds": ["c1"]}], "weakPoints": ["人物"], "recommendations": ["复习人物"]},
        "citationDiagnostics": {
            "noteCitationCoverage": 1,
            "quoteInSourceRate": 1,
            "averageConfidence": 1,
            "averageNoteSupportScore": 1,
            "explicitRefResolutionRate": 1,
            "lowSupportNoteRate": 0,
        },
        "_meta": {"chunkCount": 1, "agentModules": ["M1", "M2", "M3", "M4", "M5", "M6"]},
    }

    attach_quality_diagnostics(result)

    diagnostics = result["qualityDiagnostics"]
    assert diagnostics["passed"] is False
    assert diagnostics["overallScore"] <= 74
