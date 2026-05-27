import { Card } from "../../components/Card";
import { TopBar } from "../../components/TopBar";
import { isDemoMode } from "../../services/demoMode";

export function ProfileScreen() {
  return (
    <div className="space-y-5 pb-6">
      <TopBar title="我的" subtitle="运行配置与演示状态" />
      <div className="px-5">
        <Card title="当前模式" subtitle="Runtime">
          <div className="rounded-2xl bg-slate-50 p-4">
            <p className="text-[14px] font-semibold text-slate-900">{isDemoMode() ? "演示模式" : "真实 API 模式"}</p>
            <p className="mt-2 text-[13px] leading-5 text-slate-500">
              设置 `VITE_DEMO_MODE=false` 后，前端会通过 `agentApi.runAgent` 调用真实后端。
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}
