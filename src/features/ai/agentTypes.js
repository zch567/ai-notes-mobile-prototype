const emptyAgentResult = {
  id: "",
  topic: "",
  summary: "",
  keywords: [],
  outline: [],
  reportPlan: [],
  warnings: [],
  errors: [],
  agentStages: [],
  assetSummary: {},
  qualitySummary: {},
  qualityDiagnostics: {},
  learningLoopState: {},
  sources: [],
  notes: [],
  citations: [],
  citationDiagnostics: {},
  mindMap: {
    nodes: [],
    edges: [],
  },
  review: {
    questions: [],
    masteryScore: 0,
    weakPoints: [],
    recommendations: [],
  },
};

export function normalizeAgentResult(rawResult) {
  const source = rawResult && typeof rawResult === "object" ? rawResult : {};
  const reviewSource = source.review || {};
  const mindMapSource = source.mindMap || source.mindmap || {};
  const normalizedMindMapSource = Array.isArray(mindMapSource)
    ? mindMapListToGraph(mindMapSource, source.topic)
    : mindMapSource;

  const result = {
    ...emptyAgentResult,
    ...source,
    keywords: source.keywords || emptyAgentResult.keywords,
    outline: source.outline || emptyAgentResult.outline,
    warnings: source.warnings || source.warning || emptyAgentResult.warnings,
    errors: source.errors || source.error || emptyAgentResult.errors,
    mindMap: {
      ...emptyAgentResult.mindMap,
      ...normalizedMindMapSource,
    },
    review: {
      ...emptyAgentResult.review,
      ...reviewSource,
      questions: reviewSource.questions || source.quiz || emptyAgentResult.review.questions,
      recommendations: reviewSource.recommendations || source.suggestions || emptyAgentResult.review.recommendations,
    },
  };

  const topic = stringOrFallback(result.topic, emptyAgentResult.topic);
  const mindMap = normalizeMindMapGraph(
    normalizeArray(result.mindMap.nodes, emptyAgentResult.mindMap.nodes).map(normalizeMindMapNode),
    normalizeArray(result.mindMap.edges, emptyAgentResult.mindMap.edges).map(normalizeMindMapEdge),
    topic,
  );

  return {
    id: stringOrFallback(result.id, emptyAgentResult.id),
    topic,
    summary: stringOrFallback(result.summary, emptyAgentResult.summary),
    keywords: normalizeArray(result.keywords, emptyAgentResult.keywords).map(String),
    outline: normalizeArray(result.outline, emptyAgentResult.outline).map(normalizeOutlineItem),
    reportPlan: normalizeArray(source.reportPlan || source.report_plan, emptyAgentResult.reportPlan).map(normalizeOutlineItem),
    warnings: normalizeArray(result.warnings, emptyAgentResult.warnings).map(normalizeDiagnostic).filter(Boolean),
    errors: normalizeArray(result.errors, emptyAgentResult.errors).map(normalizeDiagnostic).filter(Boolean),
    agentStages: normalizeArray(result.agentStages, emptyAgentResult.agentStages).map(normalizeStage),
    assetSummary: firstNonEmptyObject(result.assetSummary, result.asset_summary),
    qualitySummary: firstNonEmptyObject(result.qualitySummary, result.quality_summary, result.qualityDiagnostics, result.quality_diagnostics),
    learningLoopState: firstNonEmptyObject(result.learningLoopState, result.learning_loop_state),
    sources: normalizeArray(result.sources, emptyAgentResult.sources).map(normalizeSource),
    notes: normalizeArray(result.notes, emptyAgentResult.notes).map(normalizeNote),
    citations: normalizeArray(result.citations, emptyAgentResult.citations).map(normalizeCitation),
    citationDiagnostics: normalizeObject(result.citationDiagnostics || result.citation_diagnostics),
    qualityDiagnostics: normalizeQualityDiagnostics(
      firstNonEmptyObject(result.qualityDiagnostics, result.quality_diagnostics, result.qualitySummary, result.quality_summary)
    ),
    _meta: normalizeObject(result._meta || result.meta),
    mindMap,
    review: {
      questions: normalizeArray(result.review.questions, emptyAgentResult.review.questions).map(normalizeQuestion),
      masteryScore: clamp(numberOrFallback(result.review.masteryScore, emptyAgentResult.review.masteryScore), 0, 100),
      weakPoints: normalizeArray(result.review.weakPoints, emptyAgentResult.review.weakPoints).map(String),
      recommendations: normalizeArray(result.review.recommendations, emptyAgentResult.review.recommendations)
        .map(normalizeRecommendation)
        .filter(Boolean),
    },
  };
}

