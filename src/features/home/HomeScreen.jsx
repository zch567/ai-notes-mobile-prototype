import { Card } from "../../components/Card";
import { TopBar } from "../../components/TopBar";
import { deriveAgentResultInsights } from "../ai/agentTypes";

export function HomeScreen({ result, onStart, onOpenNote }) {
  const hasResult = Boolean(result?.topic || result?.summary || result?.notes?.length);
  const { assetSummary } = deriveAgentResultInsights(result);
  const assetTimeText = hasResult
    ? formatAssetTime(assetSummary.generatedAt || result?.updatedAt || result?.createdAt)
    : "尚未生成";

  return (
    <div className="space-y-5 pb-6">
      <TopBar title="智序知识助手" subtitle="把学习资料变成可追溯、可复习的知识资产" />

      <div className="px-5">
        <section className="rounded-[28px] border border-blue-100 bg-white p-4 shadow-[0_18px_42px_rgba(37,99,235,0.12)]">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[12px] font-semibold uppercase tracking-[0.2em] text-blue-500">AI Notes</p>
              <h2 className="mt-2 text-[22px] font-semibold leading-tight tracking-tight text-slate-950">生成学习笔记</h2>
              <p className="mt-2 text-[13px] leading-5 text-slate-500">
                上传资料或粘贴文本，自动整理为笔记、导图和复习题。
              </p>
            </div>
            <span className="shrink-0 rounded-2xl bg-blue-50 px-3 py-2 text-[12px] font-semibold text-blue-700">文档接入</span>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {["文本", "PDF", "PPTX", "Word"].map((item) => (
              <span key={item} className="rounded-full bg-slate-50 px-3 py-1 text-[11px] font-semibold text-slate-500 ring-1 ring-slate-200">
                {item}
              </span>
            ))}
          </div>

          <button onClick={onStart} className="mt-4 w-full rounded-2xl bg-blue-600 px-5 py-3 text-[14px] font-semibold text-white shadow-sm shadow-blue-100">
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
            <div className="min-w-0">
              <div>
                <h3 className="text-[17px] font-semibold text-slate-900">{hasResult ? assetSummary.topic : "暂无真实生成结果"}</h3>
                <p className="mt-2 text-[13px] leading-5 text-slate-500">
                  {hasResult ? assetSummary.summary : "配置并调用后端后，这里会展示最近一次 AgentResult。"}
                </p>
              </div>
              <p className="mt-4 text-[12px] text-slate-400">{assetTimeText}</p>
            </div>
          </button>
        </Card>
      </div>
    </div>
  );
}

function formatAssetTime(value) {
  if (!value) return "生成时间待同步";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "生成时间待同步";
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}
