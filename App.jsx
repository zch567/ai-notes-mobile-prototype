import React, { useEffect, useState } from "react";

const recentNotes = [
  { title: "高等数学复习", tag: "学习", meta: "课堂视频 | 9 分钟前", preview: "极限、导数与积分的核心概念已整理成分层笔记。" },
  { title: "产品需求拆解", tag: "工作", meta: "PPT 导入 | 今天 10:22", preview: "围绕用户留存、内容摄取和 AI 摘要建立行动清单。" },
  { title: "阅读：知识管理", tag: "阅读", meta: "PDF 文档 | 昨天", preview: "将长文内容提炼为可复用的框架与关键词。" },
];

const library = [
  { title: "机器学习导论", category: "学习", meta: "视频 + 文档", preview: "监督学习、损失函数、训练与验证的整理版本。" },
  { title: "产品策略复盘", category: "工作", meta: "会议纪要", preview: "围绕增长、留存、内容摄取做的结构化复盘。" },
  { title: "论文阅读笔记", category: "研究", meta: "PDF", preview: "提取研究方法、结论、限制条件和后续方向。" },
];

const resultSections = [
  { title: "主题摘要", points: ["本内容围绕 AI 笔记如何帮助学习者吸收长内容。", "系统会自动识别章节、关键术语和可执行结论。"] },
  { title: "结构化输出", points: ["按主题拆分为层级标题、重点列表和关联说明。", "支持从链接、文本和文档同时生成统一结果。"] },
  { title: "智能标注", points: ["知识点", "复习重点", "待办项", "延伸阅读"] },
];

