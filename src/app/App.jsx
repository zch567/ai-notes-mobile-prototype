import { useEffect, useMemo, useState } from "react";
import { AGENT_STATUS, DETAIL_VIEWS } from "./navigation";
import { BottomNav } from "../components/BottomNav";
import { StatusBar } from "../components/StatusBar";
import { demoAgentResult } from "../data/demoAgentResult";
import { InputScreen } from "../features/ai/InputScreen";
import { LoadingScreen } from "../features/ai/LoadingScreen";
import { ResultScreen } from "../features/ai/ResultScreen";
import { runAgent } from "../features/ai/agentApi";
import { HomeScreen } from "../features/home/HomeScreen";
import { MindMapLibraryScreen, MindMapScreen } from "../features/mindmap/MindMapScreen";
import { NoteDetailScreen } from "../features/notes/NoteDetailScreen";
import { NotesScreen } from "../features/notes/NotesScreen";
import { ReviewScreen } from "../features/notes/ReviewScreen";
import { ProfileScreen } from "../features/profile/ProfileScreen";
import { ShowcaseScreen } from "../features/showcase/ShowcaseScreen";
import { isWebViewShell } from "../services/appShellMode";
import {
  activateAgentResult,
  deleteAgentResultRecord,
  initializeLocalDemoFs,
  readActiveAgentResult,
  readAgentResultHistory,
  readInputDraft,
  readNoteSettings,
  saveActiveAgentResult,
  saveInputDraft,
  saveNoteSettings,
  setAgentResultPinned,
} from "../services/localDemoFs";

const RUNNING_AGENT_STAGES = [
  {
    id: "prepare",
    label: "准备材料",
    text: "正在整理输入内容和上传文件信息，准备交给后端处理。",
  },
  {
    id: "parse",
    label: "解析资料",
    text: "后端会抽取文本、拆分片段，并保留可追溯的来源位置。",
  },
  {
    id: "generate",
    label: "正在调用大模型生成笔记",
    text: "后端正在调用已配置的大模型，围绕主题、摘要和核心知识点生成结构化笔记。",
  },
  {
    id: "ground",
    label: "绑定引用",
    text: "系统会把笔记内容和来源片段对齐，生成可回看的证据链。",
  },
  {
    id: "compose",
    label: "组织学习资产",
    text: "正在组合笔记、导图和复习题，形成统一的学习结果。",
  },
  {
    id: "finalize",
    label: "等待结果",
    text: "前端正在等待后端返回完整 AgentResult，完成后可回到 AI 页查看结果。",
  },
];

