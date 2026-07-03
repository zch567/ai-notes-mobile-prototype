from __future__ import annotations

import copy
import logging
import re
import zipfile
from dataclasses import replace
from html import unescape
from pathlib import Path
from xml.etree import ElementTree

from ..doc_conversion import convert_legacy_doc
from .schemas import ParseDiagnosis, RawBlock
from .text_utils import is_empty_or_meaningless, looks_like_garbled, looks_like_heading, normalize_text


SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown", ".doc", ".docx", ".pdf", ".pptx"}
_PARSE_CACHE: dict[tuple[str, float, int], list[RawBlock]] = {}
_PARSE_CACHE_LIMIT = 16
logging.getLogger("pypdf").setLevel(logging.ERROR)


def read_text_file(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def parse_document(path: Path) -> list[RawBlock]:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported file type: {path.suffix}")
    resolved = path.resolve()
    stat = resolved.stat()
    cache_key = (str(resolved), stat.st_mtime, stat.st_size)
    cached = _PARSE_CACHE.get(cache_key)
    if cached is not None:
        return copy.deepcopy(cached)

    if suffix in {".txt", ".md", ".markdown"}:
        blocks = _parse_plain_text(path)
    elif suffix == ".doc":
        converted = convert_legacy_doc(path)
        blocks = [replace(block, source_type="doc", file_name=path.name) for block in _parse_docx(converted)]
    elif suffix == ".docx":
        blocks = _parse_docx(path)
    elif suffix == ".pdf":
        blocks = _parse_pdf(path)
    else:
        blocks = _parse_pptx(path)
    _PARSE_CACHE[cache_key] = copy.deepcopy(blocks)
    if len(_PARSE_CACHE) > _PARSE_CACHE_LIMIT:
        _PARSE_CACHE.pop(next(iter(_PARSE_CACHE)))
    return blocks


def _parse_plain_text(path: Path) -> list[RawBlock]:
    paragraphs = re.split(r"\n\s*\n", normalize_text(read_text_file(path)))
    blocks: list[RawBlock] = []
    current_heading = ""
    for index, paragraph in enumerate(paragraphs, start=1):
        text = normalize_text(paragraph)
        if not text:
            continue
        if looks_like_heading(text):
            current_heading = text
        blocks.append(
            RawBlock(
                text=text,
                source_type="text",
                file_name=path.name,
                block_index=index,
                paragraph=index,
                heading=current_heading,
                source_ref=f"para_{index}",
            )
        )
    return blocks


def _parse_docx(path: Path) -> list[RawBlock]:
    with zipfile.ZipFile(path) as package:
        root = ElementTree.fromstring(package.read("word/document.xml"))
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = root.find(f"{{{w}}}body")
    blocks: list[RawBlock] = []
    current_heading = ""
    paragraph_index = 0
    for child in list(body) if body is not None else []:
        if child.tag == f"{{{w}}}p":
            text = normalize_text("".join(node.text or "" for node in child.findall(f".//{{{w}}}t")))
            if not text:
                continue
            paragraph_index += 1
            style_node = child.find(f".//{{{w}}}pStyle")
            style = style_node.get(f"{{{w}}}val", "") if style_node is not None else ""
            if style.lower().startswith("heading") or looks_like_heading(text):
                current_heading = text
            blocks.append(
                RawBlock(
                    text=unescape(text),
                    source_type="docx",
                    file_name=path.name,
                    block_index=len(blocks) + 1,
                    paragraph=paragraph_index,
                    heading=current_heading,
                    source_ref=f"para_{paragraph_index}",
                )
            )
        elif child.tag == f"{{{w}}}tbl":
            rows: list[str] = []
            for row in child.findall(f".//{{{w}}}tr"):
                cells = [
                    normalize_text(" ".join(node.text or "" for node in cell.findall(f".//{{{w}}}t")))
                    for cell in row.findall(f"{{{w}}}tc")
                ]
                if any(cells):
                    rows.append(" | ".join(cells))
            if rows:
                paragraph_index += 1
                blocks.append(
                    RawBlock(
                        text="[TABLE]\n" + "\n".join(rows),
                        source_type="docx",
                        file_name=path.name,
                        block_index=len(blocks) + 1,
                        paragraph=paragraph_index,
                        heading=current_heading,
                        source_ref=f"para_{paragraph_index}",
                    )
                )
    return blocks


def _parse_pdf(path: Path) -> list[RawBlock]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF parsing needs pypdf") from exc

    blocks: list[RawBlock] = []
    reader = PdfReader(str(path))
    for page_number, page in enumerate(reader.pages, start=1):
        text = normalize_text(page.extract_text() or "")
        if not text:
            continue
        paragraphs = re.split(r"\n\s*\n", text)
        if len(paragraphs) == 1:
            paragraphs = _group_pdf_lines(text.splitlines())
        current_heading = ""
        for paragraph_index, paragraph in enumerate(paragraphs, start=1):
            value = normalize_text(paragraph)
            if not value:
                continue
            heading = _pdf_heading(value)
            if heading:
                current_heading = heading
            blocks.append(
                RawBlock(
                    text=value,
                    source_type="pdf",
                    file_name=path.name,
                    block_index=len(blocks) + 1,
                    page=page_number,
                    paragraph=paragraph_index,
                    heading=current_heading,
                    source_ref=f"page_{page_number}",
                )
            )
    return blocks


def _pdf_heading(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:4]:
        if looks_like_heading(line):
            return line
    return ""


def _group_pdf_lines(lines: list[str]) -> list[str]:
    groups: list[str] = []
    buffer: list[str] = []
    for line in lines:
        value = normalize_text(line)
        if not value:
            continue
        if buffer and (looks_like_heading(value) or len(" ".join(buffer)) >= 500):
            groups.append("\n".join(buffer))
            buffer = []
        buffer.append(value)
    if buffer:
        groups.append("\n".join(buffer))
    return groups


def _parse_pptx(path: Path) -> list[RawBlock]:
    with zipfile.ZipFile(path) as package:
        names = sorted(
            (name for name in package.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
            key=lambda name: int(re.search(r"slide(\d+)\.xml", name).group(1)),
        )
        namespaces = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
        blocks: list[RawBlock] = []
        for slide_number, name in enumerate(names, start=1):
            root = ElementTree.fromstring(package.read(name))
            paragraphs: list[str] = []
            for paragraph in root.findall(".//a:p", namespaces):
                text = normalize_text("".join(node.text or "" for node in paragraph.findall(".//a:t", namespaces)))
                if text:
                    paragraphs.append(unescape(text))
            heading = paragraphs[0] if paragraphs else ""
            for paragraph_index, text in enumerate(paragraphs, start=1):
                blocks.append(
                    RawBlock(
                        text=text,
                        source_type="pptx",
                        file_name=path.name,
                        block_index=len(blocks) + 1,
                        slide=slide_number,
                        paragraph=paragraph_index,
                        heading=heading,
                        source_ref=f"slide_{slide_number}",
                    )
                )
    return blocks


def diagnose_parsing(
    blocks: list[RawBlock],
    *,
    file_name: str = "",
    source_type: str = "",
    total_pages: int = 0,
    total_slides: int = 0,
    chunk_count: int = 0,
) -> ParseDiagnosis:
    if not blocks:
        return ParseDiagnosis(
            file_name=file_name,
            source_type=source_type,
            total_pages=total_pages,
            total_slides=total_slides,
            issues=["解析结果为空，未提取到任何有效内容"],
        )

    block_count = len(blocks)
    heading_count = sum(1 for block in blocks if block.heading and looks_like_heading(block.text))
    total_chars = sum(len(block.text) for block in blocks)
    average_block_chars = total_chars / block_count if block_count > 0 else 0
    empty_blocks = sum(1 for block in blocks if is_empty_or_meaningless(block.text))
    empty_page_ratio = empty_blocks / block_count if block_count > 0 else 0
    garbled_blocks = sum(1 for block in blocks if looks_like_garbled(block.text))
    garbled_ratio = garbled_blocks / block_count if block_count > 0 else 0

    issues: list[str] = []
    if empty_page_ratio > 0.3:
        issues.append(f"空文本块比例较高 ({empty_page_ratio:.1%})，可能存在大量空白页或解析失败")
    if garbled_ratio > 0.05:
        issues.append(f"疑似乱码比例较高 ({garbled_ratio:.1%})，可能是扫描件或编码问题")
    if heading_count == 0:
        issues.append("未识别到任何标题，文档结构可能不清晰")
    if average_block_chars < 20:
        issues.append(f"平均每块字符数过小 ({average_block_chars:.0f})，可能解析过于碎片化")
    if average_block_chars > 2000:
        issues.append(f"平均每块字符数过大 ({average_block_chars:.0f})，可能解析粒度太粗")
    if source_type == "pdf":
        if total_pages > 0 and block_count < total_pages * 0.5:
            issues.append(f"PDF共{total_pages}页，但只提取到{block_count}个文本块，可能存在大量图片页或解析失败")
    elif source_type == "pptx":
        if total_slides > 0 and block_count < total_slides:
            issues.append(f"PPT共{total_slides}页，但只提取到{block_count}个文本块，可能存在大量纯图片幻灯片")

    return ParseDiagnosis(
        file_name=file_name or blocks[0].file_name,
        source_type=source_type or blocks[0].source_type,
        total_pages=total_pages,
        total_slides=total_slides,
        raw_block_count=block_count,
        chunk_count=chunk_count,
        heading_count=heading_count,
        empty_page_ratio=round(empty_page_ratio, 4),
        garbled_ratio=round(garbled_ratio, 4),
        average_block_chars=round(average_block_chars, 2),
        issues=issues,
    )


def get_document_stats(path: Path) -> dict[str, int]:
    suffix = path.suffix.lower()
    result = {"total_pages": 0, "total_slides": 0}
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            result["total_pages"] = len(reader.pages)
        except Exception:
            pass
    elif suffix == ".pptx":
        try:
            with zipfile.ZipFile(path) as package:
                slide_names = [name for name in package.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)]
                result["total_slides"] = len(slide_names)
        except Exception:
            pass
    elif suffix == ".docx":
        try:
            with zipfile.ZipFile(path) as package:
                root = ElementTree.fromstring(package.read("word/document.xml"))
                w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                paragraphs = root.findall(f".//{{{w}}}p")
                result["total_paragraphs"] = len(paragraphs)
        except Exception:
            pass
    return result
