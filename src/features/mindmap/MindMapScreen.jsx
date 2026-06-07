import { useEffect, useMemo, useState } from "react";
import { Card } from "../../components/Card";
import { TopBar } from "../../components/TopBar";
import { isWebViewShell } from "../../services/appShellMode";

export function MindMapLibraryScreen({ result, onOpenMap }) {
  const nodeCount = result.mindMap.nodes.length;
  const edgeCount = result.mindMap.edges.length;
  const savedMaps = [
    {
      id: result.id || "current-map",
      title: result.topic,
      summary: result.summary,
      meta: `${nodeCount} 个节点 · ${edgeCount} 条连线`,
      status: nodeCount ? "可打开" : "待生成",
    },
  ];

  return (
    <div className="space-y-5 pb-6">
      <TopBar title="导图目录" subtitle="查看已保存的知识导图" />

      <div className="px-5">
        <Card title="已保存导图" subtitle="Mind Maps">
          <div className="space-y-3">
            {savedMaps.map((item) => (
              <button
                key={item.id}
                onClick={onOpenMap}
                className="w-full rounded-[28px] border border-slate-200 bg-slate-50 p-4 text-left transition hover:border-blue-200 hover:bg-white"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-slate-400">当前结果</p>
                    <h2 className="mt-2 text-[18px] font-semibold tracking-tight text-slate-900">{item.title}</h2>
                    <p className="mt-2 line-clamp-2 text-[13px] leading-5 text-slate-500">{item.summary}</p>
                  </div>
                  <span className="shrink-0 rounded-full bg-blue-50 px-3 py-1 text-[12px] font-semibold text-blue-600">
                    {item.status}
                  </span>
                </div>
                <div className="mt-4 flex items-center justify-between rounded-2xl bg-white px-3 py-2 text-[12px] font-semibold text-slate-500">
                  <span>{item.meta}</span>
                  <span className="text-blue-600">进入横屏</span>
                </div>
              </button>
            ))}
          </div>
        </Card>
      </div>

      <div className="px-5">
        <Card title="导图说明" subtitle="Usage">
          <div className="space-y-3 text-[13px] leading-6 text-slate-600">
            <p>导图目录用于承载后续多份学习资料生成的知识图谱。当前阶段先展示最近一次 AgentResult 生成的导图。</p>
            <p>点击具体导图后进入横屏画布，适合录屏展示节点关系和知识点详情。</p>
          </div>
        </Card>
      </div>
    </div>
  );
}

