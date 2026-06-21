from pathlib import Path

import pytest

from app import doc_conversion
from app.rag import parsing
from app.rag.schemas import RawBlock


def test_doc_parser_converts_then_preserves_original_source_metadata(tmp_path: Path, monkeypatch):
    source = tmp_path / "legacy.doc"
    source.write_bytes(b"legacy-word")
    converted = tmp_path / "legacy.docx"
    converted.write_bytes(b"converted")

    monkeypatch.setattr(parsing, "convert_legacy_doc", lambda path: converted)
    monkeypatch.setattr(
        parsing,
        "_parse_docx",
        lambda path: [
            RawBlock(
                text="转换后的正文",
                source_type="docx",
                file_name=path.name,
                block_index=1,
                paragraph=1,
                source_ref="para_1",
            )
        ],
    )

    blocks = parsing.parse_document(source)

    assert blocks[0].text == "转换后的正文"
    assert blocks[0].source_type == "doc"
    assert blocks[0].file_name == "legacy.doc"


def test_doc_conversion_reports_non_windows_requirement(tmp_path: Path, monkeypatch):
    source = tmp_path / "legacy.doc"
    source.write_bytes(b"legacy-word")
    monkeypatch.setattr(doc_conversion.platform, "system", lambda: "Linux")

    with pytest.raises(ValueError, match="save the file as DOCX"):
        doc_conversion.convert_legacy_doc(source)
