#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.contracts import RunAgentRequest
from app.evaluation import compare_results, write_comparison_report
from app.service import AgentService


DEFAULT_INPUT = (
    BACKEND_ROOT.parent
    / "ai-notes-mobile-prototype"
    / "ai-notes-mobile-prototype"
    / "test_set"
    / "text"
    / "Transformer介绍.docx"
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Lanxin RAG with deterministic offline RAG.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out", type=Path, default=BACKEND_ROOT / "evaluation_outputs" / "lanxin_vs_offline")
    parser.add_argument("--top-k", type=int, default=2)
    args = parser.parse_args()

    service = AgentService()
    offline, offline_ms = _run(
        service,
        RunAgentRequest(filePath=str(args.input), pipeline="rag-only", topK=args.top_k),
    )
    lanxin, lanxin_ms = _run(
        service,
        RunAgentRequest(
            filePath=str(args.input),
            pipeline="hybrid",
            provider="lanxin",
            strictProvider=True,
            topK=args.top_k,
        ),
    )
    comparison = compare_results(
        offline,
        lanxin,
        offline_latency_ms=offline_ms,
        lanxin_latency_ms=lanxin_ms,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "offline.result.json").write_text(json.dumps(offline, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out / "lanxin.result.json").write_text(json.dumps(lanxin, ensure_ascii=False, indent=2), encoding="utf-8")
    json_path, report_path = write_comparison_report(comparison, args.out)
    print(json.dumps({"comparison": str(json_path), "report": str(report_path), **comparison}, ensure_ascii=False, indent=2))


def _run(service: AgentService, request: RunAgentRequest) -> tuple[dict, int]:
    start = time.perf_counter()
    result = service.run(request)
    return result, round((time.perf_counter() - start) * 1000)


if __name__ == "__main__":
    main()
