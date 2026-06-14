import { requestJSON } from "../../services/apiClient";
import { normalizeAgentResult } from "./agentTypes";

export async function runAgent(input) {
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

function applyInputTitlePatch(result, input) {
  const title = input?.sourceMeta?.title;
  if (!title || !looksLikeTemporaryTopic(result.topic)) return result;

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
