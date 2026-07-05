import { useMemo, useState } from "react";
import { Card } from "../../components/Card";
import { TopBar } from "../../components/TopBar";

export function HomeScreen({ result, learningLog = {}, onStart, onOpenNote }) {
  const hasResult = Boolean(result?.topic || result?.summary || result?.notes?.length);
  const log = normalizeLearningLog(learningLog);
  const calendarDays = getRecentSevenDays(log.dailyRecords);
  const activeDays = calendarDays.filter((day) => day.hasActivity).length;
  const scoreTrend = useMemo(() => createLearningScoreTrend(calendarDays), [calendarDays]);
  const todayScore = scoreTrend[scoreTrend.length - 1]?.score || 0;
  const overviewStats = [
    { label: "学习时长", value: formatLearningDuration(log.totalStudySeconds) },
    { label: "做题数量", value: `${log.reviewSessions} 道` },
    { label: "生成笔记", value: `${log.generatedNotes} 次` },
    { label: "阅读笔记", value: `${log.readNotes} 次` },
  ];
  const [selectedDayKey, setSelectedDayKey] = useState(null);
  const selectedDay = useMemo(
    () => calendarDays.find((day) => day.key === selectedDayKey) || null,
    [calendarDays, selectedDayKey],
  );

  return (
    <div className="space-y-5 pb-6">
      <TopBar title="智序知识助手" subtitle="把学习资料变成可追踪、可复习的知识资产" />

      <div className="px-5">
        <Card title="我的学习日志" subtitle="Learning Calendar">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[13px] font-semibold text-slate-950">最近 7 天学习记录</p>
              <p className="mt-1 text-[12px] leading-5 text-slate-500">生成、阅读、做题数量和停留时长会自动沉淀到每日格子中。</p>
            </div>
            <div className="shrink-0 rounded-2xl bg-blue-50 px-3 py-2 text-center">
              <p className="text-[18px] font-semibold leading-none text-blue-700">{todayScore}</p>
              <p className="mt-1 text-[10px] font-semibold text-blue-500">今日分数</p>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-4 gap-2">
            {overviewStats.map((item) => (
              <div key={item.label} className="min-w-0 rounded-[18px] border border-slate-200 bg-slate-50 px-2 py-2 text-center">
                <p className="truncate text-[12px] font-semibold text-slate-950">{item.value}</p>
                <p className="mt-1 text-[10px] font-semibold text-slate-400">{item.label}</p>
              </div>
            ))}
          </div>

          <div className="mt-4 grid grid-cols-7 gap-1.5">
            {calendarDays.map((day) => (
              <button
                type="button"
                key={day.key}
                onClick={() => setSelectedDayKey((current) => (current === day.key ? null : day.key))}
                className={[
                  "relative flex aspect-[0.78] min-h-[66px] flex-col items-center justify-center rounded-[18px] border px-1 py-2 text-center transition",
                  selectedDayKey === day.key
                    ? "border-blue-500 bg-blue-600 text-white shadow-sm shadow-blue-100"
                    : day.isToday
                      ? "border-blue-200 bg-blue-50 text-blue-700"
                    : day.hasActivity
                      ? "border-blue-100 bg-white text-slate-950"
                      : "border-slate-200 bg-slate-50 text-slate-400",
                ].join(" ")}
                aria-pressed={selectedDayKey === day.key}
                aria-label={`${day.weekday} ${day.dateLabel}${day.hasActivity ? " 有学习记录" : " 无学习记录"}`}
              >
                <p className={selectedDayKey === day.key ? "text-[10px] font-semibold text-blue-100" : "text-[10px] font-semibold text-slate-400"}>
                  {day.weekday}
                </p>
                <p className="mt-1 text-[15px] font-semibold leading-none">{day.dateLabel}</p>
                {day.hasActivity ? (
                  <span
                    className={[
                      "absolute bottom-2 h-1.5 w-1.5 rounded-full",
                      selectedDayKey === day.key ? "bg-white" : "bg-blue-500",
                    ].join(" ")}
                    aria-hidden="true"
                  />
                ) : null}
              </button>
            ))}
          </div>

          <LearningScoreChart days={scoreTrend} activeDays={activeDays} selectedDayKey={selectedDayKey} />

          {selectedDay ? (
            <div className="mt-4 rounded-[22px] border border-blue-100 bg-blue-50 px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[13px] font-semibold text-blue-900">{selectedDay.isToday ? "今日学习" : `${selectedDay.dateLabel} 学习记录`}</p>
                  <p className="mt-1 text-[11px] font-semibold text-blue-700/70">{selectedDay.weekday}</p>
                </div>
                <span className="shrink-0 rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-blue-700">
                  {selectedDay.learningScore} 分
                </span>
              </div>

              {selectedDay.hasActivity ? (
                <div className="mt-3 grid grid-cols-4 gap-2">
                  {[
                    { label: "生成", value: `${selectedDay.generatedNotes} 次` },
                    { label: "阅读", value: `${selectedDay.readNotes} 次` },
                    { label: "做题", value: `${selectedDay.reviewSessions} 道` },
                    { label: "时长", value: formatShortDuration(selectedDay.totalStudySeconds, "0 分") },
                  ].map((item) => (
                    <div key={item.label} className="min-w-0 rounded-2xl bg-white px-2 py-2 text-center">
                      <p className="truncate text-[12px] font-semibold text-blue-900">{item.value}</p>
                      <p className="mt-1 text-[10px] font-semibold text-blue-500">{item.label}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-3 text-[13px] leading-5 text-blue-900/75">这一天还没有学习记录。</p>
              )}
            </div>
          ) : null}

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

function LearningScoreChart({ days, activeDays, selectedDayKey }) {
  const chart = createScoreChartGeometry(days);
  const averageScore = days.length
    ? Math.round(days.reduce((sum, day) => sum + day.score, 0) / days.length)
    : 0;

  return (
    <section className="mt-4 rounded-[24px] border border-slate-200 bg-slate-50 px-3 py-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[13px] font-semibold text-slate-950">学习分数趋势</p>
          <p className="mt-1 text-[11px] leading-4 text-slate-500">按生成、阅读、做题和时长综合计算</p>
        </div>
        <div className="shrink-0 rounded-2xl bg-white px-3 py-2 text-center shadow-sm">
          <p className="text-[17px] font-semibold leading-none text-slate-950">{averageScore}</p>
          <p className="mt-1 text-[10px] font-semibold text-slate-400">7日均分</p>
        </div>
      </div>

      <div className="mt-3 overflow-hidden rounded-[18px] bg-white px-2 py-2 shadow-inner">
        <svg viewBox="0 0 320 118" role="img" aria-label={`最近 7 天学习分数折线图，活跃 ${activeDays} 天`} className="h-[118px] w-full">
          <defs>
            <linearGradient id="learningScoreArea" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#2563eb" stopOpacity="0.22" />
              <stop offset="100%" stopColor="#2563eb" stopOpacity="0.02" />
            </linearGradient>
          </defs>
          {[25, 50, 75].map((score) => {
            const y = chart.yForScore(score);
            return (
              <g key={score}>
                <line x1="16" x2="304" y1={y} y2={y} stroke="#e2e8f0" strokeDasharray="4 5" />
                <text x="306" y={y + 3} textAnchor="start" className="fill-slate-300 text-[8px] font-semibold">
                  {score}
                </text>
              </g>
            );
          })}
          <path d={chart.areaPath} fill="url(#learningScoreArea)" />
          <polyline points={chart.pointString} fill="none" stroke="#2563eb" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" />
          {chart.points.map((point) => (
            <g key={point.key}>
              <circle
                cx={point.x}
                cy={point.y}
                r={selectedDayKey === point.key ? 5 : 4}
                fill={selectedDayKey === point.key ? "#1d4ed8" : "#ffffff"}
                stroke="#2563eb"
                strokeWidth="2"
              />
              <text x={point.x} y="109" textAnchor="middle" className="fill-slate-400 text-[8px] font-semibold">
                {point.shortLabel}
              </text>
            </g>
          ))}
        </svg>
      </div>
    </section>
  );
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
      learningScore: calculateDailyLearningScore(record),
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

function createLearningScoreTrend(days) {
  return days.map((day) => ({
    ...day,
    score: day.learningScore,
    shortLabel: day.isToday ? "今" : day.weekday.replace("周", ""),
  }));
}

function createScoreChartGeometry(days) {
  const left = 18;
  const right = 292;
  const top = 16;
  const bottom = 88;
  const step = days.length > 1 ? (right - left) / (days.length - 1) : 0;
  const yForScore = (score) => Math.round((bottom - (clamp(score, 0, 100) / 100) * (bottom - top)) * 10) / 10;
  const points = days.map((day, index) => ({
    ...day,
    x: Math.round((left + step * index) * 10) / 10,
    y: yForScore(day.score),
  }));
  const pointString = points.map((point) => `${point.x},${point.y}`).join(" ");
  const areaPath = points.length
    ? `M ${points[0].x} ${bottom} L ${points.map((point) => `${point.x} ${point.y}`).join(" L ")} L ${points[points.length - 1].x} ${bottom} Z`
    : "";

  return { points, pointString, areaPath, yForScore };
}

function calculateDailyLearningScore(record) {
  const durationMinutes = Math.floor(Math.max(0, Number(record?.totalStudySeconds) || 0) / 60);
  const generateScore = Math.min(Math.max(0, Number(record?.generatedNotes) || 0) * 18, 18);
  const readingScore = Math.min(Math.max(0, Number(record?.readNotes) || 0) * 10, 20);
  const questionScore = Math.min(Math.max(0, Number(record?.reviewSessions) || 0) * 7, 35);
  const durationScore = Math.min(durationMinutes / 30, 1) * 27;

  return Math.round(clamp(generateScore + readingScore + questionScore + durationScore, 0, 100));
}

function toDateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatShortDuration(seconds) {
  const minutes = Math.floor(Math.max(0, Number(seconds) || 0) / 60);
  if (minutes < 1) return "0 分";
  if (minutes < 60) return `${minutes} 分`;
  return `${Math.floor(minutes / 60)}.${Math.floor((minutes % 60) / 6)} h`;
}

function formatLearningDuration(seconds) {
  const totalMinutes = Math.floor(Math.max(0, Number(seconds) || 0) / 60);
  if (totalMinutes < 1) return "<1 分";
  if (totalMinutes < 60) return `${totalMinutes} 分`;
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return minutes ? `${hours}时${minutes}分` : `${hours} 小时`;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}
