import { Card } from "../../components/Card";
import { TopBar } from "../../components/TopBar";

export function LoadingScreen({ stages, job }) {
  const visibleStages = job?.stages?.length ? job.stages : stages;
  const current = getCurrentStageIndex(visibleStages, job);
  const progress = clampProgress(job?.progress ?? estimateProgress(current, visibleStages.length));
  const currentStage = visibleStages[current] || {};
  const currentLabel = job?.label || currentStage.label || "正在生成";
  const currentText = job?.text || currentStage.text || "正在处理学习材料...";

  return (
    <div className="space-y-5 pb-6">
      <TopBar title="笔记生成中" subtitle="可以暂时离开此界面" />
      <div className="px-5">
        <Card title="生成任务清单" subtitle={`${progress}% · Todo List`}>
          <div className="rounded-2xl border border-blue-100 bg-blue-50/70 px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <p className="min-w-0 text-[14px] font-semibold leading-5 text-slate-900">{currentLabel}</p>
              <span className="shrink-0 rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-blue-700">{progress}%</span>
            </div>
            <p className="mt-2 text-[12px] leading-5 text-slate-600">{currentText}</p>
          </div>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-blue-100">
            <div className="h-full rounded-full bg-blue-600 transition-all duration-300" style={{ width: `${progress}%` }} />
          </div>
          <p className="mt-3 text-[12px] leading-5 text-slate-400">你可以先查看其它页面，生成完成后可回到 AI 页查看结果。</p>
          <div className="mt-4 space-y-2" role="list" aria-label="生成任务清单">
            {visibleStages.map((stage, index) => (
              <TodoStageItem key={stage.id} stage={stage} state={getStageState(index, current)} />
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

function TodoStageItem({ stage, state }) {
  const done = state === "done";
  const active = state === "active";
  const rowClass = done
    ? "border-blue-100 bg-blue-50/70"
    : active
      ? "border-blue-200 bg-white shadow-[0_10px_24px_rgba(37,99,235,0.12)]"
      : "border-slate-100 bg-slate-50";
  const markerClass = done
    ? "border-blue-600 bg-blue-600 text-white"
    : active
      ? "border-blue-600 bg-white text-blue-600"
      : "border-slate-200 bg-white text-slate-300";
  const statusClass = done ? "text-blue-700" : active ? "text-blue-600" : "text-slate-400";
  const statusText = done ? "已完成" : active ? "进行中" : "待开始";

  return (
    <div role="listitem" className={`grid grid-cols-[28px_minmax(0,1fr)_52px] items-start gap-3 rounded-2xl border px-3 py-3 ${rowClass}`}>
      <span className={`mt-0.5 flex h-6 w-6 items-center justify-center rounded-full border text-[12px] font-bold leading-none ${markerClass}`}>
        {done ? "✓" : active ? <span className="h-2.5 w-2.5 rounded-full bg-blue-600" /> : null}
      </span>
      <div className="min-w-0">
        <p className="text-[13px] font-semibold leading-5 text-slate-900">{stage.label}</p>
        <p className="mt-1 break-words text-[12px] leading-5 text-slate-500">{stage.text}</p>
      </div>
      <span className={`pt-0.5 text-right text-[11px] font-semibold leading-5 ${statusClass}`}>{statusText}</span>
    </div>
  );
}

function getStageState(index, current) {
  if (index < current) return "done";
  if (index === current) return "active";
  return "pending";
}

function getCurrentStageIndex(stages, job) {
  if (!stages.length) return 0;
  const index = stages.findIndex((stage) => stage.id === job?.stageId);
  if (index >= 0) return index;
  const progress = clampProgress(job?.progress);
  const inferred = stages.findIndex((stage) => Number(stage.progress || 0) >= progress);
  return inferred >= 0 ? inferred : stages.length - 1;
}

function estimateProgress(current, length) {
  return length ? Math.min(((current + 1) / (length + 1)) * 100, 92) : 0;
}

function clampProgress(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.min(Math.max(number, 0), 100);
}