export function deriveAgentResultInsights(result) {
  const source = result && typeof result === "object" ? result : emptyAgentResult;
  const assetSummary = deriveAssetSummary(source);
  const qualitySummary = deriveQualitySummary(source, assetSummary);
  const learningLoopState = deriveLearningLoopState(source);

  return {
    assetSummary,
    qualitySummary,
    learningLoopState,
  };
}

export function deriveAssetSummary(result) {
  const explicit = normalizeObject(result?.assetSummary || result?.asset_summary);
  const meta = normalizeObject(result?._meta || result?.meta);
  const assetMeta = normalizeObject(meta.assetMeta || meta.asset_meta || result?.assetMeta || result?.asset_meta);
  const sourceMeta = normalizeObject(meta.sourceMeta || meta.source_meta || result?.sourceMeta || result?.source_meta);
  const notes = normalizeArray(result?.notes, []);
  const sources = normalizeArray(result?.sources, []);
  const citations = normalizeArray(result?.citations, []);
  const mindMapNodes = normalizeArray(result?.mindMap?.nodes, []);
  const reviewQuestions = normalizeArray(result?.review?.questions, []);
  const uniqueCitationIds = new Set();

  notes.forEach((note) => {
    normalizeArray(note?.citationIds, []).forEach((id) => uniqueCitationIds.add(String(id)));
  });
  citations.forEach((citation) => {
    if (citation?.sourceId) uniqueCitationIds.add(String(citation.sourceId));
  });

  const noteCount = numberOrFallback(explicit.noteCount, notes.length, 0);
  const sourceCount = numberOrFallback(explicit.sourceCount, sources.length, 0);
  const citationCount = numberOrFallback(explicit.citationCount, uniqueCitationIds.size || citations.length, 0);
  const mindMapNodeCount = numberOrFallback(explicit.mindMapNodeCount, mindMapNodes.length, 0);
  const reviewQuestionCount = numberOrFallback(explicit.reviewQuestionCount, reviewQuestions.length, 0);
  const fileName = stringOrFallback(explicit.fileName || assetMeta.fileName || sourceMeta.fileName, "");
  const materialType = stringOrFallback(explicit.materialType || assetMeta.materialType || sourceMeta.mimeType || meta.inputType, inferMaterialType(fileName));
  const generatedAt = stringOrFallback(explicit.generatedAt || assetMeta.generatedAt || meta.generatedAt || meta.createdAt || meta.completedAt, "");
  const readyCount = [noteCount, sourceCount, mindMapNodeCount, reviewQuestionCount].filter((value) => value > 0).length;

  return {
    ...explicit,
    topic: stringOrFallback(explicit.topic, result?.topic || "未命名资料"),
    summary: stringOrFallback(explicit.summary, result?.summary || "等待生成结构化学习资产。"),
    fileName,
    materialType,
    generatedAt,
    noteCount,
    sourceCount,
    citationCount,
    mindMapNodeCount,
    mindMapEdgeCount: numberOrFallback(explicit.mindMapEdgeCount, normalizeArray(result?.mindMap?.edges, []).length, 0),
    reviewQuestionCount,
    status: stringOrFallback(explicit.status, readyCount >= 3 ? "ready" : noteCount ? "partial" : "empty"),
    statusText: stringOrFallback(explicit.statusText, readyCount >= 3 ? "知识资产包已就绪" : noteCount ? "资产仍在补全" : "等待生成资产"),
    summaryText: stringOrFallback(
      explicit.summaryText,
      noteCount
        ? `已沉淀 ${noteCount} 条笔记、${sourceCount} 个来源、${reviewQuestionCount} 道复习题。`
        : "生成后会汇总笔记、引用、导图和复习任务。"
    ),
    nextAction: stringOrFallback(explicit.nextAction, reviewQuestionCount ? "开始复习" : mindMapNodeCount ? "查看导图" : noteCount ? "查看笔记" : "开始生成"),
  };
}

