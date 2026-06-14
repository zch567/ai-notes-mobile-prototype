import os
import time
from pathlib import Path

import pytest

from app.bootstrap import WORKSPACE_ROOT
from app.config import settings
from app.contracts import RunAgentRequest
from app.evaluation import compare_results
from app.service import AgentService


INPUT = (
    WORKSPACE_ROOT
    / "ai-notes-mobile-prototype"
    / "ai-notes-mobile-prototype"
    / "test_set"
    / "text"
    / "Transformer介绍.docx"
)


@pytest.mark.skipif(
    os.getenv("RUN_LANXIN_INTEGRATION") != "1",
    reason="Set RUN_LANXIN_INTEGRATION=1 to consume a real Lanxin API call.",
)
def test_real_lanxin_rag_compares_with_offline(tmp_path: Path):
    object.__setattr__(settings, "allowed_input_root", WORKSPACE_ROOT.resolve())
    object.__setattr__(settings, "output_dir", (tmp_path / "runtime").resolve())
    service = AgentService()

    start = time.perf_counter()
    offline = service.run(RunAgentRequest(filePath=str(INPUT), pipeline="rag-only"))
    offline_ms = round((time.perf_counter() - start) * 1000)

    start = time.perf_counter()
    lanxin = service.run(
        RunAgentRequest(
            filePath=str(INPUT),
            pipeline="hybrid",
            provider="lanxin",
            strictProvider=True,
        )
    )
    lanxin_ms = round((time.perf_counter() - start) * 1000)
    comparison = compare_results(
        offline,
        lanxin,
        offline_latency_ms=offline_ms,
        lanxin_latency_ms=lanxin_ms,
    )

    assert comparison["offline"]["contractValid"] is True
    assert comparison["lanxin"]["contractValid"] is True
    assert comparison["lanxin"]["provider"] == "lanxin"
    assert comparison["lanxin"]["fallbackUsed"] is False
    assert comparison["lanxin"]["quoteInSourceRate"] == 1
