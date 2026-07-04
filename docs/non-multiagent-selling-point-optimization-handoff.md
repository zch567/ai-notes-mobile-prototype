# 非多 Agent 卖点优化交接文档

本文面向下一个 Codex 对话，用于继续优化三个非多 Agent 方向的比赛卖点。多 Agent、图像判决 Agent、多模态路由等方向由其他人负责，本任务不要展开实现。

## 目标

围绕以下三个卖点做“可展示、可验收、移动端不臃肿”的产品化优化：

1. `Learning Asset Pipeline`：学习资料知识资产化。
2. `Generation Observability Dashboard`：生成质量可观测。
3. `Mobile Learning Loop`：移动端学习闭环。

核心判断标准不是堆功能，而是让评委和用户能在手机端快速看懂：资料已经变成结构化知识资产，生成质量有可解释指标，学习流程可以从输入走到复习和追问。

## 当前基线

项目已经具备以下基础：

- 后端统一返回 `AgentResult`，包含 `topic`、`summary`、`notes`、`sources`、`citations`、`mindMap`、`review` 等结构。
- 后端已有 `agentStages`、`_meta.modelLog`、`modelLogs`、`citationDiagnostics`、契约校验接口和持久化结果。
- 前端已有首页、AI 输入、生成结果、笔记详情、引用回链、思维导图、复习评估、后端连接配置等页面。
- Android WebView APK 已能通过 `http://10.0.2.2:8000` 连接电脑后端，适合现场或校园网环境演示。
- `docs/backend-quality-selling-points.md` 已记录三个卖点的现状、短板和移动端展示约束。

本轮前端最小落地已补充：

- `agentTypes.js` 导出 `deriveAgentResultInsights(result)`，统一派生 `assetSummary`、`qualitySummary` 和 `learningLoopState`。
- 首页、笔记库和结果页已增加知识资产摘要、生成质量摘要和“输入 -> 笔记 -> 引用 -> 导图 -> 复习 -> 问答”闭环步骤。
- 结果页把后端诊断和 RAG 检索放入可展开区域，主屏保留结论、关键指标和下一步动作。
- 复习页完成后会显示本次复习反馈和薄弱点回看建议。

主要短板：

- 知识资产目前散落在各页面中，缺少统一的资产卡片、资产元信息和资产库叙事。
- 生成质量指标存在，但分散在多个字段和调试区域，没有形成一眼可懂的质量摘要。
- 移动端闭环页面已经存在，但“输入 -> 笔记 -> 引用 -> 导图 -> 复习 -> 问答”的流程感不够强。

## 实施原则

- 不破坏现有 `AgentResult` 契约。新增字段应保持可选，前端要能兼容旧结果。
- 优先复用已有数据推导指标，只有确实需要时再改后端结构。
- 移动端遵守“主界面只给结论，详情页再给证据”：首页和结果页只展示摘要、状态和下一步动作。
- 不把模型日志、引用明细、校验细节全部铺在主屏；诊断信息应折叠、分层或放到二级区域。
- 不实现多 Agent，不新增视觉模型链路，不引入会拖慢演示的大型依赖。
- 不提交 `.env`、日志、运行产物、`dist`、`node_modules`、APK 构建产物。

## 推荐实现顺序

### 第一步：统一前端派生指标

先在前端基于 `AgentResult` 增加轻量 selector/helper，派生以下信息：

- `assetSummary`：笔记数、来源数、引用数、导图节点数、复习题数、生成时间、资料类型或文件名。
- `qualitySummary`：总览等级、引用覆盖、结构完整、复习可用、告警列表。
- `learningLoopState`：输入、笔记、引用、导图、复习、问答等步骤的完成状态。

建议优先只做前端派生，减少后端改动风险。若后端已有 `_meta` 或 `citationDiagnostics` 可直接消费，前端 helper 负责兜底。

### 第二步：强化结果页的质量摘要

在结果页加入一个简洁的“生成质量摘要”模块：

- 只展示 3 到 4 个关键指标，例如引用覆盖、结构完整、复习可用、资料覆盖。
- 给出一句质量摘要，例如“本次生成已形成知识资产，引用覆盖良好，可进入复习”。
- 详细诊断继续放在折叠区或已有后端诊断区域，避免主屏拥挤。

### 第三步：强化知识资产表达

在首页或笔记库中增加“知识资产卡片”表达：

- 展示主题、摘要、笔记数、引用数、导图节点数、复习题数。
- 明确把一次生成结果称为“学习资产”或“知识资产包”。
- 提供少量高频入口：看笔记、看导图、做复习。

