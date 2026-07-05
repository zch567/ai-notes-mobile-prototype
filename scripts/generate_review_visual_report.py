from __future__ import annotations

import html
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.orchestrator import build_agent_result_from_modules  # noqa: E402
from app.config import settings  # noqa: E402
from app.contracts import ReviewAnswerItem  # noqa: E402
from app.normalization import normalize_agent_result  # noqa: E402
from app.rag.grounding import ground_result  # noqa: E402
from app.rag.schemas import SourceChunk  # noqa: E402
from app.service import AgentService  # noqa: E402
import app.service as service_module  # noqa: E402


OUT_DIR = REPO_ROOT.parent / "review-question-visual-report"
RESULT_ID = "rag-review-visual-demo"


@dataclass
class FakeLog:
    requestId: str = "visual-review-demo"
    provider: str = "lanxin"
    model: str = "fake-review-model"
    taskType: str = "M7_review_assessment"
    inputChars: int = 0
    outputChars: int = 0
    latencyMs: int = 0
    status: str = "success"
    fallbackUsed: bool = False
    error: str | None = None


class FakeReviewProvider:
    def __init__(self) -> None:
        self.payload: dict[str, Any] | None = None

    def generate_module_json(self, module: str, prompt: str, payload: dict[str, Any], *, max_tokens: int = 4096):
        self.payload = payload
        wrong = payload.get("wrong_questions") or []
        explanations = []
        weak_points = []
        for item in wrong:
            title = item.get("relatedNoteTitle") or item.get("relatedNoteId") or "关联知识点"
            weak_points.append(title)
            explanations.append(
                {
                    "questionId": item.get("questionId"),
                    "mistakeReason": "把题干中的关键学习目标和干扰选项混淆了，没有先回到关联笔记判断概念边界。",
                    "correctThinking": f"先定位本题考察的知识点“{title}”，再用来源片段判断哪个选项与标准答案一致。",
                    "knowledgePoint": title,
                    "remediation": "重读关联笔记，用一句话复述正确选项成立的依据，并逐项说明其他选项为什么不成立。",
                }
            )
        return {
            "wrongQuestionExplanations": explanations,
            "weakPoints": weak_points,
            "reviewSuggestions": [
                "先回看错题关联笔记，圈出定义、作用、条件这三类关键词。",
                "把正确选项和错误选项放在同一张对照表中，写出排除理由。",
                "完成订正后闭卷重做同类单选题，再用简答题复述对应知识点。",
            ],
        }, FakeLog(inputChars=len(json.dumps(payload, ensure_ascii=False)))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    runtime_root = OUT_DIR / "runtime"
    object.__setattr__(settings, "output_dir", runtime_root.resolve())

    chunks = make_chunks()
    result = make_agent_result(chunks)
    run_dir = runtime_root / RESULT_ID
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "chunks.json").write_text(
        json.dumps([chunk.to_dict() for chunk in chunks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    fake_provider = FakeReviewProvider()
    original_create_provider = service_module.create_provider
    service_module.create_provider = lambda _name=None: fake_provider
    try:
        assessment = AgentService().submit_review_answers(
            result_id=RESULT_ID,
            answers=[
                ReviewAnswerItem(questionId="q1", answer="A"),
                ReviewAnswerItem(questionId="q2", answer="A"),
                ReviewAnswerItem(questionId="q3", answer="B"),
            ],
            provider_name="lanxin",
            strict=True,
        )
    finally:
        service_module.create_provider = original_create_provider

    report_path = OUT_DIR / "review-questions-visual-report.html"
    payload_path = OUT_DIR / "review-assessment-payload.json"
    result_path = OUT_DIR / "review-agent-result.json"
    assessment_path = OUT_DIR / "review-assessment-result.json"
    payload_path.write_text(json.dumps(fake_provider.payload or {}, ensure_ascii=False, indent=2), encoding="utf-8")
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    assessment_path.write_text(json.dumps(assessment, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(result, assessment, fake_provider.payload or {}), encoding="utf-8")

    print(report_path)
    print(assessment_path)


def make_chunks() -> list[SourceChunk]:
    return [
        SourceChunk(
            id="review-demo-c1",
            sourceId="review-demo",
            title="RAG 引用 grounding",
            text="RAG 通过检索到的来源片段约束生成内容，要求回答和笔记能回链到原文证据，降低无依据生成。",
            sourceType="text",
            fileName="review-demo.md",
            chunkIndex=1,
            sourceRef="para_1",
            heading="RAG 引用 grounding",
            paragraphStart=1,
            paragraphEnd=1,
        ),
        SourceChunk(
            id="review-demo-c2",
            sourceId="review-demo",
            title="复习题设计",
            text="复习题应覆盖核心概念、易错边界和应用场景。单选题适合检测概念辨析和条件判断。",
            sourceType="text",
            fileName="review-demo.md",
            chunkIndex=2,
            sourceRef="para_2",
            heading="复习题设计",
            paragraphStart=2,
            paragraphEnd=2,
        ),
        SourceChunk(
            id="review-demo-c3",
            sourceId="review-demo",
            title="错题反馈",
            text="错题反馈需要指出错误原因、正确思路、对应知识点，并给出可执行的复习加强建议。",
            sourceType="text",
            fileName="review-demo.md",
            chunkIndex=3,
            sourceRef="para_3",
            heading="错题反馈",
            paragraphStart=3,
            paragraphEnd=3,
        ),
    ]


def make_agent_result(chunks: list[SourceChunk]) -> dict[str, Any]:
    outputs = {
        "M2": {
            "topic": "复习题与错题反馈后端链路",
            "summary": "本资料用于验证后端能生成单选复习题，并在用户提交答案后给出错题解析和复习建议。",
        },
        "M3": {
            "notes": [
                {
                    "note_id": "n1",
                    "title": "RAG grounding 的作用",
                    "summary": "RAG 使用检索证据约束生成，帮助笔记和回答回链原文。",
                    "content": "RAG 通过来源片段约束生成内容，降低无依据输出。",
                    "source_refs": ["review-demo-c1"],
                },
                {
                    "note_id": "n2",
                    "title": "单选题适用场景",
                    "summary": "单选题适合检测概念辨析、易错边界和条件判断。",
                    "content": "复习题应覆盖核心概念、易错边界和应用场景。",
                    "source_refs": ["review-demo-c2"],
                },
                {
                    "note_id": "n3",
                    "title": "错题反馈结构",
                    "summary": "错题反馈需要包含错误原因、正确思路、知识点和补救动作。",
                    "content": "错题反馈需要指出错误原因、正确思路、对应知识点，并给出可执行建议。",
                    "source_refs": ["review-demo-c3"],
                },
            ]
        },
        "M4": {},
        "M6": {
            "quiz": [
                {
                    "question_id": "q1",
                    "question_type": "single_choice",
                    "question": "RAG grounding 在学习笔记后端中的主要作用是什么？",
                    "options": [
                        "A. 用检索到的来源证据约束生成内容",
                        "B. 只负责改变前端按钮颜色",
                        "C. 删除所有来源片段以减少干扰",
                        "D. 跳过引用校验直接输出结论",
                    ],
                    "answer": "A",
                    "explanation": "RAG grounding 的核心是让生成内容能回链来源证据。",
                    "related_note_id": "n1",
                },
                {
                    "question_id": "q2",
                    "question_type": "single_choice",
                    "question": "单选复习题最适合优先检测哪类学习目标？",
                    "options": [
                        "A. 文件上传速度",
                        "B. 页面滚动距离",
                        "C. 概念辨析和条件判断",
                        "D. 用户头像样式",
                    ],
                    "answer": "C",
                    "explanation": "单选题适合检测概念边界、易错点和条件判断。",
                    "related_note_id": "n2",
                },
                {
                    "question_id": "q3",
                    "question_type": "single_choice",
                    "question": "一次有效的错题反馈至少应包含什么？",
                    "options": [
                        "A. 只告诉用户继续努力",
                        "B. 错误原因、正确思路、知识点和补救动作",
                        "C. 只显示标准答案，不解释原因",
                        "D. 隐藏用户答案以避免挫败感",
                    ],
                    "answer": "B",
                    "explanation": "错题反馈需要帮助用户理解为什么错、怎么改。",
                    "related_note_id": "n3",
                },
            ]
        },
    }
    draft = build_agent_result_from_modules(outputs, chunks, input_path=None, prompt_source="visual-demo")
    grounded = ground_result(draft, chunks, top_k=1)
    normalized = normalize_agent_result(grounded)
    normalized["id"] = RESULT_ID
    return normalized


def render_report(result: dict[str, Any], assessment: dict[str, Any], payload: dict[str, Any]) -> str:
    questions = result.get("review", {}).get("questions", [])
    question_results = {item["questionId"]: item for item in assessment.get("questionResults", [])}
    explanations = {item.get("questionId"): item for item in assessment.get("wrongQuestionExplanations", [])}
    question_html = "\n".join(render_question(item, question_results.get(item.get("id"), {}), explanations.get(item.get("id"))) for item in questions)
    weak_html = "".join(f"<li>{esc(item)}</li>" for item in assessment.get("weakPoints", [])) or "<li>暂无薄弱点</li>"
    suggestion_html = "".join(f"<li>{esc(item)}</li>" for item in assessment.get("reviewSuggestions", [])) or "<li>暂无建议</li>"
    payload_count = len(payload.get("wrong_questions") or [])
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>复习题后端效果可视化报告</title>
{style_block()}
</head>
<body>
<header>
  <h1>复习题后端效果可视化报告</h1>
  <p>{esc(result.get("topic"))}</p>
  <div class="meta"><span>生成时间：{esc(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))}</span><span>题目数：{len(questions)}</span><span>错题上下文：{payload_count}</span></div>
</header>
<main>
  <section class="summary-grid">
    <div class="metric"><strong>{esc(assessment.get("masteryScore"))}%</strong><span>本次掌握度</span></div>
    <div class="metric"><strong>{esc(assessment.get("correctCount"))}/{esc(assessment.get("totalCount"))}</strong><span>答对题数</span></div>
    <div class="metric"><strong>{len(assessment.get("wrongQuestionExplanations", []))}</strong><span>错题解析</span></div>
  </section>
  <section class="panel">
    <h2>复习题与答题结果</h2>
    {question_html}
  </section>
  <section class="panel two-col">
    <div>
      <h2>薄弱点</h2>
      <ul>{weak_html}</ul>
    </div>
    <div>
      <h2>复习加强建议</h2>
      <ul>{suggestion_html}</ul>
    </div>
  </section>
  <section class="panel">
    <h2>后端检测结论</h2>
    <ul>
      <li>复习题支持 <code>single_choice</code> 输入并规范化为前端可渲染的 <code>single-choice</code>。</li>
      <li>提交答案后，后端能识别 A/B/C/D 并映射为选项全文。</li>
      <li>错题会携带关联笔记和来源片段进入大模型解析 payload。</li>
      <li>接口返回掌握度、逐题判分、错题解析、薄弱点和复习建议。</li>
    </ul>
  </section>
</main>
</body>
</html>"""


def render_question(question: dict[str, Any], result: dict[str, Any], explanation: dict[str, Any] | None) -> str:
    options = []
    user_answer = result.get("userAnswer", "")
    correct_answer = result.get("correctAnswer", question.get("answer", ""))
    for option in question.get("options") or []:
        classes = ["option"]
        if option == correct_answer:
            classes.append("correct")
        if option == user_answer and option != correct_answer:
            classes.append("wrong")
        options.append(f"<li class='{' '.join(classes)}'>{esc(option)}</li>")
    status = "正确" if result.get("isCorrect") else "错误"
    status_class = "ok" if result.get("isCorrect") else "bad"
    explanation_html = ""
    if explanation:
        explanation_html = f"""<div class="analysis">
          <h3>错题解析</h3>
          <p><b>错误原因：</b>{esc(explanation.get("mistakeReason"))}</p>
          <p><b>正确思路：</b>{esc(explanation.get("correctThinking"))}</p>
          <p><b>知识点：</b>{esc(explanation.get("knowledgePoint"))}</p>
          <p><b>补救动作：</b>{esc(explanation.get("remediation"))}</p>
        </div>"""
    return f"""<article class="question">
      <div class="q-head"><span class="badge">{esc(question.get("id"))}</span><span class="status {status_class}">{status}</span><span class="note">关联笔记：{esc(question.get("relatedNoteId"))}</span></div>
      <h3>{esc(question.get("question"))}</h3>
      <ol>{''.join(options)}</ol>
      <p class="answer"><b>用户答案：</b>{esc(user_answer or "未作答")} <b>标准答案：</b>{esc(correct_answer)}</p>
      <p class="explain"><b>题目解析：</b>{esc(question.get("explanation"))}</p>
      {explanation_html}
    </article>"""


def style_block() -> str:
    return """<style>
body{margin:0;background:#f6f8fb;color:#172033;font-family:"Microsoft YaHei","Segoe UI",Arial,sans-serif;line-height:1.6}
header{background:#fff;border-bottom:1px solid #dbe3ef;padding:26px 34px}h1{margin:0;font-size:26px}header p{margin:6px 0;color:#526071}.meta{display:flex;gap:10px;flex-wrap:wrap;color:#667085;font-size:13px}
main{max-width:1080px;margin:0 auto;padding:22px}.summary-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:16px}.metric,.panel{background:#fff;border:1px solid #dbe3ef;border-radius:8px}.metric{padding:16px}.metric strong{display:block;font-size:30px;color:#0f766e}.metric span{color:#667085}
.panel{padding:18px;margin-bottom:16px}.two-col{display:grid;grid-template-columns:1fr 1fr;gap:18px}h2{margin:0 0 12px;font-size:20px}.question{border:1px solid #e3e9f2;border-radius:8px;padding:16px;margin:12px 0;background:#fbfcfe}.q-head{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.badge,.status,.note{border-radius:999px;padding:2px 9px;font-size:12px}.badge{background:#eaf7f4;color:#0f766e}.status.ok{background:#ecfdf3;color:#067647}.status.bad{background:#fff1f3;color:#b42318}.note{border:1px solid #dbe3ef;color:#667085}
ol{padding-left:22px}.option{padding:7px 9px;margin:6px 0;border:1px solid #dbe3ef;border-radius:6px;background:#fff}.option.correct{border-color:#12b76a;background:#ecfdf3}.option.wrong{border-color:#f04438;background:#fff1f3}.answer,.explain{color:#344054}.analysis{border-left:4px solid #b42318;background:#fff7f7;padding:10px 12px;border-radius:6px}.analysis h3{margin:0 0 8px}code{background:#eef2f7;padding:1px 5px;border-radius:4px}
@media(max-width:760px){header{padding:20px}main{padding:14px}.summary-grid,.two-col{grid-template-columns:1fr}}
</style>"""


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


if __name__ == "__main__":
    main()
