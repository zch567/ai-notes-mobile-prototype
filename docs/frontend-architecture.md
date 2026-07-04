# 前端协作架构

## 目录边界

```text
src/app/          应用入口、导航常量、全局页面状态
src/components/   通用 UI 组件
src/data/         输入样例和历史兼容数据，不再作为生成结果兜底
src/features/     业务页面，按功能拆分
src/services/     API 客户端、运行模式等基础服务
```

## 分工建议

| 模块 | 负责人 | 说明 |
|---|---|---|
| `src/features/ai` | 前端 + 后端联调 | 输入、Loading、结果页、Agent API adapter |
| `src/features/notes` | 前端 | 笔记库、笔记详情、复习评估 |
| `src/features/mindmap` | 前端 | 导图渲染与节点工作台 |
| `src/services` | 后端 + 前端 | 请求封装、环境切换 |
| `src/data` | 前端 + 材料 | 只保留公开演示样例 |

## 开发规则

- 页面组件只消费归一化后的 `AgentResult`。
- 页面组件不直接写 `fetch`。
- 后端字段变化先改 `src/features/ai/agentTypes.js`，不要到处改页面。
- 面向展示的资产摘要、质量摘要和学习闭环状态优先在 `agentTypes.js` 通过 helper 派生，页面不要各自重复统计。
- 导航 id 和状态值统一从 `src/app/navigation.js` 引用。
- 输入样例数据只能放在 `src/data/`，不要散落到页面中。

## 接后端流程

1. 后端实现 `POST /api/agent/run`。
2. 前端设置 `.env`：

```text
VITE_DEMO_MODE=false
VITE_API_BASE_URL=http://127.0.0.1:8000
```

3. 后端返回接近 `AgentResult` 的 JSON。
4. 前端在 `agentTypes.js` 中兜底和归一化字段。
5. 页面无需改动。