如果时间允许，可以增加前端本地资产索引；如果时间紧，先基于最近结果和本地记录做最小展示。

### 第四步：强化移动端学习闭环

在首页或结果页顶部加入轻量闭环进度：

```text
输入 -> 笔记 -> 引用 -> 导图 -> 复习 -> 问答
```

展示上应使用图标、短标签和完成态，不放长解释文案。点击后进入对应页面或触发对应动作。

复习完成后，给出更明确的反馈：

- 已完成本次复习。
- 掌握度或答题表现。
- 建议回看薄弱点。

## 建议触碰文件

优先关注：

- `src/features/ai/agentTypes.js`：新增派生 helper 或可选字段规范。
- `src/features/ai/ResultScreen.jsx`：质量摘要、学习闭环入口、诊断折叠。
- `src/features/notes/`：知识资产卡片或笔记库入口增强。
- `src/features/profile/` 或首页相关文件：如已有最近结果入口，可增强资产表达。
- `src/data/demoAgentResult.js`：补充 demo 数据，保证离线展示不空。
- `docs/agent-result-contract.md`：如果新增可选字段或派生指标，必须同步说明。
- `docs/backend-quality-selling-points.md`：实现后更新完成度和展示说明。

后端文件只有在必要时再改：

- `backend/app/` 下与归一化、持久化、契约校验相关的模块。
- 若增加后端返回字段，应保持兼容旧前端和旧结果文件。

## 移动端 UI 约束

每个页面只承担一个核心任务：

- 首页：最近知识资产、闭环进度、下一步动作。
- 结果页：摘要、质量总览、主行动入口。
- 笔记详情：阅读和引用回链。
- 导图页：概念关系和节点详情。
- 复习页：题目、掌握度、薄弱点和建议。

避免：

- 在首页塞完整笔记、导图、模型日志和引用详情。
- 在结果页同时展示过多指标表格。
- 用长段说明解释功能。
- 为比赛卖点堆叠按钮，导致手机端主路径变混乱。

## 验收标准

- 三个卖点在产品中都有可见承载：
  - 知识资产化：至少有资产卡片或资产摘要。
  - 质量可观测：至少有质量摘要和可展开诊断。
  - 移动端闭环：至少有闭环步骤和下一步动作。
- 主屏信息密度可控，首屏不出现大面积调试数据。
- 旧的 `AgentResult` 仍能正常渲染，不因缺少新增字段报错。
- `npm run test` 通过。
- `npm run build:webview` 通过。
- 如修改后端，补充接口级检查，并确认 APK 仍可通过 `http://10.0.2.2:8000` 访问后端。

## 给下一个对话的提示词

可以直接复制以下内容开启新对话：

```text
请先阅读项目根目录 AGENTS.md，然后进入 项目文件/ai-notes-mobile-prototype。

任务：实现非多 Agent 方向的比赛卖点优化。不要实现多 Agent、图像判决 Agent、多模态路由或视觉模型链路，这部分由其他人负责。本轮只做三个方向：

1. Learning Asset Pipeline：学习资料知识资产化
2. Generation Observability Dashboard：生成质量可观测
3. Mobile Learning Loop：移动端学习闭环

请先阅读：
- docs/backend-quality-selling-points.md
- docs/non-multiagent-selling-point-optimization-handoff.md
- docs/agent-result-contract.md
- README.md
- 开发规范.md
- docs/frontend-architecture.md

实现要求：
- 保持 AgentResult 兼容，新增字段必须可选；优先用前端 helper 从现有 AgentResult 派生 assetSummary、qualitySummary、learningLoopState。
- 移动端不能臃肿。首页和结果页只展示结论、少量关键指标和下一步动作；详细诊断放折叠区或二级区域。
- 至少让三个卖点都有可见承载：
  - 知识资产卡片或资产摘要
  - 生成质量摘要与可展开诊断
  - 输入、笔记、引用、导图、复习、问答的闭环步骤
- 不提交 .env、日志、运行产物、dist、node_modules、APK 构建产物。
- 修改接口字段或数据结构时同步更新 docs/agent-result-contract.md 和相关说明文档。

建议步骤：
1. 先看 git status，确认工作区状态。
2. 梳理 ResultScreen、首页/笔记入口、复习页现有结构。
3. 增加派生 helper 和轻量 UI 组件。
4. 保持页面信息分层，避免主屏堆满指标。
5. 运行 npm run test 和 npm run build:webview。
6. 最后给出改动摘要、测试结果和剩余风险。
```
