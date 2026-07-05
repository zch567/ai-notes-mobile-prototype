from __future__ import annotations

import copy
import logging
import posixpath
import re
import zipfile
from dataclasses import replace
from html import unescape
from pathlib import Path
from xml.etree import ElementTree

from ..doc_conversion import convert_legacy_doc
from ..ocr import LanxinOcrClient, OcrImage, ocr_text_from_regions
from .schemas import ParseDiagnosis, RawBlock
from .text_utils import is_empty_or_meaningless, looks_like_garbled, looks_like_heading, normalize_text


SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown", ".doc", ".docx", ".pdf", ".pptx"}
_PARSE_CACHE: dict[tuple[str, float, int], list[RawBlock]] = {}
_PARSE_CACHE_LIMIT = 16
logging.getLogger("pypdf").setLevel(logging.ERROR)


def detect_ocr_need(path: Path) -> dict[str, object]:
    """Lightweight preflight for deciding whether OCR can add missing content.

    Text-native documents should not pay the OCR cost. PDF/PPTX files with
    embedded images, diagrams, charts, connectors, or very sparse extracted text
    often need OCR because the important information is visual or positional.
    """
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _detect_pdf_ocr_need(path)
    if suffix == ".pptx":
        return _detect_pptx_ocr_need(path)
    return {"enabled": False, "reason": "text-native-document", "signals": []}


def _detect_pdf_ocr_need(path: Path) -> dict[str, object]:
    signals: list[str] = []
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        pages = list(reader.pages)
        image_pages = 0
        sparse_image_pages = 0
        for page in pages:
            images = list(getattr(page, "images", []) or [])
            text = normalize_text(page.extract_text() or "")
            if images:
                image_pages += 1
                if len(text) < 180:
                    sparse_image_pages += 1
        if image_pages:
            signals.append(f"pdf-image-pages:{image_pages}")
        if sparse_image_pages:
            signals.append(f"pdf-sparse-image-pages:{sparse_image_pages}")
        enabled = bool(image_pages)
        return {
            "enabled": enabled,
            "reason": "pdf-has-images-or-visual-layout" if enabled else "pdf-text-extraction-sufficient",
            "signals": signals,
        }
    except Exception as exc:
        return {"enabled": False, "reason": f"pdf-ocr-preflight-failed:{type(exc).__name__}", "signals": signals}


