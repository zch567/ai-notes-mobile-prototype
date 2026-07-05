import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { chatAgent } from "../ai/agentApi";

const defaultSettings = {
  reviewMode: false,
  showCitations: true,
  autoSave: true,
};

const initialChatMessages = [
  {
    role: "assistant",
    text: "你可以直接问我这篇笔记的重点、帮你压缩成提纲，或者让它更适合复习。",
  },
];

export function NoteDetailScreen({
  result,
  settings = defaultSettings,
  setSettings = () => {},
  onResultChange = () => {},
  onBack,
  onOpenReview,
  initialSourceId = null,
  onSourceLocated = () => {},
}) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [activeSourceId, setActiveSourceId] = useState(null);
  const [bubbleLayout, setBubbleLayout] = useState(null);
  const [editHistory, setEditHistory] = useState(() => ({
    past: [],
    present: createNoteSnapshot(result),
    future: [],
  }));
  const [isEditing, setIsEditing] = useState(false);
  const [editDraft, setEditDraft] = useState(() => createNoteSnapshot(result));
  const [draftHistory, setDraftHistory] = useState(() => ({
    past: [],
    future: [],
  }));
  const [messages, setMessages] = useState(initialChatMessages);
  const [isChatSending, setIsChatSending] = useState(false);
  const [chatError, setChatError] = useState("");
  const shellRef = useRef(null);
  const resultIdRef = useRef(result.id);
  const messageListRef = useRef(null);
  const bubbleScrollRef = useRef(null);
  const activeAnchorRef = useRef(null);
  const noteScrollRef = useRef(null);
  const noteDocumentRef = useRef(null);
  const pendingSourceScrollRef = useRef(null);
  const editDraftRef = useRef(editDraft);

  const sourceById = useMemo(() => new Map(result.sources.map((source) => [source.id, source])), [result.sources]);
  const citationBySourceId = useMemo(() => {
    const map = new Map();
    result.citations.forEach((citation) => {
      if (!map.has(citation.sourceId)) map.set(citation.sourceId, citation);
    });
    return map;
  }, [result.citations]);
  const activeSource = activeSourceId ? sourceById.get(activeSourceId) : null;
  const activeCitation = activeSourceId ? citationBySourceId.get(activeSourceId) : null;
  const sourceParagraphs = result.sources.map((source) => source.text);
  const citationIds = result.notes.flatMap((note) => note.citationIds);
  const missingCitationCount = citationIds.filter((sourceId) => !sourceById.has(sourceId)).length;
  const canUndo = editHistory.past.length > 0;
  const canRedo = editHistory.future.length > 0;
  const canUndoCurrentEdit = isEditing ? draftHistory.past.length > 0 : canUndo;
  const canRedoCurrentEdit = isEditing ? draftHistory.future.length > 0 : canRedo;

  useEffect(() => {
    if (resultIdRef.current === result.id) return;

    resultIdRef.current = result.id;
    setEditHistory({
      past: [],
      present: createNoteSnapshot(result),
      future: [],
    });
    const nextDraft = createNoteSnapshot(result);
    editDraftRef.current = nextDraft;
    setEditDraft(nextDraft);
    setDraftHistory({ past: [], future: [] });
    setIsEditing(false);
    setMessages(initialChatMessages);
    setChatInput("");
    setChatError("");
    setIsChatSending(false);
  }, [result]);

  useEffect(() => {
    if (!settings.showCitations) {
      setActiveSourceId(null);
    }
  }, [settings.showCitations]);

  useEffect(() => {
    if (!messageListRef.current) return;
    messageListRef.current.scrollTop = messageListRef.current.scrollHeight;
  }, [messages, chatOpen]);

  const scrollActiveSourceIntoView = useCallback((behavior = "smooth") => {
    const sourceId = pendingSourceScrollRef.current || activeSourceId;
    if (!sourceId || !bubbleScrollRef.current) return;

    const activeRow = bubbleScrollRef.current.querySelector(`[data-source-row-id="${cssEscape(sourceId)}"]`);
    if (!activeRow) return;

    activeRow.scrollIntoView({ block: "center", behavior });
    pendingSourceScrollRef.current = null;
  }, [activeSourceId]);

  const updateBubbleLayout = useCallback(() => {
    if (!activeSource || !shellRef.current) {
      setBubbleLayout(null);
      return;
    }

    const anchor = activeAnchorRef.current;
    if (!anchor) return;

    const containerRect = shellRef.current.getBoundingClientRect();
    const anchorRect = anchor.getBoundingClientRect();
    const bubbleWidth = Math.min(306, containerRect.width - 32);
    const bubbleHeight = 332;
    const anchorCenterX = anchorRect.left - containerRect.left + anchorRect.width / 2;

    let left = anchorCenterX - bubbleWidth / 2;
    left = Math.max(16, Math.min(left, containerRect.width - bubbleWidth - 16));

    const spaceBelow = containerRect.bottom - anchorRect.bottom;
    const spaceAbove = anchorRect.top - containerRect.top;
    const openBelow = spaceBelow >= bubbleHeight + 18 || spaceBelow >= spaceAbove;
    let top = openBelow ? anchorRect.bottom - containerRect.top + 12 : anchorRect.top - containerRect.top - bubbleHeight - 12;
    top = Math.max(16, Math.min(top, containerRect.height - bubbleHeight - 16));

    setBubbleLayout({ left, top, width: bubbleWidth, height: bubbleHeight });
  }, [activeSource]);

  useEffect(() => {
    updateBubbleLayout();
  }, [updateBubbleLayout]);

  useEffect(() => {
    if (!activeSource) return undefined;

    pendingSourceScrollRef.current = activeSource.id;
    const layoutFrame = window.requestAnimationFrame(() => {
      updateBubbleLayout();
      window.requestAnimationFrame(() => scrollActiveSourceIntoView("auto"));
    });

    return () => window.cancelAnimationFrame(layoutFrame);
  }, [activeSource, updateBubbleLayout, scrollActiveSourceIntoView]);

  useEffect(() => {
    if (!activeSource) return undefined;

    const scrollContainer = noteScrollRef.current;
    const handleLayoutChange = () => updateBubbleLayout();
    scrollContainer?.addEventListener("scroll", handleLayoutChange, { passive: true });
    window.addEventListener("resize", handleLayoutChange);

    return () => {
      scrollContainer?.removeEventListener("scroll", handleLayoutChange);
      window.removeEventListener("resize", handleLayoutChange);
    };
  }, [activeSource, updateBubbleLayout]);

  useEffect(() => {
    if (!initialSourceId) return;
    if (!settings.showCitations) {
      onSourceLocated();
      return;
    }

    const anchor = noteDocumentRef.current?.querySelector(`[data-source-id="${cssEscape(initialSourceId)}"]`);
    if (!anchor || anchor.disabled) {
      onSourceLocated();
      return;
    }

    anchor.scrollIntoView({ block: "center", behavior: "smooth" });
    activeAnchorRef.current = anchor;
    setActiveSourceId(initialSourceId);
    pendingSourceScrollRef.current = initialSourceId;
    window.requestAnimationFrame(() => {
      updateBubbleLayout();
      scrollActiveSourceIntoView();
    });
    onSourceLocated();
  }, [initialSourceId, settings.showCitations, updateBubbleLayout, scrollActiveSourceIntoView, onSourceLocated]);

  function toggleSource(sourceId, anchor) {
    const isSameAnchor = activeSourceId === sourceId && activeAnchorRef.current === anchor;

    if (isSameAnchor) {
      activeAnchorRef.current = null;
      setActiveSourceId(null);
      return;
    }

    activeAnchorRef.current = anchor;
    pendingSourceScrollRef.current = sourceId;
    setActiveSourceId(sourceId);

    window.requestAnimationFrame(() => {
      updateBubbleLayout();
      scrollActiveSourceIntoView();
    });
  }

  function commitNoteSnapshot(nextSnapshot) {
    const normalizedSnapshot = normalizeNoteSnapshot(nextSnapshot);
    setEditHistory((current) => {
      if (isSameNoteSnapshot(current.present, normalizedSnapshot)) return current;

      return {
        past: [...current.past, current.present].slice(-80),
        present: normalizedSnapshot,
        future: [],
      };
    });
    onResultChange((current) => applyNoteSnapshotToResult(current, normalizedSnapshot));
  }

  function updateTopic(topic) {
    commitNoteSnapshot({
      topic,
      notes: cloneNotes(result.notes),
    });
  }

  function updateNoteBlock(blockId, patch) {
    commitNoteSnapshot({
      topic: result.topic,
      notes: result.notes.map((block) => (block.id === blockId ? { ...block, ...patch } : block)),
    });
  }

  function commitNoteDocumentFromDom() {
    if (!noteDocumentRef.current) return;

    const nextNotes = result.notes.map((note) => {
      const noteNode = noteDocumentRef.current.querySelector(`[data-note-id="${cssEscape(note.id)}"]`);
      if (!noteNode) return note;

      const title = noteNode.querySelector("[data-note-title]")?.textContent?.trim() || note.title;
      const content = noteNode.querySelector("[data-note-content]")?.textContent?.trim() || "";
      return {
        ...note,
        title,
        content,
      };
    });

    commitNoteSnapshot({
      topic: result.topic,
      notes: nextNotes,
    });
  }

  function undoNoteEdit() {
    if (!canUndo) return;

    const previous = editHistory.past[editHistory.past.length - 1];
    setEditHistory((current) => ({
      past: current.past.slice(0, -1),
      present: previous,
      future: [current.present, ...current.future].slice(0, 80),
    }));
    onResultChange((current) => applyNoteSnapshotToResult(current, previous));
  }

  function redoNoteEdit() {
    if (!canRedo) return;

    const next = editHistory.future[0];
    setEditHistory((current) => ({
      past: [...current.past, current.present].slice(-80),
      present: next,
      future: current.future.slice(1),
    }));
    onResultChange((current) => applyNoteSnapshotToResult(current, next));
  }

  function updateEditDraft(updater) {
    const current = editDraftRef.current;
    const nextSnapshot = typeof updater === "function" ? updater(current) : updater;
    const normalizedSnapshot = normalizeNoteSnapshot(nextSnapshot);
    if (isSameNoteSnapshot(current, normalizedSnapshot)) return;

    setDraftHistory((history) => ({
      past: [...history.past, current].slice(-80),
      future: [],
    }));
    editDraftRef.current = normalizedSnapshot;
    setEditDraft(normalizedSnapshot);
  }

  function undoDraftEdit() {
    if (!draftHistory.past.length) return;

    const previous = draftHistory.past[draftHistory.past.length - 1];
    const currentDraft = editDraftRef.current;
    setDraftHistory((current) => ({
      past: current.past.slice(0, -1),
      future: [currentDraft, ...current.future].slice(0, 80),
    }));
    editDraftRef.current = previous;
    setEditDraft(previous);
  }

  function redoDraftEdit() {
    if (!draftHistory.future.length) return;

    const next = draftHistory.future[0];
    const currentDraft = editDraftRef.current;
    setDraftHistory((current) => ({
      past: [...current.past, currentDraft].slice(-80),
      future: current.future.slice(1),
    }));
    editDraftRef.current = next;
    setEditDraft(next);
  }

  function undoCurrentEdit() {
    if (isEditing) {
      undoDraftEdit();
      return;
    }
    undoNoteEdit();
  }

  function redoCurrentEdit() {
    if (isEditing) {
      redoDraftEdit();
      return;
    }
    redoNoteEdit();
  }

  function startFreeEdit() {
    setActiveSourceId(null);
    const nextDraft = createNoteSnapshot(result);
    editDraftRef.current = nextDraft;
    setEditDraft(nextDraft);
    setDraftHistory({ past: [], future: [] });
    setIsEditing(true);
  }

  function cancelFreeEdit() {
    const nextDraft = createNoteSnapshot(result);
    editDraftRef.current = nextDraft;
    setEditDraft(nextDraft);
    setDraftHistory({ past: [], future: [] });
    setIsEditing(false);
  }

  function saveFreeEdit() {
    commitNoteSnapshot(editDraftRef.current);
    setDraftHistory({ past: [], future: [] });
    setIsEditing(false);
  }

  function updateDraftTopic(topic) {
    updateEditDraft((current) => ({
      ...current,
      topic,
    }));
  }

  function updateDraftNote(noteId, patch) {
    updateEditDraft((current) => ({
      ...current,
      notes: current.notes.map((note) => (note.id === noteId ? { ...note, ...patch } : note)),
    }));
  }

  function addDraftNote() {
    updateEditDraft((current) => ({
      ...current,
      notes: [
        ...current.notes,
        {
          id: createLocalNoteId(current.notes),
          title: "新笔记小节",
          summary: "",
          content: "",
          keyPoints: [],
          blocks: [],
          citationIds: [],
          sourceRefs: [],
          level: 1,
          parentId: "",
        },
      ],
    }));
  }

  function deleteDraftNote(noteId) {
    updateEditDraft((current) => {
      if (current.notes.length <= 1) return current;
      return {
        ...current,
        notes: current.notes.filter((note) => note.id !== noteId),
      };
    });
  }

  async function sendMessage() {
    const text = chatInput.trim();
    if (!text || isChatSending) return;

    setMessages((prev) => [
      ...prev,
      { role: "user", text },
    ]);
    setChatInput("");
    setChatOpen(true);
    setChatError("");
    setIsChatSending(true);

    try {
      const response = await chatAgent({
        resultId: result.id,
        question: text,
        topK: 3,
      });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: response.answer || "当前资料没有足够证据回答这个问题。",
          citations: normalizeChatCitations(response.used_citations),
          suggestions: normalizeChatSuggestions(response.follow_up_suggestions),
        },
      ]);
    } catch (err) {
      setChatError(err instanceof Error ? err.message : "AI 对话请求失败，请检查后端连接。");
    } finally {
      setIsChatSending(false);
    }
  }

  function openChatCitation(sourceId) {
    if (!sourceById.has(sourceId)) return;
    const anchor = noteDocumentRef.current?.querySelector(`[data-source-id="${cssEscape(sourceId)}"]`);
    if (anchor && !anchor.disabled) {
      anchor.scrollIntoView({ block: "center", behavior: "smooth" });
      activeAnchorRef.current = anchor;
    }
    setActiveSourceId(sourceId);
    pendingSourceScrollRef.current = sourceId;
    window.requestAnimationFrame(() => {
      updateBubbleLayout();
      scrollActiveSourceIntoView();
    });
  }

  const contentPaddingBottom = chatOpen ? "calc(40vh + 20px)" : "96px";

  if (settingsOpen) {
    return (
      <NoteSettingsScreen
        settings={settings}
        setSettings={setSettings}
        onBack={() => setSettingsOpen(false)}
      />
    );
  }

  return (
    <div ref={shellRef} className="relative flex h-full flex-col px-5 pt-3">
      <header className="flex-none">
        <div className="relative flex items-center justify-between">
          <button onClick={onBack} className="relative z-10 text-[14px] font-medium text-slate-500">
            返回
          </button>

          <div className="pointer-events-none absolute inset-x-0 top-1/2 -translate-y-1/2">
            <div className="relative flex items-center justify-start gap-3 pl-12">
              <button
                type="button"
                onClick={undoCurrentEdit}
                disabled={!canUndoCurrentEdit}
                className={`pointer-events-auto flex h-[26px] w-[26px] items-center justify-center rounded-full border text-[13px] leading-none shadow-sm transition ${
                  canUndoCurrentEdit ? "border-slate-300 bg-white text-slate-700" : "border-slate-200 bg-white text-slate-300"
                }`}
                aria-label="撤销笔记修改"
                title="撤销"
              >
                ↺
              </button>
              <button
                type="button"
                onClick={redoCurrentEdit}
                disabled={!canRedoCurrentEdit}
                className={`pointer-events-auto flex h-[26px] w-[26px] items-center justify-center rounded-full border text-[13px] leading-none shadow-sm transition ${
                  canRedoCurrentEdit ? "border-slate-300 bg-white text-slate-700" : "border-slate-200 bg-white text-slate-300"
                }`}
                aria-label="重做笔记修改"
                title="重做"
              >
                ↻
              </button>
              <span className="pointer-events-none absolute left-1/2 -translate-x-1/2 text-center text-[12px] font-medium tracking-[0.18em] text-slate-400">
                {settings.autoSave ? "笔记将会自动保存" : "自动保存已关闭"}
              </span>
            </div>
          </div>

          <div className="relative z-10 flex items-center gap-4">
            <button
              onClick={onOpenReview}
              className="flex h-8 w-8 items-center justify-center rounded-full border border-blue-200 bg-blue-500 text-[12px] font-medium text-white shadow-sm"
              aria-label="复习"
            >
              复习
            </button>
            <button
              onClick={() => {
                setChatOpen(false);
                setSettingsOpen(true);
              }}
              className="text-[14px] font-medium text-slate-900"
            >
              配置
            </button>
          </div>
        </div>
      </header>

      <main ref={noteScrollRef} className="min-h-0 flex-1 overflow-y-auto pt-16" style={{ paddingBottom: contentPaddingBottom }}>
        <article className="space-y-6">
          <section className="space-y-3">
            <p className="text-[12px] uppercase tracking-[0.24em] text-slate-400">Agent 生成笔记</p>
            {isEditing ? (
              <input
                value={editDraft.topic}
                onChange={(event) => updateDraftTopic(event.target.value)}
                className="w-full rounded-[22px] border border-blue-100 bg-white px-4 py-3 text-[28px] font-semibold tracking-tight text-slate-900 outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-50"
                aria-label="编辑笔记标题"
              />
            ) : (
              <h1 className="text-[34px] font-normal tracking-tight text-slate-900">{result.topic}</h1>
            )}
            <p className="text-[12px] text-slate-400">
              {isEditing
                ? "正在编辑：可自由修改标题、摘要、正文和知识点，保存后会同步到本地历史。"
                : settings.reviewMode ? "复习模式已开启：优先关注标题、重点和引用证据" : "由 AgentResult.notes / sources / citations 渲染"}
            </p>
          </section>

          {settings.reviewMode ? (
            <section className="rounded-[24px] border border-blue-100 bg-blue-50 px-4 py-3 text-[13px] leading-6 text-blue-900">
              复习模式会弱化编辑感，帮助你按章节快速回看知识点。可以随时进入配置页关闭。
            </section>
          ) : null}

          <section className="space-y-4">
            <p className="text-[12px] uppercase tracking-[0.24em] text-slate-400">正文</p>
            <div className="text-[15px] leading-8 text-slate-700">
              {isEditing ? (
                <NoteFreeEditor
                  draft={editDraft}
                  onUpdateNote={updateDraftNote}
                  onAddNote={addDraftNote}
                  onDeleteNote={deleteDraftNote}
                />
              ) : result.notes.length ? (
                <div
                  key={result.id}
                  ref={noteDocumentRef}
                  className="min-h-[340px] text-[15px] leading-8 text-slate-700"
                  aria-label="整篇笔记正文"
                >
                  {result.notes.map((note, index) => (
                    <LearningNoteCard
                      key={note.id}
                      note={note}
                      index={index}
                      settings={settings}
                      sourceById={sourceById}
                      result={result}
                      activeSourceId={activeSourceId}
                      toggleSource={toggleSource}
                    />
                  ))}
                </div>
              ) : (
                <div className="rounded-[24px] border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-[13px] leading-6 text-slate-500">
                  当前结果没有返回结构化笔记。请检查后端 JSON 中的 <span className="font-semibold text-slate-700">notes</span> 字段是否为数组。
                </div>
              )}
            </div>
          </section>

          {!settings.showCitations ? (
            <section className="rounded-[24px] border border-slate-200 bg-slate-50 px-4 py-3 text-[13px] leading-6 text-slate-500">
              原文引用已在配置中隐藏。打开后可点击编号查看来源片段。
            </section>
          ) : null}

          {settings.showCitations && missingCitationCount ? (
            <section className="rounded-[24px] border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] leading-6 text-amber-900">
              有 {missingCitationCount} 个引用编号没有匹配到来源片段。请和后端对齐
              <span className="font-semibold"> notes[].citationIds -&gt; sources[].id </span>
              的关系。
            </section>
          ) : null}
        </article>
      </main>

      {isEditing ? (
        <div
          className="absolute left-5 right-5 z-20 flex flex-wrap items-center justify-end gap-2"
          style={{ bottom: chatOpen ? "calc(40vh + 16px)" : "92px" }}
        >
          <button
            type="button"
            onClick={undoDraftEdit}
            disabled={!draftHistory.past.length}
            className="rounded-full border border-slate-200 bg-white px-3 py-2 text-[12px] font-semibold leading-none text-slate-600 shadow-sm transition active:scale-95 disabled:text-slate-300 disabled:opacity-60"
            aria-label="撤回当前编辑"
          >
            撤回
          </button>
          <button
            type="button"
            onClick={redoDraftEdit}
            disabled={!draftHistory.future.length}
            className="rounded-full border border-slate-200 bg-white px-3 py-2 text-[12px] font-semibold leading-none text-slate-600 shadow-sm transition active:scale-95 disabled:text-slate-300 disabled:opacity-60"
            aria-label="取消撤回当前编辑"
          >
            取消撤回
          </button>
          <button
            type="button"
            onClick={cancelFreeEdit}
            className="rounded-full border border-slate-200 bg-white px-3 py-2 text-[12px] font-semibold leading-none text-slate-600 shadow-sm transition active:scale-95"
            aria-label="取消编辑"
          >
            取消
          </button>
          <button
            type="button"
            onClick={saveFreeEdit}
            className="rounded-full bg-blue-600 px-4 py-2.5 text-[13px] font-semibold leading-none text-white shadow-[0_16px_36px_rgba(37,99,235,0.32)] transition active:scale-95"
            aria-label="保存当前笔记"
          >
            保存
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={startFreeEdit}
          className="absolute right-5 z-20 rounded-full bg-blue-600 px-5 py-3 text-[14px] font-semibold leading-none text-white shadow-[0_16px_36px_rgba(37,99,235,0.32)] transition active:scale-95"
          style={{ bottom: chatOpen ? "calc(40vh + 16px)" : "92px" }}
          aria-label="编辑当前笔记"
        >
          编辑
        </button>
      )}

      {activeSource && bubbleLayout ? (
        <div
          className="absolute z-30"
          style={{
            left: `${bubbleLayout.left}px`,
            top: `${bubbleLayout.top}px`,
            width: `${bubbleLayout.width}px`,
          }}
        >
          <div className="relative overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-[0_20px_60px_rgba(15,23,42,0.18)]">
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">引用来源</p>
                <p className="mt-1 text-[13px] font-medium text-slate-800">{getReadableSourceTitle(activeSource)}</p>
                <p className="mt-1 text-[11px] text-slate-400">
                  {formatSourceLocation(activeSource, activeCitation)}
                </p>
              </div>
              <button onClick={() => setActiveSourceId(null)} className="text-[13px] font-medium text-slate-500">
                收起
              </button>
            </div>
            <div ref={bubbleScrollRef} className="max-h-[248px] overflow-y-auto px-4 py-4 text-[13px] leading-6 text-slate-700">
              {activeCitation?.quote ? (
                <div className="mb-3 rounded-2xl border border-amber-200 bg-amber-50 px-3 py-3 text-amber-950">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-white px-2 py-1 text-[11px] font-semibold text-amber-700 ring-1 ring-amber-100">
                      原文 quote
                    </span>
                    {activeCitation.confidence ? (
                      <span className="rounded-full bg-white px-2 py-1 text-[11px] font-semibold text-slate-500 ring-1 ring-slate-200">
                        置信度 {Math.round(activeCitation.confidence * 100)}%
                      </span>
                    ) : null}
                    {activeCitation.retrievalScore ? (
                      <span className="rounded-full bg-white px-2 py-1 text-[11px] font-semibold text-slate-500 ring-1 ring-slate-200">
                        score {Number(activeCitation.retrievalScore).toFixed(2)}
                      </span>
                    ) : null}
                  </div>
                  <p>{activeCitation.quote}</p>
                </div>
              ) : null}
              {sourceParagraphs.map((paragraph, index) => {
                const source = result.sources[index];
                const isActive = source?.id === activeSource.id;
                return (
                  <p
                    key={source?.id || paragraph}
                    data-source-row-id={source?.id || ""}
                    className={`mb-3 rounded-2xl px-3 py-2 ${
                      isActive ? "bg-amber-50 text-slate-900 ring-1 ring-amber-200" : "bg-transparent"
                    }`}
                  >
                    {paragraph}
                  </p>
                );
              })}
            </div>
          </div>
        </div>
      ) : null}

      <ChatDock
        chatOpen={chatOpen}
        setChatOpen={setChatOpen}
        chatInput={chatInput}
        setChatInput={setChatInput}
        messages={messages}
        isChatSending={isChatSending}
        chatError={chatError}
        messageListRef={messageListRef}
        sendMessage={sendMessage}
        onCitationClick={openChatCitation}
        sourceById={sourceById}
      />
    </div>
  );
}

