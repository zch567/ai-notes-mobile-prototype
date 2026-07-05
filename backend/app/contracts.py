from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExtensibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class AgentStage(ExtensibleModel):
    id: str
    label: str
    text: str


class Source(ExtensibleModel):
    id: str
    title: str
    text: str


class Note(ExtensibleModel):
    id: str
    title: str
    content: str
    citationIds: list[str] = Field(default_factory=list)


class Citation(ExtensibleModel):
    id: str
    sourceId: str
    noteId: str


class MindMapNode(ExtensibleModel):
    id: str
    label: str
    desc: str = ""
    detail: str = ""
    x: float = 50
    y: float = 50
    line: str = "#93c5fd"
    fill: str = "#ffffff"


class MindMapEdge(ExtensibleModel):
    from_: str = Field(alias="from")
    to: str

    model_config = ConfigDict(extra="allow", populate_by_name=True, serialize_by_alias=True)


class MindMap(ExtensibleModel):
    nodes: list[MindMapNode] = Field(default_factory=list)
    edges: list[MindMapEdge] = Field(default_factory=list)


class ReviewQuestion(ExtensibleModel):
    id: str
    type: str = "single-choice"
    question: str
    options: list[str] = Field(default_factory=list)
    answer: str = ""
    explanation: str = ""
    citationIds: list[str] = Field(default_factory=list)


class Review(ExtensibleModel):
    questions: list[ReviewQuestion] = Field(default_factory=list)
    masteryScore: float = 0
    weakPoints: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class AgentResult(ExtensibleModel):
    id: str
    topic: str
    summary: str
    agentStages: list[AgentStage] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    notes: list[Note] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    mindMap: MindMap = Field(default_factory=MindMap)
    review: Review = Field(default_factory=Review)

    @model_validator(mode="after")
    def validate_links(self) -> "AgentResult":
        source_ids = {source.id for source in self.sources}
        note_ids = {note.id for note in self.notes}
        invalid_note_links = {
            citation_id
            for note in self.notes
            for citation_id in note.citationIds
            if citation_id not in source_ids
        }
        invalid_question_links = {
            citation_id
            for question in self.review.questions
            for citation_id in question.citationIds
            if citation_id not in source_ids
        }
        invalid_citations = [
            citation.id
            for citation in self.citations
            if citation.sourceId not in source_ids or citation.noteId not in note_ids
        ]
        if invalid_note_links or invalid_question_links or invalid_citations:
            raise ValueError(
                "Invalid AgentResult links: "
                f"notes={sorted(invalid_note_links)}, "
                f"questions={sorted(invalid_question_links)}, "
                f"citations={invalid_citations}"
            )
        return self


class RunAgentRequest(ExtensibleModel):
    filePath: str | None = None
    sourceText: str | None = None
    fileName: str = "pasted-text.md"
    pipeline: str = "hybrid"
    provider: str | None = None
    strictProvider: bool = True
    ocrTextDir: str | None = None
    officeOcrDir: str | None = None
    topK: int = Field(default=2, ge=1, le=8)

    @model_validator(mode="after")
    def require_input(self) -> "RunAgentRequest":
        if not self.filePath and not (self.sourceText and self.sourceText.strip()):
            raise ValueError("filePath or sourceText is required")
        if self.provider and self.provider != "lanxin":
            raise ValueError("provider must be 'lanxin'")
        return self


class RagQueryRequest(ExtensibleModel):
    query: str
    chunksPath: str | None = None
    resultId: str | None = None
    topK: int = Field(default=5, ge=1, le=20)


class ChatAgentRequest(ExtensibleModel):
    question: str
    resultId: str
    provider: str | None = None
    strictProvider: bool = True
    topK: int = Field(default=3, ge=1, le=8)

    @model_validator(mode="after")
    def validate_chat_request(self) -> "ChatAgentRequest":
        if not self.question.strip():
            raise ValueError("question is required")
        if self.provider and self.provider != "lanxin":
            raise ValueError("provider must be 'lanxin'")
        return self


class ChatAgentResponse(ExtensibleModel):
    answer: str
    used_citations: list[Any] = Field(default_factory=list)
    related_notes: list[Any] = Field(default_factory=list)
    is_fully_supported_by_sources: bool = False
    unsupported_parts: list[Any] = Field(default_factory=list)
    follow_up_suggestions: list[str] = Field(default_factory=list)


class ReviewAnswerItem(ExtensibleModel):
    questionId: str
    answer: str


class ReviewSubmitRequest(ExtensibleModel):
    resultId: str
    answers: list[ReviewAnswerItem] = Field(default_factory=list)
    provider: str | None = "lanxin"
    strictProvider: bool = True

    @model_validator(mode="after")
    def validate_review_submit_request(self) -> "ReviewSubmitRequest":
        if not self.resultId.strip():
            raise ValueError("resultId is required")
        if not self.answers:
            raise ValueError("answers is required")
        if self.provider and self.provider != "lanxin":
            raise ValueError("provider must be 'lanxin'")
        return self


class ReviewQuestionFeedback(ExtensibleModel):
    questionId: str
    question: str = ""
    userAnswer: str = ""
    correctAnswer: str = ""
    isCorrect: bool = False
    explanation: str = ""
    relatedNoteId: str = ""


class ReviewSubmitResponse(ExtensibleModel):
    resultId: str
    masteryScore: float = 0
    correctCount: int = 0
    totalCount: int = 0
    questionResults: list[ReviewQuestionFeedback] = Field(default_factory=list)
    wrongQuestionExplanations: list[dict[str, Any]] = Field(default_factory=list)
    weakPoints: list[str] = Field(default_factory=list)
    reviewSuggestions: list[str] = Field(default_factory=list)


class ValidateRequest(ExtensibleModel):
    result: dict[str, Any]
