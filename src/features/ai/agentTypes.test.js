import test from "node:test";
import assert from "node:assert/strict";

import { deriveAgentResultInsights, normalizeAgentResult } from "./agentTypes.js";

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

test("deduplicates backend core-summary mind-map root against center topic", () => {
  const result = normalizeAgentResult({
    topic: "操作系统",
    mindMap: {
      nodes: [
        { id: "root", label: "操作系统", desc: "中心主题" },
        { id: "summary", label: "本章核心考点总结", desc: "与中心主题重复" },
        { id: "process", label: "进程管理" },
      ],
      edges: [
        { from: "root", to: "summary" },
        { from: "summary", to: "process" },
      ],
    },
  });

  assert.deepEqual(result.mindMap.nodes.map((node) => node.id), ["root", "process"]);
  assert.deepEqual(result.mindMap.edges.map((edge) => [edge.from, edge.to]), [["root", "process"]]);
});

test("derives asset, quality and learning-loop summaries from legacy AgentResult", () => {
  const result = normalizeAgentResult({
    id: "result-2",
    topic: "线性回归",
    summary: "学习摘要",
    notes: [
      { id: "n1", title: "定义", content: "正文", citationIds: ["s1"] },
      { id: "n2", title: "训练", content: "正文", citationIds: ["s2"] },
    ],
    sources: [{ id: "s1", text: "来源 1" }, { id: "s2", text: "来源 2" }],
    citations: [{ id: "c1", sourceId: "s1" }, { id: "c2", sourceId: "s2" }],
    citationDiagnostics: { noteCitationCoverage: 1, quoteInSourceRate: 0.5 },
    mindMap: { nodes: [{ id: "center", label: "线性回归" }], edges: [] },
    review: { questions: [{ id: "q1", question: "问题" }], masteryScore: 80 },
  });

  const { assetSummary, qualitySummary, learningLoopState } = deriveAgentResultInsights(result);

  assert.equal(assetSummary.noteCount, 2);
  assert.equal(assetSummary.citationCount, 2);
  assert.equal(assetSummary.reviewQuestionCount, 1);
  assert.equal(qualitySummary.citationCoverage, 1);
  assert.equal(qualitySummary.quoteHitRate, 0.5);
  assert.equal(qualitySummary.diagnostics.length, 4);
  assert.deepEqual(learningLoopState.steps.map((step) => step.label), ["输入", "笔记", "引用", "导图", "复习", "问答"]);
  assert.equal(learningLoopState.completedCount, 6);
});

test("keeps optional summary extension fields compatible", () => {
  const result = normalizeAgentResult({
    topic: "概率论",
    asset_summary: { fileName: "course.pdf", noteCount: 9 },
    quality_diagnostics: { overallScore: 88, warnings: ["引用需要抽查"] },
    learning_loop_state: { steps: [{ id: "review", done: true }] },
  });
  const { assetSummary, qualitySummary, learningLoopState } = deriveAgentResultInsights(result);

  assert.equal(result.assetSummary.fileName, "course.pdf");
  assert.equal(assetSummary.fileName, "course.pdf");
  assert.equal(assetSummary.noteCount, 9);
  assert.equal(qualitySummary.overallScore, 88);
  assert.deepEqual(qualitySummary.warnings, ["引用需要抽查"]);
  assert.equal(learningLoopState.steps.find((step) => step.id === "review").done, true);
});
