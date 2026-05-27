import { demoAgentResult } from "../../data/demoAgentResult";

const emptyAgentResult = {
  id: "",
  topic: "",
  summary: "",
  agentStages: [],
  sources: [],
  notes: [],
  citations: [],
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
  const result = {
    ...emptyAgentResult,
    ...source,
    mindMap: {
      ...emptyAgentResult.mindMap,
      ...(source.mindMap || {}),
    },
    review: {
      ...emptyAgentResult.review,
      ...(source.review || {}),
    },
  };

  return {
    id: stringOrFallback(result.id, demoAgentResult.id),
    topic: stringOrFallback(result.topic, demoAgentResult.topic),
    summary: stringOrFallback(result.summary, demoAgentResult.summary),
    agentStages: normalizeArray(result.agentStages, demoAgentResult.agentStages).map(normalizeStage),
    sources: normalizeArray(result.sources, demoAgentResult.sources).map(normalizeSource),
    notes: normalizeArray(result.notes, demoAgentResult.notes).map(normalizeNote),
    citations: normalizeArray(result.citations, demoAgentResult.citations).map(normalizeCitation),
    mindMap: {
      nodes: normalizeArray(result.mindMap.nodes, demoAgentResult.mindMap.nodes).map(normalizeMindMapNode),
      edges: normalizeArray(result.mindMap.edges, demoAgentResult.mindMap.edges).map(normalizeMindMapEdge),
    },
    review: {
      questions: normalizeArray(result.review.questions, demoAgentResult.review.questions).map(normalizeQuestion),
      masteryScore: numberOrFallback(result.review.masteryScore, demoAgentResult.review.masteryScore),
      weakPoints: normalizeArray(result.review.weakPoints, demoAgentResult.review.weakPoints).map(String),
      recommendations: normalizeArray(result.review.recommendations, demoAgentResult.review.recommendations).map(String),
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
  return {
    id: stringOrFallback(source?.id, String(index + 1)),
    title: stringOrFallback(source?.title, `Source ${index + 1}`),
    text: stringOrFallback(source?.text, ""),
  };
}

function normalizeNote(note, index) {
  return {
    id: stringOrFallback(note?.id, `note-${index + 1}`),
    title: stringOrFallback(note?.title, `第 ${index + 1} 节`),
    content: stringOrFallback(note?.content, ""),
    citationIds: normalizeArray(note?.citationIds, []).map(String),
  };
}

function normalizeCitation(citation, index) {
  return {
    id: stringOrFallback(citation?.id, String(index + 1)),
    sourceId: stringOrFallback(citation?.sourceId, citation?.id || String(index + 1)),
    noteId: stringOrFallback(citation?.noteId, ""),
  };
}

function normalizeMindMapNode(node, index) {
  return {
    id: stringOrFallback(node?.id, `node-${index + 1}`),
    label: stringOrFallback(node?.label, `Node ${index + 1}`),
    desc: stringOrFallback(node?.desc, ""),
    detail: stringOrFallback(node?.detail, ""),
    x: numberOrFallback(node?.x, 50),
    y: numberOrFallback(node?.y, 50),
    line: stringOrFallback(node?.line, "#93c5fd"),
    fill: stringOrFallback(node?.fill, "#ffffff"),
  };
}

function normalizeMindMapEdge(edge) {
  return {
    from: stringOrFallback(edge?.from, ""),
    to: stringOrFallback(edge?.to, ""),
  };
}

function normalizeQuestion(question, index) {
  return {
    id: stringOrFallback(question?.id, `question-${index + 1}`),
    type: stringOrFallback(question?.type, "single-choice"),
    question: stringOrFallback(question?.question, ""),
    options: normalizeArray(question?.options, []).map(String),
    answer: stringOrFallback(question?.answer, ""),
    explanation: stringOrFallback(question?.explanation, ""),
    citationIds: normalizeArray(question?.citationIds, []).map(String),
  };
}

function normalizeArray(value, fallback) {
  return Array.isArray(value) && value.length > 0 ? value : fallback;
}

function stringOrFallback(value, fallback) {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function numberOrFallback(value, fallback) {
  return Number.isFinite(Number(value)) ? Number(value) : fallback;
}