export default function App() {
  useMemo(() => initializeLocalDemoFs(), []);
  const initialAgentResult = useMemo(() => readActiveAgentResult(), []);
  const [nav, setNav] = useState("home");
  const [detailView, setDetailView] = useState(null);
  const [agentStatus, setAgentStatus] = useState(AGENT_STATUS.IDLE);
  const [agentResult, setAgentResult] = useState(initialAgentResult);
  const [resultHistory, setResultHistory] = useState(() => readAgentResultHistory());
  const [inputDraft, setInputDraft] = useState(() => readInputDraft());
  const [noteSettings, setNoteSettings] = useState(() => readNoteSettings(initialAgentResult.id));
  const [agentJob, setAgentJob] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setNoteSettings(readNoteSettings(agentResult.id));
  }, [agentResult.id]);

  useEffect(() => {
    saveInputDraft(inputDraft);
  }, [inputDraft]);

  useEffect(() => {
    saveNoteSettings(agentResult.id, noteSettings);
  }, [agentResult.id, noteSettings]);

  async function handleRunAgent(input) {
    setError("");
    setAgentJob(createInitialAgentJob());
    setAgentStatus(AGENT_STATUS.LOADING);
    setNav("ai");
    setDetailView(null);

    try {
      const result = await runAgent(input, { onProgress: setAgentJob });
      setAgentResult(result);
      saveActiveAgentResult(result);
      setResultHistory(readAgentResultHistory());
      setAgentJob(null);
      setAgentStatus(AGENT_STATUS.SUCCESS);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Agent 调用失败");
      setAgentResult(demoAgentResult);
      saveActiveAgentResult(demoAgentResult, "fallback");
      setResultHistory(readAgentResultHistory());
      setAgentJob(null);
      setAgentStatus(AGENT_STATUS.ERROR);
    }
  }

  function updateAgentResult(nextResultOrUpdater) {
    setAgentResult((current) => {
      const nextResult = typeof nextResultOrUpdater === "function"
        ? nextResultOrUpdater(current)
        : nextResultOrUpdater;

      saveActiveAgentResult(nextResult, "local-edit");
      setResultHistory(readAgentResultHistory());
      return nextResult;
    });
  }

  function selectHistoryResult(resultId) {
    if (!resultId || resultId === agentResult.id) return agentResult;

    const nextResult = activateAgentResult(resultId);
    setAgentResult(nextResult);
    setResultHistory(readAgentResultHistory());
    setAgentStatus(AGENT_STATUS.SUCCESS);
    return nextResult;
  }

  function handlePinHistoryResult(resultId, pinned) {
    setResultHistory(setAgentResultPinned(resultId, pinned));
  }

  function handleDeleteHistoryResult(resultId) {
    const deletion = deleteAgentResultRecord(resultId);
    setAgentResult(deletion.activeResult);
    setResultHistory(deletion.history);
    if (resultId === agentResult.id) {
      setDetailView(null);
    }
  }

  function handleNav(next) {
    setNav(next);
    setDetailView(null);
    if (next === "ai" && agentStatus !== AGENT_STATUS.LOADING && agentStatus !== AGENT_STATUS.SUCCESS && agentStatus !== AGENT_STATUS.ERROR) {
      setAgentStatus(AGENT_STATUS.IDLE);
    }
  }

  function openNote(resultId) {
    if (resultId) selectHistoryResult(resultId);
    setDetailView(DETAIL_VIEWS.NOTE);
    setNav("notes");
  }

  function openMindMap(resultId) {
    if (resultId) selectHistoryResult(resultId);
    setDetailView(DETAIL_VIEWS.MINDMAP);
    setNav("mindmap");
  }

  function openReview() {
    setDetailView(DETAIL_VIEWS.REVIEW);
    setNav("notes");
  }

  const screen = getScreen({
    nav,
    detailView,
    agentStatus,
    agentResult,
    resultHistory,
    agentJob,
    error,
    handleRunAgent,
    openNote,
    openMindMap,
    openReview,
    selectHistoryResult,
    handlePinHistoryResult,
    handleDeleteHistoryResult,
    setDetailView,
    setNav,
    setAgentStatus,
    inputDraft,
    setInputDraft,
    noteSettings,
    setNoteSettings,
    updateAgentResult,
  });

  const isLandscapeMindMap = nav === "mindmap" && detailView === DETAIL_VIEWS.MINDMAP;
  const showBottomNav = !detailView && !isLandscapeMindMap;
  const isWebView = isWebViewShell();
  const viewportMetrics = useWebViewViewportMetrics(isWebView);
  const navHeight = viewportMetrics.compactNav ? 82 : 104;
  const webViewShellStyle = isWebView
    ? {
        "--app-viewport-height": `${viewportMetrics.height}px`,
        "--bottom-nav-height": `${navHeight}px`,
        "--bottom-nav-offset": `${viewportMetrics.bottomOffset}px`,
      }
    : undefined;
  const shellClass = isWebView
    ? "h-[var(--app-viewport-height)] w-screen flex-col border-0 bg-slate-100 shadow-none"
    : isLandscapeMindMap
      ? "h-[min(430px,calc(100vh-3rem))] w-full max-w-[920px] origin-center flex-col rounded-[34px] border border-slate-200 bg-slate-100 shadow-[0_24px_80px_rgba(15,23,42,0.12)] max-[640px]:fixed max-[640px]:left-1/2 max-[640px]:top-1/2 max-[640px]:m-0 max-[640px]:h-[calc(100vw-1.25rem)] max-[640px]:w-[calc(100vh-1.25rem)] max-[640px]:max-w-none max-[640px]:-translate-x-1/2 max-[640px]:-translate-y-1/2 max-[640px]:rotate-90"
      : "h-[calc(100vh-3rem)] max-w-[430px] flex-col rounded-[40px] border border-slate-200 bg-slate-100 shadow-[0_24px_80px_rgba(15,23,42,0.12)]";
  const pageClass = isWebView
    ? `h-[var(--app-viewport-height)] min-h-[var(--app-viewport-height)] overflow-hidden bg-slate-100 text-slate-900 ${isLandscapeMindMap ? "overflow-hidden" : ""}`
    : `min-h-screen bg-[radial-gradient(circle_at_top,#eff6ff_0%,#f8fafc_36%,#ffffff_80%)] px-4 py-6 text-slate-900 ${isLandscapeMindMap ? "flex items-center max-[640px]:overflow-hidden max-[640px]:p-0" : ""}`;
  const contentSafeAreaStyle = isWebView
    ? {
        paddingTop: isLandscapeMindMap
          ? "max(10px, env(safe-area-inset-top))"
          : "max(22px, env(safe-area-inset-top))",
        paddingBottom: showBottomNav
          ? "calc(var(--bottom-nav-height) + var(--bottom-nav-offset) + 8px)"
          : undefined,
      }
    : undefined;

  return (
    <div className={pageClass} style={webViewShellStyle}>
      <div className={`relative mx-auto flex overflow-hidden ${shellClass}`} style={webViewShellStyle}>
        {isWebView ? null : <StatusBar />}
        <main
          className={`min-h-0 flex-1 ${showBottomNav ? (isWebView ? "overflow-y-auto" : "overflow-y-auto pb-28") : "overflow-hidden"}`}
          style={contentSafeAreaStyle}
        >
          {screen}
        </main>
        {agentStatus === AGENT_STATUS.LOADING ? (
          <GenerationFloatingStatus
            job={agentJob}
            onOpen={() => {
              setNav("ai");
              setDetailView(null);
            }}
            showBottomNav={showBottomNav}
            isWebView={isWebView}
          />
        ) : null}
        {showBottomNav ? (
          <div
            className="absolute left-0 right-0 z-20"
            style={isWebView ? { bottom: "var(--bottom-nav-offset)" } : { bottom: 0 }}
          >
            <BottomNav
              active={nav}
              onChange={handleNav}
              isWebView={isWebView}
              compact={isWebView && viewportMetrics.compactNav}
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}

function useWebViewViewportMetrics(enabled) {
  const [metrics, setMetrics] = useState(() => getWebViewViewportMetrics());

  useEffect(() => {
    if (!enabled || typeof window === "undefined") return undefined;

    let frameId = 0;
    const update = () => {
      window.cancelAnimationFrame(frameId);
      frameId = window.requestAnimationFrame(() => {
        setMetrics(getWebViewViewportMetrics());
      });
    };

    update();
    window.addEventListener("resize", update);
    window.addEventListener("orientationchange", update);
    window.visualViewport?.addEventListener("resize", update);
    window.visualViewport?.addEventListener("scroll", update);

    return () => {
      window.cancelAnimationFrame(frameId);
      window.removeEventListener("resize", update);
      window.removeEventListener("orientationchange", update);
      window.visualViewport?.removeEventListener("resize", update);
      window.visualViewport?.removeEventListener("scroll", update);
    };
  }, [enabled]);

  return metrics;
}

function getWebViewViewportMetrics() {
  if (typeof window === "undefined") {
    return {
      height: 720,
      bottomOffset: 0,
      compactNav: false,
    };
  }

  const visualViewport = window.visualViewport;
  const layoutHeight = window.innerHeight || document.documentElement.clientHeight || 720;
  const visualHeight = visualViewport?.height || layoutHeight;
  const visualTop = visualViewport?.offsetTop || 0;
  const height = Math.max(360, Math.floor(visualHeight));
  const bottomOffset = Math.max(0, Math.floor(layoutHeight - visualHeight - visualTop));

  return {
    height,
    bottomOffset,
    compactNav: height < 680,
  };
}

function createInitialAgentJob() {
  const stage = RUNNING_AGENT_STAGES[0];
  return {
    status: "running",
    progress: 2,
    stageId: stage.id,
    label: stage.label,
    text: stage.text,
    stages: RUNNING_AGENT_STAGES,
  };
}

function GenerationFloatingStatus({ job, onOpen, showBottomNav, isWebView }) {
  const progress = Math.round(Math.min(Math.max(Number(job?.progress || 0), 0), 100));
  const label = job?.label || "正在调用大模型生成笔记";
  const text = job?.text || "可以暂时离开此界面，完成后可回到 AI 页查看结果。";
  const bottom = showBottomNav
    ? isWebView
      ? "calc(var(--bottom-nav-height) + var(--bottom-nav-offset) + 12px)"
      : "104px"
    : "16px";

  return (
    <button
      type="button"
      onClick={onOpen}
      className="absolute left-4 right-4 z-30 rounded-2xl border border-blue-100 bg-white/95 px-4 py-3 text-left shadow-[0_18px_48px_rgba(37,99,235,0.20)] backdrop-blur"
      style={{ bottom }}
    >
      <div className="flex items-center justify-between gap-3">
        <p className="text-[13px] font-semibold text-slate-900">笔记正在生成中</p>
        <span className="shrink-0 rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-700">{progress}%</span>
      </div>
      <p className="mt-1 line-clamp-2 text-[12px] leading-5 text-slate-500">{label} · {text}</p>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-blue-100">
        <div className="h-full rounded-full bg-blue-600 transition-all duration-300" style={{ width: `${progress}%` }} />
      </div>
    </button>
  );
}

function getScreen({
  nav,
  detailView,
  agentStatus,
  agentResult,
  resultHistory,
  agentJob,
  error,
  handleRunAgent,
  openNote,
  openMindMap,
  openReview,
  selectHistoryResult,
  handlePinHistoryResult,
  handleDeleteHistoryResult,
  setDetailView,
  setNav,
  setAgentStatus,
  inputDraft,
  setInputDraft,
  noteSettings,
  setNoteSettings,
  updateAgentResult,
}) {
  if (detailView === DETAIL_VIEWS.NOTE) {
    return (
      <NoteDetailScreen
        result={agentResult}
        settings={noteSettings}
        setSettings={setNoteSettings}
        onResultChange={updateAgentResult}
        onBack={() => setDetailView(null)}
        onOpenReview={openReview}
      />
    );
  }

  if (detailView === DETAIL_VIEWS.REVIEW) {
    return <ReviewScreen result={agentResult} onBack={() => setDetailView(DETAIL_VIEWS.NOTE)} />;
  }

  if (detailView === DETAIL_VIEWS.MINDMAP) {
    return <MindMapScreen result={agentResult} onResultChange={updateAgentResult} onBack={() => setDetailView(null)} />;
  }

  if (nav === "home") {
    return <HomeScreen result={agentResult} onStart={() => setNav("ai")} onOpenNote={openNote} />;
  }

  if (nav === "notes") {
    return (
      <NotesScreen
        result={agentResult}
        history={resultHistory}
        onOpenNote={openNote}
        onSelectHistory={selectHistoryResult}
        onPinHistory={handlePinHistoryResult}
        onDeleteHistory={handleDeleteHistoryResult}
      />
    );
  }

  if (nav === "mindmap") {
    return (
      <MindMapLibraryScreen
        result={agentResult}
        history={resultHistory}
        onOpenMap={openMindMap}
        onSelectHistory={selectHistoryResult}
        onPinHistory={handlePinHistoryResult}
        onDeleteHistory={handleDeleteHistoryResult}
      />
    );
  }

  if (nav === "showcase") {
    return (
      <ShowcaseScreen
        result={agentResult}
        onOpenNote={openNote}
        onOpenMindMap={() => {
          openMindMap();
        }}
        onRunAgent={() => {
          setNav("ai");
          setAgentStatus(AGENT_STATUS.IDLE);
        }}
      />
    );
  }
  if (nav === "profile") {
    return <ProfileScreen />;
  }

  if (agentStatus === AGENT_STATUS.LOADING) {
    return <LoadingScreen stages={RUNNING_AGENT_STAGES} job={agentJob} />;
  }

  if (agentStatus === AGENT_STATUS.SUCCESS || agentStatus === AGENT_STATUS.ERROR) {
    return (
      <div>
        {error ? (
          <div className="mx-5 mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] leading-5 text-amber-900">
            API 调用失败，已回退到演示数据：{error}
          </div>
        ) : null}
        <ResultScreen
          result={agentResult}
          onOpenNote={openNote}
          onOpenMindMap={() => setNav("mindmap")}
          onOpenReview={openReview}
          onRetry={() => setAgentStatus(AGENT_STATUS.IDLE)}
          onResultChange={updateAgentResult}
        />
      </div>
    );
  }

  return (
    <InputScreen
      onRun={handleRunAgent}
      status={agentStatus}
      draft={inputDraft}
      onDraftChange={setInputDraft}
    />
  );
}
