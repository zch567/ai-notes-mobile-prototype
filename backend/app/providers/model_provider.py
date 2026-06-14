from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class ProviderChunk:
    id: str
    sourceId: str
    title: str
    text: str
    sourceType: str
    fileName: str
    page: int | None = None
    slide: int | None = None
    paragraph: int | None = None
    chunkIndex: int = 0


@dataclass
class ModelLog:
    requestId: str
    provider: str
    model: str
    taskType: str
    inputChars: int
    outputChars: int
    latencyMs: int
    status: str
    fallbackUsed: bool
    error: str | None = None


class ModelProvider:
    name = "base"
    model = "none"

    def generate_json(self, chunks: list[ProviderChunk]) -> tuple[dict[str, Any], ModelLog]:
        raise NotImplementedError

    def generate_module_json(
        self,
        module: str,
        prompt: str,
        payload: dict[str, Any],
        *,
        max_tokens: int = 4096,
    ) -> tuple[dict[str, Any], ModelLog]:
        raise NotImplementedError


class OpenAICompatibleProvider(ModelProvider):
    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int | None = None,
        retries: int = 0,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.retries = max(0, retries)

    def generate_json(self, chunks: list[ProviderChunk]) -> tuple[dict[str, Any], ModelLog]:
        request_id = str(uuid.uuid4())
        selected = select_context(chunks)
        system_prompt, user_prompt = build_prompt(selected)
        start = time.time()
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 4096,
        }
        url = f"{self.base_url}/chat/completions"
        if self.name == "lanxin":
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}requestId={request_id}"

        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                payload = post_json(url, body, self.api_key, timeout_seconds=self.timeout_seconds)
                content = payload["choices"][0]["message"]["content"]
                result = parse_model_json(content)
                result = normalize_result(result, selected)
                return result, ModelLog(
                    requestId=request_id,
                    provider=self.name,
                    model=self.model,
                    taskType="note_generation",
                    inputChars=len(user_prompt),
                    outputChars=len(content),
                    latencyMs=int((time.time() - start) * 1000),
                    status="success",
                    fallbackUsed=False,
                )
            except Exception as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(min(4, 1 + attempt))

        raise RuntimeError(f"{self.name} provider failed: {last_error or 'unknown provider error'}")

    def generate_module_json(
        self,
        module: str,
        prompt: str,
        payload: dict[str, Any],
        *,
        max_tokens: int = 4096,
    ) -> tuple[dict[str, Any], ModelLog]:
        request_id = str(uuid.uuid4())
        system_prompt = (
            "You are a learning-material backend Agent module. Return strict JSON only. "
            "Do not use Markdown fences and do not add facts not supported by the input."
        )
        user_prompt = prompt.strip() + "\n\nInput JSON:\n" + compact_json(payload)
        start = time.time()
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        url = f"{self.base_url}/chat/completions"
        if self.name == "lanxin":
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}requestId={request_id}"

        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = post_json(url, body, self.api_key, timeout_seconds=self.timeout_seconds)
                content = response["choices"][0]["message"]["content"]
                result = parse_model_json(content)
                return result, ModelLog(
                    requestId=request_id,
                    provider=self.name,
                    model=self.model,
                    taskType=module.upper(),
                    inputChars=len(user_prompt),
                    outputChars=len(content),
                    latencyMs=int((time.time() - start) * 1000),
                    status="success",
                    fallbackUsed=False,
                )
            except Exception as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(min(4, 1 + attempt))

        raise RuntimeError(f"{self.name} provider failed during {module}: {last_error or 'unknown provider error'}")


def select_context(chunks: list[ProviderChunk], limit: int = 8) -> list[ProviderChunk]:
    return chunks[:limit]


def build_prompt(chunks: list[ProviderChunk]) -> tuple[str, str]:
    system_prompt = (
        "你是移动端 AI 学习助手的后端 Agent。请只根据给定资料生成结构化学习 JSON。"
        "不要编造引用，所有 citationIds 必须来自输入 chunk id。"
    )
    context = "\n\n".join(
        f"[{chunk.id}] {chunk.title}\n{chunk.text[:1200]}" for chunk in chunks
    )
    user_prompt = f"""
请根据资料生成 JSON，字段必须适配前端：
- id, topic, summary
- agentStages: id, label, text
- sources: id, title, text
- notes: id, title, content, citationIds
- citations: id, sourceId, noteId
- mindMap: nodes(id,label,desc,detail,x,y,line,fill), edges(from,to)
- review: questions(id,type,question,options,answer,explanation,citationIds), masteryScore, weakPoints, recommendations

资料：
{context}

只返回 JSON，不要使用 Markdown 代码块。
""".strip()
    return system_prompt, user_prompt


def post_json(url: str, body: dict[str, Any], api_key: str, timeout_seconds: int | None = None) -> dict[str, Any]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds or int(os.getenv("MODEL_TIMEOUT_MS", "60"))) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        message = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code}: {message[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc


def parse_model_json(text: str) -> dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def compact_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def normalize_result(result: dict[str, Any], chunks: list[ProviderChunk]) -> dict[str, Any]:
    valid_ids = {chunk.id for chunk in chunks}
    result.setdefault("sources", [asdict(chunk) for chunk in chunks])
    result.setdefault("notes", [])
    result.setdefault("citations", [])
    result.setdefault("review", {})
    result.setdefault("mindMap", {"nodes": [], "edges": []})
    result.setdefault("agentStages", [])
    result.setdefault("topic", infer_topic(chunks))
    result.setdefault("summary", "")
    result.setdefault("id", f"agent-{uuid.uuid4().hex[:8]}")

    for note in result.get("notes", []):
        ids = [item for item in note.get("citationIds", []) if item in valid_ids]
        note["citationIds"] = ids

    result["citations"] = [
        citation for citation in result.get("citations", [])
        if citation.get("sourceId") in valid_ids or citation.get("id") in valid_ids
    ]
    return result


def infer_topic(chunks: list[ProviderChunk]) -> str:
    file_stems = {Path(chunk.fileName).stem for chunk in chunks}
    keywords = extract_keywords(" ".join(chunk.text for chunk in chunks), limit=3)
    if file_stems:
        primary = sorted(file_stems)[0]
        extras = [keyword for keyword in keywords if keyword not in primary][:2]
        return " / ".join([primary, *extras])
    if keywords:
        return " / ".join(keywords)
    return "学习资料"


def extract_keywords(text: str, limit: int = 5) -> list[str]:
    candidates = re.findall(r"[A-Za-z][A-Za-z0-9\- ]{2,40}|[\u4e00-\u9fff]{2,12}", text)
    stop_words = {
        "the", "and", "for", "with", "this", "that", "from", "are", "you",
        "的", "了", "和", "是", "在", "对", "与", "及", "或", "一个", "一种",
        "例如", "可以", "通过", "主要", "包括", "进行", "使用", "需要", "具有",
    }
    scores: dict[str, int] = {}
    for item in candidates:
        key = item.strip()
        lowered = key.lower()
        if lowered in stop_words or len(key) < 2 or not is_allowed_keyword(key):
            continue
        if re.fullmatch(r"\d+", key):
            continue
        scores[key] = scores.get(key, 0) + 1
    ranked = sorted(scores.items(), key=lambda pair: (-pair[1], len(pair[0])))
    return [item for item, _score in ranked[:limit]]


def is_allowed_keyword(value: str) -> bool:
    for char in value:
        if char.isascii() and (char.isalnum() or char in {" ", "-"}):
            continue
        if "\u4e00" <= char <= "\u9fff":
            continue
        return False
    return True
