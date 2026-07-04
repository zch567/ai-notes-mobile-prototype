from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.evaluation import evaluate_result
from app.rag.chunking import build_chunks
from app.rag.fingerprint import corpus_hash
from app.rag.parsing import parse_document
from app.rag.result_builder import build_agent_result

SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown", ".docx", ".pptx", ".pdf"}
THRESHOLDS = {
    "quoteInSourceRate": 0.99,
    "noteCitationCoverage": 0.95,
    "lowSupportNoteRateMax": 0.20,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic RAG grounding audit over a file or directory.")
    parser.add_argument("--input", default=str(BACKEND_ROOT.parent / "test_set"), help="File or directory to audit.")
    parser.add_argument("--out", default=str(BACKEND_ROOT.parents[1] / "evaluation_outputs" / "rag_grounding_audit"), help="Output directory.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when any blocking threshold fails.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum files to audit, 0 means all.")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    out_dir = _prepare_output_dir(Path(args.out).resolve())

    files = _collect_files(input_path)
    if args.limit > 0:
        files = files[: args.limit]

    cases = [_audit_file(path) for path in files]
    summary = _summary(cases)
    report = {"input": str(input_path), "thresholds": THRESHOLDS, "summary": summary, "cases": cases}

    json_path = out_dir / "rag_grounding_audit.json"
    md_path = out_dir / "rag_grounding_audit.md"
    html_path = out_dir / "rag_grounding_audit.html"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8-sig")
    html_path.write_text(_html(report), encoding="utf-8-sig")

    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "html": str(html_path), "summary": summary}, ensure_ascii=False, indent=2))
    return 1 if args.strict and summary["blockingFailureCount"] else 0


def _prepare_output_dir(preferred: Path) -> Path:
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        return preferred
    except PermissionError:
        fallback = BACKEND_ROOT.parents[1] / "evaluation_outputs" / "rag_grounding_audit"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def _collect_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() in SUPPORTED_SUFFIXES else []
    return sorted(item for item in path.rglob("*") if item.is_file() and item.suffix.lower() in SUPPORTED_SUFFIXES)


