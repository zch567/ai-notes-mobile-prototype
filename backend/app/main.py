from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .contracts import AgentResult, ChatAgentRequest, RagQueryRequest, RunAgentRequest, ValidateRequest
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
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/agent/run-file", response_model=AgentResult, response_model_by_alias=True)
async def run_agent_file(
    file: UploadFile = File(...),
    pipeline: str = Form("hybrid"),
    provider: str | None = Form(None),
    strictProvider: bool = Form(True),
    topK: int = Form(2),
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
            topK=topK,
        )
        return service.run(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/agent/result/{result_id}", response_model=AgentResult, response_model_by_alias=True)
def get_result(result_id: str) -> dict:
    try:
        return service.get_result(result_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown result: {result_id}") from exc


@app.post("/api/agent/validate")
def validate_result(request: ValidateRequest) -> dict:
    try:
        return service.validate(request.result)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/rag/query")
def rag_query(request: RagQueryRequest) -> dict:
    try:
        return service.query(
            query=request.query,
            chunks_path=request.chunksPath,
            result_id=request.resultId,
            top_k=request.topK,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def save_upload_file(file: UploadFile, *, sourceTitle: str | None = None) -> Path:
    original_name = file.filename or "uploaded.md"
    suffix = Path(original_name).suffix.lower()
    if suffix not in {".txt", ".md", ".markdown", ".docx", ".pdf", ".pptx"}:
        raise ValueError(f"Unsupported file type: {suffix or original_name}")

    content = await file.read()
    if not content:
        raise ValueError("Uploaded file is empty")

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


@app.post("/api/agent/chat")
def chat_agent(request: ChatAgentRequest) -> dict:
    try:
        return service.chat(
            question=request.question,
            result_id=request.resultId,
            provider_name=request.provider,
            strict=request.strictProvider,
            top_k=request.topK,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
