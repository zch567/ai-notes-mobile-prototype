import { useMemo, useState } from "react";
import { TopBar } from "../../components/TopBar";

export function MindMapScreen({ result }) {
  const { nodes, edges } = result.mindMap;
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const nodeById = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);
  const selectedNode = selectedNodeId ? nodeById.get(selectedNodeId) : null;
  const workbenchOpen = Boolean(selectedNode);
  const workbenchOnLeft = selectedNode && selectedNode.id !== "center" ? selectedNode.x >= 50 : false;
  const shiftX = workbenchOpen ? 50 - (selectedNode?.x ?? 50) : 0;
  const shiftY = workbenchOpen ? 50 - (selectedNode?.y ?? 50) : 0;

  return (
    <div className="flex h-full flex-col">
      <TopBar title="知识导图" subtitle="后端只需返回 nodes / edges，前端负责展示" />

      <div className="min-h-0 flex-1 px-4 pb-4 pt-4">
        <div className="h-full overflow-hidden rounded-[30px] border border-slate-200 bg-slate-100 shadow-inner">
          <div className={`flex h-full w-full ${workbenchOpen ? (workbenchOnLeft ? "flex-row-reverse" : "flex-row") : "flex-row"}`}>
            <div className={`relative h-full min-w-0 overflow-hidden bg-slate-100 ${workbenchOpen ? "w-[60%]" : "w-full"}`}>
              <div
                className="absolute inset-0 transition-transform duration-300 ease-out"
                style={workbenchOpen ? { transform: `translate3d(${shiftX}%, ${shiftY}%, 0)` } : undefined}
              >
                <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                  {edges.map((edge) => {
                    const from = nodeById.get(edge.from);
                    const to = nodeById.get(edge.to);
                    if (!from || !to) return null;
                    const sideX = to.x < 50 ? 38 : to.x > 50 ? 62 : 50;
                    const controlY = to.y < 50 ? 35 : 65;
                    const path = `M ${from.x} ${from.y} C ${sideX} ${controlY}, ${sideX} ${to.y}, ${to.x} ${to.y}`;
                    return (
                      <path
                        key={`${edge.from}-${edge.to}`}
                        d={path}
                        fill="none"
                        stroke={to.line || "#93c5fd"}
                        strokeLinecap="round"
                        strokeWidth="1.4"
                        opacity="0.82"
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
                      className={`absolute z-10 -translate-x-1/2 -translate-y-1/2 border text-center shadow-[0_14px_30px_rgba(15,23,42,0.10)] transition-transform ${
                        isSelected ? "scale-[1.04] ring-2 ring-blue-200" : ""
                      } ${
                        isCenter
                          ? "w-[138px] rounded-[28px] border-blue-200 bg-white px-4 py-4"
                          : "max-w-[160px] rounded-[22px] px-3 py-3 text-left"
                      }`}
                      style={{
                        left: `${node.x}%`,
                        top: `${node.y}%`,
                        borderColor: isCenter ? "#bfdbfe" : node.line || "#cbd5e1",
                        backgroundColor: isCenter ? "#ffffff" : node.fill || "#ffffff",
                      }}
                    >
                      {isCenter ? (
                        <>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-blue-500">中心主题</p>
                          <h3 className="mt-2 text-[18px] font-semibold tracking-tight text-slate-900">{node.label}</h3>
                        </>
                      ) : (
                        <>
                          <p className="text-[12px] font-semibold text-slate-900">{node.label}</p>
                          <p className="mt-1 text-[11px] leading-4 text-slate-600">{node.desc}</p>
                        </>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            {workbenchOpen ? (
              <aside className="h-full w-[40%] flex-shrink-0 border-l border-slate-200 bg-white/95 px-4 py-4 shadow-[0_12px_40px_rgba(15,23,42,0.08)]">
                <div className="flex h-full flex-col">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 space-y-1">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">工作台</p>
                      <h4 className="text-[20px] font-semibold tracking-tight text-slate-900">{selectedNode.label}</h4>
                      <p className="text-[12px] leading-5 text-slate-500">{selectedNode.desc || "查看节点说明与后续操作。"}</p>
                    </div>
                    <button
                      onClick={() => setSelectedNodeId(null)}
                      className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-[12px] font-semibold text-slate-500"
                    >
                      收起
                    </button>
                  </div>

                  <div className="mt-4 grid grid-cols-2 gap-1.5">
                    {["新增子节点", "新增同级", "重命名", "删除节点"].map((item) => (
                      <button key={item} className="rounded-xl border border-slate-200 bg-slate-50 px-2.5 py-2 text-[11px] font-medium text-slate-700 shadow-sm">
                        {item}
                      </button>
                    ))}
                  </div>

                  <div className="mt-4 flex min-h-0 flex-1 flex-col rounded-[24px] border border-slate-200 bg-slate-50 px-4 py-4">
                    <div className="flex items-center justify-between">
                      <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-slate-400">具体内容</p>
                      <p className="text-[11px] font-medium text-slate-400">滑动查看</p>
                    </div>
                    <div className="mt-3 min-h-0 flex-1 overflow-y-auto rounded-[20px] bg-white px-4 py-4 text-[13px] leading-6 text-slate-600 shadow-inner">
                      {(selectedNode.detail || "后端可在节点中返回 detail 字段，前端会在这里展示。")
                        .split("\n\n")
                        .map((paragraph) => (
                          <p key={paragraph} className="mt-3 first:mt-0">
                            {paragraph}
                          </p>
                        ))}
                    </div>
                  </div>
                </div>
              </aside>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
