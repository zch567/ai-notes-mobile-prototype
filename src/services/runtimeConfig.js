const STORAGE_KEY = "zhixu:runtime-config";

function getEnvApiBaseUrl() {
  return import.meta.env.VITE_API_BASE_URL || "";
}

export function normalizeApiBaseUrl(value) {
  return String(value || "").trim().replace(/\/+$/, "");
}

export function getRuntimeConfig() {
  const stored = readStoredConfig();
  const mode = "api";
  const apiBaseUrl = normalizeApiBaseUrl(stored?.apiBaseUrl || getEnvApiBaseUrl());

  return {
    mode,
    apiBaseUrl,
    source: stored ? "local" : "env",
  };
}

export function saveRuntimeConfig(config) {
  const nextConfig = {
    mode: "api",
    apiBaseUrl: normalizeApiBaseUrl(config?.apiBaseUrl),
  };

  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(nextConfig));
  }

  return nextConfig;
}

export function clearRuntimeConfig() {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(STORAGE_KEY);
  }
}

export function isApiMode() {
  return getRuntimeConfig().mode === "api";
}

export function getApiBaseUrl() {
  return getRuntimeConfig().apiBaseUrl;
}

export async function testBackendConnection(baseUrl, timeoutMs = 5000) {
  const normalizedBaseUrl = normalizeApiBaseUrl(baseUrl);
  if (!normalizedBaseUrl) {
    throw new Error("请先填写后端地址");
  }

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${normalizedBaseUrl}/health`, {
      headers: {
        Accept: "application/json",
      },
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`后端返回 ${response.status}`);
    }

    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }

    return {
      ok: true,
      baseUrl: normalizedBaseUrl,
      payload,
    };
  } catch (err) {
    if (err?.name === "AbortError") {
      throw new Error("连接超时，请确认手机和电脑在同一局域网");
    }
    throw new Error(err instanceof Error ? err.message : "无法连接后端");
  } finally {
    window.clearTimeout(timeout);
  }
}

function readStoredConfig() {
  if (typeof window === "undefined") return null;

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}
