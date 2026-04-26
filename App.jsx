import React, { useEffect, useRef, useState } from "react";

const recentNotes = [
  {
    id: "math-review",
    title: "高等数学复习",
    tag: "学习",
    meta: "视频链接 · 9 分钟前",
    preview: "极限、导数与积分的核心概念已经整理成分层笔记。",
    updatedAt: "2026-04-26 09:12",
    summary:
      "整理极限、导数、积分与常见题型的复习笔记，适合在考试前快速回看。",
    sections: [
      "极限的定义、常见求法和无穷小替换",
      "导数与微分的核心公式、链式法则和应用题",
      "积分基本概念、换元法与定积分求面积",
    ],
    highlights: ["知识点分层", "例题归纳", "考前复习"],
  },
  {
    id: "product-spec",
    title: "产品需求拆解",
    tag: "工作",
    meta: "PPT 导入 · 今天 10:22",
    preview: "围绕用户留存、内容提取和 AI 摘要建立行动清单。",
    updatedAt: "2026-04-26 10:22",
    summary:
      "将需求目标、用户路径与功能边界拆分成可执行的开发清单，帮助团队统一理解。",
    sections: [
      "用户目标：快速生成可复习的结构化笔记",
      "核心能力：摘要、导图、笔记管理与搜索",
      "后续动作：补充上传入口、详情页和分享能力",
    ],
    highlights: ["需求拆解", "里程碑", "行动项"],
  },
  {
    id: "reading-notes",
    title: "阅读：知识管理",
    tag: "阅读",
    meta: "PDF 文档 · 昨天",
    preview: "将长文内容提炼为可复用的框架与关键词。",
    updatedAt: "2026-04-25 18:40",
    summary: "从知识管理主题文章中提炼可复用方法，方便后续做个人笔记系统整理。",
    sections: [
      "信息筛选：只保留可复用的概念和方法",
      "结构组织：按主题、案例和结论分层记录",
      "实践建议：定期回顾和再加工已有笔记",
    ],
    highlights: ["框架提炼", "方法总结", "长期复用"],
  },
];

const studyPaths = [
  {
    title: "把课程内容压缩成复习提纲",
    tag: "学习路径",
    desc: "从长视频里提取重点，再生成适合回看的结构化笔记。",
  },
  {
    title: "用思维导图整理章节关系",
    tag: "方法",
    desc: "把散落的概念、定义和例题组织成一棵清晰的知识树。",
  },
];

const suggestedUseCases = [
  "课程视频整理",
  "文档摘要提炼",
  "会议纪要生成",
  "知识导图复盘",
  "文本一键转笔记",
];

const libraryNotes = [
  {
    id: "ml-intro",
    title: "机器学习导论",
    category: "学习",
    source: "视频",
    updated: "12 分钟前",
    status: "已生成",
    preview: "监控学习、损失函数、训练与验证的结构化整理版本。",
    updatedAt: "2026-04-26 11:10",
    summary: "围绕机器学习基础概念整理的课堂笔记，保留了常见术语和核心流程。",
    sections: [
      "监督学习与无监督学习的区别",
      "损失函数、优化目标与模型评估",
      "训练、验证、测试集的作用",
    ],
    highlights: ["基础概念", "模型训练", "验证流程"],
  },
  {
    id: "product-review",
    title: "产品策略复盘",
    category: "工作",
    source: "PPT",
    updated: "昨天 18:20",
    status: "已编辑",
    preview: "围绕增长、留存、内容策略和行动清单做的复盘笔记。",
    updatedAt: "2026-04-25 18:20",
    summary: "基于产品策略汇报整理的复盘内容，突出增长路径和下一步的优先级。",
    sections: [
      "增长策略：拉新、激活、留存的主线",
      "内容策略：高价值内容与分发方式",
      "行动项：版本迭代与实验排期",
    ],
    highlights: ["增长复盘", "策略拆解", "版本迭代"],
  },
  {
    id: "paper-notes",
    title: "论文阅读笔记",
    category: "阅读",
    source: "PDF",
    updated: "3 天前",
    status: "含导图",
    preview: "提取研究方法、结论、限制条件和后续方向的清晰摘要。",
    updatedAt: "2026-04-23 14:05",
    summary: "论文阅读的结构化摘要，适合快速回顾研究问题、方法和结论。",
    sections: [
      "研究问题与论文目标",
      "实验方法、样本与评价指标",
      "结论、局限与后续研究方向",
    ],
    highlights: ["研究方法", "实验结果", "后续方向"],
  },
];