export function deriveQualitySummary(result, assetSummary = deriveAssetSummary(result)) {
  const explicit = normalizeObject(
    result?.qualitySummary || result?.quality_summary || result?.qualityDiagnostics || result?.quality_diagnostics
  );
  const citationDiagnostics = normalizeObject(result?.citationDiagnostics || result?.citation_diagnostics);
  const warnings = normalizeArray(result?.warnings, []);
  const errors = normalizeArray(result?.errors, []);
  const citationCoverage = normalizedPercent(
    explicit.citationCoverage ??
    explicit.citationScore ??
    citationDiagnostics.noteCitationCoverage ??
    citationDiagnostics.citationCoverage,
    fallbackRatio(assetSummary.citationCount, assetSummary.noteCount || 1)
  );
  const quoteHitRate = normalizedPercent(
    explicit.quoteHitRate ?? citationDiagnostics.quoteInSourceRate ?? citationDiagnostics.quoteHitRate,
    citationCoverage
  );
  const structureCompleteness = normalizedPercent(
    explicit.structureCompleteness ?? explicit.assetCompleteness,
    deriveStructureCompleteness(result, assetSummary)
  );
  const reviewReadiness = normalizedPercent(
    explicit.reviewReadiness ?? explicit.reviewScore,
    assetSummary.reviewQuestionCount ? 1 : 0
  );
  const assetCoverage = normalizedPercent(
    explicit.assetCoverage ?? explicit.coverageScore,
    deriveAssetCoverage(assetSummary)
  );
  const warningList = normalizeArray(explicit.warnings, [])
    .map(normalizeDiagnostic)
    .filter(Boolean)
    .concat(errors.map(normalizeDiagnostic).filter(Boolean))
    .concat(warnings.map(normalizeDiagnostic).filter(Boolean))
    .slice(0, 4);
  const score = clamp(
    numberOrFallback(
      explicit.overallScore,
      Math.round((citationCoverage * 0.3 + structureCompleteness * 0.3 + reviewReadiness * 0.2 + assetCoverage * 0.2) * 100)
    ),
    0,
    100
  );
  const level = stringOrFallback(explicit.level || explicit.grade, qualityLevel(score, warningList.length));

  return {
    ...explicit,
    overallScore: score,
    level,
    citationCoverage,
    quoteHitRate,
    structureCompleteness,
    reviewReadiness,
    assetCoverage,
    warnings: warningList,
    summaryText: stringOrFallback(explicit.summaryText, qualitySummaryText(score, citationCoverage, reviewReadiness, warningList.length)),
    diagnostics: [
      { id: "asset", label: "资料覆盖", value: assetCoverage, detail: `${assetSummary.sourceCount} 个来源片段` },
      { id: "citation", label: "引用可信", value: citationCoverage, detail: `${assetSummary.citationCount} 个引用绑定` },
      { id: "structure", label: "结构完整", value: structureCompleteness, detail: `${assetSummary.noteCount} 条笔记 / ${assetSummary.mindMapNodeCount} 个导图节点` },
      { id: "review", label: "复习可用", value: reviewReadiness, detail: `${assetSummary.reviewQuestionCount} 道复习题` },
    ],
  };
}

