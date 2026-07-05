from __future__ import annotations

import copy
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from .contracts import RunAgentRequest
from .errors import NotFoundError
from .service import AgentService


AGENT_JOB_STAGES = [
    {
        "id": "prepare",
        "label": "准备材料",
        "text": "正在整理输入内容和上传文件信息，准备交给后端处理。",
        "progress": 5,
    },
    {
        "id": "parse",
        "label": "解析资料",
        "text": "后端正在抽取文本、拆分片段，并保留可追溯的来源位置。",
        "progress": 20,
    },
    {
        "id": "generate",
        "label": "生成笔记",
        "text": "Agent 正在围绕主题、摘要和核心知识点生成结构化笔记。",
        "progress": 45,
    },
    {
        "id": "ground",
        "label": "绑定引用",
        "text": "系统正在把笔记内容和来源片段对齐，生成可回看的证据链。",
        "progress": 70,
    },
    {
        "id": "compose",
        "label": "组织学习资产",
        "text": "正在组合笔记、导图和复习题，形成统一的学习结果。",
        "progress": 85,
    },
    {
        "id": "finalize",
        "label": "保存结果",
        "text": "正在保存完整 AgentResult，完成后可回到 AI 页查看结果。",
        "progress": 95,
    },
]


class AgentJobStore:
    def __init__(self, service: AgentService) -> None:
        self._service = service
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def start(self, request: RunAgentRequest) -> dict[str, Any]:
        job_id = f"job-{uuid.uuid4().hex[:10]}"
        now = _now()
        initial_stage = AGENT_JOB_STAGES[0]
        job = {
            "jobId": job_id,
            "status": "queued",
            "progress": 0,
            "stageId": initial_stage["id"],
            "label": initial_stage["label"],
            "text": initial_stage["text"],
            "stages": AGENT_JOB_STAGES,
            "resultId": "",
            "result": None,
            "error": "",
            "createdAt": now,
            "updatedAt": now,
        }
        with self._lock:
            self._jobs[job_id] = job

        thread = threading.Thread(target=self._run, args=(job_id, request), daemon=True)
        thread.start()
        return self.get(job_id)

    def get(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise NotFoundError(job_id)
            return copy.deepcopy(job)

    def update(self, job_id: str, **updates: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.update({key: value for key, value in updates.items() if value is not None})
            job["updatedAt"] = _now()

    def _run(self, job_id: str, request: RunAgentRequest) -> None:
        self.update(job_id, status="running", progress=2)
        try:
            result = self._service.run(
                request,
                progress=lambda update: self.update(job_id, **normalize_progress_update(update)),
            )
            self.update(
                job_id,
                status="succeeded",
                progress=100,
                stageId="done",
                label="生成完成",
                text="学习结果已生成完成。",
                resultId=result.get("id", ""),
                result=result,
                error="",
            )
        except Exception as exc:  # noqa: BLE001 - job status must preserve user-facing failure details.
            self.update(
                job_id,
                status="failed",
                progress=100,
                stageId="failed",
                label="生成失败",
                text="生成过程中出现错误。",
                error=str(exc),
            )


def normalize_progress_update(update: dict[str, Any]) -> dict[str, Any]:
    stage_id = str(update.get("stageId") or update.get("stage_id") or "")
    stage = next((item for item in AGENT_JOB_STAGES if item["id"] == stage_id), {})
    return {
        "status": update.get("status") or "running",
        "progress": _clamp_progress(update.get("progress", stage.get("progress", 0))),
        "stageId": stage_id or stage.get("id", ""),
        "label": update.get("label") or stage.get("label", ""),
        "text": update.get("text") or stage.get("text", ""),
        "stages": AGENT_JOB_STAGES,
    }


def _clamp_progress(value: Any) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return 0
    return max(0, min(number, 100))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
