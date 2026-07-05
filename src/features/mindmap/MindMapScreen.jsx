import { useEffect, useMemo, useRef, useState } from "react";
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

export function MindMapScreen({ result, onResultChange = () => {}, onBack, onLocateSource = () => {} }) {
  const { nodes, edges } = result.mindMap;
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [collapsedNodeIds, setCollapsedNodeIds] = useState(() => new Set());
  const [interactionMode, setInteractionMode] = useState(null);
  const [renderRevision, setRenderRevision] = useState(0);
  const zoomRef = useRef(1);
  const canvasRef = useRef(null);
  const viewportRef = useRef(null);
  const interactionRef = useRef(null);
  const panOffsetRef = useRef({ x: 0, y: 0 });
  const zoomLabelRef = useRef(null);
  const suppressClickRef = useRef(false);
  const isWebView = isWebViewShell();
  const presentableMap = useMemo(() => createPresentableMindMap(nodes, edges, result.topic, collapsedNodeIds), [nodes, edges, result.topic, collapsedNodeIds]);
  const displayNodes = presentableMap.nodes;
  const displayEdges = presentableMap.edges;
  const nodeById = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);
  const displayNodeById = useMemo(() => new Map(displayNodes.map((node) => [node.id, node])), [displayNodes]);
  const selectedNode = selectedNodeId ? nodeById.get(selectedNodeId) : null;
  const centerNode = nodeById.get("root") || nodeById.get("center") || nodes[0];
  const displayCenterNode = displayNodeById.get(centerNode?.id) || displayNodes[0];
  const displaySelectedNode = selectedNodeId ? displayNodeById.get(selectedNodeId) : null;
  const stableSelectedNode = selectedNodeId ? presentableMap.nodes.find((node) => node.id === selectedNodeId) : null;
  const detailNode = displaySelectedNode || displayCenterNode;
  const draggedNodeId = interactionMode === "node" ? interactionRef.current?.nodeId : null;
  const selectedRelations = useMemo(
    () =>
      displayEdges.filter(
        (edge) =>
          selectedNodeId &&
          hasRelationMetadata(edge) &&
          (edge.from === selectedNodeId || edge.to === selectedNodeId),
      ),
    [displayEdges, selectedNodeId],
  );
  const focusNode = interactionMode ? stableSelectedNode || displaySelectedNode : displaySelectedNode;
  const focusX = focusNode ? 50 - focusNode.x : 0;
  const focusY = focusNode ? 50 - focusNode.y : 0;
  const focusOffsetX = focusX * 0.06;
  const focusOffsetY = focusY * 0.08;
  const toolboxSide = displaySelectedNode?.x > 58 ? "left" : "right";
  const toolboxVertical = displaySelectedNode?.y > 56 ? "top" : "bottom";
  const zoomDockSide = displaySelectedNode && toolboxSide === "left" ? "right" : "left";
  const zoomDockVertical = displaySelectedNode && toolboxVertical === "bottom" ? "top" : "bottom";
  const showNodePanel = displaySelectedNode;
  const hasMap = nodes.length > 0;
  const selectedHasChildren = selectedNode ? edges.some((edge) => edge.from === selectedNode.id) : false;
  const selectedCollapsed = selectedNode ? collapsedNodeIds.has(selectedNode.id) : false;
  const mapActions = [
    { key: "source", label: "定位原文", onClick: locateSource, disabled: !detailNode },
    { key: "child", label: "新增子节点", onClick: addChildNode, disabled: !hasMap },
    { key: "sibling", label: "同级节点", onClick: addSiblingNode, disabled: !selectedNode || selectedNode.id === centerNode?.id },
    { key: "rename", label: "重命名", onClick: renameNode, disabled: !detailNode },
    { key: "toggle", label: selectedCollapsed ? "展开分支" : "折叠分支", onClick: toggleBranch, disabled: !selectedNode || !selectedHasChildren },
    { key: "hide", label: "隐藏分支", onClick: hideBranch, disabled: !selectedNode || selectedNode.id === centerNode?.id },
  ];

  useEffect(() => {
    const androidShell = window.AndroidShell;
    if (!isWebView || !androidShell?.setMindMapLandscape) return undefined;

    androidShell.setMindMapLandscape(true);
    return () => androidShell.setMindMapLandscape(false);
  }, [isWebView]);

  useEffect(() => {
    applyViewportTransform(panOffsetRef.current);
  }, [focusOffsetX, focusOffsetY]);

  function applyViewportTransform(nextPanOffset) {
    if (!viewportRef.current) return;
    viewportRef.current.style.transform = `translate3d(calc(${focusOffsetX}% + ${nextPanOffset.x}px), calc(${focusOffsetY}% + ${nextPanOffset.y}px), 0) scale(${zoomRef.current})`;
  }

  function updateZoom(nextZoomOrUpdater) {
    const nextZoom = typeof nextZoomOrUpdater === "function"
      ? nextZoomOrUpdater(zoomRef.current)
      : nextZoomOrUpdater;

    zoomRef.current = clampZoom(nextZoom);
    if (zoomLabelRef.current) {
      zoomLabelRef.current.textContent = `${Math.round(zoomRef.current * 100)}%`;
    }
    applyViewportTransform(panOffsetRef.current);
  }

  function schedulePanFrame(interaction) {
    if (interaction.frameId) return;
    interaction.frameId = window.requestAnimationFrame(() => {
      interaction.frameId = 0;
      applyViewportTransform(interaction.latestPan || interaction.panStart);
    });
  }

  function scheduleNodeFrame(interaction) {
    if (interaction.frameId) return;
    interaction.frameId = window.requestAnimationFrame(() => {
      interaction.frameId = 0;
      applyNodeLayout(interaction.workingPositions, { nodeId: interaction.nodeId, updateEdges: false });
    });
  }

  function cancelInteractionFrame(interaction) {
    if (!interaction?.frameId) return;
    window.cancelAnimationFrame(interaction.frameId);
    interaction.frameId = 0;
  }

  function applyNodeLayout(positionById, options = {}) {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const onlyNodeId = options.nodeId;
    const updateEdges = options.updateEdges !== false;

    displayNodes.forEach((node) => {
      if (onlyNodeId && node.id !== onlyNodeId) return;
      const position = positionById[node.id];
      if (!position) return;
      const element = canvas.querySelector(`[data-mindmap-node-id="${escapeSelectorValue(node.id)}"]`);
      if (!element) return;
      element.style.left = `${position.x}%`;
      element.style.top = `${position.y}%`;
    });

    if (!updateEdges) return;

    displayEdges.forEach((edge, index) => {
      const from = nodeWithPosition(displayNodeById.get(edge.from), positionById);
      const to = nodeWithPosition(displayNodeById.get(edge.to), positionById);
      if (!from || !to) return;

      const curve = getEdgeCurve(from, to);
      const path = canvas.querySelector(`[data-mindmap-edge-index="${index}"]`);
      path?.setAttribute("d", curve.path);

      const label = canvas.querySelector(`[data-mindmap-edge-label-index="${index}"]`);
      if (label) {
        label.style.left = `${curve.label.x}%`;
        label.style.top = `${curve.label.y}%`;
      }
    });
  }

  function nodeWithPosition(node, positionById) {
    const position = node ? positionById[node.id] : null;
    return node && position ? { ...node, x: position.x, y: position.y } : node;
  }

  function handleCanvasPointerDown(event) {
    if (event.button !== undefined && event.button !== 0) return;
    if (event.target.closest?.("button, aside")) return;

    interactionRef.current = {
      type: "pan",
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      panStart: panOffsetRef.current,
      latestPan: panOffsetRef.current,
      frameId: 0,
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
    event.preventDefault();
  }

  function handleNodePointerDown(event, node) {
    if (selectedNodeId !== node.id) return;

    const canvasRect = canvasRef.current?.getBoundingClientRect();
    if (!canvasRect) return;

    interactionRef.current = {
      type: "node",
      pointerId: event.pointerId,
      nodeId: node.id,
      startX: event.clientX,
      startY: event.clientY,
      startNode: { x: node.x, y: node.y },
      canvasRect,
      positionsAtStart: Object.fromEntries(displayNodes.map((item) => [item.id, { x: item.x, y: item.y }])),
      workingPositions: Object.fromEntries(displayNodes.map((item) => [item.id, { x: item.x, y: item.y }])),
      latestNode: { x: node.x, y: node.y },
      frameId: 0,
      moved: false,
    };
    suppressClickRef.current = false;
    setInteractionMode("node");
    canvasRef.current.setPointerCapture?.(event.pointerId);
    event.stopPropagation();
    event.preventDefault();
  }

  function handleCanvasPointerMove(event) {
    const interaction = interactionRef.current;
    if (!interaction || interaction.pointerId !== event.pointerId) return;

    const deltaX = event.clientX - interaction.startX;
    const deltaY = event.clientY - interaction.startY;

    if (interaction.type === "pan") {
      interaction.latestPan = {
        x: interaction.panStart.x + deltaX,
        y: interaction.panStart.y + deltaY,
      };
      schedulePanFrame(interaction);
      event.preventDefault();
      return;
    }

    if (interaction.type === "node") {
      const moved = Math.hypot(deltaX, deltaY) > 3;
      interaction.moved = interaction.moved || moved;
      suppressClickRef.current = interaction.moved;

      const nextPosition = {
        x: clampNodeX(interaction.startNode.x + (deltaX / (interaction.canvasRect.width * zoomRef.current)) * 100),
        y: clampNodeY(interaction.startNode.y + (deltaY / (interaction.canvasRect.height * zoomRef.current)) * 100),
      };
      interaction.latestNode = nextPosition;
      interaction.workingPositions[interaction.nodeId] = nextPosition;
      scheduleNodeFrame(interaction);
      event.preventDefault();
    }
  }

  function handleCanvasPointerUp(event) {
    const interaction = interactionRef.current;
    if (!interaction || interaction.pointerId !== event.pointerId) return;

    cancelInteractionFrame(interaction);

    if (interaction.type === "pan") {
      panOffsetRef.current = interaction.latestPan || interaction.panStart;
      applyViewportTransform(panOffsetRef.current);
    }

    if (interaction.type === "node" && interaction.moved) {
      applyNodeLayout(interaction.workingPositions, { nodeId: interaction.nodeId, updateEdges: false });
      const nextPositions = {
        ...interaction.positionsAtStart,
        [interaction.nodeId]: interaction.latestNode,
      };
      updateMindMap({
        nodes: nodes.map((node) => {
          const nextPosition = nextPositions[node.id];
          return nextPosition ? { ...node, x: nextPosition.x, y: nextPosition.y } : node;
        }),
      }, interaction.nodeId);
      setRenderRevision((current) => current + 1);
    }

    event.currentTarget.releasePointerCapture?.(event.pointerId);
    interactionRef.current = null;
    if (interaction.type === "node") setInteractionMode(null);
  }

  function handleCanvasPointerCancel(event) {
    const interaction = interactionRef.current;
    if (interaction?.pointerId !== event.pointerId) return;
    cancelInteractionFrame(interaction);
    if (interaction.type === "pan") applyViewportTransform(panOffsetRef.current);
    if (interaction.type === "node") {
      applyNodeLayout(interaction.positionsAtStart, { nodeId: interaction.nodeId, updateEdges: false });
      setRenderRevision((current) => current + 1);
    }
    interactionRef.current = null;
    if (interaction.type === "node") setInteractionMode(null);
  }

  function handleNodeClick(nodeId) {
    if (suppressClickRef.current) {
      suppressClickRef.current = false;
      return;
    }
    setSelectedNodeId((current) => (current === nodeId ? null : nodeId));
  }

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

    setCollapsedNodeIds((current) => {
      const next = new Set(current);
      next.delete(parent.id);
      return next;
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

  function locateSource() {
    if (!detailNode) return;
    onLocateSource(detailNode);
  }

  function toggleBranch() {
    if (!selectedNode || !selectedHasChildren) return;

    setCollapsedNodeIds((current) => {
      const next = new Set(current);
      if (next.has(selectedNode.id)) {
        next.delete(selectedNode.id);
      } else {
        next.add(selectedNode.id);
      }
      return next;
    });
  }

  function hideBranch() {
    if (!selectedNode || selectedNode.id === centerNode?.id) return;

    const hiddenNodeIds = collectDescendantNodeIds(selectedNode.id, edges);
    hiddenNodeIds.add(selectedNode.id);

    const nextNodes = nodes.filter((node) => !hiddenNodeIds.has(node.id));
    const nextEdges = edges.filter((edge) => !hiddenNodeIds.has(edge.from) && !hiddenNodeIds.has(edge.to));
    setCollapsedNodeIds((current) => {
      const next = new Set(current);
      hiddenNodeIds.forEach((id) => next.delete(id));
      return next;
    });
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

        <header className="relative z-10 flex h-12 flex-none items-center justify-between border-b border-white/70 bg-white/72 px-4 backdrop-blur-xl">
        <div className="flex min-w-0 items-center gap-2.5">
          <button onClick={onBack} className="shrink-0 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600 shadow-sm">
            返回
          </button>
          <div className="min-w-0">
            <h1 className="truncate text-[16px] font-semibold tracking-tight text-slate-950">知识导图横屏模式</h1>
            <p className="truncate text-[10px] text-slate-500">Landscape canvas · {nodes.length} nodes · {edges.length} links</p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-500 shadow-sm">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
          横屏演示
        </div>
        </header>

        <div className="relative z-10 min-h-0 flex-1 p-3">
        <section
          ref={canvasRef}
          onPointerDown={handleCanvasPointerDown}
          onPointerMove={handleCanvasPointerMove}
          onPointerUp={handleCanvasPointerUp}
          onPointerCancel={handleCanvasPointerCancel}
          className="relative h-full min-w-0 cursor-grab overflow-hidden rounded-[24px] border border-white/80 bg-white/64 shadow-[inset_0_1px_0_rgba(255,255,255,0.9),0_20px_50px_rgba(15,23,42,0.12)] backdrop-blur-xl active:cursor-grabbing"
          style={{
            touchAction: "none",
            transform: "translateZ(0)",
            WebkitBackfaceVisibility: "hidden",
          }}
        >
          <div className={`absolute left-3 top-3 z-20 flex items-center gap-2 rounded-full border border-slate-200 bg-white/86 px-2.5 py-1 shadow-sm transition-opacity ${displaySelectedNode ? "pointer-events-none opacity-0" : "opacity-100"}`}>
            <span className="text-[10px] font-semibold text-slate-500">点击节点查看详情</span>
          </div>

          <div
            key={`mindmap-render-${renderRevision}`}
            ref={viewportRef}
            className="absolute inset-0 origin-center"
            style={{
              transform: `translate3d(calc(${focusOffsetX}% + ${panOffsetRef.current.x}px), calc(${focusOffsetY}% + ${panOffsetRef.current.y}px), 0) scale(${zoomRef.current})`,
              backfaceVisibility: "hidden",
              WebkitBackfaceVisibility: "hidden",
              contain: "layout style",
              willChange: "transform",
            }}
          >
            <svg className="absolute inset-0 h-full w-full overflow-visible" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              <defs>
                <filter id="softShadow" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="1" stdDeviation="1.2" floodColor="#0f172a" floodOpacity="0.16" />
                </filter>
              </defs>
              {displayEdges.map((edge, index) => {
                if (isEdgeConnectedToNode(edge, draggedNodeId)) return null;
                const from = displayNodeById.get(edge.from);
                const to = displayNodeById.get(edge.to);
                if (!from || !to) return null;
                const curve = getEdgeCurve(from, to);
                return (
                  <path
                    key={`${edge.from}-${edge.to}-${index}`}
                    data-mindmap-edge-index={index}
                    d={curve.path}
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

            {displayEdges.map((edge, index) => {
              if (isEdgeConnectedToNode(edge, draggedNodeId)) return null;
              const from = displayNodeById.get(edge.from);
              const to = displayNodeById.get(edge.to);
              if (!from || !to || !hasRelationMetadata(edge)) return null;
              const curve = getEdgeCurve(from, to);
              return (
                <div
                  key={`label-${edge.from}-${edge.to}-${index}`}
                  data-mindmap-edge-label-index={index}
                  className="pointer-events-none absolute z-[5] -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/90 bg-white/90 px-2 py-0.5 text-[8px] font-semibold tracking-wide text-slate-500 shadow-sm backdrop-blur"
                  style={{
                    left: `${curve.label.x}%`,
                    top: `${curve.label.y}%`,
                  }}
                >
                  {edge.label || edgeTypeLabel(edge.type)}
                </div>
              );
            })}

            {displayNodes.map((node) => {
              const isCenter = node.id === displayCenterNode?.id;
              const isSelected = selectedNodeId === node.id;
              return (
                <button
                  key={node.id}
                  data-mindmap-node-id={node.id}
                  onClick={() => handleNodeClick(node.id)}
                  onPointerDown={(event) => handleNodePointerDown(event, node)}
                  className={`absolute z-10 -translate-x-1/2 -translate-y-1/2 overflow-hidden border text-left shadow-[0_16px_30px_rgba(15,23,42,0.12)] ${
                    interactionMode === "node" && isSelected ? "transition-none" : "transition duration-200 hover:-translate-y-[52%] hover:shadow-[0_20px_38px_rgba(15,23,42,0.16)]"
                  } ${
                    isSelected ? "scale-[1.05] ring-2 ring-slate-900/10" : ""
                  } ${isSelected ? "cursor-move" : "cursor-pointer"} ${isCenter ? "w-[170px] rounded-[26px] border-blue-200 bg-white px-4 py-4 text-center" : "w-[160px] rounded-[20px] px-3 py-3"}`}
                  style={{
                    left: `${node.x}%`,
                    top: `${node.y}%`,
                    borderColor: isCenter ? "#bfdbfe" : node.line || "#cbd5e1",
                    backgroundColor: isCenter ? "#ffffff" : node.fill || "#ffffff",
                    willChange: isSelected ? "left, top" : "auto",
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
                      <div className="mt-2 flex items-start justify-between gap-2">
                        <p className="min-w-0 flex-1 line-clamp-2 break-words text-[11px] leading-4 text-slate-600">{node.desc}</p>
                        {node.childCount ? (
                          <span className="shrink-0 rounded-full bg-white/70 px-1.5 py-0.5 text-[10px] font-semibold text-slate-500">
                            {node.collapsed ? `+${node.childCount}` : `子${node.childCount}`}
                          </span>
                        ) : null}
                      </div>
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

          <div
            className={`absolute z-30 flex items-center gap-1.5 rounded-full border border-white/80 bg-white/86 px-1.5 py-1.5 shadow-[0_14px_36px_rgba(15,23,42,0.12)] backdrop-blur-xl ${
              zoomDockSide === "right" ? "right-3" : "left-3"
            } ${zoomDockVertical === "top" ? "top-3" : "bottom-3"}`}
          >
            <button
              type="button"
              onClick={() => updateZoom((current) => current - zoomBounds.step)}
              className="grid h-7 w-7 place-items-center rounded-full border border-slate-200 bg-white text-[15px] font-semibold text-slate-700 shadow-sm"
              aria-label="缩小导图"
            >
              -
            </button>
            <button
              type="button"
              onClick={() => updateZoom(1)}
              className="min-w-[42px] rounded-full px-1 text-[11px] font-semibold text-slate-500"
              aria-label="重置导图缩放"
            >
              <span ref={zoomLabelRef}>{Math.round(zoomRef.current * 100)}%</span>
            </button>
            <button
              type="button"
              onClick={() => updateZoom((current) => current + zoomBounds.step)}
              className="grid h-7 w-7 place-items-center rounded-full border border-slate-200 bg-white text-[15px] font-semibold text-slate-700 shadow-sm"
              aria-label="放大导图"
            >
              +
            </button>
          </div>

          {showNodePanel ? (
            <aside
              className={`absolute z-40 flex max-h-[calc(100%-1.5rem)] w-[220px] max-w-[28%] flex-col rounded-[16px] border border-white/80 bg-white/90 p-2.5 shadow-[0_12px_30px_rgba(15,23,42,0.14)] backdrop-blur-xl transition-opacity ${
                interactionMode === "node" ? "pointer-events-none opacity-0" : "opacity-100"
              } ${
                toolboxSide === "left" ? "left-3" : "right-3"
              } ${
                toolboxVertical === "top"
                  ? "top-3"
                  : "bottom-3"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-[10px] font-semibold uppercase text-slate-400">当前节点</p>
                  <h2 className="mt-0.5 line-clamp-2 text-[14px] font-semibold leading-tight tracking-tight text-slate-950">{detailNode?.label || result.topic}</h2>
                  <p className="hidden">
                    {detailNode?.desc || "查看来源说明、编辑操作和复习线索。"}
                  </p>
                </div>
                <button onClick={() => setSelectedNodeId(null)} className="shrink-0 rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-semibold text-slate-500">
                  收起
                </button>
              </div>

              <div className="mt-2 grid grid-cols-2 gap-1.5">
                {mapActions.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    onClick={item.onClick}
                    disabled={item.disabled}
                    className={`rounded-lg border px-2 py-1 text-[10px] font-semibold shadow-sm transition ${
                      item.disabled
                        ? "cursor-not-allowed border-slate-100 bg-slate-50 text-slate-300"
                        : "border-slate-200 bg-white text-slate-700 hover:border-blue-200 hover:bg-blue-50"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>

              <div className="hidden">
                <Metric label="节点" value={displayNodes.length} />
                <Metric label="连线" value={displayEdges.length} />
              </div>

              <div className="hidden">
                <div className="flex items-center justify-between">
                  <p className="text-[10px] font-semibold uppercase text-slate-400">具体内容</p>
                  <p className="text-[10px] font-medium text-slate-400">滑动查看</p>
                </div>
                <div className="mt-2 max-h-24 overflow-y-auto rounded-[14px] bg-white px-3 py-3 text-[12px] leading-5 text-slate-600 shadow-inner">
                  {(detailNode?.detail || result.summary || "后端可在节点中返回 detail 字段，前端会在这里展示。")
                    .split("\n\n")
                    .map((paragraph) => (
                      <p key={paragraph} className="mt-3 first:mt-0">
                        {paragraph}
                      </p>
                    ))}
                </div>
              </div>
              {selectedRelations.length ? (
                <div className="hidden">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-blue-500">关联关系</p>
                  <div className="mt-2 max-h-20 space-y-1.5 overflow-y-auto">
                    {selectedRelations.map((edge, index) => {
                      const isOutgoing = edge.from === selectedNodeId;
                      const peer = displayNodeById.get(isOutgoing ? edge.to : edge.from);
                      return (
                        <div key={`${edge.from}-${edge.to}-${index}`} className="rounded-xl bg-white px-2.5 py-1.5 text-[10px] leading-4 text-slate-600">
                          <p className="font-semibold text-slate-800">
                            {isOutgoing ? "指向" : "来自"} {peer?.label || "关联节点"} · {edge.label || edgeTypeLabel(edge.type)}
                          </p>
                          {edge.reason ? <p className="mt-1 text-slate-500">{edge.reason}</p> : null}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : null}
            </aside>
          ) : null}
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

const nodeCoordinateBounds = {
  minX: -800,
  maxX: 900,
  minY: -600,
  maxY: 700,
};

const zoomBounds = {
  min: 0.45,
  max: 2.2,
  step: 0.15,
};

function getEdgeCurve(from, to) {
  const start = edgeAnchorPoint(from, to);
  const end = edgeAnchorPoint(to, from);
  const deltaX = end.x - start.x;
  const deltaY = end.y - start.y;
  const distance = Math.max(Math.hypot(deltaX, deltaY), 1);
  const bend = clamp(distance * 0.08, 2.4, 7);
  const normal = {
    x: -deltaY / distance,
    y: deltaX / distance,
  };
  const controlA = {
    x: start.x + deltaX * 0.42 + normal.x * bend,
    y: start.y + deltaY * 0.42 + normal.y * bend,
  };
  const controlB = {
    x: start.x + deltaX * 0.58 + normal.x * bend,
    y: start.y + deltaY * 0.58 + normal.y * bend,
  };

  return {
    path: `M ${roundPoint(start.x)} ${roundPoint(start.y)} C ${roundPoint(controlA.x)} ${roundPoint(controlA.y)}, ${roundPoint(controlB.x)} ${roundPoint(controlB.y)}, ${roundPoint(end.x)} ${roundPoint(end.y)}`,
    label: cubicBezierPoint(
      start,
      controlA,
      controlB,
      end,
      0.5,
    ),
  };
}

function edgeAnchorPoint(node, toward) {
  const halfWidth = node.depth === 0 ? 9.5 : 8.9;
  const halfHeight = node.depth === 0 ? 7.2 : 6.2;
  const deltaX = toward.x - node.x;
  const deltaY = toward.y - node.y;

  if (!deltaX && !deltaY) return { x: node.x, y: node.y };

  const scaleX = deltaX ? halfWidth / Math.abs(deltaX) : Number.POSITIVE_INFINITY;
  const scaleY = deltaY ? halfHeight / Math.abs(deltaY) : Number.POSITIVE_INFINITY;
  const scale = Math.min(scaleX, scaleY);

  return {
    x: node.x + deltaX * scale,
    y: node.y + deltaY * scale,
  };
}

function cubicBezierPoint(start, controlA, controlB, end, t) {
  const oneMinusT = 1 - t;
  const x =
    oneMinusT ** 3 * start.x +
    3 * oneMinusT ** 2 * t * controlA.x +
    3 * oneMinusT * t ** 2 * controlB.x +
    t ** 3 * end.x;
  const y =
    oneMinusT ** 3 * start.y +
    3 * oneMinusT ** 2 * t * controlA.y +
    3 * oneMinusT * t ** 2 * controlB.y +
    t ** 3 * end.y;

  return {
    x: roundPoint(x),
    y: roundPoint(y),
  };
}

function roundPoint(value) {
  return Math.round(value * 10) / 10;
}

function createPresentableMindMap(nodes, edges, topic, collapsedNodeIds = new Set()) {
  if (!nodes.length) {
    return { nodes: [], edges: [] };
  }

  const sourceNodeById = new Map(nodes.map((node) => [node.id, node]));
  const center = sourceNodeById.get("root") || sourceNodeById.get("center") || nodes[0];
  const validNodeIds = new Set(nodes.map((node) => node.id));
  const normalizedEdges = edges
    .filter((edge) => validNodeIds.has(edge.from) && validNodeIds.has(edge.to) && edge.from !== edge.to)
    .map((edge) => ({ ...edge, from: edge.from, to: edge.to }));

  return createCoordinateLayout(center, nodes, normalizedEdges, topic, collapsedNodeIds);
}

function createCoordinateLayout(center, nodes, edges, topic, collapsedNodeIds) {
  const nonCenterNodes = nodes.filter((node) => node.id !== center.id);
  const useNodeCoordinates = hasUsableNodeCoordinates(nodes);
  const childrenByParent = buildChildrenByParent(edges);
  const hiddenNodeIds = collectCollapsedDescendantIds(collapsedNodeIds, childrenByParent);
  const centerNode = normalizeDisplayNode(center, 0, {
    topic,
    isCenter: true,
    x: useNodeCoordinates ? numberOrFallback(center.x, 50) : 50,
    y: useNodeCoordinates ? numberOrFallback(center.y, 50) : 50,
    depth: 0,
    childCount: (childrenByParent.get(center.id) || []).length || nonCenterNodes.length,
    collapsed: collapsedNodeIds.has(center.id),
  });
  const placed = [centerNode];
  const childNodes = nonCenterNodes
    .filter((node) => !hiddenNodeIds.has(node.id))
    .map((node, index) => {
      const slot = pickNodeSlot(index, nonCenterNodes.length, placed);
      const childIds = childrenByParent.get(node.id) || [];
      const nextNode = normalizeDisplayNode(node, index + 1, {
        topic,
        x: useNodeCoordinates ? numberOrFallback(node.x, slot.x) : slot.x,
        y: useNodeCoordinates ? numberOrFallback(node.y, slot.y) : slot.y,
        depth: inferNodeDepth(node.id, edges, center.id),
        childCount: childIds.length,
        collapsed: collapsedNodeIds.has(node.id),
      });
      placed.push(nextNode);
      return nextNode;
    });
  const presentableNodes = [centerNode, ...childNodes];
  const presentableNodeIds = new Set(presentableNodes.map((node) => node.id));
  const presentableEdges = edges.filter((edge) => presentableNodeIds.has(edge.from) && presentableNodeIds.has(edge.to));

  return {
    nodes: presentableNodes,
    edges: presentableEdges.length
      ? presentableEdges
      : childNodes.map((node) => ({ from: center.id, to: node.id })),
  };
}

function hasUsableNodeCoordinates(nodes) {
  const coordinateKeys = nodes
    .map((node) => {
      const x = Number(node.x);
      const y = Number(node.y);
      if (!Number.isFinite(x) || !Number.isFinite(y)) return "";
      return `${Math.round(x * 10) / 10},${Math.round(y * 10) / 10}`;
    })
    .filter(Boolean);

  if (coordinateKeys.length < Math.min(nodes.length, 2)) return false;

  const distinctCoordinates = new Set(coordinateKeys);
  if (distinctCoordinates.size >= Math.min(nodes.length, 3)) return true;

  return distinctCoordinates.size > 1 && !coordinateKeys.every((key) => key === "50,50");
}

function buildChildrenByParent(edges) {
  return edges.reduce((map, edge) => {
    if (!map.has(edge.from)) map.set(edge.from, []);
    if (!map.get(edge.from).includes(edge.to)) map.get(edge.from).push(edge.to);
    return map;
  }, new Map());
}

function collectCollapsedDescendantIds(collapsedNodeIds, childrenByParent) {
  const hiddenNodeIds = new Set();
  collapsedNodeIds.forEach((nodeId) => {
    const queue = [...(childrenByParent.get(nodeId) || [])];
    while (queue.length) {
      const childId = queue.shift();
      if (hiddenNodeIds.has(childId)) continue;
      hiddenNodeIds.add(childId);
      queue.push(...(childrenByParent.get(childId) || []));
    }
  });
  return hiddenNodeIds;
}

function inferNodeDepth(nodeId, edges, centerId) {
  if (nodeId === centerId) return 0;

  const parentByChild = new Map();
  edges.forEach((edge) => {
    if (!parentByChild.has(edge.to)) parentByChild.set(edge.to, edge.from);
  });

  let depth = 1;
  let currentId = nodeId;
  const seen = new Set([nodeId]);
  while (parentByChild.has(currentId)) {
    const parentId = parentByChild.get(currentId);
    if (!parentId || seen.has(parentId)) break;
    if (parentId === centerId) return depth;
    seen.add(parentId);
    currentId = parentId;
    depth += 1;
  }

  return depth;
}

function normalizeDisplayNode(node, index, options) {
  const isCenter = Boolean(options.isCenter);
  const color = isCenter ? { fill: "#ffffff", line: "#2563eb" } : nodeColor(node, Math.max(index - 1, 0));
  return {
    ...node,
    label: node.label || (isCenter ? options.topic || "中心主题" : "知识点"),
    desc: compactMapText(node.desc || detailSummary(node.detail) || (isCenter ? "中心主题" : "点击查看详情"), isCenter ? 20 : 18),
    x: clampNodeX(options.x),
    y: clampNodeY(options.y),
    depth: options.depth || 0,
    childCount: options.childCount || 0,
    collapsed: Boolean(options.collapsed),
    fill: isCenter ? node.fill || color.fill : color.fill,
    line: isCenter ? node.line || color.line : color.line,
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

function compactMapText(text, limit = 18) {
  const normalized = String(text || "").replace(/\s+/g, " ").trim();
  if (normalized.length <= limit) return normalized;
  return `${normalized.slice(0, limit - 1)}…`;
}

function detailSummary(detail) {
  if (!detail) return "";
  return String(detail).split(/\n+/).find((paragraph) => paragraph.trim())?.trim() || "";
}

function hasRelationMetadata(edge) {
  return Boolean(
    (edge?.type && edge.type !== "hierarchy") ||
      edge?.label ||
      edge?.reason ||
      edge?.sourceRefs?.length ||
      edge?.confidence,
  );
}

function isEdgeConnectedToNode(edge, nodeId) {
  return Boolean(nodeId && edge && (edge.from === nodeId || edge.to === nodeId));
}

function edgeTypeLabel(type) {
  return {
    hierarchy: "层级",
    prerequisite: "先修",
    component: "组成",
    mechanism: "机制",
    "training-flow": "流程",
    evolution: "演进",
    application: "应用",
    contrast: "对比",
    evidence: "证据",
    solution: "解法",
  }[type] || "";
}

function Metric({ label, value }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 shadow-sm">
      <p className="text-[15px] font-semibold leading-none text-slate-950">{value}</p>
      <p className="mt-1 text-[10px] leading-none text-slate-400">{label}</p>
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

function clampNodeX(value) {
  return clamp(numberOrFallback(value, 50), nodeCoordinateBounds.minX, nodeCoordinateBounds.maxX);
}

function clampNodeY(value) {
  return clamp(numberOrFallback(value, 50), nodeCoordinateBounds.minY, nodeCoordinateBounds.maxY);
}

function clampZoom(value) {
  return Math.round(clamp(value, zoomBounds.min, zoomBounds.max) * 100) / 100;
}

function numberOrFallback(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function escapeSelectorValue(value) {
  return String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}
