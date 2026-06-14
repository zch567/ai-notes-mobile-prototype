import { demoAgentResult } from "../../data/demoAgentResult";
import { requestJSON } from "../../services/apiClient";
import { isDemoMode } from "../../services/demoMode";
import { normalizeAgentResult } from "./agentTypes";

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function runAgent(input) {
  if (isDemoMode()) {
    await wait(700);
    return normalizeAgentResult(demoAgentResult);
  }

  const result = await requestJSON("/api/agent/run", {
    method: "POST",
    body: JSON.stringify(input),
  });
  return normalizeAgentResult(result?.data && typeof result.data === "object" ? result.data : result);
}

export async function getProviderStatus() {
  if (isDemoMode()) {
    return {
      configuredProvider: "demo",
      lanxin: {
        configured: false,
        model: "demo-mode",
      },
      secretsFilePresent: false,
    };
  }

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
