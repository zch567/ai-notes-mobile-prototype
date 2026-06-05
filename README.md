# AI 笔记移动端原型

这是一个基于 React + Vite + Tailwind CSS 的移动端前端原型，用于展示“智序知识助手”的 AI 学习闭环。

## 当前结构

```text
src/app/          应用入口、导航状态
src/components/   通用组件
src/data/         演示数据
src/features/     业务页面
src/services/     API 与运行模式
docs/             协作与接口文档
```

核心数据结构是 `AgentResult`。页面统一消费归一化后的 `AgentResult`，后端字段变化优先在 `src/features/ai/agentTypes.js` 处理。

## 本地运行

```bash
npm install
npm run dev
```

默认使用演示模式。复制 `.env.example` 为 `.env` 后可切换真实 API：

```text
VITE_DEMO_MODE=false
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 构建

```bash
npm run build
```

## 文档

- `docs/frontend-architecture.md`：前端模块边界。
- `docs/agent-result-contract.md`：后端返回数据契约。
- `docs/frontend-adapter-checklist.md`：第二周 C 任务前端适配清单。
- `docs/backend-api-interface.md`：前后端接口联调说明。
- `docs/collaboration-checklist.md`：多人协作检查清单。