export function deriveLearningLoopState(result) {
  const explicit = normalizeObject(result?.learningLoopState || result?.learning_loop_state);
  const stepsSource = normalizeArray(explicit.steps, []);
  const steps = [
    createLoopStep("input", "输入", hasInput(result)),
    createLoopStep("notes", "笔记", normalizeArray(result?.notes, []).length > 0),
    createLoopStep("citations", "引用", hasCitations(result)),
    createLoopStep("mindMap", "导图", normalizeArray(result?.mindMap?.nodes, []).length > 0),
    createLoopStep("review", "复习", normalizeArray(result?.review?.questions, []).length > 0),
    createLoopStep("qa", "问答", canAsk(result)),
  ].map((step) => {
    const override = stepsSource.find((item) => item?.id === step.id || item?.key === step.id);
    return override ? { ...step, ...override, done: Boolean(override.done ?? override.completed ?? step.done) } : step;
  });
  const completedCount = steps.filter((step) => step.done).length;
  const nextStep = steps.find((step) => !step.done) || steps[steps.length - 1];

  return {
    ...explicit,
    steps,
    completedCount,
    totalCount: steps.length,
    progress: steps.length ? completedCount / steps.length : 0,
    nextStep,
    summaryText: stringOrFallback(explicit.summaryText, `${completedCount}/${steps.length} 个学习环节已就绪`),
  };
}

function normalizeStage(stage, index) {
  return {
    id: stringOrFallback(stage?.id, `stage-${index + 1}`),
    label: stringOrFallback(stage?.label, `Stage ${index + 1}`),
    text: stringOrFallback(stage?.text, "正在处理学习材料..."),
  };
}

function normalizeSource(source, index) {
  const sourceRef = source?.sourceRef || source?.source_ref || source?.ref;
  return {
    ...(source || {}),
    id: stringOrFallback(source?.id || source?.sourceId || source?.source_id || sourceRef, String(index + 1)),
    title: stringOrFallback(source?.title, `Source ${index + 1}`),
    text: stringOrFallback(source?.text || source?.content, ""),
    page: valueStringOrFallback(source?.page || source?.pageNumber || source?.page_number || source?.slide, ""),
    slide: valueStringOrFallback(source?.slide, ""),
    paragraphStart: valueStringOrFallback(source?.paragraphStart || source?.paragraph_start || source?.paragraph, ""),
    paragraphEnd: valueStringOrFallback(source?.paragraphEnd || source?.paragraph_end, ""),
    lineStart: valueStringOrFallback(source?.lineStart || source?.line_start, ""),
    lineEnd: valueStringOrFallback(source?.lineEnd || source?.line_end, ""),
    chunkId: stringOrFallback(source?.chunkId || source?.chunk_id || source?.id, ""),
    sourceRef: stringOrFallback(sourceRef, ""),
  };
}

function normalizeNote(note, index) {
  const noteId = note?.id || note?.node_id || note?.nodeId;
  const sourceRefs = normalizeArray(note?.sourceRefs || note?.source_refs || note?.refs, []).map(String);
  return {
    ...(note || {}),
    id: stringOrFallback(noteId, `note-${index + 1}`),
    title: stringOrFallback(note?.title, `第 ${index + 1} 节`),
    content: stringOrFallback(note?.content, ""),
    summary: stringOrFallback(note?.summary, ""),
    keyPoints: normalizeArray(note?.keyPoints || note?.key_points, []).map(normalizeTextItem).filter(Boolean),
    examples: normalizeArray(note?.examples, []).map(normalizeStructuredValue).filter(Boolean),
    relations: normalizeArray(note?.relations, []).map(normalizeStructuredValue).filter(Boolean),
    blocks: normalizeArray(note?.blocks, []).map(normalizeNoteBlock).filter(Boolean),
    sourceRefs,
    citationIds: normalizeArray(note?.citationIds, sourceRefs).map(String),
    level: numberOrFallback(note?.level, inferLevelFromNodeId(noteId), 1),
    parentId: stringOrFallback(note?.parentId || note?.parent_id, inferParentId(noteId)),
  };
}

