import { useEffect, useMemo, useRef, useState } from "react";

export function NoteDetailScreen({ result, onBack, onOpenReview }) {
  const [chatOpen, setChatOpen] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [activeSourceId, setActiveSourceId] = useState(null);
  const [bubbleLayout, setBubbleLayout] = useState(null);
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "你可以直接问我这篇笔记的重点、帮你压缩成提纲，或者让它更适合复习。",
    },
  ]);
  const shellRef = useRef(null);
  const messageListRef = useRef(null);
  const bubbleScrollRef = useRef(null);
  const citationButtonRefs = useRef({});

  const sourceById = useMemo(() => new Map(result.sources.map((source) => [source.id, source])), [result.sources]);
  const activeSource = activeSourceId ? sourceById.get(activeSourceId) : null;
  const sourceParagraphs = result.sources.map((source) => source.text);
  const citationIds = result.notes.flatMap((note) => note.citationIds);
  const missingCitationCount = citationIds.filter((sourceId) => !sourceById.has(sourceId)).length;

  useEffect(() => {
    if (!messageListRef.current) return;
    messageListRef.current.scrollTop = messageListRef.current.scrollHeight;
  }, [messages, chatOpen]);

  useEffect(() => {
    if (!activeSource || !bubbleScrollRef.current) return;
    const index = result.sources.findIndex((source) => source.id === activeSource.id);
    bubbleScrollRef.current.scrollTop = Math.max(index, 0) * 72;
  }, [activeSource, result.sources]);

  useEffect(() => {
    if (!activeSource || !shellRef.current) {
      setBubbleLayout(null);
      return;
    }

    const anchor = citationButtonRefs.current[activeSource.id];
    if (!anchor) return;

    const containerRect = shellRef.current.getBoundingClientRect();
    const anchorRect = anchor.getBoundingClientRect();
    const bubbleWidth = Math.min(306, containerRect.width - 32);
    const bubbleHeight = 248;
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

  function toggleSource(sourceId) {
    setActiveSourceId((current) => (current === sourceId ? null : sourceId));
  }

  function sendMessage() {
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
  }

  const contentPaddingBottom = chatOpen ? "calc(40vh + 20px)" : "96px";

  return (
    <div ref={shellRef} className="relative flex h-full flex-col px-5 pt-3">
      <header className="flex-none">
        <div className="relative flex items-center justify-between">
          <button onClick={onBack} className="relative z-10 text-[14px] font-medium text-slate-500">
            返回
          </button>

          <div className="pointer-events-none absolute inset-x-0 top-1/2 -translate-y-1/2">
            <div className="relative flex items-center justify-start gap-3 pl-12">
              <button className="pointer-events-auto flex h-[26px] w-[26px] items-center justify-center rounded-full border border-slate-200 bg-white text-[13px] leading-none text-slate-300 shadow-sm">
                ↺
              </button>
              <button className="pointer-events-auto flex h-[26px] w-[26px] items-center justify-center rounded-full border border-slate-200 bg-white text-[13px] leading-none text-slate-300 shadow-sm">
                ↻
              </button>
              <span className="pointer-events-none absolute left-1/2 -translate-x-1/2 text-center text-[12px] font-medium tracking-[0.18em] text-slate-400">
                笔记将会自动保存
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
            <button className="text-[14px] font-medium text-slate-900">配置</button>
          </div>
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto pt-16" style={{ paddingBottom: contentPaddingBottom }}>
        <article className="space-y-6">
          <section className="space-y-3">
            <p className="text-[12px] uppercase tracking-[0.24em] text-slate-400">Agent 生成笔记</p>
            <input
              defaultValue={result.topic}
              className="w-full border-0 bg-transparent p-0 text-[34px] font-normal tracking-tight text-slate-900 outline-none placeholder:text-slate-300"
              aria-label="标题"
            />
            <p className="text-[12px] text-slate-400">由 AgentResult.notes / sources / citations 渲染</p>
          </section>

          <section className="space-y-4">
            <p className="text-[12px] uppercase tracking-[0.24em] text-slate-400">正文</p>
            <div className="space-y-5 text-[15px] leading-8 text-slate-700">
              {result.notes.length ? result.notes.map((block) => (
                <section key={block.id} className="space-y-2">
                  <h2 className="text-[16px] font-semibold tracking-tight text-slate-900">{block.title}</h2>
                  <p className="leading-8 text-slate-700">
                    {block.content}
                    {block.citationIds.map((sourceId) => {
                      const hasSource = sourceById.has(sourceId);
                      return (
                      <button
                        key={sourceId}
                        ref={(node) => {
                          if (node) citationButtonRefs.current[sourceId] = node;
                        }}
                        type="button"
                        disabled={!hasSource}
                        onClick={() => toggleSource(sourceId)}
                        className={`ml-2 inline-flex h-7 w-7 items-center justify-center rounded-full border text-[12px] font-semibold leading-none transition ${
                          !hasSource
                            ? "cursor-not-allowed border-amber-200 bg-amber-50 text-amber-600"
                            : activeSourceId === sourceId
                              ? "border-slate-900 bg-slate-900 text-white"
                              : "border-slate-300 bg-white text-slate-600"
                        }`}
                        title={hasSource ? `引用 ${sourceId}` : `引用 ${sourceId} 缺少对应 sources`}
                        aria-label={hasSource ? `引用 ${sourceId}` : `引用 ${sourceId} 缺少对应来源`}
                      >
                        {sourceId}
                      </button>
                      );
                    })}
                  </p>
                </section>
              )) : (
                <div className="rounded-[24px] border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-[13px] leading-6 text-slate-500">
                  当前结果没有返回结构化笔记。请检查后端 JSON 中的 <span className="font-semibold text-slate-700">notes</span> 字段是否为数组。
                </div>
              )}
            </div>
          </section>

          {missingCitationCount ? (
            <section className="rounded-[24px] border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] leading-6 text-amber-900">
              有 {missingCitationCount} 个引用编号没有匹配到来源片段。请和后端对齐
              <span className="font-semibold"> notes[].citationIds -&gt; sources[].id </span>
              的关系。
            </section>
          ) : null}
        </article>
      </main>

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
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">引用 {activeSource.id}</p>
                <p className="mt-1 text-[13px] font-medium text-slate-800">{activeSource.title}</p>
              </div>
              <button onClick={() => setActiveSourceId(null)} className="text-[13px] font-medium text-slate-500">
                收起
              </button>
            </div>
            <div ref={bubbleScrollRef} className="max-h-[248px] overflow-y-auto px-4 py-4 text-[13px] leading-6 text-slate-700">
              {sourceParagraphs.map((paragraph, index) => {
                const source = result.sources[index];
                const isActive = source?.id === activeSource.id;
                return (
                  <p
                    key={source?.id || paragraph}
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
        messageListRef={messageListRef}
        sendMessage={sendMessage}
      />
    </div>
  );
}

function ChatDock({ chatOpen, setChatOpen, chatInput, setChatInput, messages, messageListRef, sendMessage }) {
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
                onChange={(event) => setChatInput(event.target.value)}
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
  );
}
