from __future__ import annotations

import io
import zipfile
from pathlib import Path

from PIL import Image

from app.ocr import OcrCallStats, OcrImage, normalize_lanxin_ocr_regions
from app.rag.chunking import build_chunks
from app.rag.parsing import parse_document


class FakeOcrClient:
    def __init__(self) -> None:
        self.stats = OcrCallStats()

    def recognize_image(self, image: OcrImage) -> list[dict]:
        payload = {
            "error_code": 0,
            "result": {
                "angle": 0,
                "OCR": [
                    {
                        "words": "图中关键知识点",
                        "location": {
                            "top_left": {"x": 0.1, "y": 0.2},
                            "top_right": {"x": 0.6, "y": 0.2},
                            "down_left": {"x": 0.1, "y": 0.3},
                            "down_right": {"x": 0.6, "y": 0.3},
                        },
                    }
                ],
            },
        }
        return normalize_lanxin_ocr_regions(payload, image=image, request_id="test-request")


def test_pptx_lanxin_ocr_regions_are_preserved_in_chunks(tmp_path: Path):
    pptx = tmp_path / "ocr-demo.pptx"
    _write_minimal_pptx_with_image(pptx)

    blocks = parse_document(pptx, ocr_client=FakeOcrClient())
    chunks = build_chunks(blocks)

    ocr_chunks = [chunk for chunk in chunks if chunk.ocrRegions]
    assert ocr_chunks
    assert "[IMAGE_OCR]" in ocr_chunks[0].text
    assert "图中关键知识点" in ocr_chunks[0].text
    assert ocr_chunks[0].slide == 1
    assert ocr_chunks[0].ocrRegions[0]["location"]["top_left"]["x"] == 0.1
    assert ocr_chunks[0].ocrRegions[0]["imageBox"]["width"] > 0


def _write_minimal_pptx_with_image(path: Path) -> None:
    image_bytes = io.BytesIO()
    Image.new("RGB", (64, 32), color=(255, 255, 255)).save(image_bytes, format="PNG")
    with zipfile.ZipFile(path, "w") as package:
        package.writestr(
            "ppt/presentation.xml",
            """
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldSz cx="9144000" cy="5143500"/>
</p:presentation>
""".strip(),
        )
        package.writestr(
            "ppt/slides/slide1.xml",
            """
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:cSld><p:spTree>
    <p:sp><p:txBody><a:p><a:r><a:t>第一页标题</a:t></a:r></a:p></p:txBody></p:sp>
    <p:pic>
      <p:blipFill><a:blip r:embed="rId2"/></p:blipFill>
      <p:spPr><a:xfrm><a:off x="914400" y="514350"/><a:ext cx="1828800" cy="1028700"/></a:xfrm></p:spPr>
    </p:pic>
  </p:spTree></p:cSld>
</p:sld>
""".strip(),
        )
        package.writestr(
            "ppt/slides/_rels/slide1.xml.rels",
            """
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/>
</Relationships>
""".strip(),
        )
        package.writestr("ppt/media/image1.png", image_bytes.getvalue())
