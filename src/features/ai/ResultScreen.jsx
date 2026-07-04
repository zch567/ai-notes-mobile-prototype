import { useState } from "react";
import { Card } from "../../components/Card";
import { TopBar } from "../../components/TopBar";
import { chatAgent, getAgentResult, queryRag, validateAgentResult } from "./agentApi";
import { deriveAgentResultInsights } from "./agentTypes";

export function ResultScreen({ result, onOpenNote, onOpenMindMap, onOpenReview, onRetry, onResultChange }) {
  const [validation, setValidation] = useState(null);
  const [validationStatus, setValidationStatus] = useState("idle");
  const [refreshStatus, setRefreshStatus] = useState("idle");
  const [refreshMessage, setRefreshMessage] = useState("");
  const [ragQuery, setRagQuery] = useState("");
  const [ragHits, setRagHits] = useState([]);
  const [ragStatus, setRagStatus] = useState("idle");
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState([]);
  const [chatStatus, setChatStatus] = useState("idle");
  const { assetSummary, qualitySummary, learningLoopState } = deriveAgentResultInsights(result);
  const recommendationText = result.review.recommendations.length
    ? result.review.recommendations.join("；")
    : "当前结果还没有复习建议，后端可在 review.recommendations 中返回下一步复习动作。";
  const diagnostics = [...result.errors, ...result.warnings];
  const meta = result._meta || {};
  const modelLog = meta.modelLog || {};
  const citationDiagnostics = result.citationDiagnostics || {};
  const qualityDiagnostics = result.qualityDiagnostics || {};
  const hasQualityDiagnostics = Boolean(Object.keys(qualityDiagnostics).length);
  const hasBackendMeta = Boolean(meta.pipeline || meta.parser || modelLog.provider || Object.keys(citationDiagnostics).length);

  async function runValidation() {
    setValidationStatus("loading");
    try {
      const report = await validateAgentResult(result);
      setValidation(report);
      setValidationStatus("success");
    } catch (err) {
      setValidation({ valid: false, message: err instanceof Error ? err.message : "校验失败" });
      setValidationStatus("error");
    }
  }

  async function refreshBackendResult() {
    if (!result.id) return;
    setRefreshStatus("loading");
    setRefreshMessage("");

    try {
      const nextResult = await getAgentResult(result.id);
      onResultChange?.(nextResult);
      setRefreshStatus("success");
      setRefreshMessage("已从后端刷新当前结果");
    } catch (err) {
      setRefreshStatus("error");
      setRefreshMessage(err instanceof Error ? err.message : "刷新失败");
    }
  }

  async function runRagQuery() {
    const query = ragQuery.trim();
    if (!query) return;

    setRagStatus("loading");
    try {
      const response = await queryRag({ resultId: result.id, query, topK: 5 });
      setRagHits(response.hits || []);
      setRagStatus("success");
    } catch (err) {
      setRagHits([{ error: err instanceof Error ? err.message : "检索失败" }]);
      setRagStatus("error");
    }
  }

  async function sendChatMessage() {
    const question = chatInput.trim();
    if (!question || !result.id || chatStatus === "loading") return;

    const userMessage = { id: `u-${Date.now()}`, role: "我", text: question, tone: "user" };
    setChatMessages((messages) => [...messages, userMessage]);
    setChatInput("");
    setChatStatus("loading");

    try {
      const response = await chatAgent({ resultId: result.id, question, topK: 3 });
      const used = Array.isArray(response.used_citations) && response.used_citations.length
        ? `\n\n引用：${response.used_citations.join("、")}`
        : "";
      setChatMessages((messages) => [
        ...messages,
        {
          id: `a-${Date.now()}`,
          role: "Agent",
          tone: "agent",
          text: `${response.answer || "后端没有返回 answer 字段。"}${used}`,
        },
      ]);
    } catch (err) {
      setChatMessages((messages) => [
        ...messages,
        {
          id: `e-${Date.now()}`,
          role: "Agent",
          tone: "agent",
          text: err instanceof Error ? `问答失败：${err.message}` : "问答失败",
        },
      ]);
    } finally {
      setChatStatus("idle");
    }
  }

  return (
    <div className="space-y-5 pb-6">
      <TopBar title="生成结果" subtitle="由统一 AgentResult 渲染" />

      <div className="space-y-5 px-5">
        <Card title={assetSummary.topic} subtitle="Learning Asset">
          <div className="flex items-start justify-between gap-3">
            <p className="min-w-0 text-[14px] leading-6 text-slate-700">{assetSummary.summary}</p>
            <span className="shrink-0 rounded-full bg-emerald-50 px-3 py-1 text-[12px] font-semibold text-emerald-700">
              {assetSummary.statusText}
            </span>
          </div>
          <div className="mt-4 grid grid-cols-3 gap-2">
            <Metric label="笔记" value={assetSummary.noteCount} />
            <Metric label="引用" value={assetSummary.citationCount} />
            <Metric label="题目" value={assetSummary.reviewQuestionCount} />
          </div>
          <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-[12px] leading-5 text-slate-500">
            {assetSummary.summaryText}
            {assetSummary.fileName ? ` 来源文件：${assetSummary.fileName}` : ""}
          </div>
        </Card>

        <LearningLoopStrip state={learningLoopState} />

        <QualitySummaryCard summary={qualitySummary} />

        <Card title="下一步动作" subtitle="Actions">
          <div className="grid grid-cols-2 gap-2">
            <button onClick={onOpenNote} className="rounded-2xl bg-blue-600 px-4 py-3 text-[13px] font-semibold text-white">
              看笔记
            </button>
            <button onClick={onOpenNote} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-[13px] font-semibold text-slate-700">
              查引用
            </button>
            <button onClick={onOpenMindMap} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-[13px] font-semibold text-slate-700">
              看导图
            </button>
            <button onClick={onOpenReview} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-[13px] font-semibold text-slate-700">
              做复习
            </button>
          </div>
        </Card>

        {hasQualityDiagnostics ? (
          <Card title="质量诊断" subtitle="Quality">
            <div className="flex items-start gap-3">
              <div className="grid h-16 w-16 shrink-0 place-items-center rounded-3xl bg-blue-600 text-white shadow-sm">
                <div className="text-center">
                  <p className="text-[22px] font-semibold leading-6">{scoreText(qualityDiagnostics.overallScore)}</p>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-blue-100">Score</p>
                </div>
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[13px] leading-5 text-slate-600">
                  {qualityDiagnostics.summaryText || "后端已返回质量诊断，本次结果可继续查看和复习。"}
                </p>
                {qualityDiagnostics.warnings?.length ? (
                  <div className="mt-2 space-y-1.5">
                    {qualityDiagnostics.warnings.slice(0, 3).map((warning) => (
                      <p key={warning} className="rounded-2xl bg-amber-50 px-3 py-2 text-[12px] leading-5 text-amber-900">
                        {warning}
                      </p>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-2">
              <QualityMetric label="产物完整" value={qualityDiagnostics.assetCompleteness} />
              <QualityMetric label="引用质量" value={qualityDiagnostics.citationScore} />
              <QualityMetric label="结构质量" value={qualityDiagnostics.structureScore} />
              <QualityMetric label="复习质量" value={qualityDiagnostics.reviewScore} />
            </div>
          </Card>
        ) : null}

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

        {hasBackendMeta ? (
          <details className="rounded-[28px] border border-slate-200 bg-white p-4 shadow-sm">
            <summary className="cursor-pointer list-none text-[15px] font-semibold text-slate-900">
              后端诊断与契约校验
              <span className="ml-2 text-[12px] font-medium text-slate-400">展开</span>
            </summary>
            <div className="mt-4">
              <div className="grid grid-cols-2 gap-2">
                <DiagnosticPill label="Pipeline" value={meta.pipeline || "unknown"} />
                <DiagnosticPill label="Provider" value={modelLog.provider || meta.requestedProvider || "unknown"} />
                <DiagnosticPill label="Model" value={modelLog.model || "未记录"} />
                <DiagnosticPill label="Status" value={modelLog.status || "unknown"} />
              </div>

              {Object.keys(citationDiagnostics).length ? (
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <Metric label="引用覆盖" value={percentText(citationDiagnostics.noteCitationCoverage)} />
                  <Metric label="Quote 命中" value={percentText(citationDiagnostics.quoteInSourceRate)} />
                </div>
              ) : null}

              <button
                onClick={runValidation}
                disabled={validationStatus === "loading"}
                className="mt-3 w-full rounded-2xl bg-slate-900 px-4 py-3 text-[13px] font-semibold text-white disabled:bg-slate-300"
              >
                {validationStatus === "loading" ? "正在校验契约..." : "校验当前 AgentResult"}
              </button>

              {validation ? (
                <div className={`mt-3 rounded-2xl px-3 py-2 text-[12px] leading-5 ${
                  validation.valid ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-900"
                }`}>
                  {validation.valid
                    ? `契约有效：sources ${validation.sourceCount} · notes ${validation.noteCount} · questions ${validation.questionCount}`
                    : validation.message || "契约校验未通过"}
                </div>
              ) : null}

              <button
                onClick={refreshBackendResult}
                disabled={refreshStatus === "loading" || !result.id}
                className="mt-3 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-[13px] font-semibold text-slate-700 disabled:bg-slate-100 disabled:text-slate-300"
              >
                {refreshStatus === "loading" ? "正在刷新..." : "从后端刷新当前结果"}
              </button>
              {refreshMessage ? (
                <p className={`mt-2 text-[12px] leading-5 ${refreshStatus === "error" ? "text-rose-600" : "text-slate-500"}`}>
                  {refreshMessage}
                </p>
              ) : null}
            </div>
          </details>
        ) : null}

        <details className="rounded-[28px] border border-slate-200 bg-white p-4 shadow-sm">
          <summary className="cursor-pointer list-none text-[15px] font-semibold text-slate-900">
            来源检索
            <span className="ml-2 text-[12px] font-medium text-slate-400">展开</span>
          </summary>
          <div className="mt-4">
          <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 shadow-sm">
            <input
              value={ragQuery}
              onChange={(event) => setRagQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") runRagQuery();
              }}
              placeholder="搜索一个概念，例如：位置编码为什么必要"
              className="min-w-0 flex-1 bg-transparent text-[13px] leading-6 text-slate-700 outline-none placeholder:text-slate-300"
            />
            <button
              onClick={runRagQuery}
              disabled={ragStatus === "loading"}
              className="rounded-2xl bg-blue-600 px-3 py-2 text-[12px] font-semibold text-white disabled:bg-slate-300"
            >
              {ragStatus === "loading" ? "检索中" : "检索"}
            </button>
          </div>

          {ragHits.length ? (
            <div className="mt-3 space-y-2">
              {ragHits.map((hit, index) => (
                <div key={hit.chunk?.id || hit.error || index} className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                  {hit.error ? (
                    <p className="text-[13px] leading-5 text-amber-900">{hit.error}</p>
                  ) : (
                    <>
                      <div className="flex items-center justify-between gap-3">
                        <p className="truncate text-[13px] font-semibold text-slate-900">{hit.chunk?.title || hit.chunk?.sourceRef || `命中 ${index + 1}`}</p>
                        <span className="shrink-0 rounded-full bg-white px-2 py-1 text-[11px] font-semibold text-blue-600 ring-1 ring-blue-100">
                          {Number(hit.score || 0).toFixed(2)}
                        </span>
                      </div>
                      <p className="mt-2 line-clamp-3 text-[12px] leading-5 text-slate-500">{hit.chunk?.text || ""}</p>
                      {hit.matchedTerms?.length ? (
                        <p className="mt-2 text-[11px] font-medium text-slate-400">匹配词：{hit.matchedTerms.join("、")}</p>
                      ) : null}
                    </>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-[12px] leading-5 text-slate-500">输入问题后可直接调用后端 `/api/rag/query`，检查来源片段召回效果。</p>
          )}
          </div>
        </details>

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
              {chatMessages.length ? (
                chatMessages.map((message) => (
                  <Message key={message.id} role={message.role} tone={message.tone} text={message.text} />
                ))
              ) : (
                <Message
                  role="Agent"
                  tone="agent"
                  text={`可以继续追问“${result.topic || "当前资料"}”。${recommendationText}`}
                />
              )}
              {chatStatus === "loading" ? <Message role="Agent" tone="agent" text="正在调用后端 M7 问答..." /> : null}
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2 rounded-[22px] border border-slate-200 bg-white px-3 py-2 shadow-sm">
            <input
              value={chatInput}
              onChange={(event) => setChatInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") sendChatMessage();
              }}
              placeholder="继续追问这份学习结果..."
              className="min-w-0 flex-1 rounded-2xl bg-slate-100 px-3 py-2 text-[13px] text-slate-700 outline-none placeholder:text-slate-400"
            />
            <button
              onClick={sendChatMessage}
              disabled={chatStatus === "loading" || !chatInput.trim() || !result.id}
              className="rounded-2xl bg-slate-900 px-4 py-2 text-[13px] font-semibold text-white disabled:bg-slate-300"
            >
              发送
            </button>
          </div>
        </Card>

        <button onClick={onRetry} className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-[14px] font-semibold text-slate-700">
          重新输入
        </button>
      </div>
    </div>
  );
}

function LearningLoopStrip({ state }) {
  return (
    <Card title="移动端学习闭环" subtitle="Learning Loop">
      <div className="grid grid-cols-6 gap-1.5">
        {state.steps.map((step, index) => (
          <div key={step.id} className="text-center">
            <div className={`mx-auto grid h-8 w-8 place-items-center rounded-full text-[12px] font-semibold ${
              step.done ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-400"
            }`}>
              {index + 1}
            </div>
            <p className={`mt-1 text-[11px] font-semibold ${step.done ? "text-slate-900" : "text-slate-400"}`}>{step.label}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-blue-600" style={{ width: `${Math.round(state.progress * 100)}%` }} />
      </div>
      <p className="mt-3 text-[12px] leading-5 text-slate-500">{state.summaryText}，下一步：{state.nextStep?.label || "继续学习"}。</p>
    </Card>
  );
}

function QualitySummaryCard({ summary }) {
  return (
    <Card title="生成质量摘要" subtitle="Observability">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="text-[42px] font-semibold leading-none tracking-tight text-slate-950">{summary.overallScore}</p>
          <p className="mt-1 text-[12px] font-semibold text-slate-400">Quality score</p>
        </div>
        <span className="mb-1 rounded-full bg-blue-50 px-3 py-1 text-[12px] font-semibold text-blue-700">{summary.level}</span>
      </div>
      <p className="mt-3 text-[13px] leading-5 text-slate-600">{summary.summaryText}</p>
      <div className="mt-4 grid grid-cols-2 gap-2">
        {summary.diagnostics.map((item) => (
          <div key={item.id} className="rounded-2xl bg-slate-50 p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-[12px] font-semibold text-slate-700">{item.label}</p>
              <p className="text-[12px] font-semibold text-blue-600">{percentText(item.value)}</p>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white">
              <div className="h-full rounded-full bg-blue-600" style={{ width: percentText(item.value) }} />
            </div>
          </div>
        ))}
      </div>
      {summary.warnings.length ? (
        <details className="mt-3 rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2">
          <summary className="cursor-pointer list-none text-[12px] font-semibold text-amber-900">查看质量诊断提示</summary>
          <div className="mt-2 space-y-1">
            {summary.warnings.map((warning) => (
              <p key={warning} className="text-[12px] leading-5 text-amber-900">{warning}</p>
            ))}
          </div>
        </details>
      ) : null}
    </Card>
  );
}

function DiagnosticPill({ label, value }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2">
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">{label}</p>
      <p className="mt-1 truncate text-[12px] font-semibold text-slate-800">{value}</p>
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

function QualityMetric({ label, value }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[12px] font-medium text-slate-500">{label}</p>
        <p className="text-[14px] font-semibold text-slate-900">{scoreText(value)}</p>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200">
        <div className="h-full rounded-full bg-blue-600" style={{ width: `${scorePercent(value)}%` }} />
      </div>
    </div>
  );
}

function percentText(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return `${Math.round(number * 100)}%`;
}

function scoreText(value) {
  const number = normalizeScore(value);
  return number === null ? "-" : String(Math.round(number));
}

function scorePercent(value) {
  const number = normalizeScore(value);
  return number === null ? 0 : number;
}

function normalizeScore(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  const scaled = number <= 1 ? number * 100 : number;
  return Math.min(Math.max(scaled, 0), 100);
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
