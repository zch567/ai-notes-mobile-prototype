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
  return normalizeAgentResult(result);
}
