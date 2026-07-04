import { TopBar } from "../../components/TopBar";

export function ShowcaseScreen({ result, onOpenNote, onOpenMindMap, onRunAgent }) {
  const diagnostics = result?.citationDiagnostics || {};
  const meta = result?._meta || {};
  const reportPlan = result?.reportPlan?.length ? result.reportPlan : result?.outline || [];
  const evidenceCards = buildEvidenceCards(result);
  const mapGroups = buildMapGroups(result);
  const stages = result?.agentStages || [];

  return (
    <div className="pb-6">
      <TopBar title="能力展示" subtitle="RAGFlow / Quivr / STORM 后端优化演示" />

      <section className="px-5 pt-2">
        <div className="overflow-hidden rounded-[28px] bg-slate-950 text-white shadow-[0_22px_52px_rgba(15,23,42,0.24)]">
          <div className="p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-cyan-200">AgentResult Showcase</p>
                <h1 className="mt-3 text-[24px] font-semibold leading-tight">{result.topic || "学习资料智能整理"}</h1>
              </div>
              <span className="shrink-0 rounded-full bg-emerald-400/15 px-3 py-1 text-[12px] font-semibold text-emerald-200">
                {meta.ragVersion || "hybrid"}
              </span>
            </div>
            <p className="mt-4 text-[13px] leading-6 text-slate-300">{result.summary || "运行后端 Agent 后，这里展示结构化笔记、引用证据、报告计划和思维导图。"}</p>
            <div className="mt-5 grid grid-cols-3 gap-2">
              <HeroMetric label="Chunks" value={diagnostics.chunkCount || meta.chunkCount || result.sources?.length || 0} />
              <HeroMetric label="Citations" value={diagnostics.citationCount || result.citations?.length || 0} />
              <HeroMetric label="Notes" value={diagnostics.noteCount || result.notes?.length || 0} />
            </div>
          </div>
          <div className="grid grid-cols-2 border-t border-white/10 bg-white/[0.04]">
            <ActionButton label="查看笔记" onClick={onOpenNote} />
            <ActionButton label="打开导图" onClick={onOpenMindMap} />
          </div>
        </div>
      </section>

      <section className="mt-5 px-5">
        <div className="grid grid-cols-2 gap-3">
          <ScoreCard label="引用覆盖" value={percentText(diagnostics.noteCitationCoverage)} tone="blue" />
          <ScoreCard label="原文命中" value={percentText(diagnostics.quoteInSourceRate)} tone="emerald" />
          <ScoreCard label="来源有效" value={percentText(diagnostics.citationSourceValidity)} tone="violet" />
          <ScoreCard label="平均置信" value={percentText(diagnostics.averageConfidence)} tone="amber" />
        </div>
      </section>

      <section className="mt-5 px-5">
        <SectionTitle title="后端流水线" subtitle="Parse -> Retrieve -> Ground -> Review" />
        <div className="mt-3 space-y-3">
          {stages.slice(0, 7).map((stage, index) => (
            <div key={stage.id || index} className="flex gap-3 rounded-[22px] border border-slate-200 bg-white p-4 shadow-sm">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-2xl bg-slate-900 text-[12px] font-semibold text-white">{index + 1}</span>
              <div className="min-w-0">
                <p className="text-[14px] font-semibold text-slate-900">{stage.label}</p>
                <p className="mt-1 text-[12px] leading-5 text-slate-500">{stage.text}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-5 px-5">
        <SectionTitle title="RAG 证据链" subtitle="查询扩展、邻近上下文、可追溯引用" />
        <div className="mt-3 space-y-3">
          {evidenceCards.map((item) => (
            <div key={item.id} className="rounded-[22px] border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[14px] font-semibold text-slate-900">{item.title}</p>
                  <p className="mt-1 text-[12px] text-slate-500">{item.location}</p>
                </div>
                <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">{item.confidence}</span>
              </div>
              <p className="mt-3 rounded-2xl bg-slate-50 px-3 py-3 text-[12px] leading-5 text-slate-600">{item.quote}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-5 px-5">
        <SectionTitle title="STORM 报告计划" subtitle="先提出问题，再组织学习结构" />
        <div className="mt-3 grid gap-3">
          {reportPlan.slice(0, 5).map((item, index) => (
            <div key={item.id || index} className="rounded-[22px] bg-white p-4 shadow-sm ring-1 ring-slate-200">
              <div className="flex items-center gap-3">
                <span className="grid h-8 w-8 place-items-center rounded-2xl bg-indigo-50 text-[12px] font-semibold text-indigo-700">Q{index + 1}</span>
                <p className="min-w-0 flex-1 text-[14px] font-semibold text-slate-900">{item.title}</p>
              </div>
              <p className="mt-2 text-[12px] leading-5 text-slate-500">{item.brief || "围绕该学习问题组织概念、证据和应用。"}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-5 px-5">
        <SectionTitle title="思维导图结构" subtitle="报告分支驱动的知识图谱" />
        <div className="mt-3 rounded-[24px] border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[15px] font-semibold text-slate-900">{result.topic}</p>
              <p className="mt-1 text-[12px] text-slate-500">{result.mindMap?.nodes?.length || 0} 个节点 · {result.mindMap?.edges?.length || 0} 条关系</p>
            </div>
            <button onClick={onOpenMindMap} className="rounded-full bg-slate-900 px-3 py-2 text-[12px] font-semibold text-white">查看</button>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2">
            {mapGroups.slice(0, 6).map((node) => (
              <div key={node.id} className="min-h-[64px] rounded-2xl bg-slate-50 p-3">
                <p className="text-[12px] font-semibold text-slate-800">{node.label}</p>
                <p className="mt-1 line-clamp-2 text-[11px] leading-4 text-slate-500">{node.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mt-5 px-5">
        <SectionTitle title="复习闭环" subtitle="问题、弱点和下一步建议" />
        <div className="mt-3 rounded-[24px] bg-white p-4 shadow-sm ring-1 ring-slate-200">
          {(result.review?.questions || []).slice(0, 3).map((question, index) => (
            <div key={question.id || index} className="border-b border-slate-100 py-3 first:pt-0 last:border-b-0 last:pb-0">
              <p className="text-[13px] font-semibold text-slate-900">{question.question}</p>
              <p className="mt-1 text-[12px] leading-5 text-slate-500">{question.explanation || question.answer}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-5 px-5">
        <button onClick={onRunAgent} className="w-full rounded-[22px] bg-blue-600 px-4 py-4 text-[14px] font-semibold text-white shadow-lg shadow-blue-100">
          重新运行 Agent
        </button>
      </section>
    </div>
  );
}

function HeroMetric({ label, value }) {
  return (
    <div className="rounded-2xl bg-white/10 px-3 py-3">
      <p className="text-[18px] font-semibold text-white">{value}</p>
      <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">{label}</p>
    </div>
  );
}

function ScoreCard({ label, value, tone }) {
  const toneClass = {
    blue: "bg-blue-50 text-blue-700 ring-blue-100",
    emerald: "bg-emerald-50 text-emerald-700 ring-emerald-100",
    violet: "bg-violet-50 text-violet-700 ring-violet-100",
    amber: "bg-amber-50 text-amber-700 ring-amber-100",
  }[tone];
  return (
    <div className={`rounded-[22px] px-4 py-4 ring-1 ${toneClass}`}>
      <p className="text-[20px] font-semibold">{value}</p>
      <p className="mt-1 text-[12px] font-medium opacity-80">{label}</p>
    </div>
  );
}

function SectionTitle({ title, subtitle }) {
  return (
    <div className="flex items-end justify-between gap-3">
      <div>
        <h2 className="text-[17px] font-semibold text-slate-900">{title}</h2>
        <p className="mt-1 text-[12px] text-slate-500">{subtitle}</p>
      </div>
    </div>
  );
}

function ActionButton({ label, onClick }) {
  return (
    <button onClick={onClick} className="border-r border-white/10 px-4 py-3 text-[13px] font-semibold text-white last:border-r-0">
      {label}
    </button>
  );
}

function buildEvidenceCards(result) {
  const sourcesById = new Map((result?.sources || []).map((source) => [source.id, source]));
  return (result?.citations || []).slice(0, 4).map((citation, index) => {
    const source = sourcesById.get(citation.sourceId);
    return {
      id: citation.id || `citation-${index}`,
      title: source?.title || citation.sourceId || `引用 ${index + 1}`,
      location: [citation.sourceRef, citation.page ? `页 ${citation.page}` : ""].filter(Boolean).join(" · ") || "来源片段",
      quote: citation.quote || source?.text || "暂无 quote，运行真实后端后会展示原文证据。",
      confidence: percentText(citation.confidence),
    };
  });
}

function buildMapGroups(result) {
  const nodes = result?.mindMap?.nodes || [];
  const rootId = nodes[0]?.id || "root";
  return nodes.filter((node) => node.id !== rootId).slice(0, 8);
}

function percentText(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return `${Math.round(number * 100)}%`;
}
