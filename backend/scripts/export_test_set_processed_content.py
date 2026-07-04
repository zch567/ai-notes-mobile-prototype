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


def main() -> int:
    parser = argparse.ArgumentParser(description="Export visible processed content for test_set samples.")
    parser.add_argument("--input", default=str(BACKEND_ROOT.parent / "test_set"), help="File or directory to process.")
    parser.add_argument("--out", default=str(BACKEND_ROOT.parents[1] / "test_set_processed_outputs"), help="Output directory.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum files to process, 0 means all.")
    parser.add_argument("--notes", type=int, default=4, help="Notes per sample in HTML overview.")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    results_dir = out_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    files = _collect_files(input_path)
    if args.limit > 0:
        files = files[: args.limit]

    samples = []
    for path in files:
        samples.append(_process_file(path, results_dir))

    payload = {"input": str(input_path), "total": len(samples), "samples": samples}
    json_path = out_dir / "test_set_processed_content.json"
    html_path = out_dir / "test_set_processed_content.html"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(_html(payload, notes_per_sample=args.notes), encoding="utf-8-sig")

    print(json.dumps({"json": str(json_path), "html": str(html_path), "total": len(samples)}, ensure_ascii=False, indent=2))
    return 0


def _collect_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() in SUPPORTED_SUFFIXES else []
    return sorted(item for item in path.rglob("*") if item.is_file() and item.suffix.lower() in SUPPORTED_SUFFIXES)


def _process_file(path: Path, results_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        chunks = build_chunks(parse_document(path))
        result = build_agent_result(chunks, input_path=path)
        latency_ms = round((time.perf_counter() - started) * 1000)
        metrics = evaluate_result(result, latency_ms)
        slug = _safe_slug(path.stem)
        result_path = results_dir / f"{slug}.result.json"
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "file": str(path),
            "fileName": path.name,
            "status": "ok",
            "resultJson": str(result_path),
            "corpusHash": corpus_hash(chunks),
            "chunkCount": len(chunks),
            "topic": result.get("topic"),
            "summary": result.get("summary"),
            "notes": result.get("notes") or [],
            "citations": result.get("citations") or [],
            "reviewQuestions": (result.get("review") or {}).get("questions") or [],
            "metrics": metrics,
            "groundingPerf": (result.get("citationDiagnostics") or {}).get("groundingPerf") or {},
        }
    except Exception as exc:
        return {"file": str(path), "fileName": path.name, "status": "error", "error": f"{type(exc).__name__}: {exc}"}


def _safe_slug(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in value).strip("-") or "sample"


