from __future__ import annotations

import hashlib
import re
from collections import Counter


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "is", "it", "of", "on", "or", "that", "the", "this", "to", "was", "with",
    "一个", "一些", "以及", "使用", "其中", "可以", "因此", "如果", "对于", "就是",
    "并且", "我们", "所有", "主要", "介绍", "内容", "进行", "这个", "通过", "需要",
}


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", value).strip("-")
    return cleaned or "source"


def stable_digest(text: str, length: int = 8) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length]


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    english = re.findall(r"[a-z][a-z0-9_-]{1,40}", lowered)
    chinese_runs = re.findall(r"[\u4e00-\u9fff]{2,}", lowered)
    chinese: list[str] = []
    for run in chinese_runs:
        if 2 <= len(run) <= 8:
            chinese.append(run)
        chinese.extend(run[i : i + 2] for i in range(len(run) - 1))
    numbers = re.findall(r"\b\d+(?:\.\d+)*\b", lowered)
    return [token for token in [*english, *chinese, *numbers] if token not in STOP_WORDS]


def extract_keywords(text: str, limit: int = 8) -> list[str]:
    counts = Counter(tokenize(text))
    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], -len(pair[0]), pair[0]))
    return [token for token, _ in ranked[:limit]]


def split_sentences(text: str) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    parts = re.split(r"(?<=[。！？!?；;])\s*|\n+", normalized)
    return [part.strip() for part in parts if part.strip()]


def compact(text: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", text).strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


def looks_like_heading(text: str) -> bool:
    value = re.sub(r"\s+", " ", text).strip()
    if not value or len(value) > 80:
        return False
    if re.fullmatch(r"[\d.．\-/ ]+", value):
        return False
    if value.startswith(("•", "●", "▪", "▌", "❖")) and len(value) > 36:
        return False
    patterns = [
        r"^第[一二三四五六七八九十\d]+[章节部分]",
        r"^[一二三四五六七八九十]+[、.．]",
        r"^\d+(?:\.\d+){1,3}\s*\D",
        r"^\d+(?:\.\d+){0,3}[、.．]?\s+\S+",
        r"^[A-Z][A-Z0-9 \-]{3,}$",
    ]
    return any(re.match(pattern, value) for pattern in patterns)
