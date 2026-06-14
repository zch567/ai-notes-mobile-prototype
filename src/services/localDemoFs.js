import { sampleInputText } from "../data/sampleInputText";
import { normalizeAgentResult } from "../features/ai/agentTypes";

const STORAGE_PREFIX = "zhixu:demo:";
const SCHEMA_VERSION = 1;

const STORAGE_KEYS = {
  meta: `${STORAGE_PREFIX}meta`,
  results: `${STORAGE_PREFIX}results`,
  inputDraft: `${STORAGE_PREFIX}inputDraft`,
  noteSettings: `${STORAGE_PREFIX}noteSettings`,
  reviewProgress: `${STORAGE_PREFIX}reviewProgress`,
};

const defaultInputDraft = {
  inputType: "text",
  sourceText: sampleInputText,
  sourceTitle: "Logistic Regression 公开样例",
};

const defaultNoteSettings = {
  reviewMode: false,
  showCitations: true,
  autoSave: true,
};

export function initializeLocalDemoFs() {
  if (!canUseStorage()) return;

  const meta = readJSON(STORAGE_KEYS.meta, null);
  if (meta?.schemaVersion === SCHEMA_VERSION) return;

  writeJSON(STORAGE_KEYS.meta, {
    schemaVersion: SCHEMA_VERSION,
    activeResultId: "",
    createdAt: now(),
    updatedAt: now(),
  });

  writeJSON(STORAGE_KEYS.results, []);
  writeJSON(STORAGE_KEYS.inputDraft, {
    ...defaultInputDraft,
    updatedAt: now(),
  });
  writeJSON(STORAGE_KEYS.noteSettings, {});
  writeJSON(STORAGE_KEYS.reviewProgress, {});
}

export function readActiveAgentResult() {
  initializeLocalDemoFs();

  const meta = readJSON(STORAGE_KEYS.meta, null);
  const results = readJSON(STORAGE_KEYS.results, []);
  const activeRecord = results.find((record) => record.id === meta?.activeResultId) || results[0];

  return normalizeAgentResult(activeRecord?.agentResult || {});
}

export function saveActiveAgentResult(agentResult, sourceType = "generated") {
  if (!canUseStorage()) return;

  const normalized = normalizeAgentResult(agentResult);
  const results = readJSON(STORAGE_KEYS.results, []);
  const nextRecord = createResultRecord(normalized, sourceType);
  const nextResults = [nextRecord, ...results.filter((record) => record.id !== nextRecord.id)].slice(0, 12);

  writeJSON(STORAGE_KEYS.results, nextResults);
  writeJSON(STORAGE_KEYS.meta, {
    ...(readJSON(STORAGE_KEYS.meta, {}) || {}),
    schemaVersion: SCHEMA_VERSION,
    activeResultId: nextRecord.id,
    updatedAt: now(),
  });
}

export function readInputDraft() {
  initializeLocalDemoFs();
  const draft = readJSON(STORAGE_KEYS.inputDraft, defaultInputDraft);
  return {
    ...defaultInputDraft,
    ...draft,
  };
}

export function saveInputDraft(draft) {
  if (!canUseStorage()) return;

  writeJSON(STORAGE_KEYS.inputDraft, {
    ...defaultInputDraft,
    ...draft,
    updatedAt: now(),
  });
}

export function readNoteSettings(resultId) {
  initializeLocalDemoFs();
  const settingsByResult = readJSON(STORAGE_KEYS.noteSettings, {});
  return {
    ...defaultNoteSettings,
    ...(settingsByResult?.[resultId] || {}),
  };
}

export function saveNoteSettings(resultId, settings) {
  if (!canUseStorage() || !resultId) return;

  const settingsByResult = readJSON(STORAGE_KEYS.noteSettings, {});
  writeJSON(STORAGE_KEYS.noteSettings, {
    ...settingsByResult,
    [resultId]: {
      ...defaultNoteSettings,
      ...settings,
      updatedAt: now(),
    },
  });
}

export function readReviewProgress(resultId) {
  initializeLocalDemoFs();
  const progressByResult = readJSON(STORAGE_KEYS.reviewProgress, {});
  return {
    answeredQuestionIds: [],
    lastReviewedAt: null,
    ...(progressByResult?.[resultId] || {}),
  };
}

export function saveReviewProgress(resultId, progress) {
  if (!canUseStorage() || !resultId) return;

  const progressByResult = readJSON(STORAGE_KEYS.reviewProgress, {});
  writeJSON(STORAGE_KEYS.reviewProgress, {
    ...progressByResult,
    [resultId]: {
      answeredQuestionIds: [],
      lastReviewedAt: now(),
      ...progress,
      updatedAt: now(),
    },
  });
}

export function resetLocalDemoFs() {
  if (!canUseStorage()) return;
  Object.values(STORAGE_KEYS).forEach((key) => window.localStorage.removeItem(key));
  initializeLocalDemoFs();
}

function createResultRecord(agentResult, sourceType) {
  const normalized = normalizeAgentResult(agentResult);
  const timestamp = now();
  return {
    id: normalized.id || `result-${Date.now()}`,
    title: normalized.topic,
    summary: normalized.summary,
    sourceType,
    createdAt: timestamp,
    updatedAt: timestamp,
    agentResult: normalized,
    flags: {
      pinned: false,
      archived: false,
    },
  };
}

function readJSON(key, fallback) {
  if (!canUseStorage()) return fallback;

  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function writeJSON(key, value) {
  if (!canUseStorage()) return;

  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Demo storage is best-effort. The UI can keep running from in-memory state.
  }
}

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function now() {
  return new Date().toISOString();
}
