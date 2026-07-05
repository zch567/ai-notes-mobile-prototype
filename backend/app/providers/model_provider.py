from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


logger = logging.getLogger("model_provider.audit")
logger.setLevel(logging.INFO)
AUDIT_PREVIEW_CHARS = 1200
AUDIT_CONTEXT_CHARS = 420


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
                log_model_request(
                    provider=self.name,
                    model=self.model,
                    task_type="note_generation",
                    request_id=request_id,
                    attempt=attempt + 1,
                    max_attempts=self.retries + 1,
                    input_chars=len(user_prompt),
                    max_tokens=4096,
                )
                payload = post_json(url, body, self.api_key, timeout_seconds=self.timeout_seconds)
                content = extract_chat_content(
                    payload,
                    provider=self.name,
                    model=self.model,
                    task_type="note_generation",
                    request_id=request_id,
                    attempt=attempt + 1,
                )
                result = parse_model_json(
                    content,
                    provider=self.name,
                    model=self.model,
                    task_type="note_generation",
                    request_id=request_id,
                    attempt=attempt + 1,
                )
                result = normalize_result(result, selected)
                log_model_success(
                    provider=self.name,
                    model=self.model,
                    task_type="note_generation",
                    request_id=request_id,
                    attempt=attempt + 1,
                    input_chars=len(user_prompt),
                    output_chars=len(content),
                    latency_ms=int((time.time() - start) * 1000),
                )
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
            "Return one non-empty JSON object as the entire response. "
            "Do not use Markdown fences, comments, explanations, or trailing text. "
            "Escape every newline inside string values as \\n. "
            "Do not add facts not supported by the input."
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
            "response_format": {"type": "json_object"},
        }
        url = f"{self.base_url}/chat/completions"
        if self.name == "lanxin":
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}requestId={request_id}"

        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                log_model_request(
                    provider=self.name,
                    model=self.model,
                    task_type=module.upper(),
                    request_id=request_id,
                    attempt=attempt + 1,
                    max_attempts=self.retries + 1,
                    input_chars=len(user_prompt),
                    max_tokens=max_tokens,
                )
                response = post_json(url, body, self.api_key, timeout_seconds=self.timeout_seconds)
                content = extract_chat_content(
                    response,
                    provider=self.name,
                    model=self.model,
                    task_type=module.upper(),
                    request_id=request_id,
                    attempt=attempt + 1,
                )
                result = parse_model_json(
                    content,
                    provider=self.name,
                    model=self.model,
                    task_type=module.upper(),
                    request_id=request_id,
                    attempt=attempt + 1,
                )
                log_model_success(
                    provider=self.name,
                    model=self.model,
                    task_type=module.upper(),
                    request_id=request_id,
                    attempt=attempt + 1,
                    input_chars=len(user_prompt),
                    output_chars=len(content),
                    latency_ms=int((time.time() - start) * 1000),
                )
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


def extract_chat_content(
    payload: dict[str, Any],
    *,
    provider: str,
    model: str,
    task_type: str,
    request_id: str,
    attempt: int,
) -> str:
    choices = payload.get("choices") if isinstance(payload, dict) else None
    choice = choices[0] if isinstance(choices, list) and choices else {}
    message = choice.get("message") if isinstance(choice, dict) else {}
    content = message.get("content") if isinstance(message, dict) else ""
    if content is None:
        content = ""
    if not isinstance(content, str):
        content = str(content)
    if content.strip():
        return content

    log_empty_model_content(
        provider=provider,
        model=model,
        task_type=task_type,
        request_id=request_id,
        attempt=attempt,
        payload=payload,
        choice=choice if isinstance(choice, dict) else {},
        message=message if isinstance(message, dict) else {},
    )
    raise RuntimeError("model returned empty message content")


def parse_model_json(
    text: str,
    *,
    provider: str = "",
    model: str = "",
    task_type: str = "",
    request_id: str = "",
    attempt: int = 1,
) -> dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    candidate = _extract_json_object(text)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as original_error:
        repaired = _escape_control_chars_in_json_strings(candidate)
        try:
            result = json.loads(repaired)
            log_model_json_repair(
                provider=provider,
                model=model,
                task_type=task_type,
                request_id=request_id,
                attempt=attempt,
                error=original_error,
                raw_text=text,
                candidate=candidate,
            )
            return result
        except json.JSONDecodeError as repaired_error:
            log_model_json_failure(
                provider=provider,
                model=model,
                task_type=task_type,
                request_id=request_id,
                attempt=attempt,
                original_error=original_error,
                repaired_error=repaired_error,
                raw_text=text,
                candidate=candidate,
                repaired=repaired,
            )
            raise original_error


def _extract_json_object(text: str) -> str:
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        return match.group(0) if match else text


