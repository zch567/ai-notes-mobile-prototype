import { Card } from "../../components/Card";
import { TopBar } from "../../components/TopBar";
import { deriveAgentResultInsights } from "../ai/agentTypes";

export function HomeScreen({ result, onStart, onOpenNote }) {
  const hasResult = Boolean(result?.topic || result?.summary || result?.notes?.length);
  const { assetSummary, qualitySummary, learningLoopState } = deriveAgentResultInsights(result);

  return (
    <div className="space-y-5 pb-6">
      <TopBar title="智序知识助手" subtitle="把学习资料变成可追溯、可复习的知识资产" />

      <div className="px-5">
        <section className="rounded-[32px] bg-slate-950 p-5 text-white shadow-[0_20px_48px_rgba(15,23,42,0.22)]">
          <p className="text-[12px] font-semibold uppercase tracking-[0.24em] text-blue-200">Learning Loop</p>
          <h2 className="mt-3 text-[25px] font-semibold leading-tight tracking-tight">资料输入到复习反馈，一条链路跑完</h2>
          <p className="mt-3 text-[14px] leading-6 text-slate-300">
            当前版本只保留真实后端链路，先在“我的”页配置后端地址，再运行 Agent。
          </p>
          <button onClick={onStart} className="mt-5 rounded-2xl bg-white px-5 py-3 text-[14px] font-semibold text-slate-950">
            开始生成
          </button>
        </section>
      </div>

      <div className="px-5">
        <Card title="最近知识资产" subtitle="Latest Asset">
          <button
            onClick={hasResult ? onOpenNote : onStart}
            className="w-full rounded-3xl border border-slate-200 bg-slate-50 p-4 text-left"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-[17px] font-semibold text-slate-900">{hasResult ? assetSummary.topic : "暂无真实生成结果"}</h3>
                <p className="mt-2 text-[13px] leading-5 text-slate-500">
                  {hasResult ? assetSummary.summaryText : "配置并调用后端后，这里会展示最近一次 AgentResult。"}
                </p>
              </div>
              <span className="rounded-full bg-blue-50 px-3 py-1 text-[12px] font-semibold text-blue-600">
                {hasResult ? assetSummary.statusText : "待生成"}
              </span>
            </div>
            {hasResult ? (
              <div className="mt-4 grid grid-cols-4 gap-2">
                <MiniMetric label="笔记" value={assetSummary.noteCount} />
                <MiniMetric label="引用" value={assetSummary.citationCount} />
                <MiniMetric label="导图" value={assetSummary.mindMapNodeCount} />
                <MiniMetric label="题目" value={assetSummary.reviewQuestionCount} />
              </div>
            ) : null}
          </button>
        </Card>
      </div>

      <div className="px-5">
        <Card title="学习闭环" subtitle="Workflow">
          <div className="grid grid-cols-6 gap-1.5">
            {learningLoopState.steps.map((step, index) => (
              <div key={step.id} className="text-center">
                <div className={`mx-auto grid h-8 w-8 place-items-center rounded-full text-[12px] font-semibold ${
                  step.done ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-400"
                }`}>
                  {index + 1}
                </div>
                <p className={`mt-1 text-[11px] font-semibold ${step.done ? "text-slate-900" : "text-slate-400"}`}>{step.label}</p>
              </div>
            ))}
          </div>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
            <div className="h-full rounded-full bg-blue-600" style={{ width: `${Math.round(learningLoopState.progress * 100)}%` }} />
          </div>
          <div className="mt-4 flex items-center justify-between gap-3 rounded-2xl bg-slate-50 px-3 py-3">
            <div>
              <p className="text-[12px] font-semibold text-slate-400">生成质量</p>
              <p className="mt-1 text-[14px] font-semibold text-slate-900">{qualitySummary.overallScore} 分 · {qualitySummary.level}</p>
            </div>
            <button onClick={hasResult ? onOpenNote : onStart} className="rounded-2xl bg-slate-900 px-4 py-2 text-[12px] font-semibold text-white">
              {hasResult ? assetSummary.nextAction : "开始生成"}
            </button>
          </div>
        </Card>
      </div>
    </div>
  );
}

function MiniMetric({ label, value }) {
  return (
    <div className="rounded-2xl bg-white px-2 py-2 text-center ring-1 ring-slate-200">
      <p className="text-[14px] font-semibold text-slate-900">{value}</p>
      <p className="text-[11px] text-slate-400">{label}</p>
    </div>
  );
}