def _detect_pptx_ocr_need(path: Path) -> dict[str, object]:
    signals: list[str] = []
    try:
        with zipfile.ZipFile(path) as package:
            slide_names = sorted(
                (name for name in package.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
                key=lambda name: int(re.search(r"slide(\d+)\.xml", name).group(1)),
            )
            namespaces = {
                "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
                "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
                "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
            }
            image_slides = 0
            connector_slides = 0
            chart_or_diagram_slides = 0
            short_label_diagram_slides = 0
            for name in slide_names:
                root = ElementTree.fromstring(package.read(name))
                pictures = root.findall(".//p:pic", namespaces)
                connectors = root.findall(".//p:cxnSp", namespaces)
                charts = root.findall(".//c:chart", namespaces)
                graphic_data = root.findall(".//a:graphicData", namespaces)
                labels = [
                    normalize_text("".join(node.text or "" for node in paragraph.findall(".//a:t", namespaces)))
                    for paragraph in root.findall(".//a:p", namespaces)
                ]
                short_labels = [label for label in labels if 1 <= len(re.sub(r"\s+", "", label)) <= 12]
                if pictures:
                    image_slides += 1
                if connectors:
                    connector_slides += 1
                if charts or any("diagram" in str(item.attrib.get("uri", "")).lower() for item in graphic_data):
                    chart_or_diagram_slides += 1
                if len(short_labels) >= 4 and (pictures or connectors or chart_or_diagram_slides):
                    short_label_diagram_slides += 1
            if image_slides:
                signals.append(f"pptx-image-slides:{image_slides}")
            if connector_slides:
                signals.append(f"pptx-connector-slides:{connector_slides}")
            if chart_or_diagram_slides:
                signals.append(f"pptx-chart-or-diagram-slides:{chart_or_diagram_slides}")
            if short_label_diagram_slides:
                signals.append(f"pptx-short-label-diagrams:{short_label_diagram_slides}")
            enabled = bool(image_slides or connector_slides or chart_or_diagram_slides or short_label_diagram_slides)
            return {
                "enabled": enabled,
                "reason": "pptx-has-images-or-layout-diagrams" if enabled else "pptx-text-shapes-sufficient",
                "signals": signals,
            }
    except Exception as exc:
        return {"enabled": False, "reason": f"pptx-ocr-preflight-failed:{type(exc).__name__}", "signals": signals}


def read_text_file(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def parse_document(path: Path, *, ocr_client: LanxinOcrClient | None = None) -> list[RawBlock]:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported file type: {path.suffix}")
    resolved = path.resolve()
    stat = resolved.stat()
    cache_key = (str(resolved), stat.st_mtime, stat.st_size)
    cached = _PARSE_CACHE.get(cache_key) if ocr_client is None else None
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
        blocks = _parse_pdf(path, ocr_client=ocr_client)
    else:
        blocks = _parse_pptx(path, ocr_client=ocr_client)
    if ocr_client is None:
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


def _parse_pdf(path: Path, *, ocr_client: LanxinOcrClient | None = None) -> list[RawBlock]:
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
        if ocr_client is not None:
            blocks.extend(_ocr_pdf_page_images(page, path=path, page_number=page_number, ocr_client=ocr_client))
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


def _parse_pptx(path: Path, *, ocr_client: LanxinOcrClient | None = None) -> list[RawBlock]:
    with zipfile.ZipFile(path) as package:
        names = sorted(
            (name for name in package.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
            key=lambda name: int(re.search(r"slide(\d+)\.xml", name).group(1)),
        )
        namespaces = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
        slide_size = _pptx_slide_size(package)
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
            if ocr_client is not None:
                blocks.extend(
                    _ocr_pptx_slide_images(
                        package,
                        root,
                        slide_name=name,
                        slide_number=slide_number,
                        path=path,
                        slide_size=slide_size,
                        ocr_client=ocr_client,
                    )
                )
    return blocks


def _ocr_pdf_page_images(page: object, *, path: Path, page_number: int, ocr_client: LanxinOcrClient) -> list[RawBlock]:
    blocks: list[RawBlock] = []
    for image_index, image_file in enumerate(getattr(page, "images", []) or [], start=1):
        data = getattr(image_file, "data", b"")
        name = getattr(image_file, "name", f"image-{image_index}")
        if not data:
            ocr_client.stats.skipped += 1
            continue
        regions = _recognize_with_stats(
            ocr_client,
            OcrImage(data=data, name=str(name), container=path.name, page=page_number),
        )
        text = ocr_text_from_regions(regions)
        if not text:
            continue
        blocks.append(
            RawBlock(
                text=f"[IMAGE_OCR]\n{text}",
                source_type="pdf",
                file_name=path.name,
                block_index=10_000 + len(blocks) + 1,
                page=page_number,
                paragraph=1_000 + image_index,
                heading="",
                source_ref=f"page_{page_number}",
                ocrRegions=regions,
            )
        )
    return blocks


def _ocr_pptx_slide_images(
    package: zipfile.ZipFile,
    root: ElementTree.Element,
    *,
    slide_name: str,
    slide_number: int,
    path: Path,
    slide_size: tuple[int, int],
    ocr_client: LanxinOcrClient,
) -> list[RawBlock]:
    rels = _pptx_slide_relationships(package, slide_name)
    images = _pptx_slide_image_refs(root, slide_size=slide_size)
    blocks: list[RawBlock] = []
    for image_index, image in enumerate(images, start=1):
        target = rels.get(image["rid"])
        if not target:
            ocr_client.stats.skipped += 1
            continue
        image_path = _resolve_pptx_target(slide_name, target)
        if image_path not in package.namelist():
            ocr_client.stats.skipped += 1
            continue
        regions = _recognize_with_stats(
            ocr_client,
            OcrImage(
                data=package.read(image_path),
                name=image_path,
                container=path.name,
                slide=slide_number,
                image_box=image.get("imageBox") or {},
            ),
        )
        text = ocr_text_from_regions(regions)
        if not text:
            continue
        blocks.append(
            RawBlock(
                text=f"[IMAGE_OCR]\n{text}",
                source_type="pptx",
                file_name=path.name,
                block_index=10_000 + len(blocks) + 1,
                slide=slide_number,
                paragraph=1_000 + image_index,
                heading="",
                source_ref=f"slide_{slide_number}",
                ocrRegions=regions,
            )
        )
    return blocks


def _recognize_with_stats(ocr_client: LanxinOcrClient, image: OcrImage) -> list[dict]:
    ocr_client.stats.attempted += 1
    try:
        regions = ocr_client.recognize_image(image)
    except Exception:
        ocr_client.stats.failed += 1
        return []
    if regions:
        ocr_client.stats.succeeded += 1
    else:
        ocr_client.stats.skipped += 1
    return regions


def _pptx_slide_relationships(package: zipfile.ZipFile, slide_name: str) -> dict[str, str]:
    rel_name = str(Path(slide_name).parent / "_rels" / f"{Path(slide_name).name}.rels").replace("\\", "/")
    if rel_name not in package.namelist():
        return {}
    root = ElementTree.fromstring(package.read(rel_name))
    rels: dict[str, str] = {}
    for rel in root:
        rid = rel.attrib.get("Id")
        target = rel.attrib.get("Target")
        if rid and target:
            rels[rid] = target
    return rels


def _pptx_slide_image_refs(root: ElementTree.Element, *, slide_size: tuple[int, int]) -> list[dict]:
    namespaces = {
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    refs: list[dict] = []
    width, height = slide_size
    for pic in root.findall(".//p:pic", namespaces):
        blip = pic.find(".//a:blip", namespaces)
        rid = blip.get(f"{{{namespaces['r']}}}embed") if blip is not None else ""
        if not rid:
            continue
        off = pic.find(".//a:xfrm/a:off", namespaces)
        ext = pic.find(".//a:xfrm/a:ext", namespaces)
        image_box: dict[str, float] = {}
        if off is not None and ext is not None and width and height:
            x = float(off.attrib.get("x", 0))
            y = float(off.attrib.get("y", 0))
            cx = float(ext.attrib.get("cx", 0))
            cy = float(ext.attrib.get("cy", 0))
            image_box = {
                "x": round(x / width, 6),
                "y": round(y / height, 6),
                "width": round(cx / width, 6),
                "height": round(cy / height, 6),
            }
        refs.append({"rid": rid, "imageBox": image_box})
    return refs


def _pptx_slide_size(package: zipfile.ZipFile) -> tuple[int, int]:
    name = "ppt/presentation.xml"
    if name not in package.namelist():
        return (0, 0)
    root = ElementTree.fromstring(package.read(name))
    p = "http://schemas.openxmlformats.org/presentationml/2006/main"
    node = root.find(f".//{{{p}}}sldSz")
    if node is None:
        return (0, 0)
    return (int(node.attrib.get("cx", 0)), int(node.attrib.get("cy", 0)))


def _resolve_pptx_target(slide_name: str, target: str) -> str:
    base = posixpath.dirname(slide_name)
    return posixpath.normpath(posixpath.join(base, target))


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