function normalizeNoteBlock(block, index) {
  if (typeof block === "string") {
    return {
      type: "text",
      title: "",
      text: block,
      items: [],
      structuredItems: [],
    };
  }
  if (!block || typeof block !== "object" || Array.isArray(block)) return null;
  return {
    ...block,
    type: stringOrFallback(block.type || block.block_type, "text"),
    title: stringOrFallback(block.title || block.label, ""),
    text: stringOrFallback(block.text || block.content || block.summary, ""),
    items: normalizeArray(block.items, []).map(normalizeStructuredValue).filter(Boolean),
    structuredItems: normalizeArray(block.structuredItems || block.structured_items, [])
      .map(normalizeStructuredItem)
      .filter(Boolean),
    id: stringOrFallback(block.id, `block-${index + 1}`),
  };
}

function normalizeStructuredItem(item) {
  if (typeof item === "string") {
    return { text: item, children: [] };
  }
  if (!item || typeof item !== "object" || Array.isArray(item)) return null;
  return {
    ...item,
    text: stringOrFallback(item.text || item.title || item.label, ""),
    children: normalizeArray(item.children, []).map(normalizeStructuredValue).filter(Boolean),
  };
}

function normalizeStructuredValue(item) {
  if (typeof item === "string") return item.trim() || null;
  if (!item || typeof item !== "object" || Array.isArray(item)) return null;
  return {
    ...item,
    text: stringOrFallback(item.text || item.description || item.content, ""),
    children: normalizeArray(item.children, []).map(normalizeStructuredValue).filter(Boolean),
  };
}

function normalizeTextItem(item) {
  if (typeof item === "string") return item.trim();
  return stringOrFallback(item?.text || item?.title || item?.label, "");
}

function normalizeCitation(citation, index) {
  return {
    ...(citation || {}),
    id: stringOrFallback(citation?.id || citation?.citation_id || citation?.citationId, String(index + 1)),
    sourceId: stringOrFallback(citation?.sourceId || citation?.source_id, citation?.id || String(index + 1)),
    noteId: stringOrFallback(citation?.noteId || citation?.note_id, ""),
    quote: stringOrFallback(citation?.quote, ""),
    sourceRef: stringOrFallback(citation?.sourceRef || citation?.source_ref, ""),
    page: valueStringOrFallback(citation?.page || citation?.pageNumber || citation?.page_number, ""),
    slide: valueStringOrFallback(citation?.slide, ""),
    paragraphStart: valueStringOrFallback(citation?.paragraphStart || citation?.paragraph_start, ""),
    paragraphEnd: valueStringOrFallback(citation?.paragraphEnd || citation?.paragraph_end, ""),
    lineStart: valueStringOrFallback(citation?.lineStart || citation?.line_start, ""),
    lineEnd: valueStringOrFallback(citation?.lineEnd || citation?.line_end, ""),
    confidence: numberOrFallback(citation?.confidence, 0),
    retrievalScore: numberOrFallback(citation?.retrievalScore || citation?.retrieval_score, 0),
    matchType: stringOrFallback(citation?.matchType || citation?.match_type, ""),
  };
}

function normalizeMindMapNode(node, index) {
  const nodeId = node?.id || node?.node_id || node?.nodeId;
  return {
    id: stringOrFallback(nodeId, `node-${index + 1}`),
    label: stringOrFallback(node?.label || node?.title, `Node ${index + 1}`),
    desc: stringOrFallback(node?.desc || node?.description || node?.discription, ""),
    detail: stringOrFallback(node?.detail, ""),
    x: numberOrFallback(node?.x, 50),
    y: numberOrFallback(node?.y, 50),
    line: stringOrFallback(node?.line, "#93c5fd"),
    fill: stringOrFallback(node?.fill, "#ffffff"),
    relatedNoteId: stringOrFallback(node?.relatedNoteId || node?.related_note_id, ""),
    sourceRefs: normalizeArray(node?.sourceRefs || node?.source_refs, []).map(String),
  };
}

