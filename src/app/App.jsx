import { useEffect, useMemo, useState } from "react";
import { AGENT_STATUS, DETAIL_VIEWS } from "./navigation";
import { BottomNav } from "../components/BottomNav";
import { StatusBar } from "../components/StatusBar";
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
import { isWebViewShell } from "../services/appShellMode";
import {
  initializeLocalDemoFs,
  readActiveAgentResult,
  readInputDraft,
  readNoteSettings,
  saveActiveAgentResult,
  saveInputDraft,
  saveNoteSettings,
} from "../services/localDemoFs";

const REAL_API_STAGES = [
  { id: "submit", label: "Submit Request", text: "正在向真实后端提交学习资料..." },
  { id: "agent", label: "Agent Pipeline", text: "后端正在解析资料、调用模型并生成结构化结果..." },
  { id: "grounding", label: "Citation Grounding", text: "正在绑定引用、导图和复习评估..." },
];

export default function App() {
  useMemo(() => initializeLocalDemoFs(), []);
  const initialAgentResult = useMemo(() => readActiveAgentResult(), []);
  const [nav, setNav] = useState("home");
  const [detailView, setDetailView] = useState(null);
  const [agentStatus, setAgentStatus] = useState(AGENT_STATUS.IDLE);
  const [agentResult, setAgentResult] = useState(initialAgentResult);
  const [inputDraft, setInputDraft] = useState(() => readInputDraft());
  const [noteSettings, setNoteSettings] = useState(() => readNoteSettings(initialAgentResult.id));
  const [phase, setPhase] = useState(0);
  const [error, setError] = useState("");

  const stages = useMemo(() => agentResult.agentStages?.length ? agentResult.agentStages : REAL_API_STAGES, [agentResult]);

  useEffect(() => {
    setNoteSettings(readNoteSettings(agentResult.id));
  }, [agentResult.id]);

  useEffect(() => {
    saveInputDraft(inputDraft);
  }, [inputDraft]);

  useEffect(() => {
    saveNoteSettings(agentResult.id, noteSettings);
  }, [agentResult.id, noteSettings]);

  useEffect(() => {
    if (agentStatus !== AGENT_STATUS.LOADING) return undefined;
    setPhase(0);
    const timers = stages.slice(1).map((_, index) => setTimeout(() => setPhase(index + 1), 700 * (index + 1)));
    return () => timers.forEach(clearTimeout);
  }, [agentStatus, stages]);

  async function handleRunAgent(input) {
    setError("");
    setAgentStatus(AGENT_STATUS.LOADING);
    setNav("ai");
    setDetailView(null);

    try {
      const result = await runAgent(input);
      setAgentResult(result);
      saveActiveAgentResult(result);
      setAgentStatus(AGENT_STATUS.SUCCESS);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Agent 调用失败");
      setAgentStatus(AGENT_STATUS.ERROR);
    }
  }

  function updateAgentResult(nextResultOrUpdater) {
    setAgentResult((current) => {
      const nextResult = typeof nextResultOrUpdater === "function"
        ? nextResultOrUpdater(current)
        : nextResultOrUpdater;

      saveActiveAgentResult(nextResult, "local-edit");
      return nextResult;
    });
  }

  function handleNav(next) {
    setNav(next);
    setDetailView(null);
    if (next === "ai" && agentStatus !== AGENT_STATUS.LOADING && agentStatus !== AGENT_STATUS.SUCCESS && agentStatus !== AGENT_STATUS.ERROR) {
      setAgentStatus(AGENT_STATUS.IDLE);
    }
  }

  function openNote() {
    setDetailView(DETAIL_VIEWS.NOTE);
    setNav("notes");
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
    stages,
    phase,
    error,
    handleRunAgent,
    openNote,
    openReview,
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
  const shellClass = isWebView
    ? "h-[100dvh] w-screen flex-col border-0 bg-slate-100 shadow-none"
    : isLandscapeMindMap
      ? "h-[min(430px,calc(100vh-3rem))] w-full max-w-[920px] origin-center flex-col rounded-[34px] border border-slate-200 bg-slate-100 shadow-[0_24px_80px_rgba(15,23,42,0.12)] max-[640px]:fixed max-[640px]:left-1/2 max-[640px]:top-1/2 max-[640px]:m-0 max-[640px]:h-[calc(100vw-1.25rem)] max-[640px]:w-[calc(100vh-1.25rem)] max-[640px]:max-w-none max-[640px]:-translate-x-1/2 max-[640px]:-translate-y-1/2 max-[640px]:rotate-90"
      : "h-[calc(100vh-3rem)] max-w-[430px] flex-col rounded-[40px] border border-slate-200 bg-slate-100 shadow-[0_24px_80px_rgba(15,23,42,0.12)]";
  const pageClass = isWebView
    ? `min-h-[100dvh] bg-slate-100 text-slate-900 ${isLandscapeMindMap ? "overflow-hidden" : ""}`
    : `min-h-screen bg-[radial-gradient(circle_at_top,#eff6ff_0%,#f8fafc_36%,#ffffff_80%)] px-4 py-6 text-slate-900 ${isLandscapeMindMap ? "flex items-center max-[640px]:overflow-hidden max-[640px]:p-0" : ""}`;
  const contentSafeAreaStyle = isWebView
    ? {
        paddingTop: isLandscapeMindMap
          ? "max(10px, env(safe-area-inset-top))"
          : "max(22px, env(safe-area-inset-top))",
      }
    : undefined;

  return (
    <div className={pageClass}>
      <div className={`relative mx-auto flex overflow-hidden ${shellClass}`}>
        {isWebView ? null : <StatusBar />}
        <main
          className={`min-h-0 flex-1 ${showBottomNav ? "overflow-y-auto pb-28" : "overflow-hidden"}`}
          style={contentSafeAreaStyle}
        >
          {screen}
        </main>
        {showBottomNav ? (
          <div className="absolute bottom-0 left-0 right-0 z-20">
            <BottomNav active={nav} onChange={handleNav} isWebView={isWebView} />
          </div>
        ) : null}
      </div>
    </div>
  );
}

function getScreen({
  nav,
  detailView,
  agentStatus,
  agentResult,
  stages,
  phase,
  error,
  handleRunAgent,
  openNote,
  openReview,
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
    return <NotesScreen result={agentResult} onOpenNote={openNote} />;
  }

  if (nav === "mindmap") {
    return <MindMapLibraryScreen result={agentResult} onOpenMap={() => setDetailView(DETAIL_VIEWS.MINDMAP)} />;
  }

  if (nav === "profile") {
    return <ProfileScreen />;
  }

  if (agentStatus === AGENT_STATUS.LOADING) {
    return <LoadingScreen stages={stages} phase={phase} />;
  }

  if (agentStatus === AGENT_STATUS.SUCCESS || agentStatus === AGENT_STATUS.ERROR) {
    const hasResult = Boolean(agentResult.topic || agentResult.summary || agentResult.notes?.length);

    return (
      <div>
        {error ? (
          <div className="mx-5 mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-[13px] leading-5 text-rose-900">
            真实后端调用失败：{error}
          </div>
        ) : null}
        {hasResult ? (
          <ResultScreen
            result={agentResult}
            onOpenNote={openNote}
            onOpenMindMap={() => setNav("mindmap")}
            onRetry={() => setAgentStatus(AGENT_STATUS.IDLE)}
            onResultChange={updateAgentResult}
          />
        ) : (
          <div className="px-5 pt-4">
            <button
              onClick={() => setAgentStatus(AGENT_STATUS.IDLE)}
              className="w-full rounded-2xl bg-blue-600 px-4 py-3 text-[14px] font-semibold text-white"
            >
              返回输入页重新调用
            </button>
          </div>
        )}
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
