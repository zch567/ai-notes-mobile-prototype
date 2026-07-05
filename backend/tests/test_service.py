import asyncio
import json
import time
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import settings
from app.contracts import RunAgentRequest
from app.errors import BadRequestError
from app.main import app, save_upload_file, service as app_service
from app.service import AgentService


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["contract"] == "AgentResult/1.0"


def test_rag_only_run_returns_frontend_contract(tmp_path: Path):
    source = tmp_path / "sample.md"
    source.write_text("# 自注意力\n\n自注意力允许每个词关注其他词。", encoding="utf-8")
    object.__setattr__(settings, "allowed_input_root", tmp_path.resolve())
    object.__setattr__(settings, "output_dir", (tmp_path / "runtime").resolve())
    response = client.post("/api/agent/run", json={"filePath": str(source), "pipeline": "rag-only"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert set(["id", "topic", "summary", "agentStages", "sources", "notes", "citations", "mindMap", "review"]) <= set(result)
    assert result["notes"][0]["citationIds"]
    assert result["mindMap"]["nodes"][0]["line"]
    assert result["assetMeta"]["assetVersion"] == "learning-asset-v1"
    assert result["qualityDiagnostics"]["overallScore"] >= 0
    assert result["qualityDiagnostics"]["summaryText"]


def test_validate_endpoint_accepts_persisted_result(tmp_path: Path):
    source = tmp_path / "sample.md"
    source.write_text("# RAG\n\nRAG 使用检索结果约束生成。", encoding="utf-8")
    object.__setattr__(settings, "allowed_input_root", tmp_path.resolve())
    object.__setattr__(settings, "output_dir", (tmp_path / "runtime").resolve())
    result = client.post("/api/agent/run", json={"filePath": str(source), "pipeline": "rag-only"}).json()
    response = client.post("/api/agent/validate", json={"result": result})
    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_chat_endpoint_answers_against_persisted_result(tmp_path: Path, monkeypatch):
    source = tmp_path / "sample.md"
    source.write_text("# RAG\n\nRAG 使用检索结果约束生成，并提供可回看引用。", encoding="utf-8")
    object.__setattr__(settings, "allowed_input_root", tmp_path.resolve())
    object.__setattr__(settings, "output_dir", (tmp_path / "runtime").resolve())
    result = client.post("/api/agent/run", json={"filePath": str(source), "pipeline": "rag-only"}).json()
    observed = {}

    def fake_chat(*, question, result, chunks, provider_name=None, strict=False, top_k=3):
        observed.update(
            question=question,
            result_id=result["id"],
            chunk_count=len(chunks),
            provider_name=provider_name,
            strict=strict,
            top_k=top_k,
        )
        return {
            "answer": "RAG 通过检索到的来源片段约束回答范围。",
            "used_citations": [chunks[0].id],
            "related_notes": [result["notes"][0]["id"]],
            "is_fully_supported_by_sources": True,
            "unsupported_parts": [],
            "follow_up_suggestions": ["还可以追问引用如何回看。"],
            "_meta": {"retrievedSourceIds": [chunks[0].id]},
        }

    monkeypatch.setattr(app_service.agent, "chat", fake_chat)

    response = client.post(
        "/api/agent/chat",
        json={
            "resultId": result["id"],
            "question": "RAG 如何降低生成幻觉？",
            "provider": "lanxin",
            "topK": 2,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answer"].startswith("RAG")
    assert body["used_citations"]
    assert body["is_fully_supported_by_sources"] is True
    assert observed == {
        "question": "RAG 如何降低生成幻觉？",
        "result_id": result["id"],
        "chunk_count": 1,
        "provider_name": "lanxin",
        "strict": True,
        "top_k": 2,
    }


def test_source_text_request_is_supported(tmp_path: Path):
    object.__setattr__(settings, "allowed_input_root", tmp_path.resolve())
    object.__setattr__(settings, "output_dir", (tmp_path / "runtime").resolve())
    response = client.post(
        "/api/agent/run",
        json={"sourceText": "# RAG\n\nRAG 使用检索结果约束生成。", "pipeline": "rag-only"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["topic"]


def test_file_upload_request_is_supported(tmp_path: Path):
    object.__setattr__(settings, "allowed_input_root", tmp_path.resolve())
    object.__setattr__(settings, "output_dir", (tmp_path / "runtime").resolve())
    response = client.post(
        "/api/agent/run-file",
        data={"pipeline": "rag-only", "sourceTitle": "上传资料", "topK": "2"},
        files={"file": ("notes.md", b"# RAG\n\nRAG grounds generated answers in source chunks.", "text/markdown")},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["topic"]
    assert result["notes"]
    assert result["sources"][0]["fileName"].endswith(".md")


def test_agent_job_progress_endpoint_returns_result(tmp_path: Path):
    object.__setattr__(settings, "allowed_input_root", tmp_path.resolve())
    object.__setattr__(settings, "output_dir", (tmp_path / "runtime").resolve())
    response = client.post(
        "/api/agent/jobs",
        json={"sourceText": "# RAG\n\nRAG 使用检索结果约束生成。", "pipeline": "rag-only"},
    )
    assert response.status_code == 200, response.text
    job = response.json()
    assert job["jobId"].startswith("job-")
    assert job["status"] in {"queued", "running", "succeeded"}
    assert job["stages"]

    for _ in range(80):
        status_response = client.get(f"/api/agent/jobs/{job['jobId']}")
        assert status_response.status_code == 200, status_response.text
        job = status_response.json()
        if job["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.05)

    assert job["status"] == "succeeded", job
    assert job["progress"] == 100
    assert job["resultId"]
    assert job["result"]["id"] == job["resultId"]
    assert job["result"]["notes"]


def test_legacy_doc_upload_is_accepted(tmp_path: Path):
    object.__setattr__(settings, "output_dir", (tmp_path / "runtime").resolve())
    upload = UploadFile(filename="legacy.doc", file=BytesIO(b"legacy-word"))

    saved = asyncio.run(save_upload_file(upload, sourceTitle="旧版 Word"))

    assert saved.suffix == ".doc"
    assert saved.read_bytes() == b"legacy-word"


def test_result_id_rejects_path_traversal():
    with pytest.raises(BadRequestError, match="Invalid resultId"):
        AgentService().get_result("../outside")


def test_explicit_lanxin_enables_strict_provider(tmp_path: Path, monkeypatch):
    source = tmp_path / "sample.md"
    source.write_text("# RAG\n\nRAG 使用检索结果约束生成。", encoding="utf-8")
    object.__setattr__(settings, "allowed_input_root", tmp_path.resolve())
    object.__setattr__(settings, "output_dir", (tmp_path / "runtime").resolve())
    service = AgentService()
    observed = {}

    def fake_generate(chunks, *, input_path=None, provider_name=None, strict=False):
        observed.update(provider=provider_name, strict=strict)
        return service.rag.build_deterministic_result(chunks, source), {
            "provider": "lanxin",
            "model": "test",
            "fallbackUsed": False,
        }

    monkeypatch.setattr(service.agent, "generate", fake_generate)
    service.run(RunAgentRequest(filePath=str(source), pipeline="hybrid", provider="lanxin"))

    assert observed == {"provider": "lanxin", "strict": True}


def test_mock_provider_is_rejected():
    with pytest.raises(ValidationError, match="provider must be 'lanxin'"):
        RunAgentRequest(sourceText="# RAG", pipeline="hybrid", provider="mock")


def test_retriever_cache_reuses_same_corpus_hash(tmp_path: Path):
    chunks = [
        {
            "id": "c1",
            "sourceId": "doc",
            "title": "RAG",
            "text": "RAG uses retrieval evidence.",
            "sourceType": "text",
            "fileName": "same.md",
            "chunkIndex": 1,
            "sourceRef": "para_1",
        }
    ]
    first = tmp_path / "chunks-a.json"
    second = tmp_path / "chunks-b.json"
    first.write_text(json.dumps(chunks), encoding="utf-8")
    second.write_text(json.dumps(chunks), encoding="utf-8")
    service = AgentService()

    one = service._retriever_for(first)
    two = service._retriever_for(second)

    assert one is two
    assert len(service._retriever_cache) == 1