function normalizeMindMapEdge(edge) {
  return {
    ...(edge || {}),
    from: stringOrFallback(edge?.from || edge?.source, ""),
    to: stringOrFallback(edge?.to || edge?.target, ""),
    type: stringOrFallback(edge?.type || edge?.relation_type || edge?.relation, "hierarchy"),
    label: stringOrFallback(edge?.label || edge?.edge_label || edge?.relation_label, ""),
    reason: stringOrFallback(edge?.reason || edge?.description || edge?.relation_reason, ""),
    confidence: clamp(numberOrFallback(edge?.confidence, 0), 0, 1),
    sourceRefs: normalizeArray(edge?.sourceRefs || edge?.source_refs, []).map(String),
  };
}

function normalizeMindMapGraph(nodes, edges, topic) {
  if (!nodes.length) return { nodes, edges };

  const rootId = findMindMapRootId(nodes);
  const duplicateRootIds = new Set(
    nodes
      .filter((node) => node.id !== rootId && isCoreSummaryMindMapNode(node, topic))
      .map((node) => node.id),
  );
  const nodesById = new Map(nodes.map((node) => [node.id, node]));
  const normalizedNodes = nodes
    .filter((node) => !duplicateRootIds.has(node.id))
    .map((node) => {
      if (node.id === rootId && isCoreSummaryMindMapNode(node, topic) && topic) {
        return {
          ...node,
          label: topic,
          desc: node.desc || "中心主题",
          detail: node.detail || topic,
        };
      }
      return node;
    });
  const edgeKeys = new Set();
  const normalizedEdges = [];

  edges.forEach((edge) => {
    let from = edge.from;
    const to = edge.to;

    if (duplicateRootIds.has(to)) return;
    if (duplicateRootIds.has(from)) from = rootId;
    if (!from || !to || from === to) return;

    const key = `${from}->${to}:${edge.type || "hierarchy"}:${edge.label || ""}`;
    if (edgeKeys.has(key)) return;
    edgeKeys.add(key);
    normalizedEdges.push({ ...edge, from, to });
  });

  if (duplicateRootIds.size) {
    duplicateRootIds.forEach((nodeId) => {
      const duplicate = nodesById.get(nodeId);
      if (!duplicate || !rootId || rootId === nodeId) return;
      edges
        .filter((edge) => edge.from === nodeId && edge.to !== rootId)
        .forEach((edge) => {
          const key = `${rootId}->${edge.to}:${edge.type || "hierarchy"}:${edge.label || ""}`;
          if (edgeKeys.has(key)) return;
          edgeKeys.add(key);
          normalizedEdges.push({ ...edge, from: rootId });
        });
    });
  }

  return {
    nodes: normalizedNodes,
    edges: normalizedEdges,
  };
}

function findMindMapRootId(nodes) {
  const explicitRoot = nodes.find((node) => ["root", "center"].includes(String(node.id || "").toLowerCase()));
  return explicitRoot?.id || nodes[0]?.id || "";
}

function isCoreSummaryMindMapNode(node, topic) {
  if (node?.relatedNoteId) return false;

  const label = normalizeMindMapSemanticText(node?.label);
  const normalizedTopic = normalizeMindMapSemanticText(topic);
  const coreSummaryLabels = new Set([
    "中心主题",
    "本章核心考点总结",
    "本节核心考点总结",
    "章节核心考点总结",
    "核心考点总结",
    "核心知识点总结",
  ]);

  return coreSummaryLabels.has(label) || Boolean(normalizedTopic && label === normalizedTopic);
}

function normalizeMindMapSemanticText(value) {
  return String(value || "").replace(/\s+/g, "").replace(/[：:，,。.\-_\s]/g, "").trim();
}

