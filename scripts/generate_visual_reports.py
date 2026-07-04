from __future__ import annotations

import html
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.adapters import RagPipelineAdapter  # noqa: E402


OUT_DIR = REPO_ROOT.parent / "lanxin-polish-visual-reports"

METRIC_LABELS = {
    "noteCount": "生成 NOTE 数",
    "templateSummaryRate": "模板化概要比例",
    "lowInfoSummaryRate": "低信息概要比例",
    "emptyContentRate": "空解释内容比例",
    "lowQualityContentRate": "低质量解释内容比例",
    "activityNoteRate": "误收活动/作业页比例",
    "visualLabelPointRate": "图示碎片要点比例",
    "pageReferencePointRate": "页码引用误入要点比例",
    "longKeyPointRate": "过长要点比例",
    "numberingBreakRate": "编号断裂标题比例",
    "brokenFragmentRate": "断词/残句比例",
    "truncatedSentenceRate": "截断句比例",
    "templateContentRate": "模板化解释比例",
    "semanticFieldRepetitionRate": "语义字段重复比例",
    "weakTeachingValueRate": "弱教学价值比例",
    "weakKeyPointRate": "弱要点比例",
    "overFragmentedKeyPointRate": "要点过细比例",
    "rawConcatSummaryRate": "拼接式概要比例",
    "titleSummaryMismatchRate": "标题概要错配比例",
    "genericTemplateMismatchRate": "模板适配错误比例",
    "transitionFragmentRate": "过渡残片比例",
    "internalProcessLanguageRate": "内部过程语言比例",
    "weakExplanationRate": "解释不足比例",
    "weakLearningActionabilityRate": "学习指导不足比例",
    "weakEvidenceRelevanceRate": "证据相关性不足比例",
    "learningRoleCoverage": "学习场景覆盖",
    "fieldRepetitionRate": "字段重复比例",
    "duplicateTitleClusterRate": "重复标题簇比例",
    "citationDisplayCoverage": "可读原文摘录覆盖率",
}

