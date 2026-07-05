import { Card } from "../../components/Card";
import { TopBar } from "../../components/TopBar";

export function LoadingScreen({ stages, job }) {
  const visibleStages = job?.stages?.length ? job.stages : stages;
  const current = getCurrentStageIndex(visibleStages, job);
  const progress = clampProgress(job?.progress ?? estimateProgress(current, visibleStages.length));

  return (
    <div className="space-y-5 pb-6">
      <TopBar title="Agent 执行中" subtitle="可以暂时离开此界面" />
      <div className="px-5">
        <Card title={job?.label || visibleStages[current]?.label || "Running"} subtitle="Backend progress">
          <p className="text-[14px] leading-6 text-slate-600">{job?.text || visibleStages[current]?.text || "正在处理学习材料..."}</p>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-blue-100">
            <div className="h-full rounded-full bg-blue-600 transition-all duration-300" style={{ width: `${progress}%` }} />
          </div>
          <p className="mt-3 text-[12px] leading-5 text-slate-400">你可以先查看其它页面，生成完成后可回到 AI 页查看结果。</p>
          <div className="mt-4 space-y-2">
            {visibleStages.map((stage, index) => (
              <div key={stage.id} className="flex items-start justify-between gap-3 rounded-2xl bg-slate-50 px-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-semibold text-slate-900">{stage.label}</p>
                  <p className="break-words text-[12px] leading-5 text-slate-500">{stage.text}</p>
                </div>
                <span className={`shrink-0 whitespace-nowrap text-[12px] font-semibold leading-5 ${index <= current ? "text-blue-600" : "text-slate-300"}`}>
                  {index < current ? "完成" : index === current ? "处理中" : "等待"}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
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
