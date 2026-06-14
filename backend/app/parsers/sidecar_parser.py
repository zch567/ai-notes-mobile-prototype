from __future__ import annotations

import re
import zipfile
from html import unescape
from pathlib import Path
from xml.etree import ElementTree

from ..rag.grounding import rekey_legacy_chunks
from ..rag.schemas import SourceChunk
from ..rag.text_utils import normalize_text, slugify


def read_text_file(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def parse_with_sidecars(
    input_path: Path,
    *,
    ocr_text_dir: Path | None = None,
    office_ocr_dir: Path | None = None,
) -> list[SourceChunk]:
    legacy = parse_document(input_path, ocr_text_dir=ocr_text_dir, office_ocr_dir=office_ocr_dir)
    return rekey_legacy_chunks([chunk.__dict__ for chunk in legacy])


class LegacyChunk:
    def __init__(
        self,
        *,
        id: str,
        sourceId: str,
        title: str,
        text: str,
        sourceType: str,
        fileName: str,
        page: int | None = None,
        slide: int | None = None,
        paragraph: int | None = None,
        chunkIndex: int = 0,
    ) -> None:
        self.id = id
        self.sourceId = sourceId
        self.title = title
        self.text = text
        self.sourceType = sourceType
        self.fileName = fileName
        self.page = page
        self.slide = slide
        self.paragraph = paragraph
        self.chunkIndex = chunkIndex


def parse_document(path: Path, ocr_text_dir: Path | None = None, office_ocr_dir: Path | None = None) -> list[LegacyChunk]:
    suffix = path.suffix.lower()
    source_id = slugify(path.stem)

    if suffix in {".txt", ".md", ".markdown"}:
        text = normalize_text(read_text_file(path))
        return chunk_text(text, source_id=source_id, source_type="text", file_name=path.name)

    if suffix == ".docx":
        text = normalize_text(parse_docx(path))
        if office_ocr_dir:
            sidecar = office_ocr_dir / path.stem / "document.ocr.txt"
            if sidecar.exists():
                image_text = normalize_text(read_text_file(sidecar))
                if image_text:
                    text = normalize_text(text + "\n\n[IMAGE_OCR]\n" + image_text)
        return chunk_text(text, source_id=source_id, source_type="text", file_name=path.name)

    if suffix == ".pptx":
        chunks: list[LegacyChunk] = []
        for slide, text in parse_pptx(path, office_ocr_dir=office_ocr_dir):
            chunks.extend(
                chunk_text(
                    text,
                    source_id=source_id,
                    source_type="pptx",
                    file_name=path.name,
                    slide=slide,
                    max_chars=700,
                )
            )
        return chunks

    if suffix == ".pdf":
        if ocr_text_dir:
            ocr_chunks = parse_ocr_text_dir(ocr_text_dir, path.stem, path.name)
            if ocr_chunks:
                return ocr_chunks
        raise ValueError("PDF sidecar mode requires ocr_text_dir with OCR text files.")

    raise ValueError(f"Unsupported file type: {path.suffix}")


def parse_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as package:
        root = ElementTree.fromstring(package.read("word/document.xml"))
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = root.find(f"{{{w}}}body")
    blocks: list[str] = []
    for child in list(body) if body is not None else []:
        if child.tag == f"{{{w}}}p":
            line = "".join(node.text or "" for node in child.findall(f".//{{{w}}}t")).strip()
            if line:
                blocks.append(unescape(line))
        elif child.tag == f"{{{w}}}tbl":
            rows: list[str] = []
            for row in child.findall(f".//{{{w}}}tr"):
                cells: list[str] = []
                for cell in row.findall(f"{{{w}}}tc"):
                    value = " ".join(node.text or "" for node in cell.findall(f".//{{{w}}}t")).strip()
                    cells.append(value)
                if any(cells):
                    rows.append(" | ".join(cells))
            if rows:
                blocks.append("[TABLE]\n" + "\n".join(rows))
    return "\n\n".join(blocks)


def parse_pptx(path: Path, office_ocr_dir: Path | None = None) -> list[tuple[int, str]]:
    with zipfile.ZipFile(path) as package:
        slide_names = sorted(
            (name for name in package.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
            key=lambda name: int(re.search(r"slide(\d+)\.xml", name).group(1)),
        )
        slides: list[tuple[int, str]] = []
        namespaces = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
        for slide_number, slide_name in enumerate(slide_names, start=1):
            root = ElementTree.fromstring(package.read(slide_name))
            lines: list[str] = []
            for paragraph in root.findall(".//a:p", namespaces):
                texts = [node.text or "" for node in paragraph.findall(".//a:t", namespaces)]
                line = "".join(texts).strip()
                if line:
                    lines.append(unescape(line))
            text = normalize_text("\n\n".join(lines))
            if office_ocr_dir:
                sidecar = office_ocr_dir / path.stem / f"slide-{slide_number}.ocr.txt"
                if sidecar.exists():
                    image_text = normalize_text(read_text_file(sidecar))
                    if image_text:
                        text = normalize_text(text + "\n\n[IMAGE_OCR]\n" + image_text)
            if text:
                slides.append((slide_number, text))
    return slides


def parse_ocr_text_dir(path: Path, file_stem: str, file_name: str) -> list[LegacyChunk]:
    page_dir = path / file_stem
    if not page_dir.exists():
        return []
    chunks: list[LegacyChunk] = []
    for text_path in sorted(page_dir.glob("page-*.ocr.txt")):
        match = re.search(r"page-(\d+)", text_path.stem)
        page = int(match.group(1)) if match else None
        text = normalize_text(read_text_file(text_path))
        if not text:
            continue
        chunks.extend(
            chunk_text(
                text,
                source_id=f"{slugify(file_stem)}-ocr",
                source_type="ocr_pdf",
                file_name=file_name,
                page=page,
                max_chars=850,
            )
        )
    return chunks


def chunk_text(
    text: str,
    *,
    source_id: str,
    source_type: str,
    file_name: str,
    page: int | None = None,
    slide: int | None = None,
    max_chars: int = 900,
) -> list[LegacyChunk]:
    chunks: list[LegacyChunk] = []
    buffer: list[str] = []
    buffer_len = 0
    start_para = 1
    chunk_index = 1

    for para_index, paragraph in enumerate(split_paragraphs(text), start=1):
        if buffer and buffer_len + len(paragraph) > max_chars:
            chunk_text_value = "\n".join(buffer)
            chunks.append(
                LegacyChunk(
                    id=build_chunk_id(source_id, page, slide, chunk_index),
                    sourceId=source_id,
                    title=build_source_title(file_name, page, slide, chunk_index),
                    text=chunk_text_value,
                    sourceType=source_type,
                    fileName=file_name,
                    page=page,
                    slide=slide,
                    paragraph=start_para,
                    chunkIndex=chunk_index,
                )
            )
            chunk_index += 1
            buffer = []
            buffer_len = 0
            start_para = para_index

        buffer.append(paragraph)
        buffer_len += len(paragraph)

    if buffer:
        chunks.append(
            LegacyChunk(
                id=build_chunk_id(source_id, page, slide, chunk_index),
                sourceId=source_id,
                title=build_source_title(file_name, page, slide, chunk_index),
                text="\n".join(buffer),
                sourceType=source_type,
                fileName=file_name,
                page=page,
                slide=slide,
                paragraph=start_para,
                chunkIndex=chunk_index,
            )
        )

    return chunks


def split_paragraphs(text: str) -> list[str]:
    raw = re.split(r"\n\s*\n|(?<=[。！？.!?])\s+(?=[A-Z0-9\u4e00-\u9fff])", text)
    return [item.strip() for item in raw if item.strip()]


def build_chunk_id(source_id: str, page: int | None, slide: int | None, chunk_index: int) -> str:
    if page is not None:
        return f"{source_id}-p{page}-c{chunk_index}"
    if slide is not None:
        return f"{source_id}-s{slide}-c{chunk_index}"
    return f"{source_id}-c{chunk_index}"


def build_source_title(file_name: str, page: int | None, slide: int | None, chunk_index: int) -> str:
    if page is not None:
        return f"{file_name} / p.{page} / chunk {chunk_index}"
    if slide is not None:
        return f"{file_name} / slide {slide} / chunk {chunk_index}"
    return f"{file_name} / chunk {chunk_index}"