const branches = [
  { label: "摘要", x: 18, y: 16, bright: false, kids: ["核心观点", "一句话总结"] },
  { label: "重点", x: 58, y: 122, bright: true, kids: ["定义", "公式", "术语"] },
  { label: "行动项", x: 18, y: 286, bright: false, kids: ["复习计划", "练习题"] },
  { label: "参考资料", x: 206, y: 286, bright: false, kids: ["原文链接", "扩展阅读"] },
  { label: "概念图谱", x: 220, y: 18, bright: true, kids: ["层级关系", "主题分支", "关联网络"] },
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

function HomeScreen({ goAi }) {
  return (
    <div className="space-y-5 px-5 pb-5">
      <TopBar
        title="我的笔记"
        subtitle="4 月 19 日 星期日"
        right={
          <button className="grid h-10 w-10 place-items-center rounded-full border border-slate-200 bg-white text-slate-600 shadow-sm">🔔</button>
        }
      />

      <section className="rounded-[32px] border border-slate-200 bg-gradient-to-br from-blue-50 via-white to-slate-50 p-4 shadow-sm">
        <button onClick={goAi} className="w-full text-left active:scale-[0.99]">
          <div className="flex items-stretch gap-4">
            <div className="flex-1">
              <div className="inline-flex rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-blue-600 shadow-sm">
                AI入口
              </div>
              <h2 className="mt-3 text-[20px] font-semibold tracking-tight text-slate-900">链接、文档、文本统一采集</h2>
              <p className="mt-2 max-w-[250px] text-[13px] leading-5 text-slate-500">
                粘贴课程链接、上传 PDF / PPT，或直接输入文本，系统会自动判断并开始处理。
              </p>
            </div>
            <div className="flex w-24 shrink-0 items-center justify-center rounded-[28px] border border-blue-100 bg-white shadow-sm">
              <span className="text-[40px] font-light leading-none text-blue-500">+</span>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {["视频链接", "PDF / PPT", "文本输入"].map((item) => (
              <span key={item} className="rounded-full bg-slate-50 px-3 py-1 text-[11px] font-medium text-slate-500">
                {item}
              </span>
            ))}
          </div>
        </button>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-[18px] font-semibold tracking-tight text-slate-900">推荐内容</h2>
          <button className="text-[13px] font-medium text-blue-600">查看全部</button>
        </div>
        <div className="grid gap-3">
          {[
            { title: "AI 学习工作流", desc: "如何快速把课堂内容转成复习卡片", tag: "推荐" },
            { title: "导图整理法", desc: "用主题树管理笔记和知识结构", tag: "方法" },
          ].map((item) => (
            <button key={item.title} className="rounded-3xl border border-slate-200 bg-white p-4 text-left shadow-sm">
              <div className="inline-flex rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-600">{item.tag}</div>
              <h3 className="mt-3 text-[16px] font-semibold text-slate-900">{item.title}</h3>
              <p className="mt-2 text-[13px] leading-5 text-slate-500">{item.desc}</p>
            </button>
          ))}
        </div>
      </section>

    </div>
  );
}

function NotesScreen() {
  const cats = ["全部", "学习", "工作", "阅读", "语言"];
  return (
    <div className="space-y-5 px-5 pb-5">
      <TopBar title="笔记库" subtitle="收藏、搜索和分类管理" />
      <button className="flex w-full items-center gap-3 rounded-3xl border border-slate-200 bg-white px-4 py-4 text-left shadow-sm">
        <span className="text-slate-400">⌕</span>
        <span className="text-[15px] text-slate-400">搜索笔记、关键词或标题...</span>
      </button>
      <div className="flex flex-wrap gap-2">
        {cats.map((c, i) => (
          <button key={c} className={`rounded-full px-4 py-2 text-[13px] font-medium ${i === 0 ? "bg-blue-600 text-white" : "bg-white text-slate-500 shadow-sm ring-1 ring-slate-200"}`}>{c}</button>
        ))}
      </div>
      <div className="space-y-3">
        {library.map((note) => (
          <button key={note.title} className="w-full rounded-3xl border border-slate-200 bg-white p-4 text-left shadow-sm">
            <div className="inline-flex rounded-full bg-slate-50 px-2.5 py-1 text-[11px] font-semibold text-slate-500">{note.category}</div>
            <h3 className="mt-3 text-[16px] font-semibold text-slate-900">{note.title}</h3>
            <p className="mt-2 text-[13px] leading-5 text-slate-500">{note.preview}</p>
            <div className="mt-3 flex items-center justify-between">
              <p className="text-[12px] font-medium text-slate-400">{note.meta}</p>
              <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-600">已生成</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function InputScreen({ startLoading }) {
  return (
    <div className="space-y-5 px-5 pb-5">
      <TopBar title="采集" subtitle="将内容带入你的笔记" />
      <Card title="输入来源" subtitle="链接、文本、文档">
        <div className="space-y-4">
          <div className="rounded-[24px] border border-slate-200 bg-slate-50 p-4">
            <div className="mb-3 flex flex-wrap gap-2 text-[12px] font-medium text-slate-400">
              {["视频链接", "课程文本", "PDF / PPT", "粘贴内容"].map((t) => (
                <span key={t} className="rounded-full bg-white px-2.5 py-1 shadow-sm">{t}</span>
              ))}
            </div>
            <textarea defaultValue="在此粘贴课程视频链接或输入文本" className="min-h-[160px] w-full resize-none rounded-[20px] border border-slate-200 bg-white px-4 py-4 text-[15px] leading-6 text-slate-700 outline-none" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <button className="flex items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-[14px] font-medium text-slate-700 shadow-sm">↑ 上传文档</button>
            <button className="flex items-center justify-center gap-2 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-[14px] font-medium text-slate-500">+ 添加文件</button>
          </div>
          <button onClick={startLoading} className="w-full rounded-2xl bg-blue-600 px-4 py-4 text-[15px] font-semibold text-white shadow-sm">生成笔记</button>
        </div>
      </Card>
    </div>
  );
}

function LoadingScreen({ phase }) {
  const items = [
    { title: "解析输入", desc: "识别内容类型与结构" },
    { title: "抽取知识", desc: "提炼主题、关键词和术语" },
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
            <div className="flex h-14 w-14 items-center justify-center rounded-3xl bg-blue-600 text-white shadow-lg shadow-blue-200">⟳</div>
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
                <span className={`text-[12px] font-medium ${done ? "text-blue-600" : active ? "text-blue-500" : "text-slate-300"}`}>{done ? "完成" : active ? "进行中" : "等待中"}</span>
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
            <p className="mt-2 text-[14px] leading-6 text-slate-700">这段内容说明了智能笔记应用如何帮助学习者将长内容转化为清晰、可复习的知识结构。</p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {[{ label: "来源类型", value: "视频 + 文档" }, { label: "提取结果", value: "摘要 + 导图" }].map((item) => (
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
      <Card title="智能标注" subtitle="高亮关键词">
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
            {[
              { title: "摘要", desc: "核心观点和一句话总结", tone: "bg-white" },
              { title: "重点", desc: "定义、公式、术语", tone: "bg-blue-50" },
              { title: "参考资料", desc: "原文链接和扩展阅读", tone: "bg-white" },
            ].map((item) => (
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
        <h2 className="text-left text-[18px] font-semibold text-slate-900">用户名</h2>
      </section>
      <div className="grid grid-cols-3 gap-3">
        {["128 笔记", "41 导图", "19 收藏"].map((item) => (
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
    { id: "mindmap", label: "思维导图", icon: "◌" },
    { id: "profile", label: "个人中心", icon: "◎" },
  ];

  return (
    <div className="border-t border-slate-200 bg-white/96 px-2 py-3 backdrop-blur">
      <div className="grid grid-cols-5 items-end gap-1">
        {tabs.map((tab) => {
          const isActive = active === tab.id;
          if (tab.id === "ai") {
            return (
              <button key={tab.id} onClick={() => setNav(tab.id)} className="relative -mt-7 flex flex-col items-center justify-center">
                <div className={`flex h-14 w-14 items-center justify-center rounded-[24px] border text-[22px] shadow-lg ${isActive ? "border-blue-500 bg-blue-600 text-white shadow-blue-200" : "border-blue-200 bg-blue-500 text-white shadow-blue-100"}`}>{tab.icon}</div>
                <span className={`mt-1 text-[11px] font-medium ${isActive ? "text-blue-700" : "text-slate-400"}`}>{tab.label}</span>
              </button>
            );
          }
          return (
            <button key={tab.id} onClick={() => setNav(tab.id)} className={`flex flex-col items-center justify-center rounded-2xl px-2 py-2 text-[11px] font-medium ${isActive ? "bg-blue-50 text-blue-700" : "text-slate-400"}`}>
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
  };

  const screen =
    nav === "home" ? <HomeScreen goAi={() => handleNav("ai")} /> :
    nav === "notes" ? <NotesScreen /> :
    nav === "ai" ? (
      aiFlow === "input" ? <InputScreen startLoading={() => setAiFlow("loading")} /> :
      aiFlow === "loading" ? <LoadingScreen phase={phase} /> :
      <ResultScreen onMindMap={() => setNav("mindmap")} onContinue={() => { setAiFlow("input"); setNav("ai"); }} />
    ) :
    nav === "mindmap" ? <MindMapScreen /> :
    <ProfileScreen />;

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,#eff6ff_0%,#f8fafc_36%,#ffffff_80%)] px-4 py-6 text-slate-900">
      <div className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-[430px] flex-col overflow-hidden rounded-[40px] border border-slate-200 bg-slate-100 shadow-[0_24px_80px_rgba(15,23,42,0.12)]">
        <StatusBar />
        <div className="flex-1 overflow-y-auto">{screen}</div>
        <BottomNav active={nav} setNav={handleNav} />
      </div>
    </div>
  );
}