const resultSections = [
  {
    title: "主题摘要",
    points: ["本内容围绕 AI 笔记如何帮助学习者吸收长内容。", "系统会自动识别章节、关键词和可执行结论。"],
  },
  {
    title: "结构化输出",
    points: ["按主题拆分为层级标题、重点列表和关联说明。", "支持从链接、文本和文档同时生成统一结果。"],
  },
  {
    title: "智能标注",
    points: ["知识点", "复习重点", "待办项", "延伸阅读"],
  },
];

const mindMapBranches = [
  { title: "摘要", desc: "核心观点和一句话总结", tone: "bg-white" },
  { title: "重点", desc: "定义、公式、术语", tone: "bg-blue-50" },
  { title: "行动项", desc: "复习计划和练习题", tone: "bg-white" },
];

function TopBar({ title, subtitle, right }) {
  return (
    <div className="px-5 pt-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[12px] font-medium text-slate-400">{subtitle}</p>
          <h1 className="mt-1 text-[28px] font-semibold tracking-tight text-slate-900">{title}</h1>
        </div>
        {right}
      </div>
    </div>
  );
}

function DetailTopBar({ title, subtitle, onBack, right }) {
  return (
    <div className="px-5 pt-4">
      <div className="flex items-start justify-between gap-3">
        <button
          onClick={onBack}
          className="mt-1 flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 bg-white text-[18px] text-slate-600 shadow-sm"
          aria-label="返回"
        >
          ?
        </button>
        <div className="flex-1">
          <p className="text-[12px] font-medium text-slate-400">{subtitle}</p>
          <h1 className="mt-1 text-[28px] font-semibold tracking-tight text-slate-900">{title}</h1>
        </div>
        {right}
      </div>
    </div>
  );
}

