import { useMemo, useState } from "react";
import { Card } from "../../components/Card";
import { TopBar } from "../../components/TopBar";
import {
  clearRuntimeConfig,
  getRuntimeConfig,
  normalizeApiBaseUrl,
  saveRuntimeConfig,
  testBackendConnection,
} from "../../services/runtimeConfig";

export function ProfileScreen() {
  const initialConfig = useMemo(() => getRuntimeConfig(), []);
  const [apiBaseUrl, setApiBaseUrl] = useState(initialConfig.apiBaseUrl);
  const [savedConfig, setSavedConfig] = useState(initialConfig);
  const [testStatus, setTestStatus] = useState("idle");
  const [message, setMessage] = useState("");

  function refreshFromStorage(nextConfig = getRuntimeConfig()) {
    const effectiveConfig = nextConfig.source ? nextConfig : getRuntimeConfig();
    setSavedConfig(effectiveConfig);
    setApiBaseUrl(effectiveConfig.apiBaseUrl);
  }

  function handleSave() {
    const nextConfig = saveRuntimeConfig({ apiBaseUrl });
    refreshFromStorage(nextConfig);
    setMessage("已保存真实后端配置");
  }

  async function handleTestAndEnable() {
    setTestStatus("loading");
    setMessage("");

    try {
      const result = await testBackendConnection(apiBaseUrl);
      const nextConfig = saveRuntimeConfig({ apiBaseUrl: result.baseUrl });
      refreshFromStorage(nextConfig);
      setTestStatus("success");
      setMessage(`连接成功，已启用 ${result.baseUrl}`);
    } catch (err) {
      setTestStatus("error");
      setMessage(err instanceof Error ? err.message : "连接失败");
    }
  }

  function handleClear() {
    clearRuntimeConfig();
    refreshFromStorage();
    setTestStatus("idle");
    setMessage("已清除本机后端地址配置");
  }

  return (
    <div className="space-y-5 pb-6">
      <TopBar title="我的" subtitle="真实后端连接配置" />

      <div className="space-y-4 px-5">
        <Card title="当前模式" subtitle="Runtime">
          <div className="flex items-start justify-between gap-3 rounded-2xl bg-slate-50 p-4">
            <div>
              <p className="text-[14px] font-semibold text-slate-900">真实后端模式</p>
              <p className="mt-2 text-[13px] leading-5 text-slate-500">
                当前版本不再内置 mock 生成兜底。请启动电脑端 FastAPI 后端，并在下方填写局域网地址。
              </p>
            </div>
            <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-emerald-500" />
          </div>
        </Card>

        <Card title="后端连接" subtitle="Backend">
          <label className="block">
            <span className="mb-2 block text-[12px] font-semibold uppercase tracking-[0.18em] text-slate-400">API Base URL</span>
            <input
              value={apiBaseUrl}
              onChange={(event) => setApiBaseUrl(event.target.value)}
              onBlur={() => setApiBaseUrl(normalizeApiBaseUrl(apiBaseUrl))}
              placeholder="http://192.168.1.23:8000"
              className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-[14px] font-semibold text-slate-800 outline-none transition placeholder:text-slate-300 focus:border-blue-200 focus:shadow-sm"
            />
          </label>

          <div className="mt-3 rounded-2xl border border-blue-100 bg-blue-50 px-3 py-3">
            <p className="text-[13px] leading-5 text-blue-900">
              电脑启动后端时使用 <span className="font-semibold">0.0.0.0:8000</span>，手机和电脑连同一个 Wi-Fi，再填电脑 IPv4 地址。
            </p>
          </div>

          {message ? (
            <p className={`mt-3 text-[13px] leading-5 ${testStatus === "error" ? "text-rose-600" : "text-slate-500"}`}>{message}</p>
          ) : null}

          <div className="mt-4 grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={handleTestAndEnable}
              disabled={testStatus === "loading"}
              className="rounded-2xl bg-blue-600 px-4 py-3 text-[13px] font-semibold text-white disabled:bg-slate-300"
            >
              {testStatus === "loading" ? "测试中..." : "测试并启用"}
            </button>
            <button
              type="button"
              onClick={handleSave}
              className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-[13px] font-semibold text-slate-700"
            >
              保存配置
            </button>
          </div>

          <button
            type="button"
            onClick={handleClear}
            className="mt-3 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-[13px] font-semibold text-slate-600"
          >
            清除本机配置
          </button>

          <p className="mt-4 text-[12px] leading-5 text-slate-400">
            当前保存来源：{savedConfig.source === "local" ? "本机配置" : "环境变量默认值"}。AI 生成页会调用这个后端地址。
          </p>
        </Card>
      </div>
    </div>
  );
}
