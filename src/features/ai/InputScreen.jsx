import { useEffect, useRef, useState } from "react";
import { TopBar } from "../../components/TopBar";
import { sampleInputText } from "../../data/sampleInputText";
import { DEFAULT_GENERATION_TOP_K } from "./agentApi";

const defaultDraft = {
  inputType: "text",
  sourceText: sampleInputText,
  sourceTitle: "",
  pipeline: "rag-only",
  provider: "configured",
  strictProvider: true,
  topK: DEFAULT_GENERATION_TOP_K,
};

export function InputScreen({ onRun, status, draft = defaultDraft, onDraftChange }) {
  const [sourceText, setSourceText] = useState(draft.sourceText || sampleInputText);
  const [inputType, setInputType] = useState(normalizeInputType(draft.inputType));
  const [sourceTitle, setSourceTitle] = useState(normalizeInitialTitle(draft.sourceTitle));
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileError, setFileError] = useState("");
  const [titleError, setTitleError] = useState("");
  const titleInputRef = useRef(null);
  const inputTypes = [
    ["text", "文本"],
    ["pdf", "PDF"],
    ["pptx", "PPTX"],
    ["word", "Word"],
  ];

  useEffect(() => {
    onDraftChange?.({
      inputType,
      sourceText,
      sourceTitle,
      pipeline: "hybrid",
      provider: "configured",
      strictProvider: true,
      topK: DEFAULT_GENERATION_TOP_K,
    });
  }, [inputType, sourceText, sourceTitle, onDraftChange]);

  function runCurrentInput() {
    const trimmedTitle = sourceTitle.trim();
    if (!trimmedTitle) {
      setTitleError("请先填写资料标题，再运行 Agent。");
      titleInputRef.current?.focus();
      return;
    }

    if (inputType !== "text" && !selectedFile) {
      setFileError("请先选择要上传的文件");
      return;
    }

    onRun({
      inputType,
      sourceText: inputType === "text" ? sourceText : "",
      file: inputType === "text" ? undefined : selectedFile,
      fileName: inputType === "text" ? `${safeFileStem(trimmedTitle)}.md` : selectedFile?.name,
      pipeline: "hybrid",
      strictProvider: true,
      topK: DEFAULT_GENERATION_TOP_K,
      sourceMeta: {
        title: trimmedTitle,
        fileName: inputType === "text" ? "" : selectedFile?.name || "",
        mimeType: inputType === "text" ? "text/plain" : selectedFile?.type || "",
      },
    });
  }

  function handleFileChange(event) {
    const file = event.target.files?.[0] || null;
    setSelectedFile(file);
    setFileError("");
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
              ref={titleInputRef}
              value={sourceTitle}
              onChange={(event) => {
                setSourceTitle(event.target.value);
                if (event.target.value.trim()) setTitleError("");
              }}
              placeholder="给这份资料起一个标题"
              aria-invalid={Boolean(titleError)}
              aria-describedby={titleError ? "source-title-error" : undefined}
              className={`w-full rounded-2xl border bg-white px-4 py-3 text-[14px] font-semibold text-slate-800 outline-none transition placeholder:text-slate-300 focus:shadow-sm ${
                titleError ? "border-rose-300 focus:border-rose-300" : "border-slate-200 focus:border-blue-200"
              }`}
            />
            {titleError ? (
              <p id="source-title-error" className="mt-2 text-[12px] font-medium text-rose-600">
                {titleError}
              </p>
            ) : null}
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

function normalizeInitialTitle(value) {
  const title = String(value || "").trim();
  return title === "Logistic Regression 公开样例" ? "" : title;
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
