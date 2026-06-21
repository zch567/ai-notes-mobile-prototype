import asyncio
import json
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import settings
from app.contracts import RunAgentRequest
from app.errors import BadRequestError
from app.main import app, save_upload_file
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


def test_validate_endpoint_accepts_persisted_result(tmp_path: Path):
    source = tmp_path / "sample.md"
    source.write_text("# RAG\n\nRAG 使用检索结果约束生成。", encoding="utf-8")
    object.__setattr__(settings, "allowed_input_root", tmp_path.resolve())
    object.__setattr__(settings, "output_dir", (tmp_path / "runtime").resolve())
    result = client.post("/api/agent/run", json={"filePath": str(source), "pipeline": "rag-only"}).json()
    response = client.post("/api/agent/validate", json={"result": result})
    assert response.status_code == 200
    assert response.json()["valid"] is True


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
