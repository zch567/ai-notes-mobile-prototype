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
      "一、内容总览",
      "二、核心知识模块",
      "三、知识点关系",
      "四、全局重点总结",
      "五、复习汇总",
    ],
    keywords: ["极限", "导数", "积分", "题型"],
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
      "一、内容总览",
      "二、核心知识模块",
      "三、知识点关系",
      "四、全局重点总结",
      "五、复习汇总",
    ],
    keywords: ["需求拆解", "里程碑", "行动项"],
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
      "一、内容总览",
      "二、核心知识模块",
      "三、知识点关系",
      "四、全局重点总结",
      "五、复习汇总",
    ],
    keywords: ["框架提炼", "方法总结", "长期复用"],
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
      "一、内容总览",
      "二、核心知识模块",
      "三、知识点关系",
      "四、全局重点总结",
      "五、复习汇总",
    ],
    keywords: ["基础概念", "模型训练", "验证流程"],
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
      "一、内容总览",
      "二、核心知识模块",
      "三、知识点关系",
      "四、全局重点总结",
      "五、复习汇总",
    ],
    keywords: ["增长复盘", "策略拆解", "版本迭代"],
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
      "一、内容总览",
      "二、核心知识模块",
      "三、知识点关系",
      "四、全局重点总结",
      "五、复习汇总",
    ],
    keywords: ["研究方法", "实验结果", "后续方向"],
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

const mindMapDirectory = [
  {
    id: "math-map",
    title: "高等数学导图",
    tag: "学习",
    updated: "9 分钟前",
    preview: "把极限、导数和积分整理成一个便于复习的层级目录。",
    children: ["极限", "导数", "积分", "常见题型"],
  },
  {
    id: "product-map",
    title: "产品需求导图",
    tag: "工作",
    updated: "今天 10:22",
    preview: "围绕用户目标、核心能力和后续动作建立清晰的结构树。",
    children: ["用户目标", "核心能力", "边界约束", "行动项"],
  },
  {
    id: "reading-map",
    title: "知识管理导图",
    tag: "阅读",
    updated: "昨天",
    preview: "把长文拆成框架、方法和实践建议，便于回顾。",
    children: ["信息筛选", "结构组织", "实践建议"],
  },
  {
    id: "paper-map",
    title: "论文阅读导图",
    tag: "研究",
    updated: "3 天前",
    preview: "把研究问题、实验方法和结论整理成清晰的导图目录。",
    children: ["研究问题", "实验方法", "结论", "后续方向"],
  },
];