FAILED_LABELS = {
    "template-summary-high": "模板化概要过多",
    "low-info-summary-high": "概要信息量不足",
    "empty-content-high": "解释内容缺失过多",
    "low-quality-content-high": "解释内容质量不足",
    "activity-note-high": "活动/作业类内容被误当 NOTE",
    "visual-label-point-high": "图示标签或碎片进入要点",
    "page-reference-point-present": "页码引用误入学习要点",
    "long-key-point-high": "过长学习要点过多",
    "numbering-break-high": "编号标题断裂",
    "broken-fragment-present": "存在 PDF/PPT 断词或残句",
    "truncated-sentence-high": "截断句过多",
    "weak-explanation-high": "解释内容不足",
    "template-content-present": "存在模板化解释",
    "semantic-field-repetition-high": "概要、解释、要点语义重复过高",
    "weak-teaching-value-high": "教学价值不足",
    "weak-key-point-high": "弱要点过多",
    "over-fragmented-key-point-high": "要点切分过细",
    "raw-concat-summary-present": "存在拼接式概要",
    "title-summary-mismatch-present": "存在标题概要错配",
    "generic-template-mismatch-present": "存在解释模板适配错误",
    "transition-fragment-present": "存在过渡残片",
    "internal-process-language-present": "存在内部过程语言",
    "weak-learning-actionability-high": "学习指导不足",
    "weak-evidence-relevance-high": "原文证据相关性不足",
    "learning-role-coverage-low": "学习场景功能覆盖不足",
    "field-repetition-high": "概要、解释、要点重复过高",
    "duplicate-title-high": "存在重复或近重复 NOTE 标题",
    "citation-display-low": "可读原文摘录覆盖不足",
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    samples = [
        {"slug": "dma", "label": "第5章DMA方式", "path": pick_sample(".pdf", "DMA")},
        {"slug": "china-dream", "label": "共圆中国梦（思政课）", "path": pick_sample(".pptx", "中国梦")},
        {"slug": "wulun", "label": "考研政治_唯物论", "path": pick_sample(".docx", "唯物论")},
    ]
    adapter = RagPipelineAdapter()
    links = []
    for sample in samples:
        chunks = adapter.parse(sample["path"])
        result = adapter.build_deterministic_result(chunks, sample["path"])
        result_path = OUT_DIR / f"lanxin-{sample['slug']}-result.json"
        report_path = OUT_DIR / f"lanxin-{sample['slug']}-report.html"
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        report_path.write_text(render_report(sample, chunks, result), encoding="utf-8")
        quality = result.get("_meta", {}).get("contentQuality", {})
        links.append((sample["label"], report_path.name, len(chunks), len(result.get("notes", [])), quality))
        print(sample["label"], report_path, quality.get("passed"), quality.get("metrics"))
    (OUT_DIR / "index.html").write_text(render_index(links), encoding="utf-8")


def pick_sample(suffix: str, token: str) -> Path:
    for path in (REPO_ROOT / "test_set").rglob(f"*{suffix}"):
        if token in path.name:
            return path
    raise FileNotFoundError((suffix, token))


def render_report(sample: dict, chunks: list, result: dict) -> str:
    notes = result.get("notes", [])
    quality = result.get("_meta", {}).get("contentQuality", {})
    metrics = quality.get("metrics", {})
    failed = quality.get("failedChecks", [])
    samples = quality.get("samples", {})
    note_html = "\n".join(render_note(note, idx) for idx, note in enumerate(notes, start=1))
    metric_html = "".join(
        f"<div class='metric'><strong>{esc(value)}</strong><span>{esc(METRIC_LABELS.get(key, key))}</span></div>"
        for key, value in metrics.items()
    )
    failed_html = "".join(f"<li>{esc(FAILED_LABELS.get(item, item))}</li>" for item in failed) or "<li>无阻断项</li>"
    sample_html = render_quality_samples(samples)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{esc(sample['label'])} - 后端输出可视化</title>
{style_block()}
</head>
<body>
<header>
  <h1>{esc(sample['label'])}：后端样本处理输出</h1>
  <div class="meta"><span>生成时间：{esc(now())}</span><span>输入文件：{esc(sample['path'].name)}</span><span>模式：RAG + LearningUnit + 内容质量评估</span></div>
</header>
<main>
  <section class="panel metrics">
    <div class="metric"><strong>{len(chunks)}</strong><span>解析 chunk 数</span></div>
    <div class="metric"><strong>{len(notes)}</strong><span>生成 NOTE 数</span></div>
    <div class="metric"><strong>{'通过' if quality.get('passed') else '未通过'}</strong><span>内容质量结论</span></div>
    {metric_html}
  </section>
  <section class="panel">
    <h2>质量检查</h2>
    <ul>{failed_html}</ul>
    {sample_html}
    <p class="muted">质量项覆盖模板化概要、低信息概要、解释内容、图示碎片、断词残句、字段重复、重复标题和可读引用摘录。</p>
  </section>
  {note_html}
</main>
</body>
</html>"""


def render_quality_samples(samples: dict) -> str:
    if not samples:
        return ""
    rows = []
    for key, value in samples.items():
        if value:
            rows.append(f"<li><strong>{esc(key)}：</strong>{esc(value)}</li>")
    if not rows:
        return ""
    return "<details><summary>问题样例</summary><ul>" + "".join(rows) + "</ul></details>"


def render_note(note: dict, idx: int) -> str:
    keypoints = note.get("keyPoints") or []
    excerpts = note.get("sourceExcerpts") or []
    issues = (note.get("structure") or {}).get("qualityIssues") or note.get("quality_issues") or []
    keypoint_html = "".join(f"<li>{esc(item)}</li>" for item in keypoints[:10]) or "<li class='muted'>无独立分点</li>"
    excerpt_html = "".join(render_excerpt(item) for item in excerpts) or "<p class='muted'>未生成可读原文摘录</p>"
    issue_html = "".join(f"<span class='tag warn'>{esc(item)}</span>" for item in issues[:6]) or "<span class='tag ok'>无结构警告</span>"
    level = note.get("level", 1)
    parent = note.get("parentId") or "无"
    return f"""<article class="note level-{esc(level)}">
  <div class="note-head"><span class="note-index">NOTE {idx}</span><h2>{esc(note.get('title'))}</h2></div>
  <div class="tags"><span class="tag">层级 L{esc(level)}</span><span class="tag">父节点：{esc(parent)}</span>{issue_html}</div>
  <section class="summary"><h3>概要</h3><p>{esc(note.get('summary'))}</p></section>
  <section class="content"><h3>解释内容</h3><p>{esc(note.get('content'))}</p></section>
  <div class="grid two">
    <section><h3>要点</h3><ul>{keypoint_html}</ul></section>
    <section><h3>原文摘录与回链</h3>{excerpt_html}</section>
  </div>
</article>"""


def render_excerpt(item: dict) -> str:
    loc = item.get("sourceRef") or item.get("sourceId") or ""
    page = item.get("page")
    slide = item.get("slide")
    if page:
        loc = f"{loc} / page {page}"
    if slide:
        loc = f"{loc} / slide {slide}"
    return f"<div class='quote'><div class='quote-loc'>{esc(loc)}</div><p>{esc(item.get('quote'))}</p></div>"


def render_index(links: list[tuple[str, str, int, int, dict]]) -> str:
    items = []
    for label, name, chunks, notes, quality in links:
        status = "通过" if quality.get("passed") else "未通过"
        items.append(f"<li><a href='{esc(name)}'>{esc(label)}</a><span>chunks={chunks}, notes={notes}, quality={status}</span></li>")
    return f"<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><title>后端输出可视化报告索引</title>{style_block()}</head><body><main class='index'><h1>后端输出可视化报告索引</h1><p>生成时间：{esc(now())}</p><ul>{''.join(items)}</ul></main></body></html>"


def style_block() -> str:
    return """<style>
:root{--ink:#17202a;--muted:#667085;--line:#d9e0e8;--bg:#f6f8fb;--panel:#fff;--accent:#136f63;--warn:#9a5b00;--bad:#b42318}
*{box-sizing:border-box}body{margin:0;font-family:"Microsoft YaHei","Segoe UI",Arial,sans-serif;background:var(--bg);color:var(--ink);line-height:1.65}
header{padding:28px 34px 18px;background:#fff;border-bottom:1px solid var(--line)}h1{margin:0 0 8px;font-size:26px;letter-spacing:0}h2{margin:0;font-size:19px}h3{margin:0 0 8px;font-size:15px}
.meta{display:flex;flex-wrap:wrap;gap:10px;color:var(--muted);font-size:14px}main{max-width:1180px;margin:0 auto;padding:22px}.index{margin-top:32px;background:#fff;border:1px solid var(--line);border-radius:8px}
.panel,.note{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:18px;margin-bottom:16px}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.metric{border:1px solid var(--line);border-radius:8px;padding:14px;background:#fbfcfe;min-height:88px}.metric strong{display:block;font-size:22px;color:var(--accent)}.metric span,.muted{color:var(--muted);font-size:13px}
.note-head{display:flex;gap:12px;align-items:flex-start}.note-index{flex:0 0 auto;border:1px solid var(--line);border-radius:999px;padding:3px 10px;color:var(--accent);font-size:12px;font-weight:700}.summary,.content{margin:12px 0;padding:12px 14px;border-radius:6px}.summary{background:#f4faf8;border-left:4px solid var(--accent)}.content{background:#fff8ed;border-left:4px solid var(--warn)}
.grid.two{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(280px,.9fr);gap:16px}.tag{display:inline-block;margin:8px 6px 0 0;padding:2px 8px;border-radius:999px;border:1px solid var(--line);font-size:12px}.tag.ok{color:var(--accent)}.tag.warn{color:var(--bad);background:#fff4f2}.quote{border:1px solid var(--line);border-radius:6px;padding:10px;margin-bottom:8px;background:#fbfcfe}.quote-loc{font-size:12px;color:var(--muted);overflow-wrap:anywhere}ul{margin:0;padding-left:20px}li{margin:5px 0}a{color:var(--accent);font-weight:700}li span{color:var(--muted);margin-left:8px}details{margin-top:10px}
@media(max-width:760px){header{padding:20px}main{padding:14px}.metrics,.grid.two{grid-template-columns:1fr}h1{font-size:22px}}
</style>"""


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    main()
