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


def normalize_learning_text(text: str) -> str:
    """Clean layout artifacts before user-facing learning content is generated."""
    value = normalize_text(text)
    if not value:
        return ""
    lines: list[str] = []
    for raw in value.splitlines():
        line = _strip_learning_noise(raw.strip())
        if not line or _is_learning_noise_line(line):
            continue
        if lines and _should_merge_hard_break(lines[-1], line):
            lines[-1] = f"{lines[-1]}{line}"
        else:
            lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = _repair_inline_learning_artifacts(cleaned)
    return cleaned.strip()


def _strip_learning_noise(text: str) -> str:
    value = re.sub(r"https?://\S+", "", text, flags=re.I)
    value = re.sub(r"\b(?:www\.)?1ppt\.com\S*", "", value, flags=re.I)
    value = re.sub(r"(?:\u7b2c\u4e00)?PPT\u6a21\u677f\u7f51|PPT\u6a21\u677f|\u884c\u4e1aPPT\u6a21\u677f", "", value, flags=re.I)
    value = re.sub(r"\b(?:PAGE|Page|page)[ _-]?\d+\b", "", value)
    return re.sub(r"\s+", " ", value).strip(" -_|\t")


def _repair_inline_learning_artifacts(text: str) -> str:
    value = text
    # Repair CJK words split by OCR/PDF line extraction and then joined with a punctuation mark.
    for left, right in [
        ("主", "存"),
        ("控", "制"),
        ("方", "式"),
        ("服", "务"),
        ("可", "能"),
        ("尽", "管"),
        ("中", "断"),
        ("总", "线"),
        ("周", "期"),
        ("传", "送"),
    ]:
        value = re.sub(fr"{left}\s*[\n、]\s*{right}", left + right, value)
    value = re.sub(r"([一-龥A-Za-z0-9）)])、(服务|方式|控制权|主存|可能|周期|传送)", r"\1\2", value)
    value = re.sub(r"(和|与|或)、(服务|方式|控制权|主存|可能|周期|传送)", r"\1\2", value)
    value = re.sub(r"([，、；;])\s*(等内容|等等内容)", r"\1", value)
    value = re.sub(r"因为等等内容", "因为", value)
    return value


def _is_learning_noise_line(text: str) -> bool:
    value = text.strip()
    if not value:
        return True
    if re.fullmatch(r"\d{1,3}", value):
        return True
    if re.fullmatch(r"[\u2460-\u2469\s]+", value):
        return True
    if re.fullmatch(r"(?:BR|br)(?:[\uff08(]page_\d+[\uff09)])?", value):
        return True
    return False


def _should_merge_hard_break(previous: str, current: str) -> bool:
    prev = previous.rstrip()
    cur = current.lstrip()
    if not prev or not cur:
        return False
    if re.search(r"[\u3002\uff01\uff1f\uff1b;\uff1a:,.\uff0c\u3001\uff09)]$", prev):
        return False
    if looks_like_heading(cur):
        return False
    if re.match(r"^(?:\d+(?:\.\d+)*[.\u3001\s]|[\u2460-\u2469])", cur):
        return False
    prev_cjk = bool(re.search(r"[\u4e00-\u9fff]$", prev))
    cur_cjk = bool(re.match(r"^[\u4e00-\u9fff]", cur))
    if not (prev_cjk and cur_cjk):
        return False
    continuation_tail = "\u4e3b\u603b\u63a7\u5236\u65b9\u670d\u53ef\u5c3d\u4e2d\u5468\u4f20\u60c5\u6216\u5e76\u53ca\u5bf9\u4ee5\u4e3a\u4e0e\u5c06\u88ab\u628a\u7c7b\u6761\u5148\u540e\u6982"
    if prev[-1] in continuation_tail:
        return True
    return False

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
    parts = re.split(r"(?<=[。！？；;!?])\s*|\n+", normalized)
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
    if re.fullmatch(r"[\d.、/\- ]+", value):
        return False
    if value.startswith(("•", "◦", "▶", "►", "◆")) and len(value) > 36:
        return False
    patterns = [
        r"^第[一二三四五六七八九十百零〇\d]+[章节部分]",
        r"^[一二三四五六七八九十]+\s*[、.．]\s*\S+",
        r"^\d+(?:\.\d+){1,3}\s*\D",
        r"^\d+(?:\.\d+){0,3}[、.．]?\s+\S+",
        r"^[A-Z][A-Z0-9 \-]{3,}$",
    ]
    return any(re.match(pattern, value) for pattern in patterns)


def looks_like_garbled(text: str) -> bool:
    if not text:
        return False
    value = text.strip()
    if len(value) < 5:
        return False
    total_chars = len(value)
    normal_chars = len(re.findall(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffefA-Za-z0-9，。！？；：、,.!?:;()\-\s]", value))
    garbled_chars = len(re.findall(r"[\ufffd\u0000-\u001f\u0080-\u009f\u25a0-\u25ff\u2000-\u206f]", value))
    normal_ratio = normal_chars / total_chars
    garbled_ratio = garbled_chars / total_chars
    return normal_ratio < 0.6 or garbled_ratio > 0.1


def is_empty_or_meaningless(text: str) -> bool:
    if not text:
        return True
    value = text.strip()
    if not value:
        return True
    if re.fullmatch(r"\d+", value):
        return True
    if re.fullmatch(r"[\s，。！？；：、,.!?:;\-•►◦◆]+", value):
        return True
    meaningless = {"目录", "封面", "扉页", "版权页", "前言", "后记", "page", "Page", "PAGE"}
    return value in meaningless


def extract_heading_level(text: str) -> int:
    value = re.sub(r"\s+", " ", text).strip()
    if not looks_like_heading(value):
        return 0
    if re.match(r"^第[一二三四五六七八九十百零〇\d]+[章节]", value):
        return 1
    if re.match(r"^[一二三四五六七八九十]+\s*[、.．]\s*", value):
        return 2
    match = re.match(r"^(\d+(?:\.\d+){0,3})", value)
    if match:
        return min(match.group(1).count(".") + 1, 6)
    if re.match(r"^\d+[、.．]\s*\S+", value):
        return 2
    if re.match(r"^[A-Z][A-Z0-9 \-]{3,}$", value):
        return 2
    return 3
