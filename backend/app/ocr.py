from __future__ import annotations

import base64
import io
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from PIL import Image, UnidentifiedImageError

from .provider_config import ProviderConfig


@dataclass(frozen=True)
class OcrImage:
    data: bytes
    name: str
    container: str
    page: int | None = None
    slide: int | None = None
    image_box: dict[str, float] | None = None


@dataclass
class OcrCallStats:
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "attempted": self.attempted,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "skipped": self.skipped,
        }


class LanxinOcrClient:
    def __init__(self, *, config: ProviderConfig | None = None) -> None:
        self.config = config or ProviderConfig.load()
        self.stats = OcrCallStats()
        if not self.config.lanxin_ocr_app_key:
            raise RuntimeError("Lanxin OCR is not configured. Set LANXIN_OCR_APP_KEY or LANXIN_API_KEY.")
        if not self.config.lanxin_ocr_business_id:
            raise RuntimeError("Lanxin OCR business id is not configured. Set LANXIN_OCR_APP_ID or LANXIN_OCR_BUSINESS_ID.")

    def recognize_image(self, image: OcrImage) -> list[dict[str, Any]]:
        png_data = _to_supported_image_bytes(image.data)
        if not png_data:
            return []
        request_id = str(uuid.uuid4())
        last_error: Exception | None = None
        for attempt in range(max(0, self.config.lanxin_ocr_retries) + 1):
            try:
                response = requests.post(
                    self.config.lanxin_ocr_url,
                    params={"requestId": request_id},
                    headers={
                        "Authorization": f"Bearer {self.config.lanxin_ocr_app_key}",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data={
                        "image": base64.b64encode(png_data).decode("utf-8"),
                        "pos": self.config.lanxin_ocr_pos,
                        "businessid": self.config.lanxin_ocr_business_id,
                        "sessid": request_id,
                    },
                    timeout=self.config.lanxin_ocr_timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                if int(payload.get("error_code", 0)) != 0:
                    raise RuntimeError(f"Lanxin OCR failed: {payload.get('error_msg') or payload}")
                return normalize_lanxin_ocr_regions(payload, image=image, request_id=request_id)
            except Exception as exc:
                last_error = exc
                if attempt < self.config.lanxin_ocr_retries:
                    time.sleep(min(3, 1 + attempt))
        raise RuntimeError(f"Lanxin OCR failed: {last_error or 'unknown error'}")


def create_lanxin_ocr_client() -> LanxinOcrClient:
    return LanxinOcrClient()


def normalize_lanxin_ocr_regions(
    payload: dict[str, Any],
    *,
    image: OcrImage,
    request_id: str,
) -> list[dict[str, Any]]:
    result = payload.get("result") or {}
    angle = result.get("angle")
    rows = result.get("OCR")
    if rows is None:
        rows = result.get("words") or []
    regions: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        text = str(row.get("words") or "").strip()
        if not text:
            continue
        location = row.get("location") or {}
        regions.append(
            {
                "id": f"{_safe_stem(image.container)}-{image.page or image.slide or 0}-{index}",
                "text": text,
                "location": location,
                "angle": angle,
                "imageName": image.name,
                "imageBox": image.image_box or {},
                "page": image.page,
                "slide": image.slide,
                "provider": "lanxin-ocr",
                "requestId": request_id,
            }
        )
    return regions


def ocr_text_from_regions(regions: list[dict[str, Any]]) -> str:
    return "\n".join(str(region.get("text") or "").strip() for region in regions if str(region.get("text") or "").strip())


def _to_supported_image_bytes(data: bytes) -> bytes | None:
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format in {"JPEG", "PNG", "BMP"}:
                output = io.BytesIO()
                image.save(output, format="PNG")
                return output.getvalue()
            converted = image.convert("RGB")
            output = io.BytesIO()
            converted.save(output, format="PNG")
            return output.getvalue()
    except (UnidentifiedImageError, OSError):
        return None


def _safe_stem(value: str) -> str:
    return Path(value).stem.replace(" ", "-")[:40] or "ocr"