def _escape_control_chars_in_json_strings(text: str) -> str:
    result: list[str] = []
    in_string = False
    escaped = False

    for char in text:
        if in_string:
            if escaped:
                result.append(char)
                escaped = False
                continue
            if char == "\\":
                result.append(char)
                escaped = True
                continue
            if char == '"':
                result.append(char)
                in_string = False
                continue
            if char == "\n":
                result.append("\\n")
                continue
            if char == "\r":
                result.append("\\r")
                continue
            if char == "\t":
                result.append("\\t")
                continue
        elif char == '"':
            in_string = True
        result.append(char)

    return "".join(result)


def log_model_request(
    *,
    provider: str,
    model: str,
    task_type: str,
    request_id: str,
    attempt: int,
    max_attempts: int,
    input_chars: int,
    max_tokens: int,
) -> None:
    logger.info(
        "model_request provider=%s model=%s task=%s requestId=%s attempt=%s/%s inputChars=%s maxTokens=%s",
        provider,
        model,
        task_type,
        request_id,
        attempt,
        max_attempts,
        input_chars,
        max_tokens,
    )


def log_model_success(
    *,
    provider: str,
    model: str,
    task_type: str,
    request_id: str,
    attempt: int,
    input_chars: int,
    output_chars: int,
    latency_ms: int,
) -> None:
    logger.info(
        "model_success provider=%s model=%s task=%s requestId=%s attempt=%s inputChars=%s outputChars=%s latencyMs=%s",
        provider,
        model,
        task_type,
        request_id,
        attempt,
        input_chars,
        output_chars,
        latency_ms,
    )


def log_model_json_repair(
    *,
    provider: str,
    model: str,
    task_type: str,
    request_id: str,
    attempt: int,
    error: json.JSONDecodeError,
    raw_text: str,
    candidate: str,
) -> None:
    logger.warning(
        "model_json_repaired provider=%s model=%s task=%s requestId=%s attempt=%s error=%s line=%s column=%s char=%s rawChars=%s candidateChars=%s preview=%s",
        provider,
        model,
        task_type,
        request_id,
        attempt,
        error.msg,
        error.lineno,
        error.colno,
        error.pos,
        len(raw_text),
        len(candidate),
        _safe_log_text(raw_text[:AUDIT_PREVIEW_CHARS]),
    )


def log_model_json_failure(
    *,
    provider: str,
    model: str,
    task_type: str,
    request_id: str,
    attempt: int,
    original_error: json.JSONDecodeError,
    repaired_error: json.JSONDecodeError,
    raw_text: str,
    candidate: str,
    repaired: str,
) -> None:
    logger.error(
        "model_json_parse_failed provider=%s model=%s task=%s requestId=%s attempt=%s originalError=%s originalLine=%s originalColumn=%s originalChar=%s repairedError=%s repairedLine=%s repairedColumn=%s repairedChar=%s rawChars=%s candidateChars=%s rawPreview=%s errorContext=%s repairedContext=%s",
        provider,
        model,
        task_type,
        request_id,
        attempt,
        original_error.msg,
        original_error.lineno,
        original_error.colno,
        original_error.pos,
        repaired_error.msg,
        repaired_error.lineno,
        repaired_error.colno,
        repaired_error.pos,
        len(raw_text),
        len(candidate),
        _safe_log_text(raw_text[:AUDIT_PREVIEW_CHARS]),
        _json_error_context(candidate, original_error.pos),
        _json_error_context(repaired, repaired_error.pos),
    )


def log_empty_model_content(
    *,
    provider: str,
    model: str,
    task_type: str,
    request_id: str,
    attempt: int,
    payload: dict[str, Any],
    choice: dict[str, Any],
    message: dict[str, Any],
) -> None:
    logger.error(
        "model_empty_content provider=%s model=%s task=%s requestId=%s attempt=%s finishReason=%s payloadKeys=%s choiceKeys=%s messageKeys=%s usage=%s messagePreview=%s",
        provider,
        model,
        task_type,
        request_id,
        attempt,
        choice.get("finish_reason"),
        sorted(payload.keys()),
        sorted(choice.keys()),
        sorted(message.keys()),
        _safe_log_text(json.dumps(payload.get("usage", {}), ensure_ascii=False)),
        _safe_log_text(json.dumps(_message_preview(message), ensure_ascii=False)[:AUDIT_PREVIEW_CHARS]),
    )


def _message_preview(message: dict[str, Any]) -> dict[str, str]:
    preview: dict[str, str] = {}
    for key, value in message.items():
        if key == "content":
            preview[key] = f"<empty length={len(str(value or ''))}>"
            continue
        if isinstance(value, (dict, list)):
            preview[key] = json.dumps(value, ensure_ascii=False)[:AUDIT_CONTEXT_CHARS]
        else:
            preview[key] = str(value)[:AUDIT_CONTEXT_CHARS]
    return preview


def _json_error_context(text: str, pos: int) -> str:
    start = max(0, pos - AUDIT_CONTEXT_CHARS)
    end = min(len(text), pos + AUDIT_CONTEXT_CHARS)
    return _safe_log_text(text[start:end])


def _safe_log_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")


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