function NoteFreeEditor({ draft, onUpdateNote, onAddNote, onDeleteNote }) {
  return (
    <div className="space-y-4">
      <div className="rounded-[24px] border border-blue-100 bg-blue-50 px-4 py-3 text-[13px] leading-6 text-blue-900">
        自由编辑不会改动原文引用库；保存后，笔记标题、摘要、正文和知识点会进入当前学习资产。
      </div>

      {draft.notes.map((note, index) => (
        <section key={note.id} className="rounded-[26px] border border-slate-200 bg-white px-4 py-4 shadow-sm">
          <div className="mb-4 flex items-center justify-between gap-3">
            <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-slate-400">Note {index + 1}</p>
            <button
              type="button"
              onClick={() => onDeleteNote(note.id)}
              disabled={draft.notes.length <= 1}
              className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[12px] font-semibold text-slate-500 disabled:text-slate-300"
            >
              删除小节
            </button>
          </div>

          <label className="block">
            <span className="text-[12px] font-semibold text-slate-500">小节标题</span>
            <input
              value={note.title}
              onChange={(event) => onUpdateNote(note.id, { title: event.target.value })}
              className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-[15px] font-semibold text-slate-900 outline-none transition focus:border-blue-300 focus:bg-white"
              placeholder="输入小节标题"
            />
          </label>

          <label className="mt-4 block">
            <span className="text-[12px] font-semibold text-slate-500">本节摘要</span>
            <textarea
              value={note.summary || ""}
              onChange={(event) => onUpdateNote(note.id, { summary: event.target.value })}
              className="mt-2 min-h-[74px] w-full resize-none rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-[14px] leading-6 text-slate-700 outline-none transition focus:border-blue-300 focus:bg-white"
              placeholder="可选：写下这一小节的核心摘要"
            />
          </label>

          <label className="mt-4 block">
            <span className="text-[12px] font-semibold text-slate-500">正文内容</span>
            <textarea
              value={note.content || ""}
              onChange={(event) => onUpdateNote(note.id, { content: event.target.value })}
              className="mt-2 min-h-[160px] w-full resize-y rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-[14px] leading-7 text-slate-700 outline-none transition focus:border-blue-300 focus:bg-white"
              placeholder="自由编辑笔记正文"
            />
          </label>

          <label className="mt-4 block">
            <span className="text-[12px] font-semibold text-slate-500">核心知识点</span>
            <textarea
              value={(note.keyPoints || []).join("\n")}
              onChange={(event) => onUpdateNote(note.id, { keyPoints: splitKeyPoints(event.target.value) })}
              className="mt-2 min-h-[96px] w-full resize-none rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-[14px] leading-6 text-slate-700 outline-none transition focus:border-blue-300 focus:bg-white"
              placeholder="一行一个知识点"
            />
          </label>
        </section>
      ))}

      <button
        type="button"
        onClick={onAddNote}
        className="w-full rounded-[24px] border border-dashed border-blue-200 bg-white px-4 py-4 text-[14px] font-semibold text-blue-700"
      >
        + 新增笔记小节
      </button>
    </div>
  );
}

