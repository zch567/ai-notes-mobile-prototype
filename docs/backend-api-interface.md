# 前后端接口说明

本文档给后端联调用，描述当前前端实际调用的接口、请求体、返回结构和错误格式。页面不会直接消费模型原始输出，所有结果进入页面前都会经过 `normalizeAgentResult` 归一化。

详细字段契约以 `docs/agent-result-contract.md` 为准；本文档更偏实现和联调。

当前接口设计分为两类：首次生成和后续编辑。首次生成用于把原始学习资料转换成结构化学习结果；后续编辑用于用户基于已生成笔记继续让 AI 改写、补充、压缩、重新生成复习题或同步更新导图。

## 运行模式

前端只保留真实后端模式，支持两种后端地址配置方式：环境变量默认值，以及运行时配置。

环境变量：

```text
VITE_DEMO_MODE=false
VITE_API_BASE_URL=http://127.0.0.1:8000
```

规则：`VITE_DEMO_MODE` 固定为 `false`，前端不再直接返回本地 demo/mock 结果。

运行时配置：

- 用户可在“我的 > 后端连接”中填写 `http://电脑局域网IP:8000`，点击“测试并启用”。
- 运行时启用真实后端后，`agentApi.runAgent`、`getProviderStatus` 等接口会使用保存的后端地址。
- “清除本机配置”会回到环境变量默认后端地址。

## 接口总览

| 方法 | 路径 | 用途 | 当前状态 |
|---|---|---|---|
| `POST` | `/api/agent/run` | 输入学习资料，返回结构化 Agent 结果 | 前端已接入 |
| `POST` | `/api/agent/run-file` | 上传 PDF/PPTX/文档文件并返回结构化 Agent 结果 | 前端已接入 |
| `GET` | `/api/agent/result/{result_id}` | 根据结果 id 重新读取后端保存的 AgentResult | 前端已接入 |
| `POST` | `/api/agent/chat` | 基于已保存结果继续向 Agent 提问 | 前端已接入 |
| `POST` | `/api/agent/review/submit` | 提交本次复习答案，返回掌握度、错题解析和个性化建议 | 前端已接入 |
| `POST` | `/api/agent/review/regenerate` | 基于复习历史重新生成复习题，并更新完整 AgentResult | 前端已接入 |
| `POST` | `/api/agent/edit` | 基于已生成结果进行 AI 修改、补充、压缩或重新评估 | 接口设计阶段 |

第一阶段采用同步接口：前端点击“运行 Agent”或“让 AI 修改”后等待接口返回完整结果。后续如果需要真实进度流或异步任务，可以再扩展任务创建、轮询或 SSE 接口。

## 客户完整使用流程模拟

用户打开应用后，首先进入 AI 生成页，粘贴文本或选择 PDF、PPT 学习资料。前端把资料类型、资料正文和资料元信息传给后端，调用 `POST /api/agent/run`。

后端返回第一版 AgentResult 后，前端展示生成结果、结构化笔记、引用回链、思维导图和复习评估。用户此时可能不会立刻结束，而是继续查看笔记内容、点击引用确认来源，或者进入导图和复习页。

当用户发现某段笔记太长、例子不够、表达不适合背诵，或者希望把全文压缩成考试重点时，用户会在已有笔记基础上继续向 AI 提要求。例如“把 Sigmoid 这一节改得更适合背诵”“给这一段补一个例子”“重新生成 5 道选择题”“根据我修改后的笔记同步导图”。

这类操作不应该继续使用首次生成接口，因为用户不是重新上传资料，而是在已有 AgentResult 上做二次编辑。此时前端需要调用 `POST /api/agent/edit`，把当前结果 id、修改目标、用户指令和当前内容快照传给后端。

后端完成修改后，建议返回更新后的完整 AgentResult。这样前端可以整体替换当前结果，避免出现笔记已经改了，但导图、引用或复习题仍然停留在旧版本的问题。

## POST /api/agent/run

### 请求头

```http
Content-Type: application/json
```

### 请求体

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

