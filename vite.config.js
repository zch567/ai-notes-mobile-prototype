import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const isWebViewBuild =
    mode === "webview" || env.VITE_APP_SHELL_MODE === "webview";
  const shellMode = isWebViewBuild ? "webview" : env.VITE_APP_SHELL_MODE;
  const demoMode = isWebViewBuild ? "true" : env.VITE_DEMO_MODE;

  return {
    base: isWebViewBuild ? "./" : "/",
    plugins: [react()],
    define: {
      "import.meta.env.VITE_APP_SHELL_MODE": JSON.stringify(shellMode),
      "import.meta.env.VITE_DEMO_MODE": JSON.stringify(demoMode),
    },
  };
});
