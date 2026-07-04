from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapters import RagPipelineAdapter, SidecarCapabilityAdapter
from .agents import ModuleAgentOrchestrator
from .config import settings
from .contracts import RunAgentRequest
from .errors import BadRequestError, NotFoundError, ProviderError, ValidationError
from .normalization import normalize_agent_result, raw_contract_report
from .rag.fingerprint import corpus_hash
from .rag.io_utils import load_chunks
from .rag.llm_polish import polish_result_with_provider
from .rag.quality_diagnostics import attach_quality_diagnostics


class AgentService:
    def __init__(self) -> None:
        self.rag = RagPipelineAdapter()
        self.legacy = SidecarCapabilityAdapter()
        self.agent = ModuleAgentOrchestrator()
        self._retriever_cache: dict[str, Any] = {}

    def run(self, request: RunAgentRequest) -> dict[str, Any]:
        input_path = self._resolve_input(request)
        pipeline = request.pipeline or settings.default_pipeline
        ocr_text_dir = self._optional_safe_path(request.ocrTextDir)
        office_ocr_dir = self._optional_safe_path(request.officeOcrDir)

        if ocr_text_dir or office_ocr_dir:
            chunks = self.legacy.parse_with_sidecars(
                input_path,
                ocr_text_dir=ocr_text_dir,
                office_ocr_dir=office_ocr_dir,
            )
            parser_name = "week2-sidecar-parser"
        else:
            chunks = self.rag.parse(input_path)
            parser_name = "structure-aware-parser"
        if not chunks:
            raise BadRequestError(f"No text extracted from {input_path}")

        model_log: dict[str, Any] | None = None
        agent_meta: dict[str, Any] = {}
        if pipeline == "hybrid":
            draft, agent_meta = self.agent.generate(
                chunks,
                input_path=input_path,
                provider_name=request.provider,
                strict=request.strictProvider or request.provider == "lanxin",
            )
            result = self.rag.ground(draft, chunks, request.topK)
            model_log = agent_meta.get("modelLog")
        elif pipeline == "rag-only":
            result = self.rag.build_deterministic_result(chunks, input_path)
            if request.provider == "lanxin":
                try:
                    result, polish_meta = polish_result_with_provider(
                        result,
                        chunks,
                        provider_name=request.provider,
                    )
                    agent_meta["llmPolish"] = polish_meta
                    model_log = polish_meta.get("modelLog")
                except Exception as exc:
                    if request.strictProvider:
                        raise ProviderError(f"Lanxin note polish failed: {exc}") from exc
                    result.setdefault("warnings", []).append(f"Lanxin note polish fallback used: {exc}")
                result = self.rag.ground(result, chunks, request.topK)
        else:
            raise BadRequestError("pipeline must be 'hybrid' or 'rag-only'")

        result.setdefault("_meta", {}).update(
            {
                "pipeline": pipeline,
                "parser": parser_name,
                "contract": "AgentResult",
                "contractVersion": "1.0",
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "requestedProvider": request.provider or "configured",
            }
        )
        result["_meta"].update({key: value for key, value in agent_meta.items() if value is not None})
        if model_log:
            result["_meta"]["modelLog"] = model_log

        attach_quality_diagnostics(result)
        normalized = normalize_agent_result(result)
        result_id = normalized["id"] or f"agent-{uuid.uuid4().hex[:8]}"
        normalized["id"] = result_id
        self._persist(result_id, normalized, chunks)
        return normalized

    def validate(self, result: dict[str, Any]) -> dict[str, Any]:
        try:
            return raw_contract_report(result)
        except Exception as exc:
            raise ValidationError(str(exc)) from exc

    def query(self, *, query: str, chunks_path: str | None, result_id: str | None, top_k: int) -> dict[str, Any]:
        if chunks_path:
            path = self._safe_input_path(chunks_path)
        elif result_id:
            path = self._safe_result_dir(result_id) / "chunks.json"
        else:
            raise BadRequestError("chunksPath or resultId is required")
        if not path.exists():
            raise NotFoundError(f"Chunks not found: {path}")
        hits = self._retriever_for(path).retrieve(query, top_k=top_k)
        return {"hits": [hit.to_dict() for hit in hits]}

    def chat(
        self,
        *,
        question: str,
        result_id: str,
        provider_name: str | None,
        strict: bool,
        top_k: int,
    ) -> dict[str, Any]:
        result_dir = self._safe_result_dir(result_id)
        result_path = result_dir / "result.json"
        chunks_path = result_dir / "chunks.json"
        if not result_path.exists():
            raise NotFoundError(result_id)
        if not chunks_path.exists():
            raise NotFoundError(f"chunks for result {result_id}")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        chunks = load_chunks(chunks_path)
        return self.agent.chat(
            question=question,
            result=result,
            chunks=chunks,
            provider_name=provider_name,
            strict=strict or provider_name == "lanxin",
            top_k=top_k,
        )

    def get_result(self, result_id: str) -> dict[str, Any]:
        path = self._safe_result_dir(result_id) / "result.json"
        if not path.exists():
            raise NotFoundError(result_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def _persist(self, result_id: str, result: dict[str, Any], chunks: list[Any]) -> None:
        self._cleanup_runtime_outputs()
        run_dir = settings.output_dir / result_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "chunks.json").write_text(
            json.dumps([chunk.to_dict() for chunk in chunks], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _resolve_input(self, request: RunAgentRequest) -> Path:
        if request.filePath:
            return self._safe_input_path(request.filePath)
        input_dir = settings.output_dir / "_inputs"
        input_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(request.fileName).suffix.lower()
        if suffix not in {".txt", ".md", ".markdown"}:
            suffix = ".md"
        path = input_dir / f"input-{uuid.uuid4().hex[:12]}{suffix}"
        path.write_text(request.sourceText or "", encoding="utf-8")
        return path

    def _safe_input_path(self, value: str) -> Path:
        path = Path(value).expanduser().resolve()
        if path != settings.allowed_input_root and settings.allowed_input_root not in path.parents:
            raise BadRequestError(f"Path is outside BACKEND_ALLOWED_INPUT_ROOT: {path}")
        if not path.exists():
            raise NotFoundError(str(path))
        return path

    def _optional_safe_path(self, value: str | None) -> Path | None:
        return self._safe_input_path(value) if value else None

    def _safe_result_dir(self, result_id: str) -> Path:
        if not result_id or result_id in {".", ".."} or "/" in result_id or "\\" in result_id:
            raise BadRequestError("Invalid resultId")
        path = (settings.output_dir / result_id).resolve()
        output_root = settings.output_dir.resolve()
        if output_root not in path.parents:
            raise BadRequestError("Invalid resultId")
        return path

    def _retriever_for(self, chunks_path: Path):
        from .rag.retrieval import HybridRetriever

        resolved = chunks_path.resolve()
        chunks = load_chunks(resolved)
        key = corpus_hash(chunks)
        cached = self._retriever_cache.get(key)
        if cached:
            return cached
        retriever = HybridRetriever(chunks)
        self._retriever_cache[key] = retriever
        if len(self._retriever_cache) > 32:
            oldest = next(iter(self._retriever_cache))
            self._retriever_cache.pop(oldest, None)
        return retriever

    def _cleanup_runtime_outputs(self, *, keep: int = 80) -> None:
        output_root = settings.output_dir
        if not output_root.exists():
            return
        run_dirs = [
            item for item in output_root.iterdir()
            if item.is_dir() and item.name.startswith(("agent-", "rag-")) and (item / "result.json").exists()
        ]
        run_dirs.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        for stale in run_dirs[keep:]:
            shutil.rmtree(stale, ignore_errors=True)
