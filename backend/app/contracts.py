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


class ValidateRequest(ExtensibleModel):
    result: dict[str, Any]