function normalizeQuestion(question, index) {
  const questionId = question?.id || question?.question_id || question?.questionId;
  return {
    id: stringOrFallback(questionId, `question-${index + 1}`),
    type: normalizeQuestionType(question?.type || question?.question_type || question?.questionType),
    question: stringOrFallback(question?.question, ""),
    options: normalizeArray(question?.options, []).map(String),
    answer: stringOrFallback(question?.answer, ""),
    explanation: stringOrFallback(question?.explanation, ""),
    citationIds: normalizeArray(question?.citationIds || question?.source_refs || question?.sourceRefs || question?.refs, []).map(String),
    relatedNoteId: stringOrFallback(question?.relatedNoteId || question?.related_note_id, ""),
  };
}

function normalizeOutlineItem(item, index) {
  return {
    id: stringOrFallback(item?.id || item?.section_id || item?.sectionId, `section-${index + 1}`),
    title: stringOrFallback(item?.title, `章节 ${index + 1}`),
    brief: stringOrFallback(item?.brief || item?.summary || item?.description, ""),
    refs: normalizeArray(item?.refs || item?.source_refs || item?.sourceRefs, []).map(String),
  };
}

function normalizeDiagnostic(item) {
  if (typeof item === "string") return item;
  return stringOrFallback(item?.message || item?.detail || item?.text, "");
}

function normalizeRecommendation(item) {
  if (typeof item === "string") return item;
  return stringOrFallback(item?.suggestion || item?.message || item?.text, "");
}

function normalizeQualityDiagnostics(value) {
  const diagnostics = normalizeObject(value);
  if (!Object.keys(diagnostics).length) return {};

  return {
    overallScore: numberOrNull(diagnostics.overallScore ?? diagnostics.overall_score),
    assetCompleteness: numberOrNull(diagnostics.assetCompleteness ?? diagnostics.asset_completeness),
    citationScore: numberOrNull(diagnostics.citationScore ?? diagnostics.citation_score),
    structureScore: numberOrNull(diagnostics.structureScore ?? diagnostics.structure_score),
    reviewScore: numberOrNull(diagnostics.reviewScore ?? diagnostics.review_score),
    warnings: normalizeArray(diagnostics.warnings, []).map(normalizeDiagnostic).filter(Boolean),
    summaryText: stringOrFallback(diagnostics.summaryText || diagnostics.summary_text, ""),
  };
}

function inferMaterialType(fileName) {
  const name = typeof fileName === "string" ? fileName.toLowerCase() : "";
  if (name.endsWith(".pdf")) return "PDF";
  if (name.endsWith(".ppt") || name.endsWith(".pptx")) return "PPT";
  if (name.endsWith(".doc") || name.endsWith(".docx")) return "DOC";
  return "Text";
}

function normalizedPercent(value, fallback = 0) {
  const number = Number.isFinite(Number(value)) ? Number(value) : fallback;
  const ratio = number > 1 ? number / 100 : number;
  return clamp(ratio, 0, 1);
}

function fallbackRatio(count, total) {
  const denominator = Math.max(numberOrFallback(total, 0), 1);
  return clamp(numberOrFallback(count, 0) / denominator, 0, 1);
}

function deriveStructureCompleteness(result, assetSummary) {
  const sections = [
    assetSummary.noteCount > 0,
    normalizeArray(result?.outline, []).length > 0 || normalizeArray(result?.reportPlan, []).length > 0,
    assetSummary.mindMapNodeCount > 0,
    assetSummary.reviewQuestionCount > 0,
  ];
  return sections.filter(Boolean).length / sections.length;
}

function deriveAssetCoverage(assetSummary) {
  const checks = [
    assetSummary.noteCount >= 1,
    assetSummary.sourceCount >= 1,
    assetSummary.citationCount >= 1,
    assetSummary.mindMapNodeCount >= 1,
    assetSummary.reviewQuestionCount >= 1,
  ];
  return checks.filter(Boolean).length / checks.length;
}

function qualityLevel(score, warningCount) {
  if (score >= 86 && warningCount === 0) return "优秀";
  if (score >= 72) return "稳定";
  if (score >= 55) return "可用";
  return "待补全";
}

