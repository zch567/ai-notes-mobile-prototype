const emptyAgentResult = {
  id: "",
  topic: "",
  summary: "",
  keywords: [],
  outline: [],
  warnings: [],
  errors: [],
  agentStages: [],
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

  return {
    id: stringOrFallback(result.id, emptyAgentResult.id),
    topic: stringOrFallback(result.topic, emptyAgentResult.topic),
    summary: stringOrFallback(result.summary, emptyAgentResult.summary),
    keywords: normalizeArray(result.keywords, emptyAgentResult.keywords).map(String),
    outline: normalizeArray(result.outline, emptyAgentResult.outline).map(normalizeOutlineItem),
    warnings: normalizeArray(result.warnings, emptyAgentResult.warnings).map(normalizeDiagnostic).filter(Boolean),
    errors: normalizeArray(result.errors, emptyAgentResult.errors).map(normalizeDiagnostic).filter(Boolean),
    agentStages: normalizeArray(result.agentStages, emptyAgentResult.agentStages).map(normalizeStage),
    sources: normalizeArray(result.sources, emptyAgentResult.sources).map(normalizeSource),
    notes: normalizeArray(result.notes, emptyAgentResult.notes).map(normalizeNote),
    citations: normalizeArray(result.citations, emptyAgentResult.citations).map(normalizeCitation),
    citationDiagnostics: normalizeObject(result.citationDiagnostics || result.citation_diagnostics),
    _meta: normalizeObject(result._meta || result.meta),
    mindMap: {
      nodes: normalizeArray(result.mindMap.nodes, emptyAgentResult.mindMap.nodes).map(normalizeMindMapNode),
      edges: normalizeArray(result.mindMap.edges, emptyAgentResult.mindMap.edges).map(normalizeMindMapEdge),
    },
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
  return {
    id: stringOrFallback(noteId, `note-${index + 1}`),
    title: stringOrFallback(note?.title, `第 ${index + 1} 节`),
    content: stringOrFallback(note?.content, ""),
    citationIds: normalizeArray(note?.citationIds || note?.source_refs || note?.sourceRefs || note?.refs, []).map(String),
    level: numberOrFallback(note?.level, inferLevelFromNodeId(noteId), 1),
    parentId: stringOrFallback(note?.parentId || note?.parent_id, inferParentId(noteId)),
  };
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
  };
}

function normalizeMindMapEdge(edge) {
  return {
    from: stringOrFallback(edge?.from || edge?.source, ""),
    to: stringOrFallback(edge?.to || edge?.target, ""),
  };
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

function normalizeArray(value, fallback) {
  return Array.isArray(value) ? value : fallback;
}

function normalizeObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
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

function normalizeQuestionType(value) {
  const type = stringOrFallback(value, "single-choice");
  const typeMap = {
    single_choice: "single-choice",
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
