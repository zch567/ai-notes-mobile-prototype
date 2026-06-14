import { requestJSON } from "../../services/apiClient";
import { normalizeAgentResult } from "./agentTypes";

export async function runAgent(input) {
  if (input?.file instanceof File) {
    return runFileAgent(input);
  }

  const result = await requestJSON("/api/agent/run", {
    method: "POST",
    body: JSON.stringify(input),
  });
  return applyInputTitlePatch(
    normalizeAgentResult(result?.data && typeof result.data === "object" ? result.data : result),
    input,
  );
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

async function runFileAgent(input) {
  const formData = new FormData();
  formData.append("file", input.file);
  formData.append("pipeline", input.pipeline || "hybrid");
  if (input.provider) formData.append("provider", input.provider);
  formData.append("strictProvider", String(input.strictProvider ?? true));
  formData.append("topK", String(input.topK || 2));
  formData.append("sourceTitle", input.sourceMeta?.title || input.file.name);

  const result = await requestJSON("/api/agent/run-file", {
    method: "POST",
    body: formData,
  });
  return applyInputTitlePatch(
    normalizeAgentResult(result?.data && typeof result.data === "object" ? result.data : result),
    input,
  );
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
