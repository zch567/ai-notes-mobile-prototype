import { Card } from "../../components/Card";
import { TopBar } from "../../components/TopBar";

export function HomeScreen({ result, learningLog = {}, onStart, onOpenNote }) {
  const hasResult = Boolean(result?.topic || result?.summary || result?.notes?.length);
  const log = normalizeLearningLog(learningLog);
  const stats = [
    { label: "学习时长", value: formatDuration(log.totalStudySeconds), caption: "页面可见时自动累计" },
    { label: "生成笔记", value: `${log.generatedNotes} 次`, caption: "成功生成学习资产" },
    { label: "阅读笔记", value: `${log.readNotes} 次`, caption: "进入笔记详情" },
    { label: "复习", value: `${log.reviewSessions} 次`, caption: "打开复习页面" },
  ];

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
        <Card title="我的学习日志" subtitle="Learning Log">
          <div className="grid grid-cols-2 gap-3">
            {stats.map((item) => (
              <div key={item.label} className="rounded-[22px] border border-slate-200 bg-slate-50 px-3 py-3">
                <p className="text-[12px] font-semibold text-slate-500">{item.label}</p>
                <p className="mt-2 text-[22px] font-semibold tracking-tight text-slate-950">{item.value}</p>
                <p className="mt-1 text-[11px] leading-4 text-slate-400">{item.caption}</p>
              </div>
            ))}
          </div>

          <div className="mt-4 rounded-[22px] border border-blue-100 bg-blue-50 px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[13px] font-semibold text-blue-900">最近行为</p>
              <span className="shrink-0 rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-blue-700">
                {formatLogTime(log.lastActionAt)}
              </span>
            </div>
            <p className="mt-2 text-[13px] leading-5 text-blue-900/75">
              {log.lastAction ? `刚刚记录了「${log.lastAction}」行为。` : "生成、阅读或复习后，这里会自动更新学习轨迹。"}
            </p>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={onStart}
              className="rounded-2xl bg-blue-600 px-3 py-2.5 text-[13px] font-semibold text-white"
            >
              生成笔记
            </button>
            <button
              type="button"
              onClick={hasResult ? onOpenNote : onStart}
              className="rounded-2xl border border-blue-100 bg-white px-3 py-2.5 text-[13px] font-semibold text-blue-700"
            >
              {hasResult ? "阅读笔记" : "先生成"}
            </button>
          </div>
        </Card>
      </div>
    </div>
  );
}

function normalizeLearningLog(log) {
  return {
    generatedNotes: Math.max(0, Number(log?.generatedNotes) || 0),
    readNotes: Math.max(0, Number(log?.readNotes) || 0),
    reviewSessions: Math.max(0, Number(log?.reviewSessions) || 0),
    totalStudySeconds: Math.max(0, Number(log?.totalStudySeconds) || 0),
    lastAction: String(log?.lastAction || ""),
    lastActionAt: log?.lastActionAt || null,
  };
}

function formatDuration(seconds) {
  const totalMinutes = Math.floor(Math.max(0, Number(seconds) || 0) / 60);
  if (totalMinutes < 1) return "<1 分钟";
  if (totalMinutes < 60) return `${totalMinutes} 分钟`;
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return minutes ? `${hours}时${minutes}分` : `${hours} 小时`;
}

function formatLogTime(value) {
  if (!value) return "待记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "待记录";
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}
