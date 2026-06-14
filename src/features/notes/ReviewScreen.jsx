import { useState } from "react";
import { Card } from "../../components/Card";
import { readReviewProgress, saveReviewProgress } from "../../services/localDemoFs";

export function ReviewScreen({ result, onBack }) {
  const { review } = result;
  const [progress, setProgress] = useState(() => readReviewProgress(result.id));
  const hasQuestions = review.questions.length > 0;
  const hasWeakPoints = review.weakPoints.length > 0;
  const hasRecommendations = review.recommendations.length > 0;

  function completeReview() {
    const nextProgress = {
      answeredQuestionIds: review.questions.map((question) => question.id),
      lastReviewedAt: new Date().toISOString(),
    };
    setProgress(nextProgress);
    saveReviewProgress(result.id, nextProgress);
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-none border-b border-slate-200 bg-white px-5 py-4">
        <button onClick={onBack} className="text-[13px] font-semibold text-blue-600">
          返回
        </button>
        <h1 className="mt-2 text-[24px] font-semibold tracking-tight text-slate-950">复习评估</h1>
        <p className="mt-1 text-[13px] leading-5 text-slate-500">由 AgentResult.review 统一渲染。</p>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
        <div className="space-y-4">
          <Card title="掌握度" subtitle="Evaluation">
            <div className="flex items-end justify-between">
              <span className="text-[42px] font-semibold tracking-tight text-blue-600">{review.masteryScore}%</span>
              <span className="mb-2 text-[13px] font-semibold text-slate-400">Mastery score</span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-blue-100">
              <div className="h-full rounded-full bg-blue-600" style={{ width: `${review.masteryScore}%` }} />
            </div>
            <button
              onClick={completeReview}
              className="mt-4 w-full rounded-2xl bg-slate-900 px-4 py-3 text-[13px] font-semibold text-white"
            >
              完成本次复习并保存
            </button>
            {progress.lastReviewedAt ? (
              <p className="mt-3 text-[12px] leading-5 text-slate-500">
                最近复习：{new Date(progress.lastReviewedAt).toLocaleString()}
              </p>
            ) : null}
          </Card>

          <Card title="复习题" subtitle="Questions">
            <div className="space-y-3">
              {hasQuestions ? review.questions.map((item, index) => (
                <div key={item.id} className="rounded-2xl bg-slate-50 p-4">
                  <div className="mb-2 flex flex-wrap gap-2">
                    <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-700">
                      {questionTypeLabel(item.type)}
                    </span>
                    {item.relatedNoteId ? (
                      <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-500 ring-1 ring-slate-200">
                        关联笔记 {item.relatedNoteId}
                      </span>
                    ) : null}
                  </div>
                  <p className="text-[14px] font-semibold text-slate-900">{index + 1}. {item.question}</p>
                  {item.options ? (
                    <div className="mt-3 grid gap-2">
                      {item.options.map((option) => (
                        <div
                          key={option}
                          className={`rounded-2xl border px-3 py-2 text-[13px] ${
                            option === item.answer ? "border-blue-200 bg-white text-blue-700" : "border-slate-200 bg-white text-slate-600"
                          }`}
                        >
                          {option}
                        </div>
                      ))}
                    </div>
                  ) : null}
                  <p className="mt-3 text-[13px] leading-6 text-slate-600">{item.explanation}</p>
                </div>
              )) : (
                <EmptyState text="当前结果没有返回复习题。请检查真实后端的 review.questions 字段。" />
              )}
            </div>
          </Card>

          <Card title="薄弱点与建议" subtitle="Recommendation">
            <div className="space-y-3">
              <div>
                <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-slate-400">Weak Points</p>
                {hasWeakPoints ? (
                  <p className="mt-1 text-[14px] font-semibold text-slate-900">{review.weakPoints.join("、")}</p>
                ) : (
                  <p className="mt-1 text-[13px] leading-5 text-slate-500">暂无薄弱点。后端可在 review.weakPoints 中返回知识点名称。</p>
                )}
              </div>
              <div className="space-y-2">
                {hasRecommendations ? review.recommendations.map((item) => (
                  <p key={item} className="rounded-2xl bg-amber-50 px-3 py-2 text-[13px] leading-5 text-amber-900">
                    {item}
                  </p>
                )) : (
                  <EmptyState text="暂无复习建议。建议至少返回一个可操作动作，比如重读某个来源片段或重做某类题。" />
                )}
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function EmptyState({ text }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-4 text-[13px] leading-6 text-slate-500">
      {text}
    </div>
  );
}

function questionTypeLabel(type) {
  const labels = {
    "single-choice": "单选题",
    judgement: "判断题",
    "short-answer": "简答题",
    "concept-explanation": "概念解释",
    application: "应用理解",
  };
  return labels[type] || type || "复习题";
}
