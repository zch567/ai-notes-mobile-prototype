import { Card } from "../../components/Card";
import { TopBar } from "../../components/TopBar";

export function HomeScreen({ result, onStart, onOpenNote }) {
  const hasResult = Boolean(result?.topic || result?.summary || result?.notes?.length);

  return (
    <div className="space-y-5 pb-6">
      <TopBar title="智序知识助手" subtitle="把学习资料变成可追溯、可复习的知识资产" />

      <div className="px-5">
        <section className="rounded-[32px] bg-slate-950 p-5 text-white shadow-[0_20px_48px_rgba(15,23,42,0.22)]">
          <p className="text-[12px] font-semibold uppercase tracking-[0.24em] text-blue-200">Learning Loop</p>
          <h2 className="mt-3 text-[25px] font-semibold leading-tight tracking-tight">资料输入到复习反馈，一条链路跑完</h2>
          <p className="mt-3 text-[14px] leading-6 text-slate-300">
            当前版本只保留真实后端链路，先在“我的”页配置后端地址，再运行 Agent。
          </p>
          <button onClick={onStart} className="mt-5 rounded-2xl bg-white px-5 py-3 text-[14px] font-semibold text-slate-950">
            开始生成
          </button>
        </section>
      </div>

      <div className="px-5">
        <Card title="最近生成结果" subtitle="Latest Result">
          <button
            onClick={hasResult ? onOpenNote : onStart}
            className="w-full rounded-3xl border border-slate-200 bg-slate-50 p-4 text-left"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-[17px] font-semibold text-slate-900">{hasResult ? result.topic : "暂无真实生成结果"}</h3>
                <p className="mt-2 text-[13px] leading-5 text-slate-500">
                  {hasResult ? result.summary : "配置并调用后端后，这里会展示最近一次 AgentResult。"}
                </p>
              </div>
              <span className="rounded-full bg-blue-50 px-3 py-1 text-[12px] font-semibold text-blue-600">
                {hasResult ? "可追溯" : "待生成"}
              </span>
            </div>
          </button>
        </Card>
      </div>

      <div className="px-5">
        <Card title="学习路径" subtitle="Workflow">
          <div className="grid gap-3">
            {[
              ["1", "输入资料", "粘贴文本或选择公开样例，后续可接文件上传。"],
              ["2", "Agent 处理", "解析、抽取、引用绑定、生成笔记和导图。"],
              ["3", "复习反馈", "生成题目、掌握度和下一步复习建议。"],
            ].map(([index, title, desc]) => (
              <div key={index} className="flex gap-3 rounded-2xl bg-slate-50 p-3">
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-blue-600 text-[13px] font-semibold text-white">
                  {index}
                </span>
                <div>
                  <p className="text-[14px] font-semibold text-slate-900">{title}</p>
                  <p className="mt-1 text-[12px] leading-5 text-slate-500">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
