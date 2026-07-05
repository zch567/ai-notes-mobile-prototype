import json
from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


client = TestClient(app)


@dataclass
class FakeLog:
    requestId: str = "req-review"
    provider: str = "lanxin"
    model: str = "fake"
    taskType: str = "M7_review_assessment"
    inputChars: int = 0
    outputChars: int = 0
    latencyMs: int = 0
    status: str = "success"
    fallbackUsed: bool = False
    error: str | None = None


class FakeReviewProvider:
    def __init__(self):
        self.payload = None

    def generate_module_json(self, module, prompt, payload, *, max_tokens=4096):
        self.payload = payload
        return {
            "wrongQuestionExplanations": [
                {
                    "questionId": "q1",
                    "mistakeReason": "混淆了检索证据和界面展示。",
                    "correctThinking": "RAG 的关键是用检索证据约束生成。",
                    "knowledgePoint": "RAG grounding",
                    "remediation": "回看关联笔记并比较四个选项。",
                }
            ],
            "weakPoints": ["RAG grounding"],
            "reviewSuggestions": ["重读 RAG grounding 笔记，并说明正确选项为什么成立。"],
        }, FakeLog(taskType=module)


class FakeReviewRegenerateProvider:
    def __init__(self):
        self.payload = None

    def generate_module_json(self, module, prompt, payload, *, max_tokens=4096):
        self.payload = payload
        return {
            "quiz": [
                {
                    "question_id": "new-q1",
                    "question_type": "single_choice",
                    "skill": "application",
                    "difficulty": "medium",
                    "question": "A learner wants to reduce unsupported RAG answers. Which action best applies grounding?",
                    "options": ["A. Retrieve evidence before answering", "B. Hide all citations", "C. Skip retrieval", "D. Change the theme"],
                    "answer": "A",
                    "explanation": "Grounding applies retrieved evidence to constrain the answer.",
                    "related_note_id": "n1",
                }
            ],
            "weakPoints": ["RAG grounding"],
            "recommendations": ["Use a new scenario to explain why retrieval evidence matters."],
        }, FakeLog(taskType=module)


