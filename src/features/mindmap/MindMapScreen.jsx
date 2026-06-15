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

export function MindMapScreen({ result, onResultChange = () => {}, onBack }) {
  const { nodes, edges } = result.mindMap;
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [zoom, setZoom] = useState(1);
  const isWebView = isWebViewShell();
  const presentableMap = useMemo(() => createPresentableMindMap(nodes, edges, result.topic), [nodes, edges, result.topic]);
  const displayNodes = presentableMap.nodes;
  const displayEdges = presentableMap.edges;
  const nodeById = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);
  const displayNodeById = useMemo(() => new Map(displayNodes.map((node) => [node.id, node])), [displayNodes]);
  const selectedNode = selectedNodeId ? nodeById.get(selectedNodeId) : null;
  const centerNode = nodeById.get("center") || nodes[0];
  const displayCenterNode = displayNodeById.get(centerNode?.id) || displayNodes[0];
  const displaySelectedNode = selectedNodeId ? displayNodeById.get(selectedNodeId) : null;
  const detailNode = displaySelectedNode || displayCenterNode;
  const focusX = displaySelectedNode ? 50 - displaySelectedNode.x : 0;
  const focusY = displaySelectedNode ? 50 - displaySelectedNode.y : 0;
  const toolboxSide = displaySelectedNode?.x > 58 ? "left" : "right";
  const toolboxVertical =
    displaySelectedNode?.y > 68 ? "bottom" : displaySelectedNode?.y < 32 ? "top" : "middle";
  const hasMap = nodes.length > 0;
  const mapActions = [
    { key: "child", label: "新增子节点", onClick: addChildNode, disabled: !hasMap },
    { key: "sibling", label: "同级节点", onClick: addSiblingNode, disabled: !selectedNode || selectedNode.id === centerNode?.id },
    { key: "rename", label: "重命名", onClick: renameNode, disabled: !detailNode },
    { key: "hide", label: "隐藏分支", onClick: hideBranch, disabled: !selectedNode || selectedNode.id === centerNode?.id },
  ];

  useEffect(() => {
    const androidShell = window.AndroidShell;
    if (!isWebView || !androidShell?.setMindMapLandscape) return undefined;

    androidShell.setMindMapLandscape(true);
    return () => androidShell.setMindMapLandscape(false);
  }, [isWebView]);

  function updateMindMap(nextMindMap, nextSelectedNodeId = selectedNodeId) {
    onResultChange((current) => ({
      ...current,
      mindMap: {
        ...(current.mindMap || {}),
        ...nextMindMap,
      },
    }));
    setSelectedNodeId(nextSelectedNodeId);
  }

  function addChildNode() {
    const parent = selectedNode || centerNode;
    if (!parent) return;

    const childCount = edges.filter((edge) => edge.from === parent.id).length;
    const nodeId = createMindMapNodeId(nodes);
    const newNode = createMindMapNode({
      id: nodeId,
      parent,
      index: childCount,
      label: "新节点",
      desc: "点击重命名补充这个知识点",
    });

    updateMindMap({
      nodes: [...nodes, newNode],
      edges: [...edges, { from: parent.id, to: nodeId }],
    }, nodeId);
  }

  function addSiblingNode() {
    if (!selectedNode) return;

    const parentEdge = edges.find((edge) => edge.to === selectedNode.id);
    const parent = parentEdge ? nodeById.get(parentEdge.from) : centerNode;
    if (!parent || selectedNode.id === parent.id) return;

    const siblingCount = edges.filter((edge) => edge.from === parent.id).length;
    const nodeId = createMindMapNodeId(nodes);
    const newNode = createMindMapNode({
      id: nodeId,
      parent,
      index: siblingCount,
      label: "同级节点",
      desc: "补充同一层级的知识点",
    });

    updateMindMap({
      nodes: [...nodes, newNode],
      edges: [...edges, { from: parent.id, to: nodeId }],
    }, nodeId);
  }

  function renameNode() {
    if (!detailNode) return;

    const nextLabel = window.prompt("请输入新的节点名称", detailNode.label || "");
    if (!nextLabel || !nextLabel.trim()) return;

    const trimmedLabel = nextLabel.trim();
    updateMindMap({
      nodes: nodes.map((node) => (node.id === detailNode.id ? { ...node, label: trimmedLabel } : node)),
    }, detailNode.id);

    if (detailNode.id === centerNode?.id) {
      onResultChange((current) => ({ ...current, topic: trimmedLabel }));
    }
  }

  function hideBranch() {
    if (!selectedNode || selectedNode.id === centerNode?.id) return;

    const hiddenNodeIds = collectDescendantNodeIds(selectedNode.id, edges);
    hiddenNodeIds.add(selectedNode.id);

    const nextNodes = nodes.filter((node) => !hiddenNodeIds.has(node.id));
    const nextEdges = edges.filter((edge) => !hiddenNodeIds.has(edge.from) && !hiddenNodeIds.has(edge.to));
    updateMindMap({ nodes: nextNodes, edges: nextEdges }, null);
  }

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

        <div className="relative z-10 min-h-0 flex-1 p-4">
        <section className="relative h-full min-w-0 overflow-hidden rounded-[28px] border border-white/80 bg-white/64 shadow-[inset_0_1px_0_rgba(255,255,255,0.9),0_20px_50px_rgba(15,23,42,0.12)] backdrop-blur-xl">
          <div className="absolute left-4 top-4 z-20 flex items-center gap-2 rounded-full border border-slate-200 bg-white/90 px-3 py-1.5 shadow-sm">
            <span className="text-[11px] font-semibold text-slate-500">点击节点查看详情</span>
          </div>

          <div
            className="absolute inset-0 origin-center transition-transform duration-500 ease-out"
            style={{
              transform: `translate3d(${displaySelectedNode ? focusX * 0.25 : 0}%, ${displaySelectedNode ? focusY * 0.25 : 0}%, 0) scale(${zoom})`,
            }}
          >
            <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              <defs>
                <filter id="softShadow" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="1" stdDeviation="1.2" floodColor="#0f172a" floodOpacity="0.16" />
                </filter>
              </defs>
              {displayEdges.map((edge, index) => {
                const from = displayNodeById.get(edge.from);
                const to = displayNodeById.get(edge.to);
                if (!from || !to) return null;
                const sideX = to.x < from.x ? 35 : to.x > from.x ? 65 : 50;
                const controlY = to.y < from.y ? to.y + 14 : to.y > from.y ? to.y - 14 : to.y;
                const path = `M ${from.x} ${from.y} C ${sideX} ${controlY}, ${sideX} ${to.y}, ${to.x} ${to.y}`;
                return (
                  <path
                    key={`${edge.from}-${edge.to}-${index}`}
                    d={path}
                    fill="none"
                    stroke={to.line || "#93c5fd"}
                    strokeLinecap="round"
                    strokeWidth="2.2"
                    filter="url(#softShadow)"
                    opacity="0.88"
                  />
                );
              })}
            </svg>

            {displayNodes.map((node) => {
              const isCenter = node.id === displayCenterNode?.id;
              const isSelected = selectedNodeId === node.id;
              return (
                <button
                  key={node.id}
                  onClick={() => setSelectedNodeId((current) => (current === node.id ? null : node.id))}
                  className={`absolute z-10 -translate-x-1/2 -translate-y-1/2 overflow-hidden border text-left shadow-[0_16px_30px_rgba(15,23,42,0.12)] transition duration-200 hover:-translate-y-[52%] hover:shadow-[0_20px_38px_rgba(15,23,42,0.16)] ${
                    isSelected ? "scale-[1.05] ring-2 ring-slate-900/10" : ""
                  } ${isCenter ? "w-[170px] rounded-[26px] border-blue-200 bg-white px-4 py-4 text-center" : "w-[160px] rounded-[20px] px-3 py-3"}`}
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
                      <h3 className="mt-2 line-clamp-2 break-words text-[17px] font-semibold leading-tight tracking-tight text-slate-900">{node.label}</h3>
                    </>
                  ) : (
                    <>
                      <p className="line-clamp-2 break-words text-[12px] font-semibold leading-tight text-slate-950">{node.label}</p>
                      <p className="mt-2 line-clamp-2 break-words text-[11px] leading-4 text-slate-600">{node.desc}</p>
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

          <div className="absolute bottom-5 left-5 z-30 flex items-center gap-2 rounded-full border border-white/80 bg-white/86 px-2 py-2 shadow-[0_14px_36px_rgba(15,23,42,0.12)] backdrop-blur-xl">
            <button
              type="button"
              onClick={() => setZoom((current) => Math.max(0.72, Math.round((current - 0.12) * 100) / 100))}
              className="grid h-9 w-9 place-items-center rounded-full border border-slate-200 bg-white text-[18px] font-semibold text-slate-700 shadow-sm"
              aria-label="缩小导图"
            >
              -
            </button>
            <button
              type="button"
              onClick={() => setZoom(1)}
              className="rounded-full px-2 text-[12px] font-semibold text-slate-500"
              aria-label="重置导图缩放"
            >
              {Math.round(zoom * 100)}%
            </button>
            <button
              type="button"
              onClick={() => setZoom((current) => Math.min(1.42, Math.round((current + 0.12) * 100) / 100))}
              className="grid h-9 w-9 place-items-center rounded-full border border-slate-200 bg-white text-[18px] font-semibold text-slate-700 shadow-sm"
              aria-label="放大导图"
            >
              +
            </button>
          </div>

          {displaySelectedNode ? (
            <aside
              className={`absolute z-40 flex max-h-[calc(100%-2.5rem)] w-[360px] max-w-[42%] flex-col rounded-[28px] border border-white/80 bg-white/88 p-4 shadow-[0_20px_50px_rgba(15,23,42,0.18)] backdrop-blur-xl ${
                toolboxSide === "left" ? "left-5" : "right-5"
              } ${
                toolboxVertical === "top"
                  ? "top-5"
                  : toolboxVertical === "bottom"
                    ? "bottom-5"
                    : "top-1/2 -translate-y-1/2"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[10px] font-semibold uppercase text-slate-400">当前节点</p>
                  <h2 className="mt-1 line-clamp-2 text-[22px] font-semibold tracking-tight text-slate-950">{detailNode?.label || result.topic}</h2>
                  <p className="mt-2 line-clamp-2 text-[12px] leading-5 text-slate-500">
                    {detailNode?.desc || "查看来源说明、编辑操作和复习线索。"}
                  </p>
                </div>
                <button onClick={() => setSelectedNodeId(null)} className="shrink-0 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-[12px] font-semibold text-slate-500">
                  收起
                </button>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-2">
                {mapActions.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    onClick={item.onClick}
                    disabled={item.disabled}
                    className={`rounded-2xl border px-3 py-2 text-[12px] font-semibold shadow-sm transition ${
                      item.disabled
                        ? "cursor-not-allowed border-slate-100 bg-slate-50 text-slate-300"
                        : "border-slate-200 bg-white text-slate-700 hover:border-blue-200 hover:bg-blue-50"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>

              <div className="mt-4 grid grid-cols-2 gap-2">
                <Metric label="节点" value={displayNodes.length} />
                <Metric label="连线" value={displayEdges.length} />
              </div>

              <div className="mt-4 min-h-0 rounded-[22px] border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-center justify-between">
                  <p className="text-[11px] font-semibold uppercase text-slate-400">具体内容</p>
                  <p className="text-[11px] font-medium text-slate-400">滑动查看</p>
                </div>
                <div className="mt-3 max-h-32 overflow-y-auto rounded-[18px] bg-white px-4 py-4 text-[13px] leading-6 text-slate-600 shadow-inner">
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
          ) : (
            <div className="absolute right-5 top-5 z-30 rounded-[24px] border border-white/80 bg-white/80 px-4 py-3 shadow-[0_14px_36px_rgba(15,23,42,0.12)] backdrop-blur-xl">
              <p className="text-[10px] font-semibold uppercase text-slate-400">导图概览</p>
              <p className="mt-1 text-[14px] font-semibold text-slate-900">{displayNodes.length} 节点 · {displayEdges.length} 连线</p>
            </div>
          )}
        </section>
        </div>
      </div>
    </div>
  );
}

const mindMapSlots = [
  { x: 10, y: 13 },
  { x: 90, y: 13 },
  { x: 10, y: 41 },
  { x: 90, y: 41 },
  { x: 10, y: 69 },
  { x: 90, y: 69 },
  { x: 10, y: 91 },
  { x: 90, y: 91 },
  { x: 30, y: 13 },
  { x: 70, y: 13 },
  { x: 30, y: 41 },
  { x: 70, y: 41 },
  { x: 30, y: 69 },
  { x: 70, y: 69 },
  { x: 30, y: 91 },
  { x: 70, y: 91 },
  { x: 50, y: 13 },
  { x: 50, y: 91 },
];

const mindMapPalette = [
  { fill: "#dbeafe", line: "#4f7df3" },
  { fill: "#dcfce7", line: "#22c55e" },
  { fill: "#f3e8ff", line: "#a855f7" },
  { fill: "#ffedd5", line: "#f97316" },
  { fill: "#fef3c7", line: "#eab308" },
  { fill: "#e0f2fe", line: "#38bdf8" },
  { fill: "#fae8ff", line: "#d946ef" },
  { fill: "#e2e8f0", line: "#64748b" },
];

function createPresentableMindMap(nodes, edges, topic) {
  if (!nodes.length) {
    return { nodes: [], edges: [] };
  }

  const center = nodes.find((node) => node.id === "center" || node.id === "root") || nodes[0];
  const nonCenterNodes = nodes.filter((node) => node.id !== center.id);
  const centerNode = {
    ...center,
    id: center.id,
    label: center.label || topic || "中心主题",
    desc: center.desc || "中心主题",
    x: 50,
    y: 50,
    fill: "#ffffff",
    line: "#2563eb",
  };
  const placed = [centerNode];
  const childNodes = nonCenterNodes.map((node, index) => {
      const slot = pickNodeSlot(index, nonCenterNodes.length, placed);
      const color = nodeColor(node, index);
      const nextNode = {
        ...node,
        x: slot.x,
        y: slot.y,
        fill: color.fill,
        line: color.line,
        desc: node.desc || detailSummary(node.detail) || "点击查看详情",
      };
      placed.push(nextNode);
      return nextNode;
    });
  const presentableNodes = [centerNode, ...childNodes];

  const presentableNodeIds = new Set(presentableNodes.map((node) => node.id));
  const presentableEdges = edges
    .filter((edge) => presentableNodeIds.has(edge.from) && presentableNodeIds.has(edge.to) && edge.from !== edge.to)
    .map((edge) => ({ from: edge.from, to: edge.to }));
  const connectedTargets = new Set(presentableEdges.map((edge) => edge.to));
  nonCenterNodes.forEach((node) => {
    if (!connectedTargets.has(node.id)) {
      presentableEdges.push({ from: center.id, to: node.id });
    }
  });

  return {
    nodes: presentableNodes,
    edges: presentableEdges.length ? presentableEdges : edges,
  };
}

function nodeColor(node, index) {
  const fallback = mindMapPalette[index % mindMapPalette.length];
  return {
    fill: fallback.fill,
    line: fallback.line,
  };
}

function pickNodeSlot(index, total, placed) {
  const candidates = [
    mindMapSlots[index],
    ...mindMapSlots,
    ...Array.from({ length: Math.max(total, 1) * 6 }, (_, offset) => circleSlot(index + offset, Math.max(total, 1) * 6)),
  ].filter(Boolean);

  const openSlot = candidates.find((slot) => !hasLayoutCollision(slot, placed));
  if (openSlot) return openSlot;

  return leastCrowdedSlot(candidates, placed) || circleSlot(index, total);
}

function hasLayoutCollision(slot, placed) {
  return placed.some((node) => Math.abs(node.x - slot.x) < 20 && Math.abs(node.y - slot.y) < 26);
}

function leastCrowdedSlot(candidates, placed) {
  return candidates.reduce((best, slot) => {
    const score = placed.reduce((sum, node) => {
      const dx = Math.abs(node.x - slot.x);
      const dy = Math.abs(node.y - slot.y);
      return sum + 1 / Math.max(dx * dx + dy * dy, 1);
    }, 0);

    if (!best || score < best.score) return { slot, score };
    return best;
  }, null)?.slot;
}

function circleSlot(index, total) {
  const angle = (index / Math.max(total, 1)) * Math.PI * 2 - Math.PI / 2;
  return {
    x: Math.round((50 + Math.cos(angle) * 31) * 10) / 10,
    y: Math.round((52 + Math.sin(angle) * 30) * 10) / 10,
  };
}

function detailSummary(detail) {
  if (!detail) return "";
  return String(detail).split(/\n+/).find((paragraph) => paragraph.trim())?.trim() || "";
}

function Metric({ label, value }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-3 py-2 shadow-sm">
      <p className="text-[18px] font-semibold text-slate-950">{value}</p>
      <p className="text-[11px] text-slate-400">{label}</p>
    </div>
  );
}

function createMindMapNodeId(nodes) {
  const existingIds = new Set(nodes.map((node) => node.id));
  let index = nodes.length + 1;
  let id = `node-${Date.now().toString(36)}-${index}`;

  while (existingIds.has(id)) {
    index += 1;
    id = `node-${Date.now().toString(36)}-${index}`;
  }

  return id;
}

function createMindMapNode({ id, parent, index, label, desc }) {
  const isRightSide = parent.x <= 50;
  const offsetX = parent.id === "center" ? 24 : 16;
  const offsetY = (index % 5 - 2) * 11 + Math.floor(index / 5) * 5;

  return {
    id,
    label,
    desc,
    detail: `${label}\n\n${desc}`,
    x: clamp(parent.x + (isRightSide ? offsetX : -offsetX), 14, 86),
    y: clamp(parent.y + offsetY, 14, 86),
    fill: index % 2 === 0 ? "#fef3c7" : "#e0f2fe",
    line: index % 2 === 0 ? "#f59e0b" : "#38bdf8",
  };
}

function collectDescendantNodeIds(rootId, edges) {
  const childrenByParent = edges.reduce((map, edge) => {
    if (!map.has(edge.from)) map.set(edge.from, []);
    map.get(edge.from).push(edge.to);
    return map;
  }, new Map());
  const collected = new Set();
  const queue = [...(childrenByParent.get(rootId) || [])];

  while (queue.length) {
    const nodeId = queue.shift();
    if (collected.has(nodeId)) continue;

    collected.add(nodeId);
    queue.push(...(childrenByParent.get(nodeId) || []));
  }

  return collected;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}