def _html(payload: dict[str, Any], *, notes_per_sample: int) -> str:
    sections = []
    for sample in payload["samples"]:
        if sample.get("status") != "ok":
            sections.append(f"<section class='sample'><h2>{_e(sample.get('fileName'))}</h2><p class='error'>{_e(sample.get('error'))}</p></section>")
            continue
        notes = sample.get("notes") or []
        citations = sample.get("citations") or []
        questions = sample.get("reviewQuestions") or []
        metrics = sample.get("metrics") or {}
        perf = sample.get("groundingPerf") or {}
        note_html = []
        for note in notes[:notes_per_sample]:
            support = note.get("support") or {}
            cites = "".join(f"<span>{_e(cid)}</span>" for cid in (note.get("citationIds") or [])[:4])
            blocks = "".join(f"<li><b>{_e(block.get('type'))}</b> {_e(_block_text(block))}</li>" for block in (note.get("blocks") or [])[:3])
            note_html.append(f"<article class='note'><div class='note-head'><h3>{_e(note.get('title'))}</h3><em>{_e(support.get('level', ''))} {_e(support.get('score', ''))}</em></div><p>{_e(note.get('summary') or note.get('content'))}</p><ul>{blocks}</ul><div class='chips'>{cites}</div></article>")
        citation_html = "".join(f"<tr><td>{_e(c.get('noteId'))}</td><td>{_e(c.get('sourceRef'))}</td><td>{_e(c.get('quote'))}</td><td>{_e(c.get('confidence'))}</td></tr>" for c in citations[:8])
        question_html = "".join(f"<article class='question'><b>{_e(q.get('question'))}</b><p>{_e(q.get('answer') or q.get('explanation'))}</p></article>" for q in questions[:3])
        sections.append(f"""<section class='sample'>
<div class='sample-title'><div><small>{_e(sample.get('fileName'))}</small><h2>{_e(sample.get('topic'))}</h2></div><a href='{_e(Path(sample.get('resultJson')).as_posix())}'>result.json</a></div>
<p class='summary'>{_e(sample.get('summary'))}</p>
<div class='metrics'><div><b>{_e(len(notes))}</b><span>notes</span></div><div><b>{_e(len(citations))}</b><span>citations</span></div><div><b>{_e(metrics.get('ragGroundingScore'))}</b><span>grounding</span></div><div><b>{_e(perf.get('elapsedMs'))}</b><span>grounding ms</span></div></div>
<h3>处理后的笔记内容</h3><div class='notes'>{''.join(note_html)}</div>
<h3>引用原文 quote</h3><table><thead><tr><th>note</th><th>source</th><th>quote</th><th>confidence</th></tr></thead><tbody>{citation_html}</tbody></table>
<h3>复习题输出</h3><div class='questions'>{question_html}</div>
</section>""")
    return f"""<!doctype html>
<html lang='zh-CN'><head><meta charset='UTF-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>测试集处理后内容输出</title><style>
body{{margin:0;background:#f5f7fa;color:#17202a;font-family:Microsoft YaHei,Arial,sans-serif}}.wrap{{max-width:1180px;margin:auto;padding:24px}}header,.sample{{background:#fff;border:1px solid #dde3ea;border-radius:8px;padding:20px;margin-bottom:16px}}h1,h2,h3{{margin:0 0 10px}}p{{line-height:1.7}}small{{color:#667085;font-weight:800}}.sample-title{{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}}.sample-title a{{color:#1d4ed8;text-decoration:none;font-weight:800}}.summary{{color:#475467}}.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0}}.metrics div{{border:1px solid #e2e8f0;border-radius:8px;padding:12px;background:#f8fafc}}.metrics b{{display:block;font-size:24px}}.metrics span{{color:#667085;font-size:12px}}.notes,.questions{{display:grid;gap:10px}}.note,.question{{border:1px solid #e2e8f0;border-radius:8px;padding:14px;background:#fff}}.note-head{{display:flex;justify-content:space-between;gap:10px}}.note-head em{{font-style:normal;color:#087443;background:#e7f5ee;border-radius:999px;padding:5px 8px;height:max-content;font-size:12px}}ul{{padding-left:20px;line-height:1.65}}.chips{{display:flex;flex-wrap:wrap;gap:6px}}.chips span{{background:#eff6ff;color:#1d4ed8;border-radius:999px;padding:5px 8px;font-size:12px}}table{{width:100%;border-collapse:collapse;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;background:#fff;margin-bottom:14px}}th,td{{padding:9px;border-bottom:1px solid #edf1f5;text-align:left;vertical-align:top;font-size:13px}}th{{background:#f8fafc}}.error{{color:#b42318}}@media(max-width:820px){{.wrap{{padding:12px}}.metrics{{grid-template-columns:1fr 1fr}}.sample-title{{display:block}}}}
</style></head><body><main class='wrap'><header><h1>测试集样本处理后的真实内容</h1><p>共处理 {payload['total']} 个测试集文件；每个样本展示 topic、summary、结构化笔记、引用 quote、复习题，并链接完整 result.json。</p></header>{''.join(sections)}</main></body></html>"""


def _block_text(block: dict[str, Any]) -> str:
    if block.get("content"):
        return str(block.get("content"))
    items = block.get("items") or []
    return "; ".join(json.dumps(item, ensure_ascii=False) if isinstance(item, (dict, list)) else str(item) for item in items)


def _e(value: Any) -> str:
    return (
        str(value if value is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


if __name__ == "__main__":
    raise SystemExit(main())
