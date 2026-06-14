import { getApiBaseUrl, isApiMode } from "./runtimeConfig";

export async function requestJSON(path, options = {}) {
  const { headers, ...requestOptions } = options;
  const response = await fetch(buildApiUrl(path), {
    ...requestOptions,
    headers: {
      "Content-Type": "application/json",
      ...(headers || {}),
    },
  });

  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new Error(message || `Request failed: ${response.status}`);
  }

  return response.json();
}

function buildApiUrl(path) {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl && isApiMode() && String(path).startsWith("/")) {
    throw new Error("请先在「我的」页配置后端地址");
  }

  if (!apiBaseUrl) return path;
  return `${apiBaseUrl}${String(path).startsWith("/") ? path : `/${path}`}`;
}

async function parseErrorMessage(response) {
  const text = await response.text();
  if (!text) return "";

  try {
    const errorBody = JSON.parse(text);
    if (typeof errorBody?.message === "string" && errorBody.message.trim()) {
      const code = typeof errorBody.code === "string" && errorBody.code.trim() ? `[${errorBody.code}] ` : "";
      const detail = typeof errorBody.detail === "string" && errorBody.detail.trim() ? `：${errorBody.detail}` : "";
      return `${code}${errorBody.message}${detail}`;
    }

    if (typeof errorBody?.detail === "string" && errorBody.detail.trim()) {
      return errorBody.detail;
    }
  } catch {
    return text;
  }

  return text;
}
