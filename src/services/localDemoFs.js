import { sampleInputText } from "../data/sampleInputText";
import { demoAgentResult } from "../data/demoAgentResult";
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
  if (meta?.schemaVersion === SCHEMA_VERSION) {
    ensureInitialAgentResult(meta);
    return;
  }

  writeJSON(STORAGE_KEYS.meta, {
    schemaVersion: SCHEMA_VERSION,
    activeResultId: demoAgentResult.id,
    createdAt: now(),
    updatedAt: now(),
  });

  writeJSON(STORAGE_KEYS.results, [createResultRecord(demoAgentResult, "seed")]);
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

export function readAgentResultHistory() {
  initializeLocalDemoFs();

  const meta = readJSON(STORAGE_KEYS.meta, null);
  const records = normalizeResultRecords(readJSON(STORAGE_KEYS.results, []));
  const sortedRecords = sortResultRecords(records);

  if (JSON.stringify(records) !== JSON.stringify(sortedRecords)) {
    writeJSON(STORAGE_KEYS.results, sortedRecords);
  }

  return sortedRecords.map((record) => ({
    ...record,
    active: record.id === meta?.activeResultId,
  }));
}

function ensureInitialAgentResult(meta) {
  const results = readJSON(STORAGE_KEYS.results, []);
  if (Array.isArray(results) && results.length > 0) return;

  const seedRecord = createResultRecord(demoAgentResult, "seed");
  writeJSON(STORAGE_KEYS.results, [seedRecord]);
  writeJSON(STORAGE_KEYS.meta, {
    ...(meta || {}),
    schemaVersion: SCHEMA_VERSION,
    activeResultId: seedRecord.id,
    updatedAt: now(),
  });
}

export function saveActiveAgentResult(agentResult, sourceType = "generated") {
  if (!canUseStorage()) return;

  const normalized = normalizeAgentResult(agentResult);
  const results = readJSON(STORAGE_KEYS.results, []);
  const existingRecord = results.find((record) => record.id === normalized.id);
  const nextRecord = createResultRecord(normalized, sourceType, existingRecord);
  const nextResults = sortResultRecords([nextRecord, ...results.filter((record) => record.id !== nextRecord.id)]).slice(0, 12);

  writeJSON(STORAGE_KEYS.results, nextResults);
  writeJSON(STORAGE_KEYS.meta, {
    ...(readJSON(STORAGE_KEYS.meta, {}) || {}),
    schemaVersion: SCHEMA_VERSION,
    activeResultId: nextRecord.id,
    updatedAt: now(),
  });
}

export function activateAgentResult(resultId) {
  initializeLocalDemoFs();

  const records = normalizeResultRecords(readJSON(STORAGE_KEYS.results, []));
  const record = records.find((item) => item.id === resultId) || records[0];
  if (!record) return normalizeAgentResult({});

  writeJSON(STORAGE_KEYS.meta, {
    ...(readJSON(STORAGE_KEYS.meta, {}) || {}),
    schemaVersion: SCHEMA_VERSION,
    activeResultId: record.id,
    updatedAt: now(),
  });

  return record.agentResult;
}

export function setAgentResultPinned(resultId, pinned) {
  if (!canUseStorage() || !resultId) return readAgentResultHistory();

  const records = normalizeResultRecords(readJSON(STORAGE_KEYS.results, []));
  const nextRecords = sortResultRecords(records.map((record) => (
    record.id === resultId
      ? {
          ...record,
          updatedAt: now(),
          flags: {
            ...record.flags,
            pinned: Boolean(pinned),
          },
        }
      : record
  )));

  writeJSON(STORAGE_KEYS.results, nextRecords);
  return readAgentResultHistory();
}

export function deleteAgentResultRecord(resultId) {
  initializeLocalDemoFs();

  const records = normalizeResultRecords(readJSON(STORAGE_KEYS.results, []));
  if (!resultId || records.length <= 1) {
    return {
      activeResult: readActiveAgentResult(),
      history: readAgentResultHistory(),
      deleted: false,
    };
  }

  const nextRecords = records.filter((record) => record.id !== resultId);
  if (nextRecords.length === records.length) {
    return {
      activeResult: readActiveAgentResult(),
      history: readAgentResultHistory(),
      deleted: false,
    };
  }

  const meta = readJSON(STORAGE_KEYS.meta, {}) || {};
  const nextActiveRecord = meta.activeResultId === resultId
    ? sortResultRecords(nextRecords)[0]
    : nextRecords.find((record) => record.id === meta.activeResultId) || sortResultRecords(nextRecords)[0];

  writeJSON(STORAGE_KEYS.results, sortResultRecords(nextRecords));
  writeJSON(STORAGE_KEYS.meta, {
    ...meta,
    schemaVersion: SCHEMA_VERSION,
    activeResultId: nextActiveRecord?.id || "",
    updatedAt: now(),
  });

  return {
    activeResult: normalizeAgentResult(nextActiveRecord?.agentResult || {}),
    history: readAgentResultHistory(),
    deleted: true,
  };
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

function createResultRecord(agentResult, sourceType, existingRecord = null) {
  const normalized = normalizeAgentResult(agentResult);
  const timestamp = now();
  return {
    id: normalized.id || `result-${Date.now()}`,
    title: normalized.topic,
    summary: normalized.summary,
    sourceType,
    createdAt: existingRecord?.createdAt || timestamp,
    updatedAt: timestamp,
    agentResult: normalized,
    flags: {
      pinned: Boolean(existingRecord?.flags?.pinned),
      archived: Boolean(existingRecord?.flags?.archived),
    },
  };
}

function normalizeResultRecords(records) {
  return (Array.isArray(records) ? records : [])
    .map((record) => {
      const agentResult = normalizeAgentResult(record?.agentResult || {});
      const timestamp = now();
      return {
        id: String(record?.id || agentResult.id || `result-${Date.now()}`),
        title: String(record?.title || agentResult.topic || "未命名资料"),
        summary: String(record?.summary || agentResult.summary || ""),
        sourceType: String(record?.sourceType || "generated"),
        createdAt: String(record?.createdAt || timestamp),
        updatedAt: String(record?.updatedAt || record?.createdAt || timestamp),
        agentResult,
        flags: {
          pinned: Boolean(record?.flags?.pinned),
          archived: Boolean(record?.flags?.archived),
        },
      };
    })
    .filter((record) => record.id);
}

function sortResultRecords(records) {
  return [...records].sort((a, b) => {
    if (Boolean(a.flags?.pinned) !== Boolean(b.flags?.pinned)) {
      return a.flags?.pinned ? -1 : 1;
    }

    const timeA = Date.parse(a.updatedAt || a.createdAt || "") || 0;
    const timeB = Date.parse(b.updatedAt || b.createdAt || "") || 0;
    return timeB - timeA;
  });
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
