import { Card } from "../../components/Card";
import { TopBar } from "../../components/TopBar";
import { deriveAgentResultInsights } from "../ai/agentTypes";

export function NotesScreen({ result, onOpenNote }) {
  const categories = ["全部", "学习", "工作", "阅读", "研究"];
  const { assetSummary, qualitySummary } = deriveAgentResultInsights(result);

  return (
    <div className="space-y-5 pb-6">
      <TopBar title="笔记库" subtitle="管理结构化笔记、引用和复习资产" />
      <div className="px-5">
        <button className="flex w-full items-center gap-3 rounded-3xl border border-slate-200 bg-white px-4 py-4 text-left shadow-sm">
          <span className="text-slate-400">⌕</span>
          <span className="text-[15px] text-slate-400">搜索笔记、主题或引用...</span>
        </button>
      </div>

      <div className="flex gap-2 overflow-x-auto px-5 pb-1">
        {categories.map((item, index) => (
          <button
            key={item}
            className={`shrink-0 rounded-full px-4 py-2 text-[13px] font-medium ${
              index === 0 ? "bg-blue-600 text-white shadow-sm" : "bg-white text-slate-500 shadow-sm ring-1 ring-slate-200"
            }`}
          >
            {item}
          </button>
        ))}
      </div>

      <div className="px-5">
        <Card title="当前知识资产包" subtitle="Learning Asset">
          <button onClick={onOpenNote} className="w-full rounded-[28px] border border-slate-200 bg-white p-4 text-left shadow-sm">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="inline-flex rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-600">
                  {assetSummary.statusText}
                </div>
                <h3 className="mt-3 text-[17px] font-semibold text-slate-900">{assetSummary.topic}</h3>
                <p className="mt-2 text-[13px] leading-5 text-slate-500">{assetSummary.summary}</p>
              </div>
              <div className="grid shrink-0 grid-cols-1 gap-2 text-center">
                <Metric label="质量" value={qualitySummary.overallScore} />
                <Metric label="掌握" value={`${result.review.masteryScore}%`} />
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {[
                `笔记 ${assetSummary.noteCount}`,
                `引用 ${assetSummary.citationCount}`,
                `导图 ${assetSummary.mindMapNodeCount}`,
                `题目 ${assetSummary.reviewQuestionCount}`,
              ].map((tag) => (
                <span key={tag} className="rounded-full bg-slate-100 px-3 py-1 text-[12px] font-semibold text-slate-600">
                  {tag}
                </span>
              ))}
            </div>
          </button>
        </Card>
      </div>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-2xl bg-slate-50 px-3 py-2">
      <p className="text-[14px] font-semibold text-slate-900">{value}</p>
      <p className="text-[11px] text-slate-400">{label}</p>
    </div>
  );
}
