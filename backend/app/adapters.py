from __future__ import annotations

from pathlib import Path
from typing import Any

from .parsers import parse_with_sidecars
from .provider_config import create_provider
from .providers import ProviderChunk
from .rag.chunking import build_chunks
from .rag.grounding import ground_result
from .rag.parsing import parse_document
from .rag.result_builder import build_agent_result
from .rag.schemas import SourceChunk


class RagPipelineAdapter:
    name = "rag-pipeline"

    def parse(self, input_path: Path) -> list[SourceChunk]:
        return build_chunks(parse_document(input_path))

    def build_deterministic_result(self, chunks: list[SourceChunk], input_path: Path) -> dict[str, Any]:
        return build_agent_result(chunks, input_path=input_path)

    def ground(self, result: dict[str, Any], chunks: list[SourceChunk], top_k: int) -> dict[str, Any]:
        return ground_result(result, chunks, top_k=top_k)


class SidecarCapabilityAdapter:
    name = "sidecar-capabilities"

    def parse_with_sidecars(
        self,
        input_path: Path,
        *,
        ocr_text_dir: Path | None = None,
        office_ocr_dir: Path | None = None,
    ) -> list[SourceChunk]:
        return parse_with_sidecars(
            input_path,
            ocr_text_dir=ocr_text_dir,
            office_ocr_dir=office_ocr_dir,
        )

    def generate_with_provider(
        self,
        chunks: list[SourceChunk],
        *,
        provider_name: str | None = None,
        strict: bool = False,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        provider = create_provider(provider_name)
        legacy_chunks = [
            ProviderChunk(
                id=chunk.id,
                sourceId=chunk.sourceId,
                title=chunk.title,
                text=chunk.text,
                sourceType=chunk.sourceType,
                fileName=chunk.fileName,
                page=chunk.page,
                slide=chunk.slide,
                paragraph=chunk.paragraphStart,
                chunkIndex=chunk.chunkIndex,
            )
            for chunk in chunks
        ]
        result, log = provider.generate_json(legacy_chunks)
        log_data = log.__dict__.copy()
        return result, log_data


# Backward-compatible aliases for older tests or local scripts.
Week3RagAdapter = RagPipelineAdapter
Week2CapabilityAdapter = SidecarCapabilityAdapter
