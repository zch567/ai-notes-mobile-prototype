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
  folders: `${STORAGE_PREFIX}folders`,
  learningLog: `${STORAGE_PREFIX}learningLog`,
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

const defaultLearningLog = {
  generatedNotes: 0,
  readNotes: 0,
  reviewSessions: 0,
  totalStudySeconds: 0,
  dailyRecords: {},
  lastAction: "",
  lastActionAt: null,
  updatedAt: null,
};

export function initializeLocalDemoFs() {
  if (!canUseStorage()) return;

  const meta = readJSON(STORAGE_KEYS.meta, null);
  if (meta?.schemaVersion === SCHEMA_VERSION) {
    ensureInitialAgentResult(meta);
    ensureAgentFolders();
    ensureLearningLog();
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
  writeJSON(STORAGE_KEYS.folders, []);
  writeJSON(STORAGE_KEYS.learningLog, {
    ...defaultLearningLog,
    updatedAt: now(),
  });
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

export function readAgentFolders() {
  initializeLocalDemoFs();
  const folders = normalizeFolders(readJSON(STORAGE_KEYS.folders, []));

  if (JSON.stringify(folders) !== JSON.stringify(readJSON(STORAGE_KEYS.folders, []))) {
    writeJSON(STORAGE_KEYS.folders, folders);
  }

  return folders;
}

export function readLearningLog() {
  initializeLocalDemoFs();
  const log = normalizeLearningLog(readJSON(STORAGE_KEYS.learningLog, defaultLearningLog));
  writeJSON(STORAGE_KEYS.learningLog, log);
  return log;
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

function ensureAgentFolders() {
  const folders = readJSON(STORAGE_KEYS.folders, null);
  if (Array.isArray(folders)) return;
  writeJSON(STORAGE_KEYS.folders, []);
}

function ensureLearningLog() {
  const log = readJSON(STORAGE_KEYS.learningLog, null);
  if (log && typeof log === "object") return;
  writeJSON(STORAGE_KEYS.learningLog, {
    ...defaultLearningLog,
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

export function setAgentResultFolder(resultId, folderId) {
  if (!canUseStorage() || !resultId) return readAgentResultHistory();

  const folders = readAgentFolders();
  const normalizedFolderId = String(folderId || "");
  const nextFolderId = normalizedFolderId && folders.some((folder) => folder.id === normalizedFolderId)
    ? normalizedFolderId
    : "";
  const records = normalizeResultRecords(readJSON(STORAGE_KEYS.results, []));
  const nextRecords = sortResultRecords(records.map((record) => (
    record.id === resultId
      ? {
          ...record,
          folderId: nextFolderId,
          updatedAt: now(),
        }
      : record
  )));

  writeJSON(STORAGE_KEYS.results, nextRecords);
  return readAgentResultHistory();
}

export function createAgentFolder(name) {
  if (!canUseStorage()) return readAgentFolders();

  const folders = readAgentFolders();
  const trimmedName = normalizeFolderName(name);
  if (!trimmedName) return folders;

  const existing = folders.find((folder) => folder.name === trimmedName);
  if (existing) return folders;

  const nextFolders = sortFolders([
    ...folders,
    {
      id: createFolderId(trimmedName, folders),
      name: trimmedName,
      createdAt: now(),
      updatedAt: now(),
    },
  ]);
  writeJSON(STORAGE_KEYS.folders, nextFolders);
  return nextFolders;
}

export function renameAgentFolder(folderId, name) {
  if (!canUseStorage() || !folderId) return readAgentFolders();

  const folders = readAgentFolders();
  const trimmedName = normalizeFolderName(name);
  if (!trimmedName) return folders;
  if (folders.some((folder) => folder.id !== folderId && folder.name === trimmedName)) return folders;

  const nextFolders = sortFolders(folders.map((folder) => (
    folder.id === folderId
      ? {
          ...folder,
          name: trimmedName,
          updatedAt: now(),
        }
      : folder
  )));
  writeJSON(STORAGE_KEYS.folders, nextFolders);
  return nextFolders;
}

export function deleteAgentFolder(folderId) {
  if (!canUseStorage() || !folderId) {
    return {
      folders: readAgentFolders(),
      history: readAgentResultHistory(),
    };
  }

  const folders = readAgentFolders().filter((folder) => folder.id !== folderId);
  const records = normalizeResultRecords(readJSON(STORAGE_KEYS.results, []));
  const nextRecords = sortResultRecords(records.map((record) => (
    record.folderId === folderId
      ? { ...record, folderId: "", updatedAt: now() }
      : record
  )));

  writeJSON(STORAGE_KEYS.folders, folders);
  writeJSON(STORAGE_KEYS.results, nextRecords);

  return {
    folders: readAgentFolders(),
    history: readAgentResultHistory(),
  };
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
    folderId: existingRecord?.folderId || "",
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
        folderId: String(record?.folderId || ""),
        flags: {
          pinned: Boolean(record?.flags?.pinned),
          archived: Boolean(record?.flags?.archived),
        },
      };
    })
    .filter((record) => record.id);
}

export function recordLearningAction(action, amount = 1) {
  if (!canUseStorage()) return normalizeLearningLog(defaultLearningLog);

  const current = normalizeLearningLog(readJSON(STORAGE_KEYS.learningLog, defaultLearningLog));
  const increment = Math.max(1, Number(amount) || 1);
  const timestamp = now();
  const dayKey = toDateKey(new Date(timestamp));
  const dailyRecord = normalizeDailyRecord(current.dailyRecords[dayKey]);
  const nextLog = {
    ...current,
    dailyRecords: {
      ...current.dailyRecords,
      [dayKey]: {
        ...dailyRecord,
        updatedAt: timestamp,
      },
    },
    updatedAt: timestamp,
    lastActionAt: timestamp,
  };

  if (action === "generate") {
    nextLog.generatedNotes += increment;
    nextLog.dailyRecords[dayKey].generatedNotes += increment;
    nextLog.lastAction = "生成笔记";
  } else if (action === "read") {
    nextLog.readNotes += increment;
    nextLog.dailyRecords[dayKey].readNotes += increment;
    nextLog.lastAction = "阅读笔记";
  } else if (action === "review") {
    nextLog.reviewSessions += increment;
    nextLog.dailyRecords[dayKey].reviewSessions += increment;
    nextLog.lastAction = `完成 ${increment} 道题`;
  }

  writeJSON(STORAGE_KEYS.learningLog, nextLog);
  return nextLog;
}

export function addLearningDuration(seconds) {
  if (!canUseStorage()) return normalizeLearningLog(defaultLearningLog);

  const current = normalizeLearningLog(readJSON(STORAGE_KEYS.learningLog, defaultLearningLog));
  const duration = Math.max(0, Math.min(Number(seconds) || 0, 3600));
  const timestamp = now();
  const dayKey = toDateKey(new Date(timestamp));
  const dailyRecord = normalizeDailyRecord(current.dailyRecords[dayKey]);
  const nextLog = {
    ...current,
    totalStudySeconds: current.totalStudySeconds + duration,
    dailyRecords: {
      ...current.dailyRecords,
      [dayKey]: {
        ...dailyRecord,
        totalStudySeconds: dailyRecord.totalStudySeconds + duration,
        updatedAt: timestamp,
      },
    },
    updatedAt: timestamp,
  };

  writeJSON(STORAGE_KEYS.learningLog, nextLog);
  return nextLog;
}

function normalizeFolders(folders) {
  return sortFolders((Array.isArray(folders) ? folders : [])
    .map((folder) => ({
      id: String(folder?.id || "").trim(),
      name: normalizeFolderName(folder?.name),
      createdAt: String(folder?.createdAt || now()),
      updatedAt: String(folder?.updatedAt || folder?.createdAt || now()),
    }))
    .filter((folder) => folder.id && folder.name));
}

function normalizeLearningLog(log) {
  const dailyRecords = Object.fromEntries(
    Object.entries(log?.dailyRecords && typeof log.dailyRecords === "object" ? log.dailyRecords : {})
      .map(([key, record]) => [key, normalizeDailyRecord(record)])
      .filter(([key]) => /^\d{4}-\d{2}-\d{2}$/.test(key))
  );

  return {
    ...defaultLearningLog,
    ...(log || {}),
    generatedNotes: Math.max(0, Number(log?.generatedNotes) || 0),
    readNotes: Math.max(0, Number(log?.readNotes) || 0),
    reviewSessions: Math.max(0, Number(log?.reviewSessions) || 0),
    totalStudySeconds: Math.max(0, Number(log?.totalStudySeconds) || 0),
    dailyRecords,
    lastAction: String(log?.lastAction || ""),
    lastActionAt: log?.lastActionAt || null,
    updatedAt: log?.updatedAt || null,
  };
}

function normalizeDailyRecord(record) {
  return {
    generatedNotes: Math.max(0, Number(record?.generatedNotes) || 0),
    readNotes: Math.max(0, Number(record?.readNotes) || 0),
    reviewSessions: Math.max(0, Number(record?.reviewSessions) || 0),
    totalStudySeconds: Math.max(0, Number(record?.totalStudySeconds) || 0),
    updatedAt: record?.updatedAt || null,
  };
}

function toDateKey(date) {
  const safeDate = Number.isNaN(date?.getTime?.()) ? new Date() : date;
  const year = safeDate.getFullYear();
  const month = String(safeDate.getMonth() + 1).padStart(2, "0");
  const day = String(safeDate.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function sortFolders(folders) {
  return [...folders].sort((a, b) => a.name.localeCompare(b.name, "zh-Hans-CN"));
}

function normalizeFolderName(name) {
  return String(name || "").trim().slice(0, 18);
}

function createFolderId(name, folders) {
  const base = normalizeFolderName(name)
    .toLocaleLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5]+/g, "-")
    .replace(/^-+|-+$/g, "") || "folder";
  const ids = new Set(folders.map((folder) => folder.id));
  let id = `folder-${base}`;
  let index = 2;
  while (ids.has(id)) {
    id = `folder-${base}-${index}`;
    index += 1;
  }
  return id;
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
