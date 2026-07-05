from __future__ import annotations

from app.rag.grounding import ground_result
from app.rag.llm_quality_review import quality_improvement_loop, review_and_rewrite_if_needed
from app.rag.quality_diagnostics import attach_quality_diagnostics
from app.rag.schemas import SourceChunk
from app.providers import ModelLog


class FakeProvider:
    name = "lanxin"
    model = "fake-quality-review"

    def __init__(self) -> None:
        self.modules: list[str] = []

    def generate_module_json(self, module, prompt, payload, *, max_tokens=4096):
        self.modules.append(module)
        if module == "M8_QUALITY_REVIEW":
            return {
                "overallVerdict": "内容对学习者帮助不足，需要让概要、要点和解释分别承担不同作用。",
                "priorityProblems": [
                    {
                        "noteId": "note-1",
                        "problem": "要点不可复习，概要像拼接原文。",
                        "cause": "生成时没有把概念解释和列表区分开。",
                        "rewriteGuidance": "围绕证据重写为完整学习点，不要重复同一批词。",
                    }
                ],
                "globalRewriteRules": ["每条要点必须能独立回答一个学习问题。"],
            }, _log(module)
        return {
            "notes": [
                {
                    "id": "note-1",
                    "title": "RAG 的引用约束作用",
                    "summary": "RAG 通过把回答绑定到检索证据，降低无依据生成的风险。",
                    "content": "学习时要抓住“先检索、再依据来源回答”的流程，并检查回答是否能回到原文片段。",
                    "keyPoints": [
                        "RAG 使用检索到的来源片段约束回答范围。",
                        "引用回链让用户能够检查回答是否有原文依据。",
                        "复习时应同时关注答案内容和支撑答案的证据。",
                    ],
                    "sourceRefs": ["c1"],
                }
            ]
        }, _log(module)


