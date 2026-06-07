# AgentResult 数据契约

前端页面统一消费 `AgentResult`。后端可以返回近似结构，但进入页面前必须经过 `normalizeAgentResult`。

## 请求接口

复赛第一阶段使用同步接口：

```text
POST /api/agent/run
POST /api/agent/edit
```

前端请求体：

```json
{
  "inputType": "text",
  "sourceText": "学习资料正文",
  "sourceMeta": {
    "title": "Logistic Regression 公开样例",
    "fileName": "",
    "mimeType": "text/plain"
  }
}
```

字段规则：

| 字段 | 类型 | 用途 |
|---|---|---|
| `inputType` | string | 输入类型，当前取值为 `text`、`pdf`、`ppt` |
| `sourceText` | string | 文本模式下的资料正文；文件模式可先为空 |
| `sourceMeta.title` | string | 用户选择的样例名或资料标题 |
| `sourceMeta.fileName` | string | 文件模式下的原始文件名 |
| `sourceMeta.mimeType` | string | 输入内容 MIME 类型 |

## 编辑请求

`POST /api/agent/edit` 用于用户在已生成笔记基础上继续让 AI 修改内容。前端需要传当前结果 id、用户指令、修改目标和当前结果快照。

```json
{
  "resultId": "run-001",
  "version": 1,
  "instruction": "把 Sigmoid 这一节改得更适合背诵，并补一个例子。",
  "editType": "rewrite",
  "target": {
    "type": "note",
    "id": "sigmoid",
    "scope": "block"
  },
  "currentSnapshot": {},
  "preserveCitations": true,
  "syncDerivedArtifacts": true
}
```

编辑接口推荐返回：

```json
{
  "result": {},
  "editMeta": {
    "resultId": "run-001",
    "version": 2,
    "changedTargets": [],
    "message": "已完成修改。"
  }
}
```

其中 `result` 是更新后的完整 `AgentResult`。复赛阶段推荐返回完整结果，避免笔记、导图、复习题之间出现状态不同步。

## 顶层结构

```json
{
  "id": "demo-logistic-regression",
  "topic": "Logistic Regression",
  "summary": "主题摘要",
  "keywords": [],
  "outline": [],
  "warnings": [],
  "errors": [],
  "agentStages": [],
  "sources": [],
  "notes": [],
  "citations": [],
  "mindMap": {
    "nodes": [],
    "edges": []
  },
  "review": {
    "questions": [],
    "masteryScore": 0,
    "weakPoints": [],
    "recommendations": []
  }
}
```

## 字段说明

| 字段 | 类型 | 用途 |
|---|---|---|
| `agentStages` | array | Loading 页阶段展示 |
| `keywords` | array | M1 主题理解提取的关键词 |
| `outline` | array | M1 主题理解归纳的章节结构 |
| `warnings` | array | 可展示的解析质量提示，例如 OCR、页码缺失、结构混乱 |
| `errors` | array | 可展示的严重问题，页面会在结果页提示 |
| `sources` | array | 来源片段与引用浮层 |
| `notes` | array | 结构化笔记正文 |
| `citations` | array | 笔记段落与来源片段绑定 |
| `mindMap.nodes` | array | 导图节点 |
| `mindMap.edges` | array | 导图连线 |
| `review.questions` | array | 复习题 |
| `review.masteryScore` | number | 掌握度 |
| `review.weakPoints` | array | 薄弱点 |
| `review.recommendations` | array | 复习建议 |

## 后端最小可返回

推荐后端直接返回 `AgentResult`。如果后端框架暂时统一包裹为 `{ "data": { ... } }`，前端当前也会兼容，但第一阶段对齐时优先使用直接返回，减少歧义。

后端至少返回：

```json
{
  "topic": "主题",
  "summary": "摘要",
  "notes": [
    {
      "id": "definition",
      "title": "一、定义",
      "content": "正文",
      "citationIds": ["1"],
      "level": 1,
      "parentId": ""
    }
  ],
  "sources": [
    {
      "id": "1",
      "title": "来源标题",
      "text": "来源原文片段",
      "page": "1",
      "chunkId": "chunk-1",
      "sourceRef": "page_1"
    }
  ]
}
```

缺失字段会由 `normalizeAgentResult` 用演示数据或默认值兜底。注意：真实返回中的空数组会被视为有意为空，不会回退到演示数据，避免联调时误判接口已经返回完整内容。

## 引用关系约定

第一阶段页面主依赖关系为：

```text
notes[].citationIds -> sources[].id
```

`citations[]` 用于统计、审计和后续扩展。若后端同时返回 `citations[]`，其中 `sourceId` 必须能定位到 `sources[].id`，`noteId` 建议对应 `notes[].id`。

## Prompt 字段别名兼容

前端页面仍只消费归一化后的 `AgentResult`。为了降低第二阶段联调成本，`normalizeAgentResult` 当前兼容以下 Prompt/后端字段别名：

| 后端或 Prompt 字段 | 归一化后字段 |
|---|---|
| `node_id`、`nodeId` | `id` |
| `source_refs`、`sourceRefs`、`refs` | `citationIds` 或 `outline[].refs` |
| `question_id`、`questionId` | `review.questions[].id` |
| `question_type`、`questionType` | `review.questions[].type` |
| `related_note_id` | `review.questions[].relatedNoteId` 或 `mindMap.nodes[].relatedNoteId` |
| `description`、`discription` | `mindMap.nodes[].desc` |
| `quiz` | `review.questions` |
| `suggestions` | `review.recommendations` |
| `mindmap` 数组 | 转换为 `mindMap.nodes` 和 `mindMap.edges` |

注意：这些别名只是前端联调兜底。正式 v1 契约仍建议后端直接返回 camelCase 的 `AgentResult`。

## 错误响应

接口失败时建议返回结构化 JSON：

```json
{
  "code": "AGENT_TIMEOUT",
  "message": "Agent 执行超时",
  "detail": "模型响应超过 60 秒"
}
```

前端会优先展示 `message`，并附带 `code` 和 `detail`。如果后端只返回纯文本，前端也会按纯文本展示。

## 数值边界

`review.masteryScore` 建议返回 `0` 到 `100` 之间的数字。前端会做兜底限制，避免异常值影响进度条展示。
