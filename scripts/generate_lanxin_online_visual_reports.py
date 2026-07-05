from __future__ import annotations

import html
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings  # noqa: E402
from app.contracts import RunAgentRequest  # noqa: E402
from app.provider_config import ProviderConfig  # noqa: E402
from app.service import AgentService  # noqa: E402


OUT_DIR = Path(os.environ.get("LANXIN_ONLINE_REPORT_OUT_DIR") or REPO_ROOT.parent / "lanxin-online-visual-reports")


SAMPLES = [
    {"slug": "dma", "label": "第5章DMA方式", "suffix": ".pdf", "token": "DMA"},
    {"slug": "china-dream", "label": "共圆中国梦（思政课）", "suffix": ".pptx", "token": "中国梦"},
    {"slug": "wulun", "label": "考研政治_唯物论", "suffix": ".docx", "token": "唯物论"},
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    object.__setattr__(settings, "allowed_input_root", REPO_ROOT.resolve())
    object.__setattr__(settings, "output_dir", (OUT_DIR / "_runtime").resolve())

    provider_status = ProviderConfig.load().status()
    service = AgentService()
    links: list[dict[str, Any]] = []
    for sample in SAMPLES:
        path = pick_sample(sample["suffix"], sample["token"])
        started = time.perf_counter()
        error = ""
        try:
            result = service.run(
                RunAgentRequest(
                    filePath=str(path),
                    fileName=path.name,
                    pipeline="rag-only",
                    provider="lanxin",
                    strictProvider=True,
                    topK=2,
                )
            )
        except Exception as exc:
            error = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            result = failed_result(sample, path, error)
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        result.setdefault("_meta", {})["onlineTest"] = {
            "lanxinNetworkCall": True,
            "elapsedMs": elapsed_ms,
            "inputFile": str(path),
            "pipeline": "rag-only",
            "provider": "lanxin",
            "enableOcr": result.get("_meta", {}).get("ocr", {}).get("mode", "auto"),
            "error": error,
        }
        json_path = OUT_DIR / f"lanxin-online-{sample['slug']}-result.json"
        html_path = OUT_DIR / f"lanxin-online-{sample['slug']}-report.html"
        json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        html_path.write_text(render_report(sample, path, result, provider_status), encoding="utf-8-sig")
        quality = result.get("qualityDiagnostics", {})
        links.append(
            {
                "label": sample["label"],
                "href": html_path.name,
                "json": json_path.name,
                "notes": len(result.get("notes") or []),
                "sources": len(result.get("sources") or []),
                "score": quality.get("overallScore"),
                "summary": quality.get("summaryText"),
                "elapsedMs": elapsed_ms,
                "passed": result.get("_meta", {}).get("contentQuality", {}).get("passed"),
            }
        )
        print(json.dumps(links[-1], ensure_ascii=False))
    (OUT_DIR / "index.html").write_text(render_index(links, provider_status), encoding="utf-8-sig")
    print(json.dumps({"index": str(OUT_DIR / "index.html"), "count": len(links)}, ensure_ascii=False, indent=2))


def pick_sample(suffix: str, token: str) -> Path:
    for path in (REPO_ROOT / "test_set").rglob(f"*{suffix}"):
        if token in path.name:
            return path
    raise FileNotFoundError((suffix, token))


def failed_result(sample: dict[str, Any], path: Path, error: str) -> dict[str, Any]:
    return {
        "id": f"lanxin-online-{sample['slug']}-failed",
        "topic": sample["label"],
        "summary": "本次 rag-only + lanxin 联网测试未完成，报告保留错误信息用于排查。",
        "agentStages": [],
        "sources": [],
        "notes": [],
        "citations": [],
        "mindMap": {"nodes": [], "edges": []},
        "review": {"questions": [], "masteryScore": 0, "weakPoints": [], "recommendations": []},
        "qualityDiagnostics": {
            "overallScore": 0,
            "summaryText": f"联网测试失败：{error}",
            "failedChecks": ["lanxin-rag-only-call-failed"],
        },
        "_meta": {
            "inputFile": str(path),
            "error": error,
        },
    }


def render_report(sample: dict[str, Any], path: Path, result: dict[str, Any], provider_status: dict[str, Any]) -> str:
    notes = result.get("notes") or []
    citations = result.get("citations") or []
    sources = {source.get("id"): source for source in result.get("sources") or []}
    diagnostics = result.get("qualityDiagnostics") or {}
    content_quality = result.get("_meta", {}).get("contentQuality") or {}
    online = result.get("_meta", {}).get("onlineTest") or {}
    perf = (result.get("citationDiagnostics") or {}).get("groundingPerf") or {}
    metric_cards = [
        ("NOTE 数", len(notes)),
        ("来源块", len(sources)),
        ("引用数", len(citations)),
        ("质量分", diagnostics.get("overallScore", "-")),
        ("耗时", f"{round(int(online.get('elapsedMs') or 0) / 1000, 1)}s"),
        ("OCR", (result.get("_meta", {}).get("ocr") or {}).get("mode", "auto")),
    ]
    cards_html = "".join(f"<div class='metric'><b>{esc(v)}</b><span>{esc(k)}</span></div>" for k, v in metric_cards)
    failed = content_quality.get("failedChecks") or []
    failed_html = "".join(f"<li>{esc(item)}</li>" for item in failed) or "<li>无阻断项</li>"
    notes_html = "".join(render_note(note, idx, sources) for idx, note in enumerate(notes, start=1))
    review_html = render_review(result.get("review") or {}, sources)
    source_html = render_sources(result.get("sources") or [])
    meta_html = render_meta(provider_status, perf, online)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{esc(sample['label'])} - 蓝心联网测试报告</title>
{style()}
</head>
<body>
<header>
  <p class="eyebrow">Lanxin Online Pipeline Test</p>
  <h1>{esc(sample['label'])}</h1>
  <p class="sub">输入文件：{esc(path.name)} · 生成时间：{esc(now())} · rag-only + lanxin polish</p>
</header>
<main>
  <section class="metrics">{cards_html}</section>
  <section class="panel">
    <h2>真实输出摘要</h2>
    <p>{esc(result.get("summary"))}</p>
    <p class="quality">{esc(diagnostics.get("summaryText") or "")}</p>
  </section>
  {meta_html}
  <section class="panel">
    <h2>质量阻断项</h2>
    <ul>{failed_html}</ul>
  </section>
  <section class="panel">
    <h2>结构化 NOTE 输出</h2>
    <div class="stack">{notes_html}</div>
  </section>
  {review_html}
  <section class="panel">
    <h2>来源块预览</h2>
    <div class="stack">{source_html}</div>
  </section>
</main>
<script>
document.querySelectorAll('[data-source]').forEach(button => {{
  button.addEventListener('click', () => {{
    const id = button.dataset.source;
    const target = document.getElementById('source-' + CSS.escape(id));
    if (target) target.scrollIntoView({{behavior:'smooth', block:'center'}});
  }});
}});
</script>
</body>
</html>"""


def render_meta(provider_status: dict[str, Any], perf: dict[str, Any], online: dict[str, Any]) -> str:
    lanxin = provider_status.get("lanxin") or {}
    rows = [
        ("聊天模型", lanxin.get("model")),
        ("grounding 检索次数", perf.get("retrievalCalls")),
        ("联网测试耗时 ms", online.get("elapsedMs")),
    ]
    row_html = "".join(f"<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in rows)
    return f"""<section class="panel">
  <h2>联网链路</h2>
  <table>{row_html}</table>
</section>"""


def render_note(note: dict[str, Any], idx: int, sources: dict[str, dict[str, Any]]) -> str:
    refs = note.get("citationIds") or note.get("sourceRefs") or note.get("source_refs") or []
    chips = "".join(f"<button type='button' data-source='{esc(ref)}'>{esc(ref)}</button>" for ref in refs[:8])
    points = note.get("keyPoints") or []
    point_html = "".join(f"<li>{esc(item)}</li>" for item in points[:10]) or "<li class='muted'>未输出要点</li>"
    blocks = note.get("blocks") or []
    block_html = "".join(render_block(block) for block in blocks[:8])
    excerpts = note.get("sourceExcerpts") or []
    excerpt_html = "".join(render_excerpt(item) for item in excerpts) or render_ref_quotes(refs, sources)
    support = note.get("support") or {}
    return f"""<article class="note">
  <div class="note-head"><span>NOTE {idx}</span><h3>{esc(note.get("title"))}</h3></div>
  <div class="tags"><em>level {esc(note.get("level", 1))}</em><em>support {esc(support.get("level", ""))} {esc(support.get("score", ""))}</em>{chips}</div>
  <section><h4>概要</h4><p>{esc(note.get("summary"))}</p></section>
  <section><h4>解释内容</h4><p>{esc(note.get("content"))}</p></section>
  <section><h4>要点</h4><ul>{point_html}</ul></section>
  <section><h4>结构块</h4>{block_html or "<p class='muted'>无结构块</p>"}</section>
  <section><h4>原文摘录与回链</h4>{excerpt_html}</section>
</article>"""


def render_block(block: dict[str, Any]) -> str:
    items = block.get("items") or []
    structured = block.get("structuredItems") or []
    if structured and not items:
        items = [item.get("text") for item in structured if isinstance(item, dict)]
    item_html = "".join(f"<li>{esc(item)}</li>" for item in items[:8])
    content = block.get("content") or ""
    return f"<div class='block'><b>{esc(block.get('title') or block.get('type'))}</b><p>{esc(content)}</p>{('<ul>'+item_html+'</ul>') if item_html else ''}</div>"


def render_excerpt(item: dict[str, Any]) -> str:
    loc = item.get("sourceRef") or item.get("sourceId") or ""
    if item.get("page"):
        loc = f"{loc} / page {item.get('page')}"
    if item.get("slide"):
        loc = f"{loc} / slide {item.get('slide')}"
    return f"<blockquote><small>{esc(loc)}</small><p>{esc(item.get('quote'))}</p></blockquote>"


def render_ref_quotes(refs: list[str], sources: dict[str, dict[str, Any]]) -> str:
    quotes = []
    for ref in refs[:3]:
        source = sources.get(ref)
        if not source:
            continue
        quotes.append(f"<blockquote><small>{esc(source.get('sourceRef') or ref)}</small><p>{esc(source.get('text'))}</p></blockquote>")
    return "".join(quotes) or "<p class='muted'>未生成可读原文摘录</p>"


def render_review(review: dict[str, Any], sources: dict[str, dict[str, Any]]) -> str:
    questions = review.get("questions") or []
    items = []
    for question in questions[:8]:
        options = "".join(f"<li>{esc(option)}</li>" for option in question.get("options") or [])
        refs = "".join(f"<button type='button' data-source='{esc(ref)}'>{esc(ref)}</button>" for ref in question.get("citationIds") or [])
        items.append(
            f"<article class='question'><h3>{esc(question.get('question'))}</h3>"
            f"{('<ol>'+options+'</ol>') if options else ''}<p><b>答案：</b>{esc(question.get('answer'))}</p>"
            f"<p><b>解析：</b>{esc(question.get('explanation'))}</p><div class='tags'>{refs}</div></article>"
        )
    return "<section class='panel'><h2>复习题输出</h2><div class='stack'>" + ("".join(items) or "<p class='muted'>无复习题</p>") + "</div></section>"


def render_sources(sources: list[dict[str, Any]]) -> str:
    rows = []
    for source in sources[:24]:
        rows.append(
            f"<article class='source' id='source-{esc(source.get('id'))}'><h3>{esc(source.get('title'))}</h3>"
            f"<p class='muted'>{esc(source.get('id'))} · {esc(source.get('sourceRef'))}</p>"
            f"<pre>{esc(source.get('text'))}</pre></article>"
        )
    return "".join(rows) or "<p class='muted'>无来源块</p>"


def render_index(links: list[dict[str, Any]], provider_status: dict[str, Any]) -> str:
    items = []
    for item in links:
        items.append(
            f"<li><a href='{esc(item['href'])}'>{esc(item['label'])}</a>"
            f"<span>notes={esc(item['notes'])}, sources={esc(item['sources'])}, score={esc(item['score'])}, "
            f"耗时={round(int(item['elapsedMs'])/1000, 1)}s</span>"
            f"<p>{esc(item.get('summary'))}</p></li>"
        )
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>蓝心联网测试可视化报告</title>{style()}</head><body><header><p class="eyebrow">Lanxin Online Test</p><h1>测试集联网处理可视化报告</h1><p class="sub">生成时间：{esc(now())} · rag-only + lanxin polish</p></header><main><section class="panel"><h2>报告入口</h2><ul class="index-list">{''.join(items)}</ul></section></main></body></html>"""


def style() -> str:
    return """<style>
:root{--bg:#f5f7fb;--panel:#fff;--ink:#182230;--muted:#667085;--line:#d7dee8;--accent:#0f766e;--accent2:#7c3aed;--warn:#b45309}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:"Microsoft YaHei","Segoe UI",Arial,sans-serif;line-height:1.65}header{background:#fff;border-bottom:1px solid var(--line);padding:28px 34px}main{max-width:1240px;margin:0 auto;padding:22px}.eyebrow{margin:0 0 6px;color:var(--accent);font-weight:700;text-transform:uppercase;letter-spacing:.04em}.sub,.muted{color:var(--muted)}h1{margin:0;font-size:28px;letter-spacing:0}h2{margin:0 0 12px;font-size:20px}h3{margin:0;font-size:17px}h4{margin:12px 0 6px}.panel,.note,.question,.source{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:16px;margin-bottom:16px}.metrics{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;margin-bottom:16px}.metric{background:#fff;border:1px solid var(--line);border-radius:8px;padding:14px;min-height:84px}.metric b{display:block;font-size:22px;color:var(--accent)}.metric span{color:var(--muted);font-size:13px}.quality{border-left:4px solid var(--accent);background:#f0fdfa;padding:10px 12px;border-radius:6px}.stack{display:grid;gap:12px}.note-head{display:flex;gap:10px;align-items:flex-start}.note-head span{border:1px solid var(--line);border-radius:999px;padding:3px 9px;color:var(--accent);font-size:12px;font-weight:700}.tags{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}.tags em,.tags button,button[data-source]{border:1px solid var(--line);background:#fbfcfe;border-radius:999px;padding:3px 8px;color:var(--muted);font-style:normal;font-size:12px;cursor:pointer}.tags button:hover,button[data-source]:hover{border-color:var(--accent);color:var(--accent)}section>p{margin-top:4px}.block{border:1px solid var(--line);border-radius:6px;background:#fbfcfe;padding:10px;margin:8px 0}blockquote{margin:8px 0;padding:10px 12px;border-left:4px solid var(--accent2);background:#faf8ff;border-radius:6px}blockquote small{color:var(--muted)}pre{white-space:pre-wrap;word-break:break-word;max-height:260px;overflow:auto;background:#0f172a;color:#e5e7eb;border-radius:6px;padding:12px}table{width:100%;border-collapse:collapse}th,td{border-bottom:1px solid var(--line);padding:8px;text-align:left;vertical-align:top}th{width:220px;color:var(--muted)}.index-list li{margin-bottom:14px}.index-list a{color:var(--accent);font-weight:700;font-size:18px}.index-list span{display:block;color:var(--muted)}a{color:var(--accent)}
@media(max-width:900px){header{padding:22px}main{padding:14px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}h1{font-size:23px}th{width:auto}}
</style>"""


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    main()
