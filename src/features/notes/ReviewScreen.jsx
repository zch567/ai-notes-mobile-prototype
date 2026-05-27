import { Card } from "../../components/Card";

export function ReviewScreen({ result, onBack }) {
  const { review } = result;

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
              <span className="mb-2 text-[13px] font-semibold text-slate-400">Demo score</span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-blue-100">
              <div className="h-full rounded-full bg-blue-600" style={{ width: `${review.masteryScore}%` }} />
            </div>
          </Card>

          <Card title="复习题" subtitle="Questions">
            <div className="space-y-3">
              {review.questions.map((item, index) => (
                <div key={item.id} className="rounded-2xl bg-slate-50 p-4">
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
              ))}
            </div>
          </Card>

          <Card title="薄弱点与建议" subtitle="Recommendation">
            <div className="space-y-3">
              <div>
                <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-slate-400">Weak Points</p>
                <p className="mt-1 text-[14px] font-semibold text-slate-900">{review.weakPoints.join("、")}</p>
              </div>
              <div className="space-y-2">
                {review.recommendations.map((item) => (
                  <p key={item} className="rounded-2xl bg-amber-50 px-3 py-2 text-[13px] leading-5 text-amber-900">
                    {item}
                  </p>
                ))}
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