function Card({ title, subtitle, children, className = "" }) {
  return (
    <section className={`rounded-[28px] border border-slate-200 bg-white shadow-[0_12px_30px_rgba(15,23,42,0.06)] ${className}`}>
      {(title || subtitle) && (
        <div className="border-b border-slate-100 px-4 py-4">
          {subtitle ? <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-slate-400">{subtitle}</p> : null}
          {title ? <h2 className="mt-1 text-[18px] font-semibold tracking-tight text-slate-900">{title}</h2> : null}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

function StatusBar() {
  return (
    <div className="flex items-center justify-between px-6 pt-5 text-[12px] font-medium text-slate-900">
      <span>9:41</span>
      <div className="flex items-center gap-1.5 text-slate-700">
        <span className="h-2.5 w-4 rounded-full border border-slate-300" />
        <span className="h-2.5 w-2.5 rounded-full border border-slate-300" />
        <span className="h-3 w-6 rounded-full border border-slate-300" />
      </div>
    </div>
  );
}

function HomeScreen({ goAi, openNote }) {
  return (
    <div className="space-y-5 px-5 pb-5">
      <TopBar
        title="我的笔记"
        subtitle="AI 驱动的学习中心"
        right={
          <button className="grid h-10 w-10 place-items-center rounded-full border border-slate-200 bg-white text-slate-600 shadow-sm">⋯</button>
        }
      />

      <section className="rounded-[32px] border border-slate-200 bg-gradient-to-br from-blue-50 via-white to-slate-50 p-4 shadow-sm">
        <div className="grid gap-4">
          <button onClick={goAi} className="w-full text-left active:scale-[0.99]">
            <div className="flex items-start gap-4">
              <div className="flex-1">
                <h2 className="mt-3 max-w-[240px] text-[22px] font-semibold leading-8 tracking-tight text-slate-900">
                  把视频、文档和文本变成结构化笔记
                </h2>
                <p className="mt-2 max-w-[280px] text-[13px] leading-5 text-slate-500">
                  一次输入即可生成摘要、结构化笔记和思维导图，让学习内容快速沉淀成可复用的知识资产。
                </p>
              </div>
              <div className="flex w-[118px] shrink-0 flex-col gap-2 rounded-[28px] border border-blue-100 bg-white p-3 shadow-sm">
                <div className="rounded-2xl bg-blue-600 px-3 py-3 text-center text-[13px] font-semibold text-white">开始 AI 任务</div>
                <div className="rounded-2xl bg-slate-50 px-3 py-2 text-[11px] font-medium text-slate-500">新建 AI 任务</div>
              </div>
            </div>
          </button>

          <div className="flex flex-wrap gap-2">
            {["视频链接", "PDF / PPT", "文本输入"].map((item) => (
              <span key={item} className="rounded-full bg-slate-50 px-3 py-1 text-[11px] font-medium text-slate-500">{item}</span>
            ))}
          </div>

          <div className="grid grid-cols-3 gap-2">
            {[
              { label: "摘要", value: "自动提炼" },
              { label: "笔记", value: "结构化输出" },
              { label: "导图", value: "一键生成" },
            ].map((item) => (
              <div key={item.label} className="rounded-[22px] border border-slate-200 bg-white px-3 py-3 shadow-sm">
                <p className="text-[11px] font-medium text-slate-400">{item.label}</p>
                <p className="mt-1 text-[13px] font-semibold text-slate-900">{item.value}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-[18px] font-semibold tracking-tight text-slate-900">继续学习</h2>
          <button className="text-[13px] font-medium text-blue-600">查看全部</button>
        </div>
        <div className="grid gap-3">
          {studyPaths.map((item) => (
            <button key={item.title} className="rounded-3xl border border-slate-200 bg-white p-4 text-left shadow-sm">
              <div className="inline-flex rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-600">{item.tag}</div>
              <h3 className="mt-3 text-[16px] font-semibold text-slate-900">{item.title}</h3>
              <p className="mt-2 text-[13px] leading-5 text-slate-500">{item.desc}</p>
            </button>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-[18px] font-semibold tracking-tight text-slate-900">最近笔记</h2>
          <button className="text-[13px] font-medium text-blue-600">管理库</button>
        </div>
        <div className="space-y-3">
          {recentNotes.map((item) => (
            <button
              key={item.title}
              onClick={() => openNote(item)}
              className="flex w-full items-center justify-between rounded-3xl border border-slate-200 bg-white p-4 text-left shadow-sm"
            >
              <div>
                <div className="inline-flex rounded-full bg-slate-50 px-2.5 py-1 text-[11px] font-semibold text-slate-500">{item.tag}</div>
                <h3 className="mt-3 text-[16px] font-semibold text-slate-900">{item.title}</h3>
                <p className="mt-2 text-[13px] leading-5 text-slate-500">{item.preview}</p>
                <p className="mt-2 text-[12px] text-slate-400">{item.meta}</p>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-3">
                <span className="whitespace-nowrap rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-600">打开</span>
                <span className="text-[16px] text-slate-300">→</span>
              </div>
            </button>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-[18px] font-semibold tracking-tight text-slate-900">推荐场景</h2>
          <button className="text-[13px] font-medium text-blue-600">更多</button>
        </div>
        <div className="flex flex-wrap gap-2">
          {suggestedUseCases.map((item) => (
            <span key={item} className="rounded-full border border-slate-200 bg-white px-3 py-2 text-[12px] font-medium text-slate-600 shadow-sm">{item}</span>
          ))}
        </div>
      </section>
    </div>
  );
}

function NotesScreen({ openNote }) {
  const cats = ["全部", "视频", "PDF", "PPT", "文本", "链接"];

  return (
    <div className="space-y-5 px-5 pb-5">
      <TopBar title="笔记库" subtitle="收藏、搜索和分类管理" />

      <div className="flex items-center gap-2">
        <button className="flex flex-1 items-center gap-3 rounded-3xl border border-slate-200 bg-white px-4 py-4 text-left shadow-sm">
          <span className="text-slate-400">⌕</span>
          <span className="text-[15px] text-slate-400">搜索笔记、关键词或标题...</span>
        </button>
        <button className="shrink-0 rounded-3xl border border-slate-200 bg-white px-4 py-4 text-[13px] font-medium text-slate-600 shadow-sm">排序</button>
      </div>

      <div className="flex flex-wrap gap-2">
        {cats.map((c, i) => (
          <button
            key={c}
            className={`rounded-full px-4 py-2 text-[13px] font-medium transition-colors ${
              i === 0 ? "bg-blue-600 text-white shadow-sm" : "bg-white text-slate-500 shadow-sm ring-1 ring-slate-200"
            }`}
          >
            {c}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {libraryNotes.map((note) => (
          <button
            key={note.title}
            onClick={() => openNote(note)}
            className="w-full rounded-3xl border border-slate-200 bg-white p-4 text-left shadow-sm"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="inline-flex rounded-full bg-slate-50 px-2.5 py-1 text-[11px] font-semibold text-slate-500">{note.category}</div>
              <span className="text-[16px] text-slate-300">→</span>
            </div>
            <h3 className="mt-3 text-[16px] font-semibold text-slate-900">{note.title}</h3>
            <p className="mt-2 text-[13px] leading-5 text-slate-500">{note.preview}</p>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-600">{note.source}</span>
              <span className="rounded-full bg-slate-50 px-2.5 py-1 text-[11px] font-semibold text-slate-500">{note.updated}</span>
              <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600">{note.status}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function NoteDetailScreen({ note, goBack }) {
  const [chatOpen, setChatOpen] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "你可以直接问我这篇笔记的重点、帮你压缩成提纲，或者让它更适合复习。",
    },
  ]);
  const messageListRef = useRef(null);
  const bodyRef = useRef(null);
  const noteBody = [note.summary, ...note.sections].join("\n\n");

  const fitBody = () => {
    const el = bodyRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  };

  useEffect(() => {
    if (!messageListRef.current) return;
    messageListRef.current.scrollTop = messageListRef.current.scrollHeight;
  }, [messages, chatOpen]);

  useEffect(() => {
    fitBody();
  }, [noteBody]);

  const sendMessage = () => {
    const text = chatInput.trim();
    if (!text) return;

    setMessages((prev) => [
      ...prev,
      { role: "user", text },
      {
        role: "assistant",
        text: `收到。你想让我围绕“${text}”继续整理，我可以帮你改成重点列表、复习提纲或者更口语化的版本。`,
      },
    ]);
    setChatInput("");
    setChatOpen(true);
  };

  const contentPaddingBottom = chatOpen ? "calc(40vh + 20px)" : "96px";

  return (
    <div className="relative min-h-full px-5 pt-3">
      <div style={{ paddingBottom: contentPaddingBottom }}>
        <div className="flex items-center justify-between">
          <button onClick={goBack} className="text-[14px] font-medium text-slate-500">
            返回
          </button>
          <button className="text-[14px] font-medium text-slate-900">保存</button>
        </div>

        <div className="mt-6 space-y-5">
          <div className="space-y-3">
            <p className="text-[12px] uppercase tracking-[0.24em] text-slate-400">{note.tag || note.category}</p>
            <input
              defaultValue={note.title}
              className="w-full border-0 bg-transparent p-0 text-[34px] font-normal tracking-tight text-slate-900 outline-none placeholder:text-slate-300"
              aria-label="标题"
            />
            <p className="text-[12px] text-slate-400">{note.updatedAt || note.meta}</p>
          </div>

          <div className="space-y-3">
            <p className="text-[12px] uppercase tracking-[0.24em] text-slate-400">正文</p>
            <textarea
              ref={bodyRef}
              defaultValue={noteBody}
              onInput={fitBody}
              className="w-full resize-none overflow-hidden border-0 bg-transparent p-0 text-[15px] leading-8 text-slate-700 outline-none placeholder:text-slate-300"
              aria-label="正文"
            />
          </div>
        </div>
      </div>

      <div
        className={`absolute bottom-0 left-0 right-0 z-20 overflow-hidden border-t border-slate-200 bg-white/95 backdrop-blur transition-[height] duration-300 ease-out ${
          chatOpen ? "h-[40vh]" : "h-[76px]"
        }`}
      >
        {chatOpen ? (
          <div className="flex h-full flex-col">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">AI 对话</p>
                <p className="mt-1 text-[13px] text-slate-600">围绕当前笔记继续提问</p>
              </div>
              <button onClick={() => setChatOpen(false)} className="text-[14px] font-medium text-slate-500">
                收起
              </button>
            </div>

            <div ref={messageListRef} className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
              {messages.map((message, index) => (
                <div key={`${message.role}-${index}`} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[82%] rounded-[20px] px-4 py-3 text-[14px] leading-6 ${
                      message.role === "user"
                        ? "bg-slate-900 text-white"
                        : "border border-slate-200 bg-slate-50 text-slate-700"
                    }`}
                  >
                    {message.text}
                  </div>
                </div>
              ))}
            </div>

            <div className="border-t border-slate-100 px-4 py-3">
              <div className="flex items-end gap-3 rounded-[22px] border border-slate-200 bg-white px-4 py-3">
                <button onClick={() => setChatOpen(false)} className="text-[12px] font-medium text-slate-400">
                  文档
                </button>
                <textarea
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onFocus={() => setChatOpen(true)}
                  placeholder="问 AI：帮我总结重点、扩写这一段..."
                  className="max-h-24 flex-1 resize-none border-0 bg-transparent p-0 text-[14px] leading-6 text-slate-700 outline-none placeholder:text-slate-300"
                  rows={1}
                />
                <button onClick={sendMessage} className="rounded-full bg-slate-900 px-4 py-2 text-[13px] font-medium text-white">
                  发送
                </button>
              </div>
            </div>
          </div>
        ) : (
          <button onClick={() => setChatOpen(true)} className="flex h-full w-full items-center justify-between gap-3 px-5 text-left">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">AI 对话</p>
              <p className="mt-1 text-[14px] text-slate-600">点击开始和 AI 聊聊这篇笔记</p>
            </div>
            <div className="rounded-full bg-slate-900 px-4 py-2 text-[13px] font-medium text-white">开始对话</div>
          </button>
        )}
      </div>
    </div>
  );
}

function InputScreen({ startLoading }) {
  const outputs = ["摘要", "结构化笔记", "重点提炼", "思维导图"];
  const steps = ["输入内容", "AI 分析结构", "生成笔记与导图"];

  return (
    <div className="space-y-5 px-5 pb-5">
      <TopBar title="AI 笔记创作" subtitle="把视频、文档或文本变成结构化笔记和思维导图" />

      <section className="rounded-[32px] border border-slate-200 bg-gradient-to-br from-blue-50 via-white to-slate-50 p-4 shadow-sm">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1">
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-blue-500">AI 工作台</p>
            <h2 className="mt-2 text-[20px] font-semibold tracking-tight text-slate-900">先输入内容，再让 AI 帮你整理成可复习的知识资产</h2>
            <p className="mt-2 text-[13px] leading-5 text-slate-500">
              选择来源类型后输入内容，系统会自动提炼摘要、结构化笔记、重点和思维导图。
            </p>
          </div>
          <div className="flex h-14 w-14 items-center justify-center rounded-3xl bg-blue-600 text-[18px] font-semibold text-white shadow-lg shadow-blue-200">
            AI
          </div>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2">
          {steps.map((step, index) => (
            <div key={step} className="rounded-[20px] border border-slate-200 bg-white px-3 py-3 shadow-sm">
              <p className="text-[11px] font-semibold text-blue-500">0{index + 1}</p>
              <p className="mt-1 text-[12px] font-medium leading-5 text-slate-700">{step}</p>
            </div>
          ))}
        </div>
      </section>

      <Card title="输入内容" subtitle="直接粘贴或输入">
        <div className="space-y-4">
          <div className="rounded-[24px] border border-slate-200 bg-slate-50 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <p className="text-[12px] font-semibold uppercase tracking-[0.22em] text-slate-400">可输入：</p>
                <p className="mt-1 text-[14px] font-semibold text-slate-900">视频链接 / 文本 / 文件内容</p>
              </div>
              <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-blue-600 shadow-sm">智能识别</span>
            </div>
            <textarea
              defaultValue="在这里粘贴视频链接、各种文件，或者直接输入文本..."
              className="min-h-[180px] w-full resize-none rounded-[20px] border border-slate-200 bg-white px-4 py-4 text-[15px] leading-6 text-slate-700 outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <button className="flex items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-[14px] font-medium text-slate-700 shadow-sm">
              上传文档
            </button>
            <button className="flex items-center justify-center gap-2 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-[14px] font-medium text-slate-500">
              添加附件
            </button>
          </div>

          <button
            onClick={startLoading}
            className="w-full rounded-2xl bg-blue-600 px-4 py-4 text-[15px] font-semibold text-white shadow-sm"
          >
            生成结构化笔记
          </button>
        </div>
      </Card>
    </div>
  );
}

function LoadingScreen({ phase }) {
  const items = [
    { title: "解析输入", desc: "识别内容类型与结构" },
    { title: "提取知识", desc: "提炼主题、关键词和术语" },
    { title: "生成结果", desc: "组织摘要、列表和关联关系" },
    { title: "构建导图", desc: "输出可视化知识网络" },
  ];

  return (
    <div className="flex min-h-[calc(100vh-180px)] flex-col justify-between px-5 pb-5">
      <div className="space-y-5 pt-3">
        <TopBar title="AI 处理中" subtitle="正在为你提炼结构化笔记" />
        <section className="rounded-[32px] border border-blue-100 bg-gradient-to-br from-blue-50 via-white to-slate-50 p-5 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[12px] font-semibold uppercase tracking-[0.24em] text-blue-500">智能分析</p>
              <h2 className="mt-2 text-[22px] font-semibold tracking-tight text-slate-900">正在提取主题、关键词和层级关系</h2>
            </div>
            <div className="flex h-14 w-14 items-center justify-center rounded-3xl bg-blue-600 text-white shadow-lg shadow-blue-200">AI</div>
          </div>
          <div className="mt-5 h-2 overflow-hidden rounded-full bg-blue-100">
            <div className="h-full rounded-full bg-blue-600 transition-all duration-300" style={{ width: `${20 + phase * 20}%` }} />
          </div>
          <p className="mt-2 text-[12px] font-medium text-slate-500">正在生成结果...</p>
        </section>
        <div className="grid gap-3">
          {items.map((item, index) => {
            const done = index < phase;
            const active = index === phase;
            return (
              <div key={item.title} className={`flex items-center justify-between rounded-2xl border px-4 py-3 shadow-sm ${done || active ? "border-blue-100 bg-white" : "border-slate-200 bg-slate-50"}`}>
                <div className="flex items-center gap-3">
                  <span className={`grid h-8 w-8 place-items-center rounded-full text-[12px] font-semibold ${done || active ? "bg-blue-50 text-blue-600" : "bg-slate-200 text-slate-500"}`}>{index + 1}</span>
                  <div>
                    <p className="text-[14px] font-semibold text-slate-900">{item.title}</p>
                    <p className="text-[12px] text-slate-500">{item.desc}</p>
                  </div>
                </div>
                <span className={`text-[12px] font-medium ${done ? "text-blue-600" : active ? "text-blue-500" : "text-slate-300"}`}>
                  {done ? "完成" : active ? "进行中" : "等待中"}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function ResultScreen({ goMindMap, goContinue }) {
  return (
    <div className="space-y-5 px-5 pb-5">
      <TopBar title="智能结果" subtitle="来自内容的结构化输出" />
      <Card title="主题摘要" subtitle="快速概览">
        <div className="grid gap-3">
          <div className="rounded-[22px] border border-blue-100 bg-blue-50/70 p-4">
            <p className="text-[12px] font-semibold uppercase tracking-[0.24em] text-blue-500">一句话总结</p>
            <p className="mt-2 text-[14px] leading-6 text-slate-700">这段内容说明了智能笔记应用如何帮助学习者把长内容转化为清晰、可复习的知识结构。</p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {[
              { label: "来源类型", value: "视频 + 文档" },
              { label: "提取结果", value: "摘要 + 导图" },
            ].map((item) => (
              <div key={item.label} className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
                <p className="text-[11px] font-medium text-slate-400">{item.label}</p>
                <p className="mt-1 text-[13px] font-semibold text-slate-900">{item.value}</p>
              </div>
            ))}
          </div>
        </div>
      </Card>
      <Card title="结构化笔记" subtitle="层级清晰">
        <div className="space-y-4">
          {resultSections.map((section) => (
            <div key={section.title} className="rounded-[24px] bg-slate-50 p-4">
              <div className="flex items-center justify-between">
                <h3 className="text-[15px] font-semibold text-slate-900">{section.title}</h3>
                <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-blue-600 shadow-sm">已优化</span>
              </div>
              <ul className="mt-3 space-y-2">
                {section.points.map((point) => (
                  <li key={point} className="flex items-start gap-2 text-[13px] leading-5 text-slate-600">
                    <span className="mt-2 h-1.5 w-1.5 rounded-full bg-blue-400" />
                    <span>{point}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Card>
      <Card title="智能标注" subtitle="高亮关键字">
        <div className="flex flex-wrap gap-2">
          {["智能采集", "复习重点", "主题分支", "关联关系", "待办项", "扩展阅读"].map((item) => (
            <span key={item} className="rounded-full border border-blue-100 bg-blue-50 px-3 py-2 text-[12px] font-medium text-blue-700">{item}</span>
          ))}
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3">
          <button onClick={goMindMap} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-[14px] font-semibold text-slate-700 shadow-sm">查看思维导图</button>
          <button onClick={goContinue} className="rounded-2xl bg-blue-600 px-4 py-3 text-[14px] font-semibold text-white shadow-sm">继续采集</button>
        </div>
      </Card>
    </div>
  );
}

function MindMapScreen() {
  return (
    <div className="space-y-5 px-5 pb-5">
      <TopBar title="思维导图" subtitle="" />
      <Card title="主题结构" subtitle="中心主题 + 少量分支">
        <div className="space-y-4">
          <div className="rounded-[28px] border border-slate-200 bg-slate-50 p-4 text-center">
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-blue-500">中心主题</p>
            <h3 className="mt-2 text-[20px] font-semibold tracking-tight text-slate-900">智能笔记</h3>
            <p className="mt-2 text-[13px] leading-5 text-slate-500">从学习内容中自动提炼摘要、重点和关联信息。</p>
          </div>
          <div className="space-y-3">
            {mindMapBranches.map((item) => (
              <div key={item.title} className={`rounded-[24px] border border-slate-200 ${item.tone} px-4 py-3 shadow-sm`}>
                <div className="flex items-center gap-3">
                  <span className="grid h-8 w-8 place-items-center rounded-full bg-slate-900 text-[12px] font-semibold text-white">•</span>
                  <div>
                    <p className="text-[14px] font-semibold text-slate-900">{item.title}</p>
                    <p className="text-[12px] text-slate-500">{item.desc}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div className="rounded-[24px] border border-dashed border-slate-300 bg-white px-4 py-3 text-[13px] text-slate-500">
            后续可以在这里继续扩展成更完整的可折叠图谱。
          </div>
        </div>
      </Card>
    </div>
  );
}

function ProfileScreen() {
  return (
    <div className="space-y-5 px-5 pb-5">
      <TopBar title="个人中心" subtitle="设置、偏好与账户信息" />
      <section className="rounded-[32px] border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-left text-[18px] font-semibold text-slate-900">用户信息</h2>
      </section>
      <div className="grid grid-cols-3 gap-3">
        {["0 笔记", "0 导图", "0 收藏"].map((item) => (
          <div key={item} className="rounded-3xl border border-slate-200 bg-white p-4 text-center shadow-sm">
            <p className="text-[12px] text-slate-400">{item.split(" ")[1]}</p>
            <p className="mt-2 text-[22px] font-semibold text-slate-900">{item.split(" ")[0]}</p>
          </div>
        ))}
      </div>
      <Card title="偏好设置" subtitle="个性化">
        <div className="space-y-3">
          {[
            ["默认输出语言", "中文"],
            ["摘要风格", "简洁"],
            ["导图主题", "深色高对比"],
          ].map(([l, v]) => (
            <div key={l} className="flex items-center justify-between rounded-2xl bg-slate-50 px-4 py-3">
              <div>
                <p className="text-[14px] font-semibold text-slate-900">{l}</p>
                <p className="text-[12px] text-slate-500">{v}</p>
              </div>
              <span className="text-slate-300">&gt;</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function BottomNav({ active, setNav }) {
  const tabs = [
    { id: "home", label: "首页", icon: "⌂" },
    { id: "notes", label: "笔记", icon: "≡" },
    { id: "ai", label: "AI", icon: "+" },
    { id: "mindmap", label: "导图", icon: "◌" },
    { id: "profile", label: "我的", icon: "◎" },
  ];

  return (
    <div className="border-t border-slate-200 bg-white/96 px-2 py-3 backdrop-blur">
      <div className="grid grid-cols-5 items-end gap-1">
        {tabs.map((tab) => {
          const isActive = active === tab.id;
          if (tab.id === "ai") {
            return (
              <button key={tab.id} onClick={() => setNav(tab.id)} className="relative -mt-7 flex flex-col items-center justify-center">
                <div className={`flex h-14 w-14 items-center justify-center rounded-[24px] border text-[22px] shadow-lg ${isActive ? "border-blue-500 bg-blue-600 text-white shadow-blue-200" : "border-blue-200 bg-blue-500 text-white shadow-blue-100"}`}>
                  {tab.icon}
                </div>
                <span className={`mt-1 text-[11px] font-medium ${isActive ? "text-blue-700" : "text-slate-400"}`}>{tab.label}</span>
              </button>
            );
          }
          return (
            <button
              key={tab.id}
              onClick={() => setNav(tab.id)}
              className={`flex flex-col items-center justify-center rounded-2xl px-2 py-2 text-[11px] font-medium ${isActive ? "bg-blue-50 text-blue-700" : "text-slate-400"}`}
            >
              <span className="text-[18px] leading-none">{tab.icon}</span>
              <span className="mt-1">{tab.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function App() {
  const [nav, setNav] = useState("home");
  const [aiFlow, setAiFlow] = useState("input");
  const [phase, setPhase] = useState(0);
  const [activeNote, setActiveNote] = useState(null);

  useEffect(() => {
    if (nav !== "ai" || aiFlow !== "loading") return undefined;
    setPhase(0);
    const timers = [
      setTimeout(() => setPhase(1), 300),
      setTimeout(() => setPhase(2), 800),
      setTimeout(() => setPhase(3), 1200),
      setTimeout(() => setPhase(4), 1600),
      setTimeout(() => setAiFlow("result"), 2100),
    ];
    return () => timers.forEach(clearTimeout);
  }, [nav, aiFlow]);

  const handleNav = (next) => {
    setNav(next);
    if (next === "ai") setAiFlow("input");
    if (activeNote) setActiveNote(null);
  };

  const openNote = (note) => {
    setActiveNote(note);
    setNav("notes");
  };

  const screen =
    activeNote ? (
      <NoteDetailScreen
        note={activeNote}
        goBack={() => {
          setActiveNote(null);
          setNav("notes");
        }}
      />
    ) : nav === "home" ? <HomeScreen goAi={() => handleNav("ai")} openNote={openNote} /> :
    nav === "notes" ? <NotesScreen openNote={openNote} /> :
    nav === "ai" ? (
      aiFlow === "input" ? <InputScreen startLoading={() => setAiFlow("loading")} /> :
      aiFlow === "loading" ? <LoadingScreen phase={phase} /> :
      <ResultScreen onMindMap={() => setNav("mindmap")} goMindMap={() => setNav("mindmap")} goContinue={() => { setAiFlow("input"); setNav("ai"); }} />
    ) :
    nav === "mindmap" ? <MindMapScreen /> :
    <ProfileScreen />;

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,#eff6ff_0%,#f8fafc_36%,#ffffff_80%)] px-4 py-6 text-slate-900">
      <div className="relative mx-auto flex h-[calc(100vh-3rem)] max-w-[430px] flex-col overflow-hidden rounded-[40px] border border-slate-200 bg-slate-100 shadow-[0_24px_80px_rgba(15,23,42,0.12)]">
        <StatusBar />
        <div className={`flex-1 overflow-y-auto ${activeNote ? "pb-5" : "pb-28"}`}>{screen}</div>
        {activeNote ? null : (
          <div className="absolute bottom-0 left-0 right-0 z-20">
            <BottomNav active={nav} setNav={handleNav} />
          </div>
        )}
      </div>
    </div>
  );
}
