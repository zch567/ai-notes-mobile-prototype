from pathlib import Path

from app.rag import parsing
from app.rag.chunking import build_chunks
from app.rag.schemas import RawBlock
from app.rag.text_utils import extract_heading_level, is_empty_or_meaningless, looks_like_garbled, looks_like_heading


def test_text_utils_heading_and_noise_detection():
    assert looks_like_heading("一、Transformer 概述")
    assert extract_heading_level("一、Transformer 概述") == 2
    assert is_empty_or_meaningless("目录")
    assert looks_like_garbled("abc\u0000def")


def test_diagnose_parsing_reports_quality_issues():
    blocks = [
        RawBlock(text="一、概述", source_type="pdf", file_name="sample.pdf", block_index=1, page=1, heading="一、概述", source_ref="page_1"),
        RawBlock(text="", source_type="pdf", file_name="sample.pdf", block_index=2, page=1, source_ref="page_1"),
        RawBlock(text="乱码\ufffd内容", source_type="pdf", file_name="sample.pdf", block_index=3, page=1, source_ref="page_1"),
    ]
    diagnosis = parsing.diagnose_parsing(blocks, file_name="sample.pdf", source_type="pdf", total_pages=10, chunk_count=2)

    assert diagnosis.raw_block_count == 3
    assert diagnosis.chunk_count == 2
    assert diagnosis.heading_count == 1
    assert diagnosis.garbled_ratio > 0
    assert diagnosis.issues


def test_get_document_stats_counts_docx_paragraphs(tmp_path: Path):
    docx = tmp_path / "sample.docx"
    docx.write_bytes(b"not-a-real-docx")
    stats = parsing.get_document_stats(docx)
    assert "total_pages" in stats and "total_slides" in stats


def test_chunking_prefers_heading_boundaries_and_preserves_metadata():
    blocks = [
        RawBlock(text="一、导言", source_type="docx", file_name="sample.docx", block_index=1, paragraph=1, heading="一、导言", source_ref="para_1"),
        RawBlock(text="第一段内容。", source_type="docx", file_name="sample.docx", block_index=2, paragraph=2, heading="一、导言", source_ref="para_2"),
        RawBlock(text="二、方法", source_type="docx", file_name="sample.docx", block_index=3, paragraph=3, heading="二、方法", source_ref="para_3"),
        RawBlock(text="第二段内容。", source_type="docx", file_name="sample.docx", block_index=4, paragraph=4, heading="二、方法", source_ref="para_4"),
    ]
    chunks = build_chunks(blocks, target_chars=12, max_chars=20)

    assert len(chunks) >= 2
    assert chunks[0].heading == "一、导言"
    assert chunks[0].sourceRef.startswith("para_")
    assert chunks[0].charEnd >= len(chunks[0].text)
    assert chunks[0].parentId


def test_parse_document_uses_cache_for_repeated_calls(tmp_path: Path):
    source = tmp_path / "sample.txt"
    source.write_text("一、标题\n\n正文", encoding="utf-8")
    parsing._PARSE_CACHE.clear()
    first = parsing.parse_document(source)
    second = parsing.parse_document(source)
    assert first[0].text == second[0].text
    assert len(parsing._PARSE_CACHE) == 1