const mindMapViewerData = {
  "math-map": {
    title: "高等数学",
    intro: "把极限、导数、积分和常见题型整理成一个适合复习的知识树。",
    centerLabel: "高数复习",
    resources: ["极限题型清单", "导数公式速记", "积分面积案例"],
    branches: [
      { id: "limits", title: "极限", desc: "定义、求法、无穷小替换", x: 16, y: 22, line: "#fb923c", fill: "#ffedd5" },
      { id: "derivative", title: "导数", desc: "链式法则、微分、应用题", x: 18, y: 50, line: "#38bdf8", fill: "#e0f2fe" },
      { id: "integral", title: "积分", desc: "换元法、定积分与面积", x: 17, y: 78, line: "#a855f7", fill: "#f3e8ff" },
      { id: "exercises", title: "题型", desc: "选择题、计算题、证明题", x: 84, y: 28, line: "#22c55e", fill: "#dcfce7" },
      { id: "mistakes", title: "易错点", desc: "符号、边界、步骤遗漏", x: 86, y: 52, line: "#eab308", fill: "#fef3c7" },
      { id: "review", title: "复习建议", desc: "按题型分段回看，搭配例题", x: 84, y: 76, line: "#0ea5e9", fill: "#dbeafe" },
    ],
  },
  "product-map": {
    title: "产品需求",
    intro: "围绕用户目标、核心能力和后续动作建立一棵清晰的需求树。",
    centerLabel: "需求拆解",
    resources: ["用户目标梳理", "核心能力清单", "版本排期建议"],
    branches: [
      { id: "goal", title: "用户目标", desc: "快速生成结构化笔记", x: 16, y: 22, line: "#fb923c", fill: "#ffedd5" },
      { id: "capability", title: "核心能力", desc: "摘要、导图、搜索、管理", x: 18, y: 50, line: "#38bdf8", fill: "#e0f2fe" },
      { id: "boundary", title: "边界约束", desc: "移动端优先，复杂度可控", x: 17, y: 78, line: "#a855f7", fill: "#f3e8ff" },
      { id: "action", title: "行动项", desc: "补入口、详情页、分享", x: 84, y: 28, line: "#22c55e", fill: "#dcfce7" },
      { id: "risk", title: "风险", desc: "交互分散，信息过载", x: 86, y: 52, line: "#eab308", fill: "#fef3c7" },
      { id: "iteration", title: "迭代", desc: "先目录，再联动 AI", x: 84, y: 76, line: "#0ea5e9", fill: "#dbeafe" },
    ],
  },
  "reading-map": {
    title: "知识管理",
    intro: "把长文拆成框架、方法和实践建议，便于快速回顾。",
    centerLabel: "阅读笔记",
    resources: ["信息筛选方法", "结构组织模板", "复盘清单"],
    branches: [
      { id: "filter", title: "信息筛选", desc: "只保留可复用的概念", x: 16, y: 22, line: "#fb923c", fill: "#ffedd5" },
      { id: "structure", title: "结构组织", desc: "主题、案例、结论三层", x: 18, y: 50, line: "#38bdf8", fill: "#e0f2fe" },
      { id: "practice", title: "实践建议", desc: "定期回顾并再加工", x: 17, y: 78, line: "#a855f7", fill: "#f3e8ff" },
      { id: "tags", title: "关键词", desc: "把关键词和摘要串起来", x: 84, y: 28, line: "#22c55e", fill: "#dcfce7" },
      { id: "review", title: "复习", desc: "按周回看笔记碎片", x: 86, y: 52, line: "#eab308", fill: "#fef3c7" },
      { id: "export", title: "导出", desc: "转成可复用目录", x: 84, y: 76, line: "#0ea5e9", fill: "#dbeafe" },
    ],
  },
  "paper-map": {
    title: "论文阅读",
    intro: "把研究问题、实验方法和结论整理成清晰的导图目录。",
    centerLabel: "论文复盘",
    resources: ["研究问题卡片", "实验方法图", "结论与局限"],
    branches: [
      { id: "question", title: "研究问题", desc: "论文到底解决什么", x: 16, y: 22, line: "#fb923c", fill: "#ffedd5" },
      { id: "method", title: "实验方法", desc: "样本、指标、流程", x: 18, y: 50, line: "#38bdf8", fill: "#e0f2fe" },
      { id: "result", title: "结论", desc: "主要发现和数据结果", x: 17, y: 78, line: "#a855f7", fill: "#f3e8ff" },
      { id: "limits", title: "局限", desc: "样本、条件和偏差", x: 84, y: 28, line: "#22c55e", fill: "#dcfce7" },
      { id: "followup", title: "后续方向", desc: "还能怎么拓展", x: 86, y: 52, line: "#eab308", fill: "#fef3c7" },
      { id: "notes", title: "笔记", desc: "摘录成复习条目", x: 84, y: 76, line: "#0ea5e9", fill: "#dbeafe" },
    ],
  },
};

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
          ←
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
                  把文档和文本变成结构化笔记
                </h2>
                <p className="mt-2 max-w-[280px] text-[13px] leading-5 text-slate-500">
                  一次输入即可生成摘要、结构化笔记和思维导图，让学习内容快速沉淀成可复用的知识资产。
                </p>
              </div>
                <div className="flex w-[118px] shrink-0 flex-col gap-2 rounded-[28px] border border-blue-100 bg-white p-3 shadow-sm">
                  <div className="rounded-2xl bg-blue-600 px-3 py-3 text-center text-[13px] font-semibold text-white">开始 AI 任务</div>
                </div>
            </div>
          </button>

          <div className="flex flex-wrap gap-2">
            {["PDF / PPT", "文本输入"].map((item) => (
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
          <h2 className="text-[18px] font-semibold tracking-tight text-slate-900">最近笔记</h2>
        </div>
      <div className="space-y-3">
          {recentNotes.map((item) => (
            <button
              key={item.title}
              onClick={() => openNote(item)}
              className="relative w-full rounded-3xl border border-slate-200 bg-white p-4 pt-4 text-left shadow-sm"
            >
              <div>
                <h3 className="mt-1 text-[16px] font-semibold text-slate-900">{item.title}</h3>
                <p className="mt-2 text-[13px] leading-5 text-slate-500">{item.preview}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {item.keywords.map((keyword) => (
                    <span
                      key={keyword}
                      className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-medium text-slate-500"
                    >
                      {keyword}
                    </span>
                  ))}
                </div>
              </div>
              <span className="absolute right-4 top-5 whitespace-nowrap text-[12px] font-medium text-slate-400">{item.updatedAt}</span>
            </button>
          ))}
        </div>
      </section>

    </div>
  );
}

function NotesScreen({ openNote }) {
  return (
    <div className="space-y-5 px-5 pb-5">
      <TopBar title="笔记库" subtitle="收藏、搜索和分类管理" />

      <div className="flex items-center gap-2">
        <button className="flex flex-1 items-center gap-3 rounded-3xl border border-slate-200 bg-white px-4 py-4 text-left shadow-sm">
          <span className="text-slate-400">⌕</span>
          <span className="text-[15px] text-slate-400">搜索笔记、关键词或标题...</span>
        </button>
      </div>

      <div className="space-y-3">
        {libraryNotes.map((note) => (
          <button
            key={note.title}
            onClick={() => openNote(note)}
            className="w-full rounded-3xl border border-slate-200 bg-white p-4 text-left shadow-sm"
          >
            <div className="flex items-start justify-between gap-3">
              <span className="text-[12px] font-medium text-slate-400">{note.updated}</span>
            </div>
            <h3 className="mt-3 text-[16px] font-semibold text-slate-900">{note.title}</h3>
            <p className="mt-2 text-[13px] leading-5 text-slate-500">{note.preview}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {note.keywords.map((keyword) => (
                <span
                  key={keyword}
                  className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-medium text-slate-500"
                >
                  {keyword}
                </span>
              ))}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function NoteDetailScreen({ note, goBack, openConfig }) {
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
  const noteBody = note.sections.join("\n\n");

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
    <div className="relative h-full px-5 pt-3">
      <div style={{ paddingBottom: contentPaddingBottom }}>
        <div className="relative flex items-center justify-between">
          <button onClick={goBack} className="relative z-10 text-[14px] font-medium text-slate-500">
            返回
          </button>
          <div className="pointer-events-none absolute inset-x-0 top-1/2 -translate-y-1/2">
            <div className="relative flex items-center justify-start gap-3 pl-12">
              <button className="pointer-events-auto flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white text-[16px] leading-none text-slate-300 shadow-sm">
                ↺
              </button>
              <button className="pointer-events-auto flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white text-[16px] leading-none text-slate-300 shadow-sm">
                ↻
              </button>
              <span className="pointer-events-none absolute left-1/2 -translate-x-1/2 text-center text-[12px] font-medium tracking-[0.18em] text-slate-400">
                笔记将会自动保存
              </span>
            </div>
          </div>
          <button onClick={openConfig} className="relative z-10 text-[14px] font-medium text-slate-900">
            配置
          </button>
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
              <div className="flex items-center gap-3 rounded-[22px] border border-slate-200 bg-white px-4 py-3">
                <button
                  onClick={() => setChatOpen(false)}
                  className="flex h-10 items-center justify-center self-center text-[12px] font-medium leading-none text-slate-400"
                >
                  文档
                </button>
                <textarea
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onFocus={() => setChatOpen(true)}
                  placeholder="问 AI：帮我总结重点、扩写这一段..."
                  className="max-h-24 flex-1 resize-none border-0 bg-transparent py-2 text-[14px] leading-6 text-slate-700 outline-none placeholder:text-slate-300"
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

function ConfigScreen({ goBack }) {
  const [reviewModeOn, setReviewModeOn] = useState(true);
  const groups = [
    { title: "复习模式", toggle: true },
    { title: "修改笔记架构", chevron: true },
    // 后续新增设置项时，直接继续往这里追加即可。
  ];

  return (
    <div className="flex h-full flex-col bg-slate-100 px-6 pt-4">
      <div className="flex items-center justify-between pb-5">
        <button onClick={goBack} className="text-[14px] font-medium text-slate-500">
          返回
        </button>
        <div className="text-[14px] font-medium text-slate-900">配置</div>
        <div className="w-[52px]" />
      </div>

      <div className="space-y-0">
        {groups.map((group) => (
          <div key={group.title} className="border-t border-slate-200 py-5 first:border-t-0 first:pt-0">
            <div className="flex items-center justify-between gap-4">
              <h2 className="text-[28px] font-medium leading-[1.1] tracking-tight text-slate-900">{group.title}</h2>
              {group.toggle ? (
                <button
                  type="button"
                  onClick={() => setReviewModeOn((value) => !value)}
                  className={`relative h-8 w-[72px] rounded-full transition-colors duration-200 ${
                    reviewModeOn ? "bg-emerald-400" : "bg-slate-300"
                  }`}
                  aria-pressed={reviewModeOn}
                  aria-label="复习模式开关"
                >
                  <span
                    className={`absolute top-1 h-6 w-6 rounded-full bg-white shadow-[0_2px_8px_rgba(15,23,42,0.18)] transition-all duration-200 ${
                    reviewModeOn ? "left-[40px]" : "left-1"
                  }`}
                  />
                </button>
              ) : group.chevron ? (
                <span className="text-[28px] leading-none text-slate-300">{"\u003e"}</span>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function InputScreen({ startLoading }) {
  const outputs = ["摘要", "结构化笔记", "重点提炼", "思维导图"];
  const steps = ["输入内容", "AI 分析结构", "生成笔记与导图"];

  return (
    <div className="space-y-5 px-5 pb-5">
      <TopBar title="AI 笔记创作" subtitle="把文档或文本变成结构化笔记和思维导图" />

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
                <p className="mt-1 text-[14px] font-semibold text-slate-900">文档 / 文本 / 文件内容</p>
              </div>
              <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-blue-600 shadow-sm">智能识别</span>
            </div>
            <textarea
              defaultValue="在这里粘贴文件内容、各种文档，或者直接输入文本..."
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
        <div className="rounded-[22px] border border-blue-100 bg-blue-50/70 p-4">
          <p className="text-[12px] font-semibold uppercase tracking-[0.24em] text-blue-500">一句话总结</p>
          <p className="mt-2 text-[14px] leading-6 text-slate-700">这份内容先把长内容压缩成可复习的结构化知识，再按重点继续展开。</p>
        </div>
      </Card>
      <Card title="结果预览" subtitle="先看输出长什么样">
        <div className="space-y-3">
          <div className="rounded-[24px] border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-slate-400">预览内容</p>
            <h3 className="mt-2 text-[16px] font-semibold text-slate-900">结构化笔记的核心内容</h3>
            <p className="mt-2 text-[13px] leading-6 text-slate-600">系统会把原始内容整理成摘要、重点、分支和后续行动，方便继续阅读或继续编辑。</p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button onClick={goMindMap} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-[14px] font-semibold text-slate-700 shadow-sm">查看思维导图</button>
            <button onClick={goContinue} className="rounded-2xl bg-blue-600 px-4 py-3 text-[14px] font-semibold text-white shadow-sm">继续采集</button>
          </div>
        </div>
      </Card>
      <Card title="AI 对话框" subtitle="用于改进结果">
        <div className="space-y-3">
          <div className="rounded-[24px] border border-slate-200 bg-slate-50 p-4">
            <div className="h-56 space-y-3 overflow-y-auto pr-1">
              <div className="rounded-2xl bg-white px-3 py-3 shadow-sm">
                <p className="text-[12px] font-semibold text-slate-500">我</p>
                <p className="mt-1 text-[13px] leading-5 text-slate-700">把这一段再压缩一点，保留最核心的定义和结论。</p>
              </div>
              <div className="rounded-2xl bg-blue-600 px-3 py-3 text-white shadow-sm">
                <p className="text-[12px] font-semibold text-blue-100">AI</p>
                <p className="mt-1 text-[13px] leading-5 text-white/90">可以，我会优先保留主题句、关键结论和下一步动作。</p>
              </div>
              <div className="rounded-2xl bg-white px-3 py-3 shadow-sm">
                <p className="text-[12px] font-semibold text-slate-500">我</p>
                <p className="mt-1 text-[13px] leading-5 text-slate-700">再补充一点，把适合复习的关键词也一起留下。</p>
              </div>
              <div className="rounded-2xl bg-blue-600 px-3 py-3 text-white shadow-sm">
                <p className="text-[12px] font-semibold text-blue-100">AI</p>
                <p className="mt-1 text-[13px] leading-5 text-white/90">收到，我会把关键词、定义和结论一起整理进结果里。</p>
              </div>
            </div>
          </div>
          <div className="rounded-[24px] border border-slate-200 bg-white px-4 py-3 shadow-sm">
            <p className="text-[12px] font-medium text-slate-400">输入对话内容</p>
            <div className="mt-3 flex items-center gap-2">
              <div className="h-10 flex-1 rounded-2xl bg-slate-100 px-3 py-2 text-[13px] text-slate-400">继续让 AI 帮你改进结果...</div>
              <button className="rounded-2xl bg-slate-900 px-4 py-2 text-[13px] font-semibold text-white">发送</button>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}

function MindMapScreen({ selectedMap, setSelectedMap }) {
  const [selectedNodeId, setSelectedNodeId] = useState(null);



  if (selectedMap) {
    const detail = mindMapViewerData[selectedMap];
    const activeBranch =
      selectedNodeId && selectedNodeId !== "center" ? detail?.branches.find((branch) => branch.id === selectedNodeId) : null;
    const activeNodeTitle = selectedNodeId === "center" ? detail?.centerLabel || "导图中心" : activeBranch?.title || "节点选项";
    const activeNodeDesc =
      selectedNodeId === "center"
        ? detail?.intro || "点击一个节点后，工作台会从另一侧弹出。"
        : activeBranch?.desc || "点击节点后会弹出对应的工作台选项。";
    const workbenchOpen = Boolean(selectedNodeId);
    const workbenchOnLeft = selectedNodeId && selectedNodeId !== "center" ? (activeBranch?.x ?? 0) >= 50 : false;
    const shiftX = workbenchOpen ? 50 - (selectedNodeId === "center" ? 50 : activeBranch?.x ?? 50) : 0;
    const shiftY = workbenchOpen ? 50 - (selectedNodeId === "center" ? 50 : activeBranch?.y ?? 50) : 0;

    return (
      <div className="relative h-full w-full overflow-hidden bg-slate-100">
        <div className={`flex h-full w-full ${workbenchOpen ? (workbenchOnLeft ? "flex-row-reverse" : "flex-row") : "flex-row"}`}>
          <div className={`relative h-full min-w-0 overflow-hidden bg-slate-100 ${workbenchOpen ? "w-[60%]" : "w-full"}`}>
            <button
              onClick={() => {
                setSelectedMap(null);
                setSelectedNodeId(null);
              }}
              className="absolute left-4 top-4 z-30 rounded-full border border-slate-200 bg-white px-4 py-2 text-[14px] font-medium text-slate-600 shadow-sm"
            >
              返回
            </button>

            <div className="absolute inset-0 bg-slate-100">
              <div
                className="absolute inset-0 transition-transform duration-300 ease-out"
                style={workbenchOpen ? { transform: `translate3d(${shiftX}%, ${shiftY}%, 0)` } : undefined}
              >
                <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                  {detail?.branches.map((branch) => {
                    const sideX = branch.x < 50 ? 38 : 62;
                    const controlY = branch.y < 50 ? 35 : 65;
                    const path = `M 50 50 C ${sideX} ${controlY}, ${sideX} ${branch.y}, ${branch.x} ${branch.y}`;
                    return <path key={branch.id} d={path} fill="none" stroke={branch.line} strokeWidth="1.4" strokeLinecap="round" opacity="0.8" />;
                  })}
                </svg>

                <button
                  onClick={() => setSelectedNodeId("center")}
                  className={`absolute left-1/2 top-1/2 z-10 w-[138px] -translate-x-1/2 -translate-y-1/2 rounded-[28px] border px-4 py-4 text-center shadow-[0_18px_34px_rgba(15,23,42,0.1)] ${
                    selectedNodeId === "center" ? "border-blue-300 bg-white ring-2 ring-blue-200" : "border-blue-200 bg-white"
                  }`}
                >
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-blue-500">中心主题</p>
                  <h3 className="mt-2 text-[18px] font-semibold tracking-tight text-slate-900">{detail?.centerLabel || "导图"}</h3>
                </button>

                {detail?.branches.map((branch) => (
                  <button
                    key={branch.id}
                    onClick={() => setSelectedNodeId(branch.id)}
                    className={`absolute z-10 max-w-[160px] rounded-[22px] border px-3 py-3 text-left shadow-sm transition-transform ${
                      selectedNodeId === branch.id ? "scale-[1.04] ring-2 ring-blue-200" : "bg-white"
                    }`}
                    style={{
                      left: `${branch.x}%`,
                      top: `${branch.y}%`,
                      transform: "translate(-50%, -50%)",
                      borderColor: branch.line,
                      backgroundColor: branch.fill,
                    }}
                  >
                    <p className="text-[12px] font-semibold text-slate-900">{branch.title}</p>
                    <p className="mt-1 text-[11px] leading-4 text-slate-600">{branch.desc}</p>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {workbenchOpen ? (
            <aside className="h-full w-[40%] flex-shrink-0 border-l border-slate-200 bg-white/95 px-4 py-4 shadow-[0_12px_40px_rgba(15,23,42,0.08)]">
              <div className="flex h-full flex-col">
                <div className="space-y-1">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">工作台</p>
                  <h4 className="text-[20px] font-semibold tracking-tight text-slate-900">{activeNodeTitle}</h4>
                  <p className="text-[12px] leading-5 text-slate-500">{activeNodeDesc}</p>
                </div>

                <div className="mt-4 grid grid-cols-2 gap-2">
                  {["新增分支", "新增子笔记", "重命名", "删除", "AI 扩写", "AI 压缩"].map((item) => (
                    <button
                      key={item}
                      className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 text-[13px] font-medium text-slate-700 shadow-sm"
                    >
                      {item}
                    </button>
                  ))}
                </div>

                <div className="mt-4 rounded-[24px] border border-dashed border-slate-200 bg-slate-50 px-4 py-4">
                  <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-slate-400">节点操作预览</p>
                  <div className="mt-3 space-y-2 text-[13px] leading-5 text-slate-600">
                    <p>• 这里先保留前端交互骨架，不接真实编辑逻辑。</p>
                    <p>• 后续可以把这些按钮接到分支创建、子节点管理和 AI 工具上。</p>
                    <p>• 当前点击其它节点，工作台会切换并重新居中导图。</p>
                  </div>
                </div>
              </div>
            </aside>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5 px-4 pb-6">
      <TopBar
        title="导图"
        subtitle=""
      />

      <div className="flex items-center gap-2">
        <button className="flex flex-1 items-center gap-3 rounded-3xl border border-slate-200 bg-white px-4 py-4 text-left shadow-sm">
          <span className="text-slate-400">⌕</span>
          <span className="text-[15px] text-slate-400">搜索导图、主题或关键词...</span>
        </button>
        <button className="shrink-0 rounded-3xl border border-slate-200 bg-white px-4 py-4 text-[13px] font-medium text-slate-600 shadow-sm">
          排序
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {["全部", "学习", "工作", "阅读", "研究"].map((item, index) => (
          <button
            key={item}
            className={`rounded-full px-4 py-2 text-[13px] font-medium transition-colors ${
              index === 0 ? "bg-blue-600 text-white shadow-sm" : "bg-white text-slate-500 shadow-sm ring-1 ring-slate-200"
            }`}
          >
            {item}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {mindMapDirectory.map((item) => (
          <button
            key={item.id}
            onClick={() => {
              setSelectedMap(item.id);
              setSelectedNodeId(null);
            }}
            className="w-full rounded-[28px] border border-slate-200 bg-white p-4 text-left shadow-sm"
          >
            <div className="flex items-start gap-3">
              <div className="min-w-0">
                <div className="inline-flex rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-500 shadow-sm ring-1 ring-slate-200">
                  {item.tag}
                </div>
                <h3 className="mt-3 text-[16px] font-semibold text-slate-900">{item.title}</h3>
                <p className="mt-2 text-[13px] leading-5 text-slate-500">{item.preview}</p>
                <p className="mt-3 text-[12px] text-slate-400">{item.updated}</p>
              </div>
            </div>
          </button>
        ))}
      </div>
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
  const [noteView, setNoteView] = useState("note");
  const [mindMapSelectedMap, setMindMapSelectedMap] = useState(null);

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
    if (activeNote) {
      setActiveNote(null);
      setNoteView("note");
    }
    if (next !== "mindmap") setMindMapSelectedMap(null);
  };

  const openNote = (note) => {
    setActiveNote(note);
    setNoteView("note");
    setNav("notes");
  };

  const screen =
    activeNote ? (
      noteView === "config" ? (
        <ConfigScreen
          goBack={() => {
            setNoteView("note");
          }}
        />
      ) : (
        <NoteDetailScreen
          note={activeNote}
          goBack={() => {
            setActiveNote(null);
            setNoteView("note");
            setNav("notes");
          }}
          openConfig={() => setNoteView("config")}
        />
      )
    ) : nav === "home" ? <HomeScreen goAi={() => handleNav("ai")} openNote={openNote} /> :
    nav === "notes" ? <NotesScreen openNote={openNote} /> :
    nav === "ai" ? (
      aiFlow === "input" ? <InputScreen startLoading={() => setAiFlow("loading")} /> :
      aiFlow === "loading" ? <LoadingScreen phase={phase} /> :
      <ResultScreen onMindMap={() => setNav("mindmap")} goMindMap={() => setNav("mindmap")} goContinue={() => { setAiFlow("input"); setNav("ai"); }} />
    ) :
    nav === "mindmap" ? <MindMapScreen selectedMap={mindMapSelectedMap} setSelectedMap={setMindMapSelectedMap} /> :
    <ProfileScreen />;

  const landscapeMindMap = nav === "mindmap" && mindMapSelectedMap !== null;
  const showBottomNav = !activeNote && !landscapeMindMap;

  return (
    <div
      className={`min-h-screen bg-[radial-gradient(circle_at_top,#eff6ff_0%,#f8fafc_36%,#ffffff_80%)] text-slate-900 ${
        landscapeMindMap ? "flex items-center justify-center overflow-hidden px-0 py-0" : "px-4 py-6"
      }`}
    >
      <div
        className={`relative mx-auto flex overflow-hidden rounded-[40px] border border-slate-200 bg-slate-100 shadow-[0_24px_80px_rgba(15,23,42,0.12)] ${
          landscapeMindMap ? "h-[430px] w-[calc(100vh-3rem)] max-w-none flex-col" : "h-[calc(100vh-3rem)] max-w-[430px] flex-col"
        }`}
      >
        <StatusBar />
        <div
          className={`flex-1 ${activeNote ? "overflow-hidden pb-0" : landscapeMindMap ? "overflow-hidden pb-0" : "overflow-y-auto"} ${
            activeNote ? "pb-0" : showBottomNav ? "pb-28" : "pb-5"
          }`}
        >
          {screen}
        </div>
        {showBottomNav ? (
          <div className="absolute bottom-0 left-0 right-0 z-20">
            <BottomNav active={nav} setNav={handleNav} />
          </div>
        ) : null}
      </div>
    </div>
  );
}