def _audit_file(path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    case: dict[str, Any] = {"file": str(path), "status": "ok"}
    try:
        chunks = build_chunks(parse_document(path))
        result = build_agent_result(chunks, input_path=path)
        latency_ms = round((time.perf_counter() - started) * 1000)
        metrics = evaluate_result(result, latency_ms)
        diagnostics = result.get("citationDiagnostics") or {}
        blocking = _blocking_failures(metrics)
        case.update({
            "corpusHash": corpus_hash(chunks),
            "chunkCount": len(chunks),
            "noteCount": len(result.get("notes") or []),
            "metrics": metrics,
            "groundingPerf": diagnostics.get("groundingPerf") or {},
            "blockingFailures": blocking,
        })
        if blocking:
            case["status"] = "failed"
    except Exception as exc:
        case.update({"status": "error", "error": f"{type(exc).__name__}: {exc}", "blockingFailures": ["audit_error"]})
    return case


def _blocking_failures(metrics: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if float(metrics.get("quoteInSourceRate", 0)) < THRESHOLDS["quoteInSourceRate"]:
        failures.append("quoteInSourceRate")
    if float(metrics.get("citationSourceValidity", 0)) < 1:
        failures.append("citationSourceValidity")
    if float(metrics.get("citationNoteValidity", 0)) < 1:
        failures.append("citationNoteValidity")
    if float(metrics.get("noteCitationCoverage", 0)) < THRESHOLDS["noteCitationCoverage"]:
        failures.append("noteCitationCoverage")
    if float(metrics.get("lowSupportNoteRate", 0)) > THRESHOLDS["lowSupportNoteRateMax"]:
        failures.append("lowSupportNoteRate")
    if float(metrics.get("explicitRefResolutionRate", 1)) < 1:
        failures.append("explicitRefResolutionRate")
    return failures


def _summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    ok_cases = [case for case in cases if case.get("status") == "ok"]
    failed_cases = [case for case in cases if case.get("blockingFailures")]
    keys = [
        "ragGroundingScore",
        "noteCitationCoverage",
        "quoteInSourceRate",
        "citationSourceValidity",
        "citationNoteValidity",
        "averageNoteSupportScore",
        "lowSupportNoteRate",
        "explicitRefResolutionRate",
    ]
    averages = {f"avg_{key}": _avg((case.get("metrics") or {}).get(key) for case in ok_cases) for key in keys}
    return {
        "total": len(cases),
        "ok": len(ok_cases),
        "failed": len(cases) - len(ok_cases),
        "blockingFailureCount": len(failed_cases),
        **averages,
        "blockingFailures": [
            {"file": case.get("file"), "failures": case.get("blockingFailures", [])}
            for case in failed_cases
        ],
    }


def _avg(values: Any) -> float:
    nums = [float(value) for value in values if value is not None]
    return round(sum(nums) / max(1, len(nums)), 4)


def _markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# RAG Grounding Audit",
        "",
        "## Summary",
        "",
        f"- Total: {summary['total']}",
        f"- OK: {summary['ok']}",
        f"- Failed: {summary['failed']}",
        f"- Blocking failure count: {summary['blockingFailureCount']}",
        f"- Average ragGroundingScore: {summary['avg_ragGroundingScore']}",
        f"- Average quoteInSourceRate: {summary['avg_quoteInSourceRate']}",
        f"- Average lowSupportNoteRate: {summary['avg_lowSupportNoteRate']}",
        "",
        "## Cases",
        "",
        "| File | Status | Score | Quote Rate | Low Support | Perf ms | Failures |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for case in report["cases"]:
        metrics = case.get("metrics") or {}
        perf = case.get("groundingPerf") or {}
        lines.append(
            "| "
            + " | ".join([
                Path(str(case.get("file", ""))).name,
                str(case.get("status", "")),
                str(metrics.get("ragGroundingScore", "")),
                str(metrics.get("quoteInSourceRate", "")),
                str(metrics.get("lowSupportNoteRate", "")),
                str(perf.get("elapsedMs", "")),
                ", ".join(case.get("blockingFailures") or []),
            ])
            + " |"
        )
    return "\n".join(lines) + "\n"




def _html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    rows = []
    for case in report["cases"]:
        metrics = case.get("metrics") or {}
        perf = case.get("groundingPerf") or {}
        rows.append(
            "<tr>"
            f"<td>{_escape(Path(str(case.get('file', ''))).name)}</td>"
            f"<td>{_escape(case.get('status', ''))}</td>"
            f"<td>{_escape(metrics.get('ragGroundingScore', ''))}</td>"
            f"<td>{_escape(metrics.get('quoteInSourceRate', ''))}</td>"
            f"<td>{_escape(metrics.get('lowSupportNoteRate', ''))}</td>"
            f"<td>{_escape(perf.get('elapsedMs', ''))}</td>"
            f"<td>{_escape(perf.get('avgMsPerNote', ''))}</td>"
            f"<td>{_escape(', '.join(case.get('blockingFailures') or []) or 'none')}</td>"
            "</tr>"
        )
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>RAG Grounding Audit</title><style>body{{margin:0;background:#f6f7f9;color:#17202a;font-family:Microsoft YaHei,Arial,sans-serif}}.wrap{{max-width:1180px;margin:auto;padding:24px}}.hero,.card,table{{background:#fff;border:1px solid #dde3ea;border-radius:8px}}.hero{{padding:22px;margin-bottom:16px}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}}.card{{padding:16px}}.card b{{display:block;font-size:28px}}.card span{{color:#667085;font-size:12px}}table{{width:100%;border-collapse:collapse;overflow:hidden}}th,td{{padding:10px;border-bottom:1px solid #edf1f5;text-align:left;font-size:13px}}th{{background:#f8fafc}}@media(max-width:820px){{.grid{{grid-template-columns:1fr 1fr}}.wrap{{padding:14px}}}}</style></head><body><main class="wrap"><section class="hero"><h1>RAG Grounding Audit</h1><p>Generated from deterministic backend audit output.</p></section><section class="grid"><div class="card"><b>{summary['total']}</b><span>Total</span></div><div class="card"><b>{summary['ok']}</b><span>OK</span></div><div class="card"><b>{summary['blockingFailureCount']}</b><span>Blocking failures</span></div><div class="card"><b>{summary['avg_ragGroundingScore']}</b><span>Avg grounding score</span></div></section><table><thead><tr><th>File</th><th>Status</th><th>Score</th><th>Quote</th><th>Low Support</th><th>Perf ms</th><th>ms/note</th><th>Failures</th></tr></thead><tbody>{''.join(rows)}</tbody></table></main></body></html>'''


def _escape(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


if __name__ == "__main__":
    raise SystemExit(main())
