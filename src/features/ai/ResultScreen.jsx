import { Card } from "../../components/Card";
import { TopBar } from "../../components/TopBar";

export function ResultScreen({ result, onOpenNote, onOpenMindMap, onRetry }) {
  const citationLinkCount = result.notes.reduce((count, note) => count + note.citationIds.length, 0);
  const recommendationText = result.review.recommendations.length
    ? result.review.recommendations.join("；")
    : "当前结果还没有复习建议，后端可在 review.recommendations 中返回下一步复习动作。";
  const diagnostics = [...result.errors, ...result.warnings];

  return (
    <div className="space-y-5 pb-6">
      <TopBar title="生成结果" subtitle="由统一 AgentResult 渲染" />

      <div className="space-y-5 px-5">
        <Card title={result.topic} subtitle="Summary">
          <p className="text-[14px] leading-6 text-slate-700">{result.summary}</p>
          <div className="mt-4 grid grid-cols-3 gap-2">
            <Metric label="来源" value={result.sources.length} />
            <Metric label="笔记" value={result.notes.length} />
            <Metric label="题目" value={result.review.questions.length} />
          </div>
          <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-[12px] leading-5 text-slate-500">
            已检测到 {citationLinkCount} 个笔记引用绑定
            {result.citations.length ? `，另有 ${result.citations.length} 条 citation 审计记录。` : "。"}
          </div>
        </Card>

        {diagnostics.length ? (
          <Card title="解析提示" subtitle="Diagnostics">
            <div className="space-y-2">
              {diagnostics.map((item) => (
                <p key={item} className="rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-[13px] leading-5 text-amber-900">
                  {item}
                </p>
              ))}
            </div>
          </Card>
        ) : null}

        {result.keywords.length || result.outline.length ? (
          <Card title="资料理解" subtitle="Understanding">
            {result.keywords.length ? (
              <div className="flex flex-wrap gap-2">
                {result.keywords.map((keyword) => (
                  <span key={keyword} className="rounded-full bg-blue-50 px-3 py-1 text-[12px] font-semibold text-blue-700">
                    {keyword}
                  </span>
                ))}
              </div>
            ) : null}

            {result.outline.length ? (
              <div className="mt-4 space-y-3">
                {result.outline.map((section, index) => (
                  <div key={section.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                    <div className="flex items-center gap-2">
                      <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-slate-900 text-[11px] font-semibold text-white">
                        {index + 1}
                      </span>
                      <p className="text-[14px] font-semibold text-slate-900">{section.title}</p>
                    </div>
                    {section.brief ? <p className="mt-2 text-[12px] leading-5 text-slate-500">{section.brief}</p> : null}
                    {section.refs.length ? (
                      <p className="mt-2 text-[11px] font-medium text-slate-400">来源：{section.refs.join("、")}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : null}
          </Card>
        ) : null}

        <Card title="输出产物" subtitle="Artifacts">
          <div className="grid gap-3">
            {[
              ["结构化笔记", "notes", "按层级输出正文，并绑定来源引用。"],
              ["引用回链", "citations", "点击引用编号即可回看来源片段。"],
              ["思维导图", "mindMap", "由节点和边组成，后续可直接接图谱渲染。"],
              ["复习评估", "review", "题目、掌握度、薄弱点和建议统一渲染。"],
            ].map(([title, tag, desc]) => (
              <div key={tag} className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                <p className="text-[14px] font-semibold text-slate-900">{title}</p>
                <p className="mt-1 text-[12px] leading-5 text-slate-500">{desc}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Agent 对话框" subtitle="Follow-up">
          <div className="rounded-[24px] border border-slate-200 bg-slate-50 p-4">
            <div className="h-48 space-y-3 overflow-y-auto pr-1">
              <Message role="我" text={`把 ${result.topic} 的核心定义和易错点再总结一下。`} />
              <Message
                role="Agent"
                tone="agent"
                text="它主要用于分类任务，通过 Sigmoid 输出概率；名称里的 regression 容易让人误以为它是回归模型。"
              />
              <Message role="我" text="哪些部分适合优先复习？" />
              <Message
                role="Agent"
                tone="agent"
                text={recommendationText}
              />
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2 rounded-[22px] border border-slate-200 bg-white px-3 py-2 shadow-sm">
            <div className="h-10 flex-1 rounded-2xl bg-slate-100 px-3 py-2 text-[13px] text-slate-400">
              继续追问这份学习结果...
            </div>
            <button className="rounded-2xl bg-slate-900 px-4 py-2 text-[13px] font-semibold text-white">发送</button>
          </div>
        </Card>

        <div className="grid grid-cols-2 gap-2">
          <button onClick={onOpenNote} className="col-span-2 rounded-2xl bg-blue-600 px-4 py-3 text-[14px] font-semibold text-white">
            查看结构化笔记
          </button>
          <button onClick={onOpenMindMap} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-[14px] font-semibold text-slate-700">
            查看导图
          </button>
          <button onClick={onRetry} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-[14px] font-semibold text-slate-700">
            重新输入
          </button>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-2xl bg-slate-50 p-3 text-center">
      <p className="text-[20px] font-semibold text-slate-950">{value}</p>
      <p className="mt-1 text-[12px] text-slate-400">{label}</p>
    </div>
  );
}

function Message({ role, text, tone = "user" }) {
  const isAgent = tone === "agent";
  return (
    <div className={`rounded-2xl px-3 py-3 shadow-sm ${isAgent ? "bg-blue-600 text-white" : "bg-white text-slate-700"}`}>
      <p className={`text-[12px] font-semibold ${isAgent ? "text-blue-100" : "text-slate-500"}`}>{role}</p>
      <p className={`mt-1 text-[13px] leading-5 ${isAgent ? "text-white/90" : "text-slate-700"}`}>{text}</p>
    </div>
  );
}
