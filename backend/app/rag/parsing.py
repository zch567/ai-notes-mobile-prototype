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
from .schemas import RawBlock
from .text_utils import looks_like_heading, normalize_text


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
        blocks = [
            replace(block, source_type="doc", file_name=path.name)
            for block in _parse_docx(converted)
        ]
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