function qualitySummaryText(score, citationCoverage, reviewReadiness, warningCount) {
  if (warningCount) return `质量分 ${score}，存在 ${warningCount} 条诊断提示，建议展开查看。`;
  if (score >= 86) return `质量分 ${score}，引用和复习链路完整，可直接进入学习。`;
  if (citationCoverage < 0.7) return `质量分 ${score}，引用覆盖偏低，建议先核验证据。`;
  if (reviewReadiness < 0.5) return `质量分 ${score}，笔记已生成，复习题仍需补充。`;
  return `质量分 ${score}，本次生成已形成可复习的知识资产。`;
}

function hasInput(result) {
  return Boolean(result?.id || result?.topic || result?._meta?.sourceMeta || result?._meta?.inputType);
}

function hasCitations(result) {
  return normalizeArray(result?.citations, []).length > 0 ||
    normalizeArray(result?.notes, []).some((note) => normalizeArray(note?.citationIds, []).length > 0);
}

function canAsk(result) {
  return Boolean(result?.id && (normalizeArray(result?.sources, []).length || normalizeArray(result?.notes, []).length));
}

function createLoopStep(id, label, done) {
  return {
    id,
    label,
    done: Boolean(done),
  };
}

function normalizeArray(value, fallback) {
  return Array.isArray(value) ? value : fallback;
}

function normalizeObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function firstNonEmptyObject(...values) {
  const objects = values.map(normalizeObject);
  return objects.find((object) => Object.keys(object).length > 0) || {};
}

function stringOrFallback(value, fallback) {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function valueStringOrFallback(value, fallback) {
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return fallback;
}

function numberOrFallback(value, fallback, min = undefined) {
  const number = Number.isFinite(Number(value)) ? Number(value) : fallback;
  return typeof min === "number" ? Math.max(number, min) : number;
}

function numberOrNull(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function normalizeQuestionType(value) {
  const type = stringOrFallback(value, "single-choice");
  const typeMap = {
    single_choice: "single-choice",
    multiple_choice: "multiple-choice",
    judgement: "judgement",
    short_answer: "short-answer",
    concept_explanation: "concept-explanation",
    application: "application",
  };
  return typeMap[type] || type;
}

function inferLevelFromNodeId(id) {
  if (typeof id !== "string" || !id.trim()) return 1;
  return id.split(".").filter(Boolean).length;
}

function inferParentId(id) {
  if (typeof id !== "string" || !id.includes(".")) return "";
  return id.split(".").slice(0, -1).join(".");
}

function mindMapListToGraph(mindMapItems, topic) {
  const normalizedNodes = mindMapItems.map((item, index) => {
    const nodeId = item?.id || item?.node_id || item?.nodeId || (index === 0 ? "center" : `node-${index}`);
    const normalizedId = nodeId === "root" ? "center" : String(nodeId);
    const position = mapNodePosition(index, mindMapItems.length);
    return {
      ...item,
      id: normalizedId,
      label: item?.label || item?.title || (index === 0 ? topic : `Node ${index + 1}`),
      desc: item?.desc || item?.description || item?.discription,
      relatedNoteId: item?.relatedNoteId || item?.related_note_id,
      x: item?.x ?? position.x,
      y: item?.y ?? position.y,
    };
  });

  const nodeIds = new Set(normalizedNodes.map((node) => node.id));
  const edges = normalizedNodes
    .filter((node) => node.id !== "center")
    .map((node) => {
      const parentId = inferParentId(node.id);
      return {
        from: parentId && nodeIds.has(parentId) ? parentId : "center",
        to: node.id,
      };
    });

  return {
    nodes: normalizedNodes,
    edges,
  };
}

function mapNodePosition(index, total) {
  if (index === 0) return { x: 50, y: 50 };
  const angle = ((index - 1) / Math.max(total - 1, 1)) * Math.PI * 2 - Math.PI / 2;
  return {
    x: Math.round((50 + Math.cos(angle) * 32) * 10) / 10,
    y: Math.round((50 + Math.sin(angle) * 30) * 10) / 10,
  };
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}
