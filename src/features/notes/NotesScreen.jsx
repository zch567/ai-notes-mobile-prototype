import { useMemo, useState } from "react";
import { Card } from "../../components/Card";
import { TopBar } from "../../components/TopBar";
import { deriveAgentResultInsights } from "../ai/agentTypes";

export function NotesScreen({
  result,
  history = [],
  onOpenNote,
  onSelectHistory = () => {},
  onPinHistory = () => {},
  onDeleteHistory = () => {},
}) {
  const [query, setQuery] = useState("");
  const records = history.length ? history : [createFallbackRecord(result)];
  const filteredRecords = useMemo(() => filterRecords(records, query), [records, query]);
  const hasQuery = query.trim().length > 0;

  return (
    <div className="space-y-5 pb-6">
      <TopBar title="笔记库" subtitle="管理结构化笔记、导图和复习资产" />
      <div className="px-5">
        <div className="flex w-full items-center gap-3 rounded-3xl border border-slate-200 bg-white px-4 py-3 text-left shadow-sm">
          <span className="text-slate-400">⌕</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索笔记、主题、引用或复习题..."
            className="min-w-0 flex-1 bg-transparent text-[15px] text-slate-700 outline-none placeholder:text-slate-400"
          />
          {hasQuery ? (
            <button
              type="button"
              onClick={() => setQuery("")}
              className="shrink-0 rounded-full bg-slate-100 px-2.5 py-1 text-[12px] font-semibold text-slate-500"
            >
              清除
            </button>
          ) : null}
        </div>
      </div>

      <div className="px-5">
        <Card title={hasQuery ? `搜索结果 ${filteredRecords.length}` : "历史笔记"} subtitle="Learning Assets">
          {filteredRecords.length ? (
            <div className="space-y-3">
              {filteredRecords.map((record) => (
              <HistoryNoteCard
                key={record.id}
                record={record}
                totalCount={records.length}
                onOpenNote={onOpenNote}
                onSelectHistory={onSelectHistory}
                onPinHistory={onPinHistory}
                onDeleteHistory={onDeleteHistory}
              />
              ))}
            </div>
          ) : (
            <EmptySearch query={query} onClear={() => setQuery("")} />
          )}
        </Card>
      </div>
    </div>
  );
}

function HistoryNoteCard({ record, totalCount, onOpenNote, onSelectHistory, onPinHistory, onDeleteHistory }) {
  const { assetSummary } = deriveAgentResultInsights(record.agentResult);
  const isPinned = Boolean(record.flags?.pinned);
  const canDelete = totalCount > 1;

  function deleteRecord() {
    if (!canDelete) return;
    const ok = window.confirm(`删除「${assetSummary.topic}」？删除后会从本地历史中移除。`);
    if (ok) onDeleteHistory(record.id);
  }

  return (
    <article className={`rounded-[28px] border bg-slate-50 p-4 shadow-sm ${record.active ? "border-blue-200 bg-blue-50/50" : "border-slate-200"}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap gap-2">
            {record.active ? <Tag tone="blue">当前</Tag> : null}
            {isPinned ? <Tag tone="amber">置顶</Tag> : null}
            <Tag>{sourceTypeLabel(record.sourceType)}</Tag>
          </div>
          <h3 className="mt-3 line-clamp-2 text-[17px] font-semibold leading-6 text-slate-900">{assetSummary.topic}</h3>
          <p className="mt-2 line-clamp-2 text-[13px] leading-5 text-slate-500">{assetSummary.summary}</p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
        <p className="text-[12px] text-slate-400">{formatDate(record.updatedAt)}</p>
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={() => onOpenNote(record.id)}
            className="rounded-2xl bg-blue-600 px-3 py-2 text-[12px] font-semibold text-white"
          >
            查看
          </button>
          <button
            type="button"
            onClick={() => onPinHistory(record.id, !isPinned)}
            className="rounded-2xl border border-blue-100 bg-white px-3 py-2 text-[12px] font-semibold text-blue-700"
          >
            {isPinned ? "取消置顶" : "置顶"}
          </button>
          <button
            type="button"
            onClick={deleteRecord}
            disabled={!canDelete}
            className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-[12px] font-semibold text-slate-500 disabled:text-slate-300"
          >
            删除
          </button>
        </div>
      </div>
    </article>
  );
}

function Tag({ children, tone = "slate" }) {
  const classes = {
    blue: "bg-blue-100 text-blue-700",
    amber: "bg-amber-100 text-amber-700",
    slate: "bg-white text-slate-500 ring-1 ring-slate-200",
  };

  return <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${classes[tone]}`}>{children}</span>;
}

function createFallbackRecord(result) {
  return {
    id: result?.id || "current-result",
    sourceType: "generated",
    updatedAt: new Date().toISOString(),
    active: true,
    flags: { pinned: false, archived: false },
    agentResult: result,
  };
}

function sourceTypeLabel(sourceType) {
  return {
    seed: "示例",
    generated: "生成",
    fallback: "演示",
    "local-edit": "已编辑",
  }[sourceType] || "历史";
}

function formatDate(value) {
  if (!value) return "刚刚更新";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "刚刚更新";
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function filterRecords(records, query) {
  const normalizedQuery = normalizeSearchText(query);
  if (!normalizedQuery) return records;

  return records.filter((record) => collectSearchText(record).includes(normalizedQuery));
}

function collectSearchText(record) {
  const result = record?.agentResult || {};
  const parts = [
    record?.title,
    record?.summary,
    sourceTypeLabel(record?.sourceType),
    result.topic,
    result.summary,
    ...(result.keywords || []),
    ...(result.sources || []).flatMap((source) => [source.title, source.fileName, source.text]),
    ...(result.notes || []).flatMap((note) => [
      note.title,
      note.content,
      ...(note.blocks || []).flatMap((block) => [block.title, block.text, block.content]),
    ]),
    ...(result.citations || []).flatMap((citation) => [citation.quote, citation.text]),
    ...(result.mindMap?.nodes || []).flatMap((node) => [node.label, node.desc, node.detail]),
    ...(result.review?.questions || []).flatMap((question) => [
      question.question,
      question.answer,
      ...(question.options || []),
      ...(question.explanation ? [question.explanation] : []),
    ]),
  ];

  return normalizeSearchText(parts.filter(Boolean).join(" "));
}

function normalizeSearchText(value) {
  return String(value || "").trim().toLocaleLowerCase();
}

function EmptySearch({ query, onClear }) {
  return (
    <div className="rounded-[24px] border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center">
      <p className="text-[14px] font-semibold text-slate-700">没有找到相关笔记</p>
      <p className="mt-2 text-[12px] leading-5 text-slate-400">当前搜索词：{query}</p>
      <button
        type="button"
        onClick={onClear}
        className="mt-4 rounded-2xl bg-white px-4 py-2 text-[12px] font-semibold text-blue-700 ring-1 ring-blue-100"
      >
        清除搜索
      </button>
    </div>
  );
}