class SequenceProvider:
    def __init__(self, summaries: list[str]) -> None:
        self.summaries = summaries
        self.modules: list[str] = []
        self.rewrite_count = 0

    def generate_module_json(self, module, prompt, payload, *, max_tokens=4096):
        self.modules.append(module)
        if module == "M8_QUALITY_REVIEW":
            return {
                "overallVerdict": "继续从学习价值角度优化。",
                "priorityProblems": [{"noteId": "note-1", "problem": "学习价值不足", "cause": "表达不完整", "rewriteGuidance": "用证据重写为完整学习点"}],
                "globalRewriteRules": ["只保留可由证据支持的学习点。"],
            }, _log(module)
        if module == "M2":
            return {
                "topic": "RAG 与可信引用",
                "summary": "RAG 用检索证据约束生成内容，并通过引用回链支持查证。",
                "keywords": ["RAG", "检索", "引用回链"],
                "core_points": [
                    {"id": "p1", "title": "检索约束", "brief": "先检索来源片段，再生成回答。"},
                    {"id": "p2", "title": "引用查证", "brief": "用回链检查回答依据。"},
                ],
            }, _log(module)
        if module == "M3":
            summary = self.summaries[min(self.rewrite_count, len(self.summaries) - 1)]
            self.rewrite_count += 1
            return {
                "notes": [
                    {
                        "note_id": "note-1",
                        "title": "RAG 的引用约束作用",
                        "summary": summary,
                        "content": "学习时要抓住先检索、再依据来源回答的流程，并检查回答是否能回到原文片段。",
                        "keyPoints": [
                            "RAG 使用检索到的来源片段约束回答范围。",
                            "引用回链让用户能够检查回答是否有原文依据。",
                            "复习时应同时关注答案内容和支撑答案的证据。",
                        ],
                        "source_refs": ["c1"],
                        "level": 1,
                    },
                    {
                        "note_id": "note-2",
                        "title": "学习笔记的证据检查",
                        "summary": "高质量笔记需要让用户同时看到结论和支撑结论的来源。",
                        "content": "复习时可以先复述答案，再回到引用片段检查是否有原文依据。",
                        "keyPoints": [
                            "学习笔记应包含可回看的原文证据。",
                            "复习题应关联到支撑答案的笔记和来源。",
                            "引用不足时用户难以判断答案是否可靠。",
                        ],
                        "source_refs": ["c1"],
                        "level": 1,
                    },
                    {
                        "note_id": "note-3",
                        "title": "生成质量的基本要求",
                        "summary": "笔记质量取决于标题、概要、要点、原文证据和复习建议是否协同服务学习。",
                        "content": "标题负责定位概念，概要解释核心含义，要点用于复习，引用用于查证。",
                        "keyPoints": [
                            "标题应指向清楚的学习对象。",
                            "概要应解释核心含义而不是拼接列表。",
                            "要点应能支持用户复习和答题。",
                        ],
                        "source_refs": ["c1"],
                        "level": 1,
                    },
                ],
                "global_summary": "RAG 学习材料强调证据约束、引用查证和学习笔记质量。",
            }, _log(module)
        if module == "M4":
            return {
                "mindmap": {
                    "nodes": [
                        {"id": "root", "label": "RAG 与可信引用", "detail": "学习主题", "source_refs": ["c1"]},
                        {"id": "n1", "label": "引用约束", "related_note_id": "note-1", "detail": "基于证据回答", "source_refs": ["c1"]},
                    ],
                    "edges": [{"from": "root", "to": "n1", "type": "hierarchy", "label": "包含", "reason": "主题包含该知识点", "confidence": 0.8, "source_refs": ["c1"]}],
                }
            }, _log(module)
        if module == "M6":
            return {
                "review": {
                    "questions": [
                        {"id": f"q{i}", "type": "single-choice", "question": f"RAG 复习题 {i}", "options": ["A. 检索证据", "B. 随机回答", "C. 删除引用", "D. 忽略来源"], "answer": "A", "explanation": "RAG 需要先检索证据。", "relatedNoteId": "note-1"}
                        for i in range(1, 6)
                    ],
                    "weakPoints": ["引用查证", "证据约束"],
                    "recommendations": ["复习时先看结论，再检查引用来源。", "用原文片段解释每道题的答案。"],
                }
            }, _log(module)
        summary = self.summaries[min(self.rewrite_count, len(self.summaries) - 1)]
        self.rewrite_count += 1
        return {
            "notes": [
                {
                    "id": "note-1",
                    "title": "RAG 的引用约束作用",
                    "summary": summary,
                    "content": "学习时要抓住先检索、再依据来源回答的流程，并检查回答是否能回到原文片段。",
                    "keyPoints": [
                        "RAG 使用检索到的来源片段约束回答范围。",
                        "引用回链让用户能够检查回答是否有原文依据。",
                        "复习时应同时关注答案内容和支撑答案的证据。",
                    ],
                    "sourceRefs": ["c1"],
                }
            ]
        }, _log(module)


