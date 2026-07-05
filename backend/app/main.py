from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import ValidationError as PydanticValidationError
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .contracts import (
    AgentResult,
    ChatAgentRequest,
    ChatAgentResponse,
    RagQueryRequest,
    ReviewRegenerateRequest,
    ReviewSubmitRequest,
    ReviewSubmitResponse,
    RunAgentRequest,
    ValidateRequest,
)
from .errors import BackendError, BadRequestError, NotFoundError, ProviderError, ValidationError
from .jobs import AgentJobStore
from .provider_config import ProviderConfig
from .service import AgentService


app = FastAPI(title="AI Notes Unified Backend", version="1.0.0")
cors_origins = list(settings.cors_origins)
allow_all_origins = "*" in cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all_origins else cors_origins,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
service = AgentService()
job_store = AgentJobStore(service)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ai-notes-unified-backend", "contract": "AgentResult/1.0"}


@app.get("/api/providers/status")
def provider_status() -> dict:
    return ProviderConfig.load().status()


@app.post("/api/agent/run", response_model=AgentResult, response_model_by_alias=True)
def run_agent(request: RunAgentRequest) -> dict:
    try:
        return service.run(request)
    except Exception as exc:
        raise_http_error(exc)


@app.post("/api/agent/run-file", response_model=AgentResult, response_model_by_alias=True)
async def run_agent_file(
    file: UploadFile = File(...),
    pipeline: str = Form("rag-only"),
    provider: str | None = Form(None),
    strictProvider: bool = Form(True),
    enableOcr: bool | None = Form(None),
    enableQualityReview: bool = Form(False),
    qualityReviewThreshold: float = Form(85),
    topK: int = Form(5),
    sourceTitle: str | None = Form(None),
) -> dict:
    try:
        file_path = await save_upload_file(file, sourceTitle=sourceTitle)
        request = RunAgentRequest(
            filePath=str(file_path),
            fileName=file.filename or file_path.name,
            pipeline=pipeline,
            provider=provider or None,
            strictProvider=strictProvider,
            enableOcr=enableOcr,
            enableQualityReview=enableQualityReview,
            qualityReviewThreshold=qualityReviewThreshold,
            topK=topK,
        )
        return service.run(request)
    except Exception as exc:
        raise_http_error(exc)


@app.post("/api/agent/jobs")
def start_agent_job(request: RunAgentRequest) -> dict:
    try:
        return job_store.start(request)
    except Exception as exc:
        raise_http_error(exc)


@app.post("/api/agent/jobs-file")
async def start_agent_file_job(
    file: UploadFile = File(...),
    pipeline: str = Form("rag-only"),
    provider: str | None = Form(None),
    strictProvider: bool = Form(True),
    enableOcr: bool | None = Form(None),
    enableQualityReview: bool = Form(False),
    qualityReviewThreshold: float = Form(85),
    topK: int = Form(5),
    sourceTitle: str | None = Form(None),
) -> dict:
    try:
        file_path = await save_upload_file(file, sourceTitle=sourceTitle)
        request = RunAgentRequest(
            filePath=str(file_path),
            fileName=file.filename or file_path.name,
            pipeline=pipeline,
            provider=provider or None,
            strictProvider=strictProvider,
            enableOcr=enableOcr,
            enableQualityReview=enableQualityReview,
            qualityReviewThreshold=qualityReviewThreshold,
            topK=topK,
        )
        return job_store.start(request)
    except Exception as exc:
        raise_http_error(exc)


@app.get("/api/agent/jobs/{job_id}")
def get_agent_job(job_id: str) -> dict:
    try:
        return job_store.get(job_id)
    except Exception as exc:
        raise_http_error(exc, not_found_detail=f"Unknown job: {job_id}")


@app.get("/api/agent/result/{result_id}", response_model=AgentResult, response_model_by_alias=True)
def get_result(result_id: str) -> dict:
    try:
        return service.get_result(result_id)
    except Exception as exc:
        raise_http_error(exc, not_found_detail=f"Unknown result: {result_id}")


@app.post("/api/agent/validate")
def validate_result(request: ValidateRequest) -> dict:
    try:
        return service.validate(request.result)
    except Exception as exc:
        raise_http_error(exc)


@app.post("/api/rag/query")
def rag_query(request: RagQueryRequest) -> dict:
    try:
        return service.query(
            query=request.query,
            chunks_path=request.chunksPath,
            result_id=request.resultId,
            provider_name=request.provider,
            top_k=request.topK,
        )
    except Exception as exc:
        raise_http_error(exc)


async def save_upload_file(file: UploadFile, *, sourceTitle: str | None = None) -> Path:
    original_name = file.filename or "uploaded.md"
    suffix = Path(original_name).suffix.lower()
    if suffix not in {".txt", ".md", ".markdown", ".doc", ".docx", ".pdf", ".pptx"}:
        raise BadRequestError(f"Unsupported file type: {suffix or original_name}")

    content = await file.read()
    if not content:
        raise BadRequestError("Uploaded file is empty")

    upload_dir = settings.output_dir / "_uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_stem = safe_file_stem(sourceTitle or Path(original_name).stem)
    file_path = upload_dir / f"{safe_stem}-{uuid.uuid4().hex[:8]}{suffix}"
    file_path.write_bytes(content)
    return file_path


def safe_file_stem(value: str) -> str:
    stem = re.sub(r'[\\/:*?"<>|]+', "-", value.strip())
    stem = re.sub(r"\s+", "-", stem).strip(".-")
    return stem[:80] or "uploaded"


@app.post("/api/agent/chat", response_model=ChatAgentResponse, response_model_by_alias=True)
def chat_agent(request: ChatAgentRequest) -> dict:
    try:
        return service.chat(
            question=request.question,
            result_id=request.resultId,
            provider_name=request.provider,
            strict=request.strictProvider,
            top_k=request.topK,
        )
    except Exception as exc:
        raise_http_error(exc)


@app.post("/api/agent/review/submit", response_model=ReviewSubmitResponse, response_model_by_alias=True)
def submit_review_answers(request: ReviewSubmitRequest) -> dict:
    try:
        return service.submit_review_answers(
            result_id=request.resultId,
            answers=request.answers,
            provider_name=request.provider,
            strict=request.strictProvider,
        )
    except Exception as exc:
        raise_http_error(exc)


@app.post("/api/agent/review/regenerate", response_model=AgentResult, response_model_by_alias=True)
def regenerate_review_questions(request: ReviewRegenerateRequest) -> dict:
    try:
        return service.regenerate_review_questions(
            result_id=request.resultId,
            review_history=request.reviewHistory,
            provider_name=request.provider,
            strict=request.strictProvider,
            question_count=request.questionCount,
        )
    except Exception as exc:
        raise_http_error(exc)


def raise_http_error(exc: Exception, *, not_found_detail: str | None = None) -> None:
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, NotFoundError) or isinstance(exc, FileNotFoundError):
        raise HTTPException(status_code=404, detail=not_found_detail or str(exc)) from exc
    if isinstance(exc, ValidationError) or isinstance(exc, PydanticValidationError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, ProviderError) or "provider failed" in str(exc).lower():
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if isinstance(exc, BadRequestError) or isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, BackendError):
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail="Internal server error") from exc
