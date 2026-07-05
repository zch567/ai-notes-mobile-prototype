import { Card } from "../../components/Card";
import { TopBar } from "../../components/TopBar";

export function HomeScreen({ result, learningLog = {}, onStart, onOpenNote }) {
  const hasResult = Boolean(result?.topic || result?.summary || result?.notes?.length);
  const log = normalizeLearningLog(learningLog);
  const calendarDays = getRecentSevenDays(log.dailyRecords);
  const activeDays = calendarDays.filter((day) => day.hasActivity).length;

  return (
    <div className="space-y-5 pb-6">
      <TopBar title="智序知识助手" subtitle="把学习资料变成可追踪、可复习的知识资产" />

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
        <Card title="我的学习日志" subtitle="Learning Calendar">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[13px] font-semibold text-slate-950">最近 7 天学习记录</p>
              <p className="mt-1 text-[12px] leading-5 text-slate-500">生成、阅读、复习和停留时长会自动沉淀到每日格子中。</p>
            </div>
            <div className="shrink-0 rounded-2xl bg-blue-50 px-3 py-2 text-center">
              <p className="text-[18px] font-semibold leading-none text-blue-700">{activeDays}</p>
              <p className="mt-1 text-[10px] font-semibold text-blue-500">活跃天数</p>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-7 gap-1.5">
            {calendarDays.map((day) => (
              <div
                key={day.key}
                className={[
                  "min-h-[102px] rounded-[18px] border px-1.5 py-2 text-center",
                  day.isToday
                    ? "border-blue-400 bg-blue-600 text-white shadow-sm shadow-blue-100"
                    : day.hasActivity
                      ? "border-blue-100 bg-blue-50 text-slate-950"
                      : "border-slate-200 bg-slate-50 text-slate-400",
                ].join(" ")}
              >
                <p className={day.isToday ? "text-[10px] font-semibold text-blue-100" : "text-[10px] font-semibold text-slate-400"}>
                  {day.weekday}
                </p>
                <p className="mt-1 text-[17px] font-semibold leading-none">{day.dateLabel}</p>
                <div className="mt-2 space-y-1 text-[10px] font-semibold leading-none">
                  <p className={day.isToday ? "text-white" : "text-slate-700"}>{day.generatedNotes || "-"} 生成</p>
                  <p className={day.isToday ? "text-blue-100" : "text-slate-500"}>{day.readNotes || "-"} 阅读</p>
                  <p className={day.isToday ? "text-blue-100" : "text-slate-500"}>{formatShortDuration(day.totalStudySeconds)}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 rounded-[22px] border border-blue-100 bg-blue-50 px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[13px] font-semibold text-blue-900">今日学习</p>
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
  const dailyRecords = log?.dailyRecords && typeof log.dailyRecords === "object" ? log.dailyRecords : {};

  return {
    generatedNotes: Math.max(0, Number(log?.generatedNotes) || 0),
    readNotes: Math.max(0, Number(log?.readNotes) || 0),
    reviewSessions: Math.max(0, Number(log?.reviewSessions) || 0),
    totalStudySeconds: Math.max(0, Number(log?.totalStudySeconds) || 0),
    dailyRecords,
    lastAction: String(log?.lastAction || ""),
    lastActionAt: log?.lastActionAt || null,
  };
}

function getRecentSevenDays(dailyRecords) {
  const today = new Date();
  const days = [];

  for (let offset = 6; offset >= 0; offset -= 1) {
    const date = new Date(today);
    date.setHours(0, 0, 0, 0);
    date.setDate(today.getDate() - offset);
    const key = toDateKey(date);
    const record = normalizeDailyRecord(dailyRecords?.[key]);

    days.push({
      ...record,
      key,
      weekday: offset === 0 ? "今天" : ["周日", "周一", "周二", "周三", "周四", "周五", "周六"][date.getDay()],
      dateLabel: `${date.getMonth() + 1}/${date.getDate()}`,
      isToday: offset === 0,
      hasActivity: record.generatedNotes > 0 || record.readNotes > 0 || record.reviewSessions > 0 || record.totalStudySeconds > 0,
    });
  }

  return days;
}

function normalizeDailyRecord(record) {
  return {
    generatedNotes: Math.max(0, Number(record?.generatedNotes) || 0),
    readNotes: Math.max(0, Number(record?.readNotes) || 0),
    reviewSessions: Math.max(0, Number(record?.reviewSessions) || 0),
    totalStudySeconds: Math.max(0, Number(record?.totalStudySeconds) || 0),
  };
}

function toDateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatShortDuration(seconds) {
  const minutes = Math.floor(Math.max(0, Number(seconds) || 0) / 60);
  if (minutes < 1) return "- 时长";
  if (minutes < 60) return `${minutes} 分`;
  return `${Math.floor(minutes / 60)}.${Math.floor((minutes % 60) / 6)} h`;
}

function formatLogTime(value) {
  if (!value) return "待记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "待记录";
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}
