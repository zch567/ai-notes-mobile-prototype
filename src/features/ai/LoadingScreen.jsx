import { Card } from "../../components/Card";
import { TopBar } from "../../components/TopBar";

export function LoadingScreen({ stages, phase }) {
  const current = Math.min(phase, Math.max(stages.length - 1, 0));
  const progress = stages.length ? ((current + 1) / stages.length) * 100 : 0;

  return (
    <div className="space-y-5 pb-6">
      <TopBar title="Agent 执行中" subtitle="展示真实 API 或演示模式下的 pipeline 状态" />
      <div className="px-5">
        <Card title={stages[current]?.label || "Running"} subtitle="Pipeline">
          <p className="text-[14px] leading-6 text-slate-600">{stages[current]?.text || "正在处理学习材料..."}</p>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-blue-100">
            <div className="h-full rounded-full bg-blue-600 transition-all duration-300" style={{ width: `${progress}%` }} />
          </div>
          <div className="mt-4 space-y-2">
            {stages.map((stage, index) => (
              <div key={stage.id} className="flex items-center justify-between rounded-2xl bg-slate-50 px-3 py-3">
                <div className="min-w-0">
                  <p className="text-[13px] font-semibold text-slate-900">{stage.label}</p>
                  <p className="truncate text-[12px] text-slate-500">{stage.text}</p>
                </div>
                <span className={`text-[12px] font-semibold ${index <= current ? "text-blue-600" : "text-slate-300"}`}>
                  {index < current ? "完成" : index === current ? "进行中" : "等待"}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