function LearningNoteCard({ note, index, settings, sourceById, result, activeSourceId, toggleSource }) {
  const keyPoints = Array.isArray(note.keyPoints) ? note.keyPoints.filter(Boolean) : [];
  const citationIds = Array.isArray(note.citationIds) ? note.citationIds : [];

  return (
    <section
      data-note-id={note.id}
      className="mb-5 rounded-[22px] border border-slate-200 bg-white px-4 py-4 shadow-sm last:mb-0"
      style={{ paddingLeft: `${Math.min(Math.max((note.level || 1) - 1, 0), 3) * 16 + 16}px` }}
    >
      <div className="mb-3 flex items-start gap-3">
        <span className="mt-1 shrink-0 rounded-full border border-blue-100 bg-blue-50 px-2 py-0.5 text-[11px] font-semibold text-blue-600">
          NOTE {index + 1}
        </span>
        <h2 data-note-title className="text-[17px] font-semibold leading-7 text-slate-950">
          {note.title}
        </h2>
      </div>

      {note.summary ? (
        <section className="mb-3 rounded-[16px] border border-blue-100 bg-blue-50/70 px-3 py-3">
          <p className="text-[12px] font-semibold text-blue-600">概要</p>
          <p className="mt-1 text-[14px] leading-7 text-blue-950">{note.summary}</p>
        </section>
      ) : null}

      {note.content ? (
        <section className="mb-3">
          <p className="text-[12px] font-semibold text-slate-500">解释内容</p>
          <p className="mt-1 whitespace-pre-wrap text-[15px] leading-8 text-slate-700">
            <span data-note-content>{note.content}</span>
            {settings.showCitations && citationIds.length ? (
              <span contentEditable={false} className="ml-1.5 inline-flex flex-wrap items-center gap-1.5 align-baseline">
                {citationIds.map((sourceId) => {
                  const hasSource = sourceById.has(sourceId);
                  const sourceIndex = result.sources.findIndex((source) => source.id === sourceId);
                  return (
                    <button
                      key={sourceId}
                      type="button"
                      data-source-id={sourceId}
                      disabled={!hasSource}
                      onClick={(event) => toggleSource(sourceId, event.currentTarget)}
                      className={`inline-flex h-6 min-w-6 items-center justify-center rounded-full border px-1.5 text-[11px] font-semibold leading-none transition ${
                        !hasSource
                          ? "cursor-not-allowed border-amber-200 bg-amber-50 text-amber-600"
                          : activeSourceId === sourceId
                            ? "border-slate-900 bg-slate-900 text-white"
                            : "border-slate-300 bg-white text-slate-600"
                      }`}
                      title={hasSource ? `引用 ${sourceId}` : `引用 ${sourceId} 缺少对应 sources`}
                      aria-label={hasSource ? `引用 ${sourceId}` : `引用 ${sourceId} 缺少对应来源`}
                    >
                      {sourceIndex >= 0 ? sourceIndex + 1 : "?"}
                    </button>
                  );
                })}
              </span>
            ) : null}
          </p>
        </section>
      ) : null}

      {keyPoints.length ? (
        <section className="rounded-[16px] border border-slate-200 bg-slate-50 px-3 py-3">
          <p className="text-[12px] font-semibold text-slate-500">要点</p>
          <ul className="mt-2 space-y-1.5 text-[14px] leading-7 text-slate-700">
            {keyPoints.map((point, pointIndex) => (
              <li key={`${point}-${pointIndex}`} className="flex gap-2">
                <span className="mt-[11px] h-1.5 w-1.5 shrink-0 rounded-full bg-blue-500" />
                <span>{point}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </section>
  );
}

function SemanticNoteDetails({ note }) {
  const visibleBlocks = (note.blocks || []).filter(
    (block) => block.type !== "summary" || block.text !== note.summary,
  );
  const hasDetails = note.summary || note.keyPoints?.length || visibleBlocks.length;
  if (!hasDetails) return null;

  return (
    <div contentEditable={false} className="mb-4 space-y-3">
      {note.summary ? (
        <div className="rounded-[18px] border border-blue-100 bg-blue-50/80 px-3.5 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-blue-500">本节摘要</p>
          <p className="mt-1.5 text-[13px] leading-6 text-blue-950">{note.summary}</p>
        </div>
      ) : null}

      {note.keyPoints?.length ? (
        <div className="rounded-[18px] border border-slate-200 bg-slate-50/80 px-3.5 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">核心知识点</p>
          <ul className="mt-2 space-y-1.5 text-[13px] leading-6 text-slate-700">
            {note.keyPoints.map((point, index) => (
              <li key={`${point}-${index}`} className="flex gap-2">
                <span className="mt-[9px] h-1.5 w-1.5 shrink-0 rounded-full bg-blue-500" />
                <span>{point}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {visibleBlocks.map((block, index) => (
        <NoteStructureBlock key={block.id || `${block.type}-${index}`} block={block} />
      ))}
    </div>
  );
}

function NoteStructureBlock({ block }) {
  const items = block.structuredItems?.length ? block.structuredItems : block.items || [];
  if (!block.title && !block.text && !items.length) return null;

  return (
    <div className="rounded-[18px] border border-slate-200 bg-white px-3.5 py-3 shadow-[0_8px_24px_rgba(15,23,42,0.05)]">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[13px] font-semibold text-slate-900">{block.title || noteBlockLabel(block.type)}</p>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">
          {noteBlockLabel(block.type)}
        </span>
      </div>
      {block.text ? <p className="mt-2 text-[13px] leading-6 text-slate-600">{block.text}</p> : null}
      {items.length ? (
        <ul className="mt-2 space-y-2 text-[13px] leading-6 text-slate-700">
          {items.map((item, index) => {
            const text = structuredItemText(item);
            const children = typeof item === "object" && item ? item.children || [] : [];
            return (
              <li key={`${text}-${index}`} className="rounded-2xl bg-slate-50 px-3 py-2">
                <div className="flex gap-2">
                  <span className="mt-[9px] h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />
                  <span>{text}</span>
                </div>
                {children.length ? (
                  <ul className="ml-3 mt-1.5 space-y-1 border-l border-slate-200 pl-3 text-[12px] text-slate-500">
                    {children.map((child, childIndex) => (
                      <li key={`${structuredItemText(child)}-${childIndex}`}>{structuredItemText(child)}</li>
                    ))}
                  </ul>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

function structuredItemText(item) {
  if (typeof item === "string") return item;
  return item?.text || item?.title || item?.label || item?.description || "";
}

function normalizeChatCitations(value) {
  const items = Array.isArray(value) ? value : [];
  const citations = items
    .map((item) => {
      if (typeof item === "string" || typeof item === "number") return String(item);
      return String(item?.sourceId || item?.source_id || item?.id || item?.chunkId || item?.chunk_id || "");
    })
    .map((item) => item.trim())
    .filter(Boolean);
  return [...new Set(citations)].slice(0, 6);
}

function normalizeChatSuggestions(value) {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => String(item || "").trim())
    .filter(Boolean)
    .slice(0, 3);
}

function noteBlockLabel(type) {
  return {
    summary: "摘要",
    outline: "结构",
    definition: "定义",
    mechanism: "机制",
    procedure: "过程",
    formula: "公式",
    effect: "作用",
    evidence: "证据",
    example: "示例",
    text: "说明",
  }[type] || "知识块";
}

function formatSourceLocation(source, citation) {
  const paragraphStart = citation?.paragraphStart || source?.paragraphStart;
  const paragraphEnd = citation?.paragraphEnd || source?.paragraphEnd;
  const lineStart = citation?.lineStart || source?.lineStart;
  const lineEnd = citation?.lineEnd || source?.lineEnd;
  const values = [
    citation?.page || source?.page ? `页码 ${citation?.page || source?.page}` : "",
    citation?.slide || source?.slide ? `Slide ${citation?.slide || source?.slide}` : "",
    paragraphStart ? `段落 ${[paragraphStart, paragraphEnd].filter(Boolean).join("-")}` : "",
    lineStart ? `行 ${[lineStart, lineEnd].filter(Boolean).join("-")}` : "",
  ];

  return values.filter(Boolean).join(" · ") || "来源片段";
}

function getReadableSourceTitle(source) {
  const title = source?.title?.trim();
  if (!title || isMachineSourceLabel(title, source)) {
    return "原文片段";
  }
  return title;
}

function isMachineSourceLabel(title, source) {
  const normalized = title.toLowerCase();
  const machineValues = [source?.id, source?.sourceRef, source?.chunkId]
    .filter(Boolean)
    .map((value) => String(value).toLowerCase());

  return (
    machineValues.some((value) => value && normalized.includes(value)) ||
    /input-[0-9a-f]{8,}/i.test(title) ||
    /(?:^|[\s/_-])para[_-]?\d+/i.test(title) ||
    /doc-[0-9a-f-]{8,}/i.test(title)
  );
}

function cssEscape(value) {
  if (typeof window !== "undefined" && window.CSS?.escape) {
    return window.CSS.escape(value);
  }
  return String(value).replace(/["\\]/g, "\\$&");
}

function createNoteSnapshot(result) {
  return {
    topic: result.topic,
    notes: cloneNotes(result.notes),
  };
}

function cloneNotes(notes) {
  return notes.map((note) => ({
    ...note,
    citationIds: [...(note.citationIds || [])],
    sourceRefs: [...(note.sourceRefs || [])],
    keyPoints: [...(note.keyPoints || [])],
    blocks: (note.blocks || []).map((block) => ({
      ...block,
      items: [...(block.items || [])],
      structuredItems: [...(block.structuredItems || [])],
    })),
  }));
}

function normalizeNoteSnapshot(snapshot) {
  const notes = (snapshot.notes || []).map((note, index) => {
    const title = String(note.title || "").trim() || `笔记小节 ${index + 1}`;
    const summary = String(note.summary || "").trim();
    const content = String(note.content || "").trim();
    const keyPoints = splitKeyPoints(note.keyPoints || []);

    return {
      ...note,
      id: String(note.id || `note-${index + 1}`),
      title,
      summary,
      content,
      keyPoints,
      blocks: (note.blocks || []).filter((block) => block?.type !== "summary"),
      citationIds: (note.citationIds || []).map(String),
      sourceRefs: (note.sourceRefs || []).map(String),
      level: Number.isFinite(Number(note.level)) ? Number(note.level) : 1,
      parentId: String(note.parentId || ""),
    };
  });

  return {
    topic: String(snapshot.topic || "").trim() || "未命名笔记",
    notes: notes.length ? notes : [
      {
        id: "note-1",
        title: "笔记小节 1",
        summary: "",
        content: "",
        keyPoints: [],
        blocks: [],
        citationIds: [],
        sourceRefs: [],
        level: 1,
        parentId: "",
      },
    ],
  };
}

function splitKeyPoints(value) {
  const items = Array.isArray(value) ? value : String(value || "").split(/\r?\n/);
  return items
    .map((item) => String(item || "").trim())
    .filter(Boolean);
}

function createLocalNoteId(notes) {
  const ids = new Set((notes || []).map((note) => String(note.id || "")));
  let index = notes.length + 1;
  let id = `local-note-${index}`;
  while (ids.has(id)) {
    index += 1;
    id = `local-note-${index}`;
  }
  return id;
}

function applyNoteSnapshotToResult(result, snapshot) {
  return {
    ...result,
    topic: snapshot.topic,
    notes: cloneNotes(snapshot.notes),
  };
}

function isSameNoteSnapshot(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function NoteSettingsScreen({ settings, setSettings, onBack }) {
  function updateSetting(key, value) {
    setSettings((current) => ({ ...current, [key]: value }));
  }

  const settingsItems = [
    {
      key: "reviewMode",
      title: "复习模式",
      desc: "开启后笔记页更偏复习阅读，突出章节回看和重点提示。",
    },
    {
      key: "showCitations",
      title: "原文引用",
      desc: "开启后在正文中显示引用编号，可点击查看来源片段。",
    },
    {
      key: "autoSave",
      title: "自动保存",
      desc: "开启后保留自动保存提示，适合后续接入真实笔记编辑。",
    },
  ];

  return (
    <div className="flex h-full flex-col px-5 pt-3">
      <header className="flex-none">
        <div className="flex items-center justify-between">
          <button onClick={onBack} className="text-[14px] font-medium text-slate-500">
            返回
          </button>
          <p className="text-[12px] font-medium tracking-[0.18em] text-slate-400">笔记配置</p>
          <button onClick={onBack} className="text-[14px] font-medium text-blue-600">
            完成
          </button>
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto pt-10 pb-8">
        <section className="space-y-3">
          <p className="text-[12px] uppercase tracking-[0.24em] text-slate-400">Settings</p>
          <h1 className="text-[34px] font-normal tracking-tight text-slate-900">笔记配置</h1>
          <p className="text-[13px] leading-6 text-slate-500">
            控制当前笔记的阅读方式、引用显示和保存提示。设置会立即作用在这篇笔记上。
          </p>
        </section>

        <section className="mt-8 space-y-3">
          {settingsItems.map((item) => (
            <div key={item.key} className="rounded-[26px] border border-slate-200 bg-white px-4 py-4 shadow-sm">
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-[15px] font-semibold text-slate-900">{item.title}</p>
                  <p className="mt-1 text-[12px] leading-5 text-slate-500">{item.desc}</p>
                </div>
                <Toggle
                  checked={settings[item.key]}
                  onChange={(checked) => updateSetting(item.key, checked)}
                />
              </div>
            </div>
          ))}
        </section>

        <section className="mt-6 rounded-[26px] border border-blue-100 bg-blue-50 px-4 py-4">
          <p className="text-[13px] font-semibold text-blue-900">当前状态</p>
          <div className="mt-3 grid gap-2 text-[12px] leading-5 text-blue-800">
            <p>复习模式：{settings.reviewMode ? "已开启" : "已关闭"}</p>
            <p>原文引用：{settings.showCitations ? "显示引用编号" : "隐藏引用编号"}</p>
            <p>自动保存：{settings.autoSave ? "显示自动保存提示" : "关闭自动保存提示"}</p>
          </div>
        </section>
      </main>
    </div>
  );
}

function Toggle({ checked, onChange }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`relative h-8 w-14 shrink-0 rounded-full transition ${checked ? "bg-blue-600" : "bg-slate-300"}`}
      aria-pressed={checked}
    >
      <span
        className={`absolute top-1 h-6 w-6 rounded-full bg-white shadow-sm transition ${
          checked ? "left-7" : "left-1"
        }`}
      />
    </button>
  );
}

function ChatDock({
  chatOpen,
  setChatOpen,
  chatInput,
  setChatInput,
  messages,
  isChatSending,
  chatError,
  messageListRef,
  sendMessage,
  onCitationClick,
  sourceById,
}) {
  return (
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
                    message.role === "user" ? "bg-slate-900 text-white" : "border border-slate-200 bg-slate-50 text-slate-700"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{message.text}</p>
                  {message.citations?.length ? (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {message.citations.map((sourceId) => {
                        const source = sourceById.get(sourceId);
                        return (
                          <button
                            key={sourceId}
                            type="button"
                            disabled={!source}
                            onClick={() => onCitationClick(sourceId)}
                            className="rounded-full border border-blue-100 bg-white px-2 py-1 text-[11px] font-semibold text-blue-700 disabled:border-slate-200 disabled:text-slate-300"
                          >
                            {source ? getReadableSourceTitle(source) : sourceId}
                          </button>
                        );
                      })}
                    </div>
                  ) : null}
                  {message.suggestions?.length ? (
                    <div className="mt-3 space-y-1.5 border-t border-slate-200 pt-2 text-[12px] leading-5 text-slate-500">
                      {message.suggestions.map((suggestion, suggestionIndex) => (
                        <p key={`${suggestion}-${suggestionIndex}`}>{suggestion}</p>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
            {isChatSending ? (
              <div className="flex justify-start">
                <div className="rounded-[20px] border border-blue-100 bg-blue-50 px-4 py-3 text-[13px] leading-6 text-blue-900">
                  后端 M7 正在检索来源并生成回答...
                </div>
              </div>
            ) : null}
            {chatError ? (
              <div className="rounded-[18px] bg-rose-50 px-3 py-2 text-[12px] leading-5 text-rose-700">
                {chatError}
              </div>
            ) : null}
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
                onChange={(event) => setChatInput(event.target.value)}
                placeholder="问 AI：帮我总结重点、扩写这一段..."
                disabled={isChatSending}
                className="max-h-24 flex-1 resize-none border-0 bg-transparent py-2 text-[14px] leading-6 text-slate-700 outline-none placeholder:text-slate-300"
                rows={1}
              />
              <button
                onClick={sendMessage}
                disabled={isChatSending || !chatInput.trim()}
                className="rounded-full bg-slate-900 px-4 py-2 text-[13px] font-medium text-white disabled:bg-slate-200 disabled:text-slate-400"
              >
                {isChatSending ? "等待" : "发送"}
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
  );
}
