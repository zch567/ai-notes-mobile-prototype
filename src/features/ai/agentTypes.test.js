import test from "node:test";
import assert from "node:assert/strict";

import { normalizeAgentResult } from "./agentTypes.js";

test("normalizes semantic learning-unit note fields", () => {
  const result = normalizeAgentResult({
    id: "result-1",
    topic: "Transformer",
    report_plan: [{ section_id: "plan-1", title: "核心机制", summary: "理解注意力", source_refs: ["chunk-1"] }],
    notes: [
      {
        node_id: "note-1",
        title: "自注意力",
        content: "正文",
        summary: "摘要",
        key_points: ["Q/K/V", { text: "缩放点积" }],
        examples: [{ type: "formula", text: "softmax(QK^T)V" }],
        relations: [{ type: "mechanism", target: "多头注意力" }],
        source_refs: ["chunk-1"],
        blocks: [
          {
            block_type: "outline",
            label: "结构拆解",
            structured_items: [{ text: "计算相关性", children: ["归一化权重"] }],
          },
        ],
      },
    ],
  });

  assert.deepEqual(result.reportPlan[0], {
    id: "plan-1",
    title: "核心机制",
    brief: "理解注意力",
    refs: ["chunk-1"],
  });
  assert.equal(result.notes[0].summary, "摘要");
  assert.deepEqual(result.notes[0].keyPoints, ["Q/K/V", "缩放点积"]);
  assert.deepEqual(result.notes[0].sourceRefs, ["chunk-1"]);
  assert.deepEqual(result.notes[0].citationIds, ["chunk-1"]);
  assert.equal(result.notes[0].blocks[0].type, "outline");
  assert.equal(result.notes[0].blocks[0].structuredItems[0].children[0], "归一化权重");
});

test("preserves typed mind-map relation fields and legacy edges", () => {
  const result = normalizeAgentResult({
    mindMap: {
      nodes: [{ id: "root", label: "主题", source_refs: ["chunk-1"] }],
      edges: [
        {
          source: "root",
          target: "attention",
          relation_type: "mechanism",
          edge_label: "机制",
          relation_reason: "注意力是核心机制",
          confidence: 0.88,
          source_refs: ["chunk-1"],
        },
        { from: "root", to: "legacy" },
      ],
    },
  });

  assert.deepEqual(result.mindMap.nodes[0].sourceRefs, ["chunk-1"]);
  assert.deepEqual(result.mindMap.edges[0], {
    source: "root",
    target: "attention",
    relation_type: "mechanism",
    edge_label: "机制",
    relation_reason: "注意力是核心机制",
    confidence: 0.88,
    source_refs: ["chunk-1"],
    from: "root",
    to: "attention",
    type: "mechanism",
    label: "机制",
    reason: "注意力是核心机制",
    sourceRefs: ["chunk-1"],
  });
  assert.equal(result.mindMap.edges[1].type, "hierarchy");
  assert.equal(result.mindMap.edges[1].label, "");
});
