const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export async function requestJSON(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new Error(message || `Request failed: ${response.status}`);
  }

  return response.json();
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
  } catch {
    return text;
  }

  return text;
}