### 请求字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `inputType` | string | 是 | 输入类型。当前前端可能传 `text`、`pdf`、`ppt` |
| `sourceText` | string | 条件必填 | `inputType=text` 时传学习资料正文；文件模式第一阶段可为空 |
| `sourceMeta` | object | 是 | 资料元信息 |
| `sourceMeta.title` | string | 否 | 用户选择的样例名或资料标题 |
| `sourceMeta.fileName` | string | 否 | 文件模式下的原始文件名 |
| `sourceMeta.mimeType` | string | 否 | MIME 类型，例如 `text/plain`、`application/pdf` |

### 成功响应

推荐后端直接返回 `AgentResult`：

```json
{
  "id": "run-001",
  "topic": "Logistic Regression",
  "summary": "本资料介绍 Logistic Regression 的分类用途、Sigmoid 概率输出和交叉熵损失。",
  "keywords": ["分类任务", "Sigmoid", "交叉熵损失"],
  "outline": [
    {
      "id": "basic",
      "title": "基础定义",
      "brief": "理解模型用途和概率输出。",
      "refs": ["1"]
    }
  ],
  "warnings": [],
  "errors": [],
  "agentStages": [
    {
      "id": "extraction",
      "label": "Knowledge Extraction",
      "text": "已抽取核心知识点。"
    }
  ],
  "sources": [
    {
      "id": "1",
      "title": "Basic definition",
      "text": "Logistic regression is a classification algorithm...",
      "page": "1",
      "chunkId": "chunk-1",
      "sourceRef": "page_1"
    }
  ],
  "notes": [
    {
      "id": "definition",
      "title": "一、Basic definition",
      "content": "Logistic Regression 是一种分类算法。",
      "citationIds": ["1"],
      "level": 1,
      "parentId": ""
    }
  ],
  "citations": [
    {
      "id": "1",
      "sourceId": "1",
      "noteId": "definition"
    }
  ],
  "mindMap": {
    "nodes": [
      {
        "id": "center",
        "label": "Logistic Regression",
        "desc": "分类任务中的概率模型入口",
        "detail": "中心节点承载本次学习资料的主题。",
        "x": 50,
        "y": 50,
        "line": "#2563eb",
        "fill": "#ffffff"
      }
    ],
    "edges": []
  },
  "review": {
    "questions": [
      {
        "id": "q1",
        "type": "single-choice",
        "question": "Logistic Regression 主要用于什么任务？",
        "options": ["分类任务", "图像压缩", "数据库索引", "文本排版"],
        "answer": "分类任务",
        "explanation": "材料 [1] 指向它主要用于分类任务。",
        "citationIds": ["1"],
        "relatedNoteId": "definition"
      }
    ],
    "masteryScore": 76,
    "weakPoints": ["Cross-entropy loss"],
    "recommendations": ["优先回看交叉熵损失"]
  }
}
```

如果后端框架已经统一包裹响应，前端也兼容以下格式：

```json
{
  "data": {
    "...": "AgentResult"
  }
}
```

但联调推荐优先直接返回 `AgentResult`，减少判断分支。

## POST /api/agent/run-file

用于前端选择 PDF/PPTX/文档文件后直接上传。请求类型为 `multipart/form-data`。

字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `file` | file | 是 | 支持 `.txt`、`.md`、`.doc`、`.docx`、`.pdf`、`.pptx` |
| `pipeline` | string | 否 | 默认 `hybrid` |
| `provider` | string | 否 | 当前仅支持 `lanxin`；为空时使用后端配置 |
| `strictProvider` | boolean | 否 | 默认 `true` |
| `topK` | number | 否 | 引用召回数量，默认 `2` |
| `sourceTitle` | string | 否 | 前端标题，用于上传文件落盘命名和结果标题修正 |

旧版 `.doc` 文件由 Windows 后端调用本机 Microsoft Word 转换为临时 DOCX 后解析。后端需要安装 Microsoft Word 和 `pywin32`；如果转换能力不可用，接口返回 400，并提示用户将文件另存为 DOCX。

成功响应与 `/api/agent/run` 一致，返回完整 `AgentResult`。

## GET /api/agent/result/{result_id}

