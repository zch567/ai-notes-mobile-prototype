import { useEffect, useState } from "react";
import { Card } from "../../components/Card";
import { TopBar } from "../../components/TopBar";
import { demoInputText } from "../../data/demoAgentResult";
import { getProviderStatus } from "./agentApi";

const defaultDraft = {
  inputType: "text",
  sourceText: demoInputText,
  sourceTitle: "Logistic Regression 公开样例",
  pipeline: "hybrid",
  provider: "configured",
  strictProvider: false,
  topK: 2,
};

export function InputScreen({ onRun, status, draft = defaultDraft, onDraftChange }) {
  const [sourceText, setSourceText] = useState(draft.sourceText || demoInputText);
  const [inputType, setInputType] = useState(draft.inputType || "text");
  const [sourceTitle, setSourceTitle] = useState(draft.sourceTitle || "Logistic Regression 公开样例");
  const [pipeline, setPipeline] = useState(draft.pipeline || "hybrid");
  const [provider, setProvider] = useState(draft.provider || "configured");
  const [strictProvider, setStrictProvider] = useState(Boolean(draft.strictProvider));
  const [topK, setTopK] = useState(draft.topK || 2);
  const [providerStatus, setProviderStatus] = useState(null);
  const [providerError, setProviderError] = useState("");
  const inputTypes = [
    ["text", "文本"],
    ["pdf", "PDF"],
    ["ppt", "PPT"],
  ];
  const pipelineOptions = [
    ["hybrid", "Hybrid", "模型草稿 + RAG 引用"],
    ["rag-only", "RAG only", "离线兜底"],
  ];
  const providerOptions = [
    ["configured", "配置默认"],
    ["mock", "Mock"],
    ["lanxin", "蓝心"],
  ];

  useEffect(() => {
    onDraftChange?.({
      inputType,
      sourceText,
      sourceTitle,
      pipeline,
      provider,
      strictProvider,
      topK,
    });
  }, [inputType, sourceText, sourceTitle, pipeline, provider, strictProvider, topK, onDraftChange]);

  useEffect(() => {
    let cancelled = false;

    async function loadProviderStatus() {
      try {
        const nextStatus = await getProviderStatus();
        if (!cancelled) {
          setProviderStatus(nextStatus);
          setProviderError("");
        }
      } catch (err) {
        if (!cancelled) {
          setProviderStatus(null);
          setProviderError(err instanceof Error ? err.message : "无法读取后端状态");
        }
      }
    }

    loadProviderStatus();
    return () => {
      cancelled = true;
    };
  }, []);

  function useSample(title) {
    setSourceText(demoInputText);
    setSourceTitle(title);
    setInputType("text");
  }

  function runCurrentInput() {
    onRun({
      inputType,
      sourceText: inputType === "text" ? sourceText : "",
      fileName: `${safeFileStem(sourceTitle)}.${inputType === "text" ? "md" : inputType}`,
      pipeline,
      provider: provider === "configured" ? undefined : provider,
      strictProvider,
      topK,
      sourceMeta: {
        title: sourceTitle,
        fileName: "",
        mimeType: inputType === "text" ? "text/plain" : "",
      },
    });
  }

  return (
    <div className="space-y-5 pb-6">
      <TopBar title="AI 生成" subtitle="输入学习资料，后续由后端 AgentPipeline 处理" />

      <div className="px-5">
        <Card title="学习材料" subtitle="Input">
          <div className="mb-4 grid grid-cols-3 gap-2 rounded-2xl bg-slate-100 p-1">
            {inputTypes.map(([id, label]) => (
              <button
                key={id}
                onClick={() => setInputType(id)}
                className={`rounded-xl px-3 py-2 text-[13px] font-semibold ${
                  inputType === id ? "bg-white text-blue-600 shadow-sm" : "text-slate-500"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="mb-4 rounded-2xl border border-blue-100 bg-blue-50 px-3 py-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-blue-500">Backend</p>
                <p className="mt-1 text-[13px] leading-5 text-blue-900">
                  {providerError
                    ? `后端状态未连接：${providerError}`
                    : `默认 Provider：${providerStatus?.configuredProvider || "读取中"}${
                        providerStatus?.lanxin?.configured ? " · 蓝心已配置" : " · 蓝心未配置"
                      }`}
                </p>
              </div>
              <span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${providerError ? "bg-amber-500" : "bg-emerald-500"}`} />
            </div>
          </div>

          <div className="mb-4 space-y-3">
            <div className="grid grid-cols-2 gap-2">
              {pipelineOptions.map(([id, label, desc]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setPipeline(id)}
                  className={`rounded-2xl border px-3 py-3 text-left transition ${
                    pipeline === id ? "border-blue-200 bg-white text-blue-700 shadow-sm" : "border-slate-200 bg-slate-50 text-slate-500"
                  }`}
                >
                  <p className="text-[13px] font-semibold">{label}</p>
                  <p className="mt-1 text-[11px] leading-4">{desc}</p>
                </button>
              ))}
            </div>

            <div className="grid grid-cols-3 gap-2 rounded-2xl bg-slate-100 p-1">
              {providerOptions.map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setProvider(id)}
                  className={`rounded-xl px-2 py-2 text-[12px] font-semibold ${
                    provider === id ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-3">
              <div>
                <p className="text-[13px] font-semibold text-slate-900">引用 TopK：{topK}</p>
                <p className="mt-1 text-[11px] leading-4 text-slate-500">每条笔记最多绑定几个来源片段</p>
              </div>
              <input
                type="range"
                min="1"
                max="5"
                value={topK}
                onChange={(event) => setTopK(Number(event.target.value))}
                className="w-28 accent-blue-600"
              />
            </div>

            <label className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-3">
              <div>
                <p className="text-[13px] font-semibold text-slate-900">严格使用所选 Provider</p>
                <p className="mt-1 text-[11px] leading-4 text-slate-500">蓝心失败时不静默降级到 Mock</p>
              </div>
              <input
                type="checkbox"
                checked={strictProvider}
                onChange={(event) => setStrictProvider(event.target.checked)}
                className="h-5 w-5 accent-blue-600"
              />
            </label>
          </div>

          {inputType === "text" ? (
          <textarea
            value={sourceText}
            onChange={(event) => setSourceText(event.target.value)}
            className="h-56 w-full resize-none rounded-2xl border border-slate-200 bg-slate-50 p-4 text-[13px] leading-6 text-slate-700 outline-none focus:border-blue-300 focus:bg-white"
          />
          ) : (
            <div className="flex h-56 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-6 text-center">
              <p className="text-[15px] font-semibold text-slate-900">{inputType.toUpperCase()} 文件接入位</p>
              <p className="mt-2 text-[13px] leading-5 text-slate-500">
                前端结构已预留，后续通过 Android 文件选择或 Web 上传把文件交给后端解析。
              </p>
              <button className="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-2 text-[13px] font-semibold text-slate-600">
                选择演示样例
              </button>
            </div>
          )}

          <div className="mt-4 grid gap-2">
            {["Logistic Regression 公开样例", "课程资料整理", "考试复习闭环"].map((item) => (
              <button
                key={item}
                onClick={() => useSample(item)}
                className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-left text-[13px] font-medium text-slate-600"
              >
                {item}
              </button>
            ))}
          </div>

          <button
            onClick={runCurrentInput}
            disabled={status === "loading"}
            className="mt-4 w-full rounded-2xl bg-blue-600 px-4 py-3 text-[14px] font-semibold text-white disabled:bg-slate-300"
          >
            {status === "loading" ? "正在运行 Agent..." : "运行 Agent"}
          </button>
        </Card>
      </div>
    </div>
  );
}

function safeFileStem(value) {
  const stem = String(value || "学习资料")
    .trim()
    .replace(/[\\/:*?"<>|]+/g, "-")
    .replace(/\s+/g, "-");
  return stem || "学习资料";
}
