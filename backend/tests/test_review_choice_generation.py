from dataclasses import dataclass

from app.agents.orchestrator import (
    ModuleAgentOrchestrator,
    build_agent_result_from_modules,
    fallback_questions,
)
from app.rag.schemas import SourceChunk


def chunk() -> SourceChunk:
    return SourceChunk(
        id="sample-doc-c0001",
        sourceId="sample-doc",
        title="RAG",
        text="RAG uses retrieval results to constrain generation and provide grounded citations.",
        sourceType="text",
        fileName="sample.md",
        chunkIndex=1,
        sourceRef="para_1",
        heading="RAG",
        paragraphStart=1,
        paragraphEnd=1,
    )


@dataclass
class FakeLog:
    requestId: str = "req-1"
    provider: str = "test"
    model: str = "fake"
    taskType: str = "M6"
    inputChars: int = 0
    outputChars: int = 0
    latencyMs: int = 0
    status: str = "success"
    fallbackUsed: bool = False
    error: str | None = None


def test_week2_quiz_output_normalizes_single_choice_questions():
    source_chunk = chunk()
    outputs = {
        "M2": {"topic": "RAG", "summary": "summary"},
        "M3": {
            "notes": [
                {
                    "note_id": "n1",
                    "title": "Grounding",
                    "content": "RAG uses retrieval results as evidence.",
                    "source_refs": [source_chunk.id],
                }
            ]
        },
        "M4": {},
        "M6": {
            "quiz": [
                {
                    "question_id": "1",
                    "question_type": "single_choice",
                    "question": "Which statement best describes RAG grounding?",
                    "options": [
                        "A. It uses retrieved evidence.",
                        "B. It ignores source material.",
                        "C. It only changes UI layout.",
                        "D. It removes citations.",
                    ],
                    "answer": "A",
                    "explanation": "RAG is grounded by retrieved evidence.",
                    "related_note_id": "n1",
                }
            ]
        },
    }

    draft = build_agent_result_from_modules(outputs, [source_chunk], input_path=None, prompt_source="test")

    question = draft["review"]["questions"][0]
    assert question["type"] == "single-choice"
    assert len(question["options"]) == 4
    assert question["answer"] == "A. It uses retrieved evidence."
    assert question["relatedNoteId"] == "n1"


def test_fallback_review_questions_include_single_choice_items():
    notes = [
        {"id": "n1", "title": "Concept A", "summary": "Concept A explains grounding."},
        {"id": "n2", "title": "Concept B", "summary": "Concept B explains retrieval."},
        {"id": "n3", "title": "Concept C", "summary": "Concept C explains citations."},
    ]

    questions = fallback_questions(notes)

    single_choice = [item for item in questions if item["type"] == "single-choice"]
    assert len(single_choice) >= 2
    assert all(len(item["options"]) == 4 for item in single_choice)
    assert all(item["answer"] in item["options"] for item in single_choice)


class FakeModuleProvider:
    def __init__(self, provider_name, calls):
        self.provider_name = provider_name
        self.calls = calls

    def generate_module_json(self, module, prompt, payload, *, max_tokens=4096):
        self.calls.append((module, self.provider_name, payload))
        if module == "M2":
            return {"topic": "RAG", "summary": "summary"}, FakeLog(taskType=module)
        if module == "M3":
            return {"notes": [{"note_id": "n1", "title": "Grounding", "content": "RAG uses retrieval."}]}, FakeLog(taskType=module)
        if module == "M4":
            return {"mindmap": {"nodes": [], "edges": []}}, FakeLog(taskType=module)
        if module == "M6":
            return {
                "quiz": [
                    {
                        "question_id": "1",
                        "question_type": "single_choice",
                        "question": "Which option is correct?",
                        "options": ["A. Retrieval", "B. Layout", "C. Login", "D. Theme"],
                        "answer": "A",
                        "related_note_id": "n1",
                    }
                ]
            }, FakeLog(taskType=module)
        return {}, FakeLog(taskType=module)


def test_modular_generation_uses_lanxin_provider_for_m6(monkeypatch):
    calls = []

    def fake_create_provider(name=None):
        return FakeModuleProvider(name or "default", calls)

    monkeypatch.setattr("app.agents.orchestrator.create_provider", fake_create_provider)
    orchestrator = ModuleAgentOrchestrator()

    _draft, _meta = orchestrator.generate([chunk()], provider_name=None)

    providers_by_module = {module: provider for module, provider, _payload in calls}
    assert providers_by_module["M6"] == "lanxin"
    assert providers_by_module["M2"] == "default"
    m6_payload = next(payload for module, _provider, payload in calls if module == "M6")
    assert "single_choice" in m6_payload["review_schema"]["quiz"][0]["question_type"]
    assert "至少 2 道 single_choice" in m6_payload["user_requirement"]
