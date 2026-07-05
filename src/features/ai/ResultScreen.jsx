import { Card } from "../../components/Card";
import { TopBar } from "../../components/TopBar";
import { deriveAgentResultInsights } from "./agentTypes";

export function ResultScreen({ result, onOpenNote, onOpenMindMap, onOpenReview, onRetry }) {
  const { assetSummary } = deriveAgentResultInsights(result);

  return (
    <div className="space-y-5 pb-6">
      <TopBar title="生成结果" subtitle="学习材料已整理完成" />

      <div className="space-y-5 px-5">
        <Card title={assetSummary.topic} subtitle="Learning Asset">
          <div className="mb-4 grid grid-cols-3 gap-2">
            <button onClick={onOpenNote} className="min-h-[56px] rounded-2xl border border-blue-100 bg-blue-50 px-2 py-3 text-[12px] font-semibold leading-5 text-blue-700">
              前往笔记页
            </button>
            <button onClick={onOpenMindMap} className="min-h-[56px] rounded-2xl border border-blue-100 bg-blue-50 px-2 py-3 text-[12px] font-semibold leading-5 text-blue-700">
              前往导图页
            </button>
            <button onClick={onOpenReview} className="min-h-[56px] rounded-2xl border border-blue-100 bg-blue-50 px-2 py-3 text-[12px] font-semibold leading-5 text-blue-700">
              前往复习页
            </button>
          </div>

          <p className="text-[14px] leading-6 text-slate-700">{assetSummary.summary}</p>
          <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-[12px] leading-5 text-slate-500">
            {assetSummary.summaryText}
            {assetSummary.fileName ? ` 来源文件：${assetSummary.fileName}` : ""}
          </div>
        </Card>

        <button onClick={onRetry} className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-[14px] font-semibold text-slate-700">
          重新输入
        </button>
      </div>
    </div>
  );
}
