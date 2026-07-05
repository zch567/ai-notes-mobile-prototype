import { requestJSON } from "../../services/apiClient";
import { normalizeAgentResult } from "./agentTypes";

const POLL_INTERVAL_MS = 900;

export async function runAgent(input, options = {}) {
  if (input?.file instanceof File) {
    return runFileAgent(input, options);
  }

  try {
    const job = await requestJSON("/api/agent/jobs", {
      method: "POST",
      body: JSON.stringify(input),
    });
    return pollAgentJob(job, input, options);
  } catch (err) {
    if (!isMissingJobEndpointError(err)) throw err;
    return runLegacyAgent(input, options);
  }
}

export async function getProviderStatus() {
  return requestJSON("/api/providers/status");
}

export async function getAgentResult(resultId) {
  const result = await requestJSON(`/api/agent/result/${encodeURIComponent(resultId)}`);
  return normalizeAgentResult(result?.data && typeof result.data === "object" ? result.data : result);
}

export async function validateAgentResult(result) {
  return requestJSON("/api/agent/validate", {
    method: "POST",
    body: JSON.stringify({ result }),
  });
}

export async function queryRag({ resultId, chunksPath, query, topK = 5 }) {
  return requestJSON("/api/rag/query", {
    method: "POST",
    body: JSON.stringify({
      resultId,
      chunksPath,
      query,
      topK,
    }),
  });
}

export async function chatAgent({ resultId, question, provider, strictProvider = true, topK = 3 }) {
  return requestJSON("/api/agent/chat", {
    method: "POST",
    body: JSON.stringify({
      resultId,
      question,
      provider,
      strictProvider,
      topK,
    }),
  });
}

export async function submitReviewAnswers({ resultId, answers, provider = "lanxin", strictProvider = true }) {
  return requestJSON("/api/agent/review/submit", {
    method: "POST",
    body: JSON.stringify({
      resultId,
      answers,
      provider,
      strictProvider,
    }),
  });
}

export async function getAgentJob(jobId) {
  return requestJSON(`/api/agent/jobs/${encodeURIComponent(jobId)}`);
}

async function runFileAgent(input, options = {}) {
  const formData = new FormData();
  formData.append("file", input.file);
  formData.append("pipeline", input.pipeline || "hybrid");
  if (input.provider) formData.append("provider", input.provider);
  formData.append("strictProvider", String(input.strictProvider ?? true));
  formData.append("topK", String(input.topK || 2));
  formData.append("sourceTitle", input.sourceMeta?.title || input.file.name);

  try {
    const job = await requestJSON("/api/agent/jobs-file", {
      method: "POST",
      body: formData,
    });
    return pollAgentJob(job, input, options);
  } catch (err) {
    if (!isMissingJobEndpointError(err)) throw err;
    return runLegacyFileAgent(input, formData, options);
  }
}

async function runLegacyAgent(input, options) {
  reportLegacyProgress(options);
  const result = await requestJSON("/api/agent/run", {
    method: "POST",
    body: JSON.stringify(input),
  });
  return applyInputTitlePatch(
    normalizeAgentResult(result?.data && typeof result.data === "object" ? result.data : result),
    input,
  );
}

async function runLegacyFileAgent(input, formData, options) {
  reportLegacyProgress(options);
  const result = await requestJSON("/api/agent/run-file", {
    method: "POST",
    body: formData,
  });
  return applyInputTitlePatch(
    normalizeAgentResult(result?.data && typeof result.data === "object" ? result.data : result),
    input,
  );
}

function reportLegacyProgress(options) {
  options.onProgress?.({
    status: "running",
    progress: 45,
    stageId: "generate",
    label: "正在调用大模型生成笔记",
    text: "当前后端还没有加载进度接口，前端已切换到旧版生成接口；生成期间仍可以离开此界面。",
    stages: [],
  });
}

async function pollAgentJob(initialJob, input, options) {
  let job = normalizeAgentJob(initialJob);
  options.onProgress?.(job);

  while (!isTerminalJob(job)) {
    await delay(POLL_INTERVAL_MS);
    job = normalizeAgentJob(await getAgentJob(job.jobId));
    options.onProgress?.(job);
  }

  if (job.status === "failed") {
    throw new Error(job.error || "Agent 调用失败");
  }

  const rawResult = job.result || (job.resultId ? await getAgentResult(job.resultId) : null);
  if (!rawResult) {
    throw new Error("后端任务完成，但没有返回 AgentResult");
  }

  return applyInputTitlePatch(
    normalizeAgentResult(rawResult?.data && typeof rawResult.data === "object" ? rawResult.data : rawResult),
    input,
  );
}

function normalizeAgentJob(rawJob) {
  const job = rawJob && typeof rawJob === "object" ? rawJob : {};
  return {
    ...job,
    jobId: String(job.jobId || job.job_id || ""),
    status: String(job.status || "running"),
    progress: clampProgress(job.progress),
    stageId: String(job.stageId || job.stage_id || ""),
    label: String(job.label || ""),
    text: String(job.text || ""),
    resultId: String(job.resultId || job.result_id || ""),
    error: String(job.error || ""),
    stages: Array.isArray(job.stages) ? job.stages : [],
    result: job.result || null,
  };
}

function isTerminalJob(job) {
  return job.status === "succeeded" || job.status === "failed";
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function clampProgress(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.min(Math.max(number, 0), 100);
}

function isMissingJobEndpointError(err) {
  return /(^|\b)(404|not found)(\b|$)/i.test(err instanceof Error ? err.message : String(err || ""));
}

function applyInputTitlePatch(result, input) {
  const title = input?.sourceMeta?.title;
  if (!title || (input?.inputType === "text" && !looksLikeTemporaryTopic(result.topic))) return result;

  return {
    ...result,
    topic: title,
    mindMap: {
      ...result.mindMap,
      nodes: result.mindMap.nodes.map((node, index) => (
        index === 0 || node.id === "root" || node.id === "center"
          ? { ...node, label: title, detail: node.detail === result.topic ? title : node.detail }
          : node
      )),
    },
  };
}

function looksLikeTemporaryTopic(topic) {
  return /^input-[0-9a-f]{8,}$/i.test(String(topic || ""));
}