def test_quality_review_rewrites_low_score_without_changing_sources(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr("app.rag.llm_quality_review.create_provider", lambda provider_name=None: provider)
    chunks = [_chunk()]
    result = ground_result(_weak_result(), chunks, top_k=1)
    attach_quality_diagnostics(result)

    rewritten, meta = review_and_rewrite_if_needed(result, chunks, provider_name="lanxin", threshold=99)
    rewritten = ground_result(rewritten, chunks, top_k=1)
    attach_quality_diagnostics(rewritten)

    assert provider.modules == ["M8_QUALITY_REVIEW", "M8_QUALITY_GUIDED_REWRITE"]
    assert meta["skipped"] is False
    assert rewritten["notes"][0]["sourceRefs"] == ["c1"]
    assert rewritten["notes"][0]["citationIds"] == ["c1"]
    assert "评分" not in rewritten["notes"][0]["content"]
    assert "RAG 通过把回答绑定到检索证据" in rewritten["notes"][0]["summary"]


def test_quality_review_skips_when_score_above_threshold(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr("app.rag.llm_quality_review.create_provider", lambda provider_name=None: provider)
    result = _weak_result()
    result["qualityDiagnostics"] = {"overallScore": 95}

    rewritten, meta = review_and_rewrite_if_needed(result, [_chunk()], provider_name="lanxin", threshold=85)

    assert rewritten is result
    assert meta["skipped"] is True
    assert provider.modules == []


def test_quality_improvement_loop_stops_after_threshold(monkeypatch):
    provider = SequenceProvider(["RAG 主要包括 RAG、检索、引用、回答等内容。", "RAG 通过把回答绑定到检索证据，降低无依据生成的风险。"])
    monkeypatch.setattr("app.rag.llm_quality_review.create_provider", lambda provider_name=None: provider)
    chunks = [_chunk()]
    result = ground_result(_weak_result(), chunks, top_k=1)
    attach_quality_diagnostics(result)

    improved, meta = quality_improvement_loop(result, chunks, provider_name="lanxin", threshold=61, top_k=1, max_rounds=3)

    assert meta["skipped"] is False
    assert len(meta["rounds"]) <= 2
    assert meta["finalScore"] >= 61
    assert {"M2", "M3", "M4", "M6"}.issubset(set(provider.modules))
    assert improved["notes"][0]["citationIds"] == ["c1"]


def test_quality_improvement_loop_uses_best_version_after_three_rounds(monkeypatch):
    provider = SequenceProvider([
        "RAG 主要包括 RAG、检索、引用、回答等内容。",
        "RAG 通过把回答绑定到检索证据，降低无依据生成的风险。",
        "RAG 主要包括 RAG、检索、引用、回答等内容。",
    ])
    monkeypatch.setattr("app.rag.llm_quality_review.create_provider", lambda provider_name=None: provider)
    chunks = [_chunk()]
    result = ground_result(_weak_result(), chunks, top_k=1)
    attach_quality_diagnostics(result)

    improved, meta = quality_improvement_loop(result, chunks, provider_name="lanxin", threshold=100, top_k=1, max_rounds=3)

    assert len(meta["rounds"]) == 3
    assert meta["usedBestVersion"] is True
    assert meta["finalScore"] == max(item["afterScore"] for item in meta["rounds"] + [{"afterScore": meta["initialScore"]}])
    assert len(improved["notes"]) >= 3
    assert {"M2", "M3", "M4", "M6"}.issubset(set(provider.modules))


def _chunk() -> SourceChunk:
    return SourceChunk(
        id="c1",
        sourceId="doc",
        title="RAG",
        text="RAG 使用检索到的来源片段约束回答范围，并提供可回看引用。",
        sourceType="text",
        fileName="rag.md",
        chunkIndex=1,
        sourceRef="para_1",
    )


def _weak_result() -> dict:
    return {
        "id": "agent-test",
        "topic": "RAG",
        "summary": "RAG 学习资料",
        "agentStages": [{"id": f"M{i}", "label": f"M{i}", "text": "ok"} for i in range(1, 7)],
        "sources": [],
        "notes": [
            {
                "id": "note-1",
                "title": "RAG",
                "summary": "RAG 主要包括 RAG、检索、引用、回答等内容。",
                "content": "RAG、检索、引用、回答。",
                "keyPoints": ["RAG", "检索", "引用"],
                "sourceRefs": ["c1"],
            }
        ],
        "citations": [],
        "mindMap": {"nodes": [{"id": "root"}, {"id": "note-1"}], "edges": [{"from": "root", "to": "note-1"}]},
        "review": {"questions": [{"id": "q1", "question": "RAG 有什么作用？", "citationIds": ["c1"]}], "weakPoints": ["RAG"], "recommendations": ["复习引用"]},
    }


def _log(module: str):
    return ModelLog(
        requestId="req",
        provider="lanxin",
        model="fake",
        taskType=module,
        inputChars=1,
        outputChars=1,
        latencyMs=1,
        status="success",
        fallbackUsed=False,
    )
