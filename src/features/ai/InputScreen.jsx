import { useState } from "react";
import { Card } from "../../components/Card";
import { TopBar } from "../../components/TopBar";
import { demoInputText } from "../../data/demoAgentResult";

export function InputScreen({ onRun, status }) {
  const [sourceText, setSourceText] = useState(demoInputText);
  const [inputType, setInputType] = useState("text");
  const inputTypes = [
    ["text", "文本"],
    ["pdf", "PDF"],
    ["ppt", "PPT"],
  ];

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
                onClick={() => setSourceText(demoInputText)}
                className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-left text-[13px] font-medium text-slate-600"
              >
                {item}
              </button>
            ))}
          </div>

          <button
            onClick={() => onRun({ sourceText })}
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