用于前端在结果页按 id 刷新后端保存的 AgentResult。成功响应为完整 `AgentResult`。

## POST /api/agent/chat

用于结果页 Agent 对话框继续追问当前资料。

请求体：

```json
{
  "resultId": "agent-xxxxxx",
  "question": "这份资料最容易混淆的点是什么？",
  "provider": "lanxin",
  "strictProvider": true,
  "topK": 3
}
```

成功响应至少包含：

```json
{
  "answer": "回答内容",
  "used_citations": ["source-id"],
  "_meta": {
    "agentModule": "M7_note_chat"
  }
}
```

## POST /api/agent/edit

### 接口作用

该接口用于用户已经生成一份学习结果后，继续让 AI 对当前结果进行修改、补充、压缩、改写、重新生成题目或同步更新导图。

它和 `/api/agent/run` 的区别是：`/api/agent/run` 面向原始学习资料，生成第一版 AgentResult；`/api/agent/edit` 面向已有 AgentResult，在当前结果基础上做二次修改。

### 请求头

```http
Content-Type: application/json
```

### 请求体

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
  "currentSnapshot": {
    "...": "当前前端持有的 AgentResult 或相关子集"
  },
  "preserveCitations": true,
  "syncDerivedArtifacts": true
}
```

### 请求字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `resultId` | string | 是 | 当前学习结果 id，用于定位是哪一次生成结果 |
| `version` | number | 否 | 当前结果版本号，用于避免基于过期内容修改 |
| `instruction` | string | 是 | 用户给 AI 的修改要求 |
| `editType` | string | 是 | 修改类型，例如 `rewrite`、`expand`、`summarize`、`add-example`、`regenerate-review`、`sync-mindmap` |
| `target` | object | 是 | 修改目标 |
| `target.type` | string | 是 | 目标类型，例如 `result`、`note`、`mindMapNode`、`reviewQuestion` |
| `target.id` | string | 否 | 目标对象 id；整篇修改时可为空 |
| `target.scope` | string | 否 | 修改范围，例如 `all`、`block`、`selection` |
| `currentSnapshot` | object | 是 | 前端当前页面上的最新 AgentResult 或相关子集 |
| `preserveCitations` | boolean | 否 | 是否尽量保留原有引用关系 |
| `syncDerivedArtifacts` | boolean | 否 | 是否同步更新导图、复习题等派生产物 |

### 成功响应

推荐后端返回更新后的完整 AgentResult，并附带编辑元信息：

```json
{
  "result": {
    "...": "更新后的完整 AgentResult"
  },
  "editMeta": {
    "resultId": "run-001",
    "version": 2,
    "changedTargets": [
      {
        "type": "note",
        "id": "sigmoid"
      },
      {
        "type": "mindMapNode",
        "id": "sigmoid"
      }
    ],
    "message": "已改写 Sigmoid 笔记，并同步更新导图节点说明。"
  }
}
```

前端处理建议：优先使用 `result` 替换当前 AgentResult；`editMeta.message` 可用于操作反馈。如果后端暂时不返回 `editMeta`，前端仍可只使用更新后的 AgentResult。

复赛阶段推荐返回完整 AgentResult，而不是只返回局部 patch。因为 AI 修改笔记经常会影响引用、导图和复习题，完整返回能保证前端状态一致。

## 最小可用响应

后端最少返回以下字段，页面即可展示核心笔记和引用：

```json
{
  "topic": "主题",
  "summary": "摘要",
  "notes": [
    {
      "id": "definition",
      "title": "一、定义",
      "content": "正文",
      "citationIds": ["1"]
    }
  ],
  "sources": [
    {
      "id": "1",
      "title": "来源标题",
      "text": "来源原文片段"
    }
  ]
}
```

缺失字段会由前端归一化层兜底；但空数组会被视为后端有意返回空结果，不会自动替换成 demo 数据。

## 编辑接口最小可用响应

`POST /api/agent/edit` 最少需要返回更新后的完整 AgentResult。即使后端只修改了一个 note block，也建议把完整结果返回给前端。

最小可用响应可以只包含 `result` 和简单的 `editMeta`。其中 `result` 会再次经过前端归一化层处理。

## 字段约束

| 字段 | 约束 |
|---|---|
| `topic`、`summary` | 建议非空字符串 |
| `keywords` | 可选字符串数组，用于展示主题关键词 |
| `outline` | 可选章节数组；字段建议为 `id`、`title`、`brief`、`refs` |
| `warnings`、`errors` | 可选字符串数组，用于展示解析质量提示或严重问题 |
| `sources[].id` | 字符串；需可被 `notes[].citationIds` 引用 |
| `sources[].page/chunkId/sourceRef` | 可选来源定位字段，用于引用浮层展示 |
| `notes[].id` | 字符串；建议稳定，方便 `citations[].noteId` 绑定 |
| `notes[].citationIds` | 字符串数组，主引用关系：`notes[].citationIds -> sources[].id` |
| `notes[].level/parentId` | 可选层级字段；前端会用 `level` 做缩进 |
| `citations[].sourceId` | 必须能定位到 `sources[].id` |
| `citations[].noteId` | 建议对应 `notes[].id` |
| `mindMap.nodes[].x/y` | 数字，推荐 0 到 100，表示画布百分比位置 |
| `mindMap.nodes[].line/fill` | 可选 CSS 颜色字符串 |
| `review.masteryScore` | 数字，推荐 0 到 100；前端会做边界限制 |
| `review.questions[].options` | 选择题选项数组；没有选项时可返回空数组 |
| `review.questions[].relatedNoteId` | 可选，关联到 `notes[].id` |

## Prompt 字段别名兼容

前端当前可兼容以下 Prompt 中间产物字段，但建议后端最终仍清洗为 camelCase `AgentResult`：

| 兼容字段 | 前端归一化目标 |
|---|---|
| `node_id` | `id` |
| `source_refs`、`refs` | `citationIds` |
| `question_id` | `review.questions[].id` |
| `question_type` | `review.questions[].type` |
| `related_note_id` | `review.questions[].relatedNoteId` |
| `description`、`discription` | `mindMap.nodes[].desc` |
| `quiz` | `review.questions` |
| `suggestions` | `review.recommendations` |
| `mindmap` 数组 | `mindMap.nodes`、`mindMap.edges` |

## 编辑目标约定

后续 AI 修改会涉及不同对象，建议前后端统一以下 target 类型：

| target.type | 用途 |
|---|---|
| `result` | 修改整份学习结果，例如全文压缩、整体风格调整 |
| `note` | 修改某条结构化笔记 |
| `mindMapNode` | 修改某个导图节点 |
| `reviewQuestion` | 修改或重生成某道复习题 |

常见 editType：

| editType | 用途 |
|---|---|
| `rewrite` | 改写表达 |
| `expand` | 扩写内容 |
| `summarize` | 压缩总结 |
| `add-example` | 补充例子 |
| `regenerate-review` | 重新生成复习题或评估 |
| `sync-mindmap` | 根据笔记同步导图 |

## 错误响应

接口失败时建议返回结构化 JSON：

```json
{
  "code": "AGENT_TIMEOUT",
  "message": "Agent 执行超时",
  "detail": "模型响应超过 60 秒"
}
```

前端展示规则：

| 字段 | 说明 |
|---|---|
| `message` | 必填，作为用户可见错误主文案 |
| `code` | 可选，用于定位错误类型 |
| `detail` | 可选，用于联调时补充原因 |

如果后端只返回纯文本，前端也会展示纯文本。

建议错误码：

| code | 场景 |
|---|---|
| `INVALID_INPUT` | 请求体缺失或格式不合法 |
| `UNSUPPORTED_INPUT_TYPE` | 暂不支持该 `inputType` |
| `DOCUMENT_PARSE_FAILED` | PDF/PPT/文本解析失败 |
| `MODEL_CALL_FAILED` | 模型调用失败 |
| `MODEL_OUTPUT_INVALID` | 模型输出无法清洗为结构化 JSON |
| `AGENT_TIMEOUT` | Agent 执行超时 |
| `RESULT_NOT_FOUND` | 编辑接口找不到对应结果 |
| `VERSION_CONFLICT` | 前端传入版本过旧，需要刷新后再修改 |
| `EDIT_TARGET_NOT_FOUND` | 找不到要修改的 note、导图节点或复习题 |

## 前端消费页面

| 页面 | 依赖字段 |
|---|---|
| AI Loading | `agentStages` |
| 生成结果 | `topic`、`summary`、`citations.length`、`notes.length`、`review.questions.length` |
| 笔记详情 | `topic`、`notes`、`sources`、`notes[].citationIds` |
| 引用浮层 | `sources[].id`、`sources[].title`、`sources[].text` |
| 思维导图 | `mindMap.nodes`、`mindMap.edges` |
| 复习评估 | `review.questions`、`review.masteryScore`、`review.weakPoints`、`review.recommendations` |
| 笔记库/首页 | `topic`、`summary`、`citations.length`、`review.masteryScore` |

## 前端编辑场景依赖字段

| 场景 | 前端传给后端 | 后端返回给前端 |
|---|---|---|
| 改写某段笔记 | `resultId`、`target.type=note`、`target.id`、`instruction`、`currentSnapshot` | 更新后的完整 AgentResult |
| 给某段补例子 | `resultId`、note id、用户要求、当前 sources 和 notes | 更新后的完整 AgentResult，引用尽量保留或补充 |
| 压缩全文 | `resultId`、`target.type=result`、全文快照、用户要求 | 更新后的完整 AgentResult |
| 重生成复习题 | `resultId`、`target.type=result` 或 `reviewQuestion`、当前笔记内容 | 更新后的完整 AgentResult 或至少更新后的 review |
| 同步导图 | `resultId`、当前 notes 和 mindMap、用户要求 | 更新后的完整 AgentResult 或至少更新后的 mindMap |

## POST /api/agent/review/regenerate

用于用户完成一轮复习后重新出题。前端会把本地题集中的复习历史一起传给后端，后端先压缩为学习情况概要，再交给 M6 生成新题，避免重复上一轮题干，并根据错题和掌握度调整题型策略。

请求体：

```json
{
  "resultId": "agent-xxx",
  "reviewHistory": [
    {
      "masteryScore": 60,
      "questionResults": [
        {
          "question": "上一轮题干",
          "userAnswer": "用户答案",
          "correctAnswer": "标准答案",
          "isCorrect": false
        }
      ],
      "wrongQuestionExplanations": [],
      "weakPoints": ["薄弱知识点"],
      "reviewSuggestions": ["上一轮复习建议"]
    }
  ],
  "provider": "lanxin",
  "strictProvider": true,
  "questionCount": 5
}
```

后端会构造 `review_history_summary`，包含 `previousQuestionStems`、`weakPoints`、`wrongExamples`、`reviewSuggestions` 和 `masteryTrend`，并生成 `adaptive_review_strategy`。M6 出题要求至少 60% 为场景应用、迁移、比较或错因诊断题，不再只生成定义类题目。

返回：更新后的完整 `AgentResult`，其中 `review.questions` 是新一轮复习题，后端会重新做引用 grounding 并持久化到 `result.json`。

## 联调检查清单

- 前端能请求到真实后端。
- APK 模式下，在“我的 > 后端连接”填写电脑局域网地址后，`/health` 测试成功。
- 后端允许前端所在地址跨域访问，例如 Vite 默认 `http://127.0.0.1:5173`。
- APK/WebView 联调时建议后端允许局域网访问来源，复赛 demo 可设置 `BACKEND_CORS_ORIGINS=*`。
- `POST /api/agent/run` 返回 JSON，且 `Content-Type` 为 `application/json`。
- 至少一个样例返回 `topic`、`summary`、`notes`、`sources`。
- 点击笔记引用编号能找到对应 `sources[].id`。
- `review.masteryScore` 在 0 到 100 范围内。
- API 失败时返回结构化错误，前端能展示错误文案而不是白屏。
- 用户对已生成笔记发起修改时，后端能根据 `resultId`、`target`、`instruction` 和 `currentSnapshot` 返回更新后的 AgentResult。