export function MindMapScreen({ result, onBack }) {
  const { nodes, edges } = result.mindMap;
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const isWebView = isWebViewShell();
  const nodeById = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);
  const selectedNode = selectedNodeId ? nodeById.get(selectedNodeId) : null;
  const centerNode = nodeById.get("center") || nodes[0];
  const detailNode = selectedNode || centerNode;
  const focusX = selectedNode ? 50 - selectedNode.x : 0;
  const focusY = selectedNode ? 50 - selectedNode.y : 0;
  const hasMap = nodes.length > 0;

  useEffect(() => {
    const androidShell = window.AndroidShell;
    if (!isWebView || !androidShell?.setMindMapLandscape) return undefined;

    androidShell.setMindMapLandscape(true);
    return () => androidShell.setMindMapLandscape(false);
  }, [isWebView]);

  return (
    <div className={`mindmap-orientation-gate relative h-full overflow-hidden bg-[#eef4f8] ${isWebView ? "mindmap-webview-orientation-gate" : ""}`}>
      <div className="mindmap-portrait-notice absolute inset-0 z-50 hidden place-items-center bg-[#eef4f8] px-8 text-center">
        <div className="max-w-[320px] rounded-[30px] border border-white/80 bg-white/88 px-6 py-7 shadow-[0_24px_70px_rgba(15,23,42,0.14)] backdrop-blur-xl">
          <div className="mx-auto grid h-16 w-16 place-items-center rounded-[24px] bg-blue-50 text-[30px] text-blue-600">
            ⟲
          </div>
          <h2 className="mt-5 text-[22px] font-semibold tracking-tight text-slate-950">请切换为横屏</h2>
          <p className="mt-3 text-[14px] leading-6 text-slate-500">
            思维导图详情需要横屏展示节点关系。旋转手机后，画布和节点详情会自动显示。
          </p>
          <button onClick={onBack} className="mt-5 rounded-full border border-slate-200 bg-white px-5 py-2 text-[13px] font-semibold text-slate-600 shadow-sm">
            返回目录
          </button>
        </div>
      </div>

      <div className="mindmap-landscape-only flex h-full flex-col overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(135deg,rgba(37,99,235,0.12),transparent_34%),radial-gradient(circle_at_78%_18%,rgba(14,165,233,0.18),transparent_28%),linear-gradient(rgba(15,23,42,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(15,23,42,0.05)_1px,transparent_1px)] bg-[length:auto,auto,28px_28px,28px_28px]" />

        <header className="relative z-10 flex h-14 flex-none items-center justify-between border-b border-white/70 bg-white/72 px-5 backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[12px] font-semibold text-slate-600 shadow-sm">
            返回
          </button>
          <div>
            <h1 className="text-[18px] font-semibold tracking-tight text-slate-950">知识导图横屏模式</h1>
            <p className="text-[11px] text-slate-500">Landscape canvas · {nodes.length} nodes · {edges.length} links</p>
          </div>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[12px] font-semibold text-slate-500 shadow-sm">
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          横屏演示
        </div>
        </header>

        <div className="relative z-10 grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_280px] gap-4 p-4">
        <section className="relative min-w-0 overflow-hidden rounded-[28px] border border-white/80 bg-white/64 shadow-[inset_0_1px_0_rgba(255,255,255,0.9),0_20px_50px_rgba(15,23,42,0.12)] backdrop-blur-xl">
          <div className="absolute left-4 top-4 z-20 flex items-center gap-2 rounded-full border border-slate-200 bg-white/90 px-3 py-1.5 shadow-sm">
            <span className="text-[11px] font-semibold text-slate-500">点击节点查看详情</span>
          </div>

          <div
            className="absolute inset-0 transition-transform duration-500 ease-out"
            style={selectedNode ? { transform: `translate3d(${focusX * 0.35}%, ${focusY * 0.35}%, 0) scale(1.05)` } : undefined}
          >
            <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              <defs>
                <filter id="softShadow" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="1" stdDeviation="1.2" floodColor="#0f172a" floodOpacity="0.16" />
                </filter>
              </defs>
              {edges.map((edge) => {
                const from = nodeById.get(edge.from);
                const to = nodeById.get(edge.to);
                if (!from || !to) return null;
                const sideX = to.x < 50 ? 38 : to.x > 50 ? 62 : 50;
                const controlY = to.y < 50 ? 34 : 66;
                const path = `M ${from.x} ${from.y} C ${sideX} ${controlY}, ${sideX} ${to.y}, ${to.x} ${to.y}`;
                return (
                  <path
                    key={`${edge.from}-${edge.to}`}
                    d={path}
                    fill="none"
                    stroke={to.line || "#93c5fd"}
                    strokeLinecap="round"
                    strokeWidth="1.15"
                    filter="url(#softShadow)"
                    opacity="0.78"
                  />
                );
              })}
            </svg>

            {nodes.map((node) => {
              const isCenter = node.id === "center";
              const isSelected = selectedNodeId === node.id;
              return (
                <button
                  key={node.id}
                  onClick={() => setSelectedNodeId((current) => (current === node.id ? null : node.id))}
                  className={`absolute z-10 -translate-x-1/2 -translate-y-1/2 border text-left shadow-[0_16px_30px_rgba(15,23,42,0.12)] transition duration-200 hover:-translate-y-[52%] hover:shadow-[0_20px_38px_rgba(15,23,42,0.16)] ${
                    isSelected ? "scale-[1.05] ring-2 ring-slate-900/10" : ""
                  } ${isCenter ? "w-[164px] rounded-[26px] border-blue-200 bg-white px-4 py-4 text-center" : "w-[142px] rounded-[20px] px-3 py-3"}`}
                  style={{
                    left: `${node.x}%`,
                    top: `${node.y}%`,
                    borderColor: isCenter ? "#bfdbfe" : node.line || "#cbd5e1",
                    backgroundColor: isCenter ? "#ffffff" : node.fill || "#ffffff",
                  }}
                >
                  {isCenter ? (
                    <>
                      <p className="text-[10px] font-semibold uppercase text-blue-500">中心主题</p>
                      <h3 className="mt-2 text-[18px] font-semibold tracking-tight text-slate-900">{node.label}</h3>
                    </>
                  ) : (
                    <>
                      <p className="truncate text-[12px] font-semibold text-slate-950">{node.label}</p>
                      <p className="mt-1 line-clamp-2 text-[11px] leading-4 text-slate-600">{node.desc}</p>
                    </>
                  )}
                </button>
              );
            })}

            {!hasMap ? (
              <div className="absolute inset-0 grid place-items-center px-8 text-center">
                <div className="max-w-[360px] rounded-[28px] border border-dashed border-slate-300 bg-white/86 px-6 py-5 shadow-sm">
                  <p className="text-[15px] font-semibold text-slate-900">暂无导图节点</p>
                  <p className="mt-2 text-[13px] leading-6 text-slate-500">
                    请检查后端 JSON 中的 mindMap.nodes 和 mindMap.edges。第二周可先返回少量节点，后续再完善布局。
                  </p>
                </div>
              </div>
            ) : null}
          </div>
        </section>

        <aside className="flex min-h-0 flex-col rounded-[28px] border border-white/80 bg-white/82 p-4 shadow-[0_20px_50px_rgba(15,23,42,0.12)] backdrop-blur-xl">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase text-slate-400">{selectedNode ? "当前节点" : "导图概览"}</p>
              <h2 className="mt-1 text-[22px] font-semibold tracking-tight text-slate-950">{detailNode?.label || result.topic}</h2>
              <p className="mt-2 text-[12px] leading-5 text-slate-500">
                {hasMap ? detailNode?.desc || "选择一个节点查看来源说明、编辑操作和复习线索。" : "当前结果还没有可渲染的导图数据。"}
              </p>
            </div>
            {selectedNode ? (
              <button onClick={() => setSelectedNodeId(null)} className="shrink-0 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-[12px] font-semibold text-slate-500">
                收起
              </button>
            ) : null}
          </div>

          <div className="mt-4 grid grid-cols-2 gap-2">
            {["新增子节点", "同级节点", "重命名", "隐藏分支"].map((item) => (
              <button key={item} className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] font-semibold text-slate-600 shadow-sm">
                {item}
              </button>
            ))}
          </div>

          <div className="mt-4 grid grid-cols-2 gap-2">
            <Metric label="节点" value={nodes.length} />
            <Metric label="连线" value={edges.length} />
          </div>

          <div className="mt-4 flex min-h-0 flex-1 flex-col rounded-[22px] border border-slate-200 bg-slate-50 p-3">
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-semibold uppercase text-slate-400">具体内容</p>
              <p className="text-[11px] font-medium text-slate-400">滑动查看</p>
            </div>
            <div className="mt-3 min-h-0 flex-1 overflow-y-auto rounded-[18px] bg-white px-4 py-4 text-[13px] leading-6 text-slate-600 shadow-inner">
              {(detailNode?.detail || result.summary || "后端可在节点中返回 detail 字段，前端会在这里展示。")
                .split("\n\n")
                .map((paragraph) => (
                  <p key={paragraph} className="mt-3 first:mt-0">
                    {paragraph}
                  </p>
                ))}
            </div>
          </div>
        </aside>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-3 py-2 shadow-sm">
      <p className="text-[18px] font-semibold text-slate-950">{value}</p>
      <p className="text-[11px] text-slate-400">{label}</p>
    </div>
  );
}