def test_review_submit_calls_lanxin_for_wrong_choice_analysis(tmp_path: Path, monkeypatch):
    result_id = "rag-review-test"
    run_dir = tmp_path / "runtime" / result_id
    run_dir.mkdir(parents=True)
    object.__setattr__(settings, "output_dir", (tmp_path / "runtime").resolve())

    result = {
        "id": result_id,
        "topic": "RAG",
        "summary": "RAG uses retrieval evidence.",
        "notes": [{"id": "n1", "title": "RAG grounding", "summary": "Use retrieved evidence."}],
        "review": {
            "questions": [
                {
                    "id": "q1",
                    "type": "single-choice",
                    "question": "What is the key idea of RAG grounding?",
                    "options": ["A. Use evidence", "B. Change theme", "C. Hide notes", "D. Skip sources"],
                    "answer": "A. Use evidence",
                    "explanation": "RAG grounds generation in retrieved evidence.",
                    "relatedNoteId": "n1",
                    "citationIds": ["c1"],
                }
            ]
        },
    }
    chunks = [
        {
            "id": "c1",
            "sourceId": "doc",
            "title": "RAG",
            "text": "RAG uses retrieved evidence to constrain generated answers.",
            "sourceType": "text",
            "fileName": "rag.md",
            "chunkIndex": 1,
            "sourceRef": "para_1",
        }
    ]
    (run_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    (run_dir / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    fake_provider = FakeReviewProvider()
    monkeypatch.setattr("app.service.create_provider", lambda _name=None: fake_provider)

    response = client.post(
        "/api/agent/review/submit",
        json={
            "resultId": result_id,
            "answers": [{"questionId": "q1", "answer": "B"}],
            "provider": "lanxin",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["masteryScore"] == 0
    assert body["correctCount"] == 0
    assert body["totalCount"] == 1
    assert body["questionResults"][0]["userAnswer"] == "B. Change theme"
    assert body["wrongQuestionExplanations"][0]["questionId"] == "q1"
    assert body["weakPoints"] == ["RAG grounding"]
    assert body["reviewSuggestions"]
    assert fake_provider.payload["wrong_questions"][0]["sources"][0]["source_id"] == "c1"


def test_review_submit_scores_multiple_choice_answers(tmp_path: Path, monkeypatch):
    result_id = "rag-review-multi-test"
    run_dir = tmp_path / "runtime" / result_id
    run_dir.mkdir(parents=True)
    object.__setattr__(settings, "output_dir", (tmp_path / "runtime").resolve())

    result = {
        "id": result_id,
        "topic": "RAG",
        "summary": "RAG uses retrieval evidence.",
        "notes": [{"id": "n1", "title": "RAG grounding", "summary": "Use retrieved evidence."}],
        "review": {
            "questions": [
                {
                    "id": "q1",
                    "type": "multiple-choice",
                    "question": "Which statements describe RAG grounding?",
                    "options": ["A. Use evidence", "B. Cite sources", "C. Hide notes", "D. Skip retrieval"],
                    "answer": ["A", "B"],
                    "explanation": "RAG grounds generation in retrieved evidence and citations.",
                    "relatedNoteId": "n1",
                    "citationIds": [],
                }
            ]
        },
    }
    (run_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    (run_dir / "chunks.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr("app.service.create_provider", lambda _name=None: FakeReviewProvider())

    response = client.post(
        "/api/agent/review/submit",
        json={
            "resultId": result_id,
            "answers": [{"questionId": "q1", "answer": "B,A"}],
            "provider": "lanxin",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["masteryScore"] == 100
    assert body["questionResults"][0]["isCorrect"] is True
    assert body["questionResults"][0]["userAnswer"] == "B. Cite sources; A. Use evidence"


def test_review_regenerate_sends_history_and_returns_application_questions(tmp_path: Path, monkeypatch):
    result_id = "rag-review-regenerate-test"
    run_dir = tmp_path / "runtime" / result_id
    run_dir.mkdir(parents=True)
    object.__setattr__(settings, "output_dir", (tmp_path / "runtime").resolve())

    result = {
        "id": result_id,
        "topic": "RAG",
        "summary": "RAG uses retrieval evidence.",
        "notes": [{"id": "n1", "title": "RAG grounding", "content": "Use retrieved evidence.", "citationIds": []}],
        "sources": [],
        "citations": [],
        "mindMap": {"nodes": [], "edges": []},
        "review": {
            "questions": [
                {
                    "id": "q1",
                    "type": "single-choice",
                    "question": "What is RAG grounding?",
                    "options": ["A. Use evidence", "B. Change theme", "C. Hide notes", "D. Skip sources"],
                    "answer": "A. Use evidence",
                    "explanation": "RAG grounds generation in retrieved evidence.",
                    "relatedNoteId": "n1",
                    "citationIds": [],
                }
            ],
            "masteryScore": 0,
            "weakPoints": [],
            "recommendations": [],
        },
    }
    chunks = [
        {
            "id": "c1",
            "sourceId": "doc",
            "title": "RAG",
            "text": "RAG uses retrieved evidence to constrain generated answers.",
            "sourceType": "text",
            "fileName": "rag.md",
            "chunkIndex": 1,
            "sourceRef": "para_1",
        }
    ]
    (run_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    (run_dir / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    fake_provider = FakeReviewRegenerateProvider()
    monkeypatch.setattr("app.agents.orchestrator.create_provider", lambda _name=None: fake_provider)

    response = client.post(
        "/api/agent/review/regenerate",
        json={
            "resultId": result_id,
            "reviewHistory": [
                {
                    "masteryScore": 0,
                    "questionResults": [
                        {
                            "question": "What is RAG grounding?",
                            "userAnswer": "B. Change theme",
                            "correctAnswer": "A. Use evidence",
                            "isCorrect": False,
                        }
                    ],
                    "weakPoints": ["RAG grounding"],
                    "reviewSuggestions": ["Review grounding with an application case."],
                }
            ],
            "provider": "lanxin",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    question = body["review"]["questions"][0]
    assert question["question"].startswith("A learner wants")
    assert question["skill"] == "application"
    assert fake_provider.payload["review_history_summary"]["previousQuestionStems"]
    assert fake_provider.payload["review_history_summary"]["weakPoints"] == ["RAG grounding"]
    assert fake_provider.payload["adaptive_review_strategy"]["questionMix"]["applicationScenario"] >= 3
    persisted = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert persisted["review"]["questions"][0]["id"] == "new-q1"
