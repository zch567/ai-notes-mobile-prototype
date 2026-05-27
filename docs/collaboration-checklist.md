# 合作开发检查清单

## 开发前

- 确认自己改哪个模块。
- 高风险文件先同步：`src/app/App.jsx`、`agentTypes.js`、`agentApi.js`。
- 拉取最新代码后再开发。

## 提交前

- 运行 `npm run build`。
- 确认首页、AI 生成、笔记详情、导图、复习评估可打开。
- 没有提交 `.env`、`dist`、日志和密钥。
- 改接口字段时同步更新 `docs/agent-result-contract.md`。
- 改导航或状态时同步更新 `src/app/navigation.js`。

## 联调时

- 后端先给一份真实返回 JSON。
- 前端先在 `agentTypes.js` 归一化字段。
- 页面组件不直接适配后端临时字段。
- API 不稳定时保留 `VITE_DEMO_MODE=true` 作为演示兜底。

