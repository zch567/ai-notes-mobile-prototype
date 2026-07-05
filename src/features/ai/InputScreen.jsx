import { useEffect, useState } from "react";
import { TopBar } from "../../components/TopBar";
import { sampleInputText } from "../../data/sampleInputText";
import { getProviderStatus } from "./agentApi";

const defaultDraft = {
  inputType: "text",
  sourceText: sampleInputText,
  sourceTitle: "Logistic Regression 公开样例",
  pipeline: "hybrid",
  provider: "configured",
  strictProvider: true,
  topK: 2,
};

export function InputScreen({ onRun, status, draft = defaultDraft, onDraftChange }) {
  const [sourceText, setSourceText] = useState(draft.sourceText || sampleInputText);
  const [inputType, setInputType] = useState(normalizeInputType(draft.inputType));
  const [sourceTitle, setSourceTitle] = useState(draft.sourceTitle || "Logistic Regression 公开样例");
  const [pipeline, setPipeline] = useState(draft.pipeline || "hybrid");
  const [provider, setProvider] = useState(draft.provider || "configured");
  const [topK, setTopK] = useState(draft.topK || 2);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileError, setFileError] = useState("");
  const [providerStatus, setProviderStatus] = useState(null);
  const [providerError, setProviderError] = useState("");
  const [configOpen, setConfigOpen] = useState(false);
  const inputTypes = [
    ["text", "文本"],
    ["pdf", "PDF"],
    ["pptx", "PPTX"],
    ["word", "Word"],
  ];
  const pipelineOptions = [
    ["hybrid", "Hybrid", "真实模型生成 + RAG 引用"],
  ];
  const providerOptions = [
    ["configured", "配置默认"],
    ["lanxin", "蓝心"],
  ];

  useEffect(() => {
    onDraftChange?.({
      inputType,
      sourceText,
      sourceTitle,
      pipeline,
      provider,
      strictProvider: true,
      topK,
    });
  }, [inputType, sourceText, sourceTitle, pipeline, provider, topK, onDraftChange]);

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

  function runCurrentInput() {
    if (inputType !== "text" && !selectedFile) {
      setFileError("请先选择要上传的文件");
      return;
    }

    onRun({
      inputType,
      sourceText: inputType === "text" ? sourceText : "",
      file: inputType === "text" ? undefined : selectedFile,
      fileName: inputType === "text" ? `${safeFileStem(sourceTitle)}.md` : selectedFile?.name,
      pipeline,
      provider: provider === "configured" ? undefined : provider,
      strictProvider: true,
      topK,
      sourceMeta: {
        title: sourceTitle,
        fileName: inputType === "text" ? "" : selectedFile?.name || "",
        mimeType: inputType === "text" ? "text/plain" : selectedFile?.type || "",
      },
    });
  }

  function handleFileChange(event) {
    const file = event.target.files?.[0] || null;
    setSelectedFile(file);
    setFileError("");
    if (file && (!sourceTitle || sourceTitle === "Logistic Regression 公开样例")) {
      setSourceTitle(file.name.replace(/\.[^.]+$/, ""));
    }
  }

  function changeInputType(nextType) {
    setInputType(nextType);
    setFileError("");
    if (nextType === "text") {
      setSelectedFile(null);
    } else if (selectedFile && !fileMatchesType(selectedFile, nextType)) {
      setSelectedFile(null);
    }
  }

  return (
    <div className="space-y-5 pb-6">
      <TopBar title="AI 生成" subtitle="输入学习资料，后续由后端 AgentPipeline 处理" />

      <div className="px-5">
        <section className="rounded-[28px] border border-slate-200 bg-white p-3 shadow-sm">
          <label className="mb-3 block">
            <span className="mb-2 block text-[12px] font-semibold uppercase tracking-[0.18em] text-slate-400">资料标题</span>
            <input
              value={sourceTitle}
              onChange={(event) => setSourceTitle(event.target.value)}
              placeholder="给这份资料起一个标题"
              className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-[14px] font-semibold text-slate-800 outline-none transition placeholder:text-slate-300 focus:border-blue-200 focus:shadow-sm"
            />
          </label>

          <div className="mb-3">
            <p className="mb-2 text-[12px] font-semibold uppercase tracking-[0.18em] text-slate-400">材料接入</p>
            <div className="grid grid-cols-4 gap-2 rounded-2xl bg-slate-100 p-1">
            {inputTypes.map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => changeInputType(id)}
                className={`rounded-xl px-3 py-2 text-[13px] font-semibold ${
                  inputType === id ? "bg-white text-blue-600 shadow-sm" : "text-slate-500"
                }`}
              >
                {label}
              </button>
            ))}
            </div>
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
                选择文件后会通过 multipart 上传到后端，再由后端解析并生成 AgentResult。
              </p>
              <label className="mt-4 cursor-pointer rounded-2xl border border-slate-200 bg-white px-4 py-2 text-[13px] font-semibold text-slate-600">
                选择文件
                <input
                  type="file"
                  accept={acceptedFileTypes(inputType)}
                  onChange={handleFileChange}
                  className="hidden"
                />
              </label>
              {selectedFile ? (
                <p className="mt-3 max-w-full truncate text-[12px] font-medium text-slate-500">{selectedFile.name}</p>
              ) : null}
              {fileError ? <p className="mt-2 text-[12px] font-medium text-rose-600">{fileError}</p> : null}
            </div>
          )}

          <button
            onClick={runCurrentInput}
            disabled={status === "loading" || (inputType !== "text" && !selectedFile)}
            className="mt-4 w-full rounded-2xl bg-blue-600 px-4 py-3 text-[14px] font-semibold text-white disabled:bg-slate-300"
          >
            {status === "loading" ? "正在运行 Agent..." : "运行 Agent"}
          </button>

          <div className="mt-4 overflow-hidden rounded-2xl border border-slate-200 bg-slate-50">
            <button
              type="button"
              onClick={() => setConfigOpen((value) => !value)}
              aria-expanded={configOpen}
              className="flex w-full items-center justify-between gap-3 px-3 py-3 text-left"
            >
              <div className="min-w-0">
                <p className="text-[13px] font-semibold text-slate-900">生成配置</p>
                <p className="mt-1 text-[11px] leading-4 text-slate-500">
                  {provider === "configured" ? "配置默认" : "蓝心"} · TopK {topK} · Strict
                </p>
              </div>
              <span className="shrink-0 rounded-full bg-white px-3 py-1 text-[12px] font-semibold text-blue-700 ring-1 ring-blue-100">
                {configOpen ? "收起" : "展开"}
              </span>
            </button>

            {configOpen ? (
              <div className="space-y-3 border-t border-slate-200 px-3 py-3">
                <div className="rounded-2xl border border-blue-100 bg-blue-50 px-3 py-3">
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

                <div className="grid gap-2">
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

                <div className="grid grid-cols-2 gap-2 rounded-2xl bg-slate-100 p-1">
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

                <div className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-3">
                  <div>
                    <p className="text-[13px] font-semibold text-slate-900">真实模型调用</p>
                    <p className="mt-1 text-[11px] leading-4 text-slate-500">后端必须调用已配置 Provider，失败时直接暴露错误</p>
                  </div>
                  <span className="rounded-full bg-emerald-50 px-3 py-1 text-[12px] font-semibold text-emerald-600">Strict</span>
                </div>
              </div>
            ) : null}
          </div>
        </section>
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

function normalizeInputType(value) {
  if (value === "pdf" || value === "pptx" || value === "word") return value;
  if (value === "ppt") return "pptx";
  if (value === "doc" || value === "docx") return "word";
  return "text";
}

function fileMatchesType(file, inputType) {
  const name = file?.name?.toLowerCase() || "";
  if (inputType === "pdf") return name.endsWith(".pdf");
  if (inputType === "pptx") return name.endsWith(".pptx");
  if (inputType === "word") return name.endsWith(".doc") || name.endsWith(".docx");
  return false;
}

function acceptedFileTypes(inputType) {
  if (inputType === "pdf") return ".pdf,application/pdf";
  if (inputType === "pptx") {
    return ".pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation";
  }
  if (inputType === "word") {
    return ".doc,.docx,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  }
  return "";
}
