export const APP_SHELL_MODE = {
  PREVIEW: "preview",
  WEBVIEW: "webview",
};

export function getAppShellMode() {
  if (typeof window !== "undefined") {
    const searchParams = new URLSearchParams(window.location.search);
    if (searchParams.get("shell") === APP_SHELL_MODE.WEBVIEW) {
      return APP_SHELL_MODE.WEBVIEW;
    }
  }

  return import.meta.env.VITE_APP_SHELL_MODE === APP_SHELL_MODE.WEBVIEW
    ? APP_SHELL_MODE.WEBVIEW
    : APP_SHELL_MODE.PREVIEW;
}

export function isWebViewShell() {
  return getAppShellMode() === APP_SHELL_MODE.WEBVIEW;
}
