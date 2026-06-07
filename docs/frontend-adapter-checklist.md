# 第二周 C 任务：前端适配清单

本文档用于第二周 C 任务交付：根据离线 Agent pipeline 的 JSON 输出，检查当前 React 前端是否能承载真实字段，并列出需要与后端、测试同学对齐的字段和风险。

## 本周目标

- 不急于正式接 API，先确认真实 JSON 能否被前端页面消费。
- 页面统一消费归一化后的 `AgentResult`，不要直接依赖模型原始输出。
- 明确 Result、NoteDetail、MindMap、Review 等页面所需字段。
- 为第 3 周真实数据渲染预研和第 4 周 API 接入降低字段变更风险。

## 页面字段依赖

| 页面 | 当前用途 | 主要依赖字段 | 必须程度 | 备注 |
|---|---|---|---|---|
| `InputScreen` | 输入文本、PDF、PPT 类型和资料元信息 | `inputType`、`sourceText`、`sourceMeta.title`、`sourceMeta.fileName`、`sourceMeta.mimeType` | 高 | 第二周文件模式可先传空文本，但后端要知道输入类型。 |
| `LoadingScreen` | 展示 Agent 阶段进度 | `agentStages[].id`、`agentStages[].label`、`agentStages[].text` | 中 | 后端不返回时前端使用默认阶段。 |
| `ResultScreen` | 展示生成结果总览和产物入口 | `topic`、`summary`、`notes`、`sources`、`citations`、`review.questions`、`review.recommendations` | 高 | 真实返回缺数组时可显示空状态，不应白屏。 |
| `ResultScreen` | 展示资料理解结果 | `keywords`、`outline`、`warnings`、`errors` | 中 | 对应 Prompt M1 的主题识别、章节结构和潜在问题。 |
| `NotesScreen` | 展示当前结构化笔记卡片 | `topic`、`summary`、`citations`、`review.masteryScore` | 中 | 后续如有多笔记库，再扩展列表数据。 |
| `NoteDetailScreen` | 展示结构化笔记和引用回链 | `notes[].id`、`notes[].title`、`notes[].content`、`notes[].citationIds`、`notes[].level`、`notes[].parentId`、`sources[].id`、`sources[].title`、`sources[].text`、`sources[].page`、`sources[].chunkId`、`sources[].sourceRef` | 高 | 第一阶段核心关系是 `notes[].citationIds -> sources[].id`。 |
| `MindMapScreen` | 横屏导图演示与节点详情 | `mindMap.nodes[].id`、`label`、`desc`、`detail`、`x`、`y`、`fill`、`line`、`mindMap.edges[].from`、`to` | 中 | 若后端不会布局，前端需要后续补自动布局。 |
| `ReviewScreen` | 展示掌握度、复习题、薄弱点、建议 | `review.masteryScore`、`review.questions[]`、`review.questions[].relatedNoteId`、`review.weakPoints[]`、`review.recommendations[]` | 高 | `masteryScore` 建议为 0-100，前端会兜底限制。 |

## 后端最小可用返回

第二周离线 pipeline 至少应返回以下字段，前端即可展示完整主链路：

```json
{
  "topic": "主题",
  "summary": "摘要",
  "notes": [
    {
      "id": "definition",
      "title": "一、核心概念",
      "content": "结构化笔记正文",
      "citationIds": ["1"]
    }
  ],
  "sources": [
    {
      "id": "1",
      "title": "来源片段 1",
      "text": "原文片段"
    }
  ],
  "citations": [
    {
      "id": "1",
      "noteId": "definition",
      "sourceId": "1"
    }
  ],
  "review": {
    "masteryScore": 72,
    "questions": [],
    "weakPoints": [],
    "recommendations": []
  }
}
```

## 与 B 对齐的问题

| 问题 | 建议口径 |
|---|---|
| 后端是否直接返回 `AgentResult`，还是包一层 `data`？ | 优先直接返回 `AgentResult`；前端暂时兼容 `{ data: {...} }`。 |
| `citations` 和 `sources` 谁是引用回链主关系？ | 页面主用 `notes[].citationIds -> sources[].id`；`citations[]` 用于统计和审计。 |
| PDF/PPT 手动抽文本时如何标记？ | 在 `sourceMeta` 或后端日志记录兜底方式，前端不展示为正式文件解析成功。 |
| 真实 JSON 空数组是否回退 demo？ | 不回退。空数组视为后端有意返回，页面显示空状态，避免误判接口完整。 |
| 错误响应怎么返回？ | 使用 `{ code, message, detail }`，前端优先展示 `message`。 |

## 与 D 对齐的问题

- 演示样例需要能看懂：`topic` 和 `summary` 不宜过长。
- 引用片段需要可核验：`sources[].text` 应保留足够上下文。
- 复习题不要明显像占位：至少 1-2 道题要有解释。
- 录屏时优先展示一条“笔记 -> 引用 -> 复习建议”的闭环路径。
- 若 PDF/PPT 解析是手工兜底，需要在测试记录中写清楚。

## 当前前端已完成

- `normalizeAgentResult` 已提供默认值和类型归一化。
- 页面已统一消费 `AgentResult`，不直接消费模型原文。
- API 调用集中在 `src/features/ai/agentApi.js` 和 `src/services/apiClient.js`。
- Demo/API 双轨保留，API 失败会回退演示数据并展示提示。
- Result、NoteDetail、MindMap、Review 页面已加固空状态和缺字段提示。
- 前端已兼容 Prompt 常见字段别名，例如 `node_id`、`source_refs`、`quiz`、`question_id`、`related_note_id`、`mindmap`。
- Result 页已能展示 `keywords`、`outline`、`warnings/errors`。
- NoteDetail 页已能根据 `notes[].level` 做层级缩进，并在引用浮层展示 page/chunk/sourceRef。
- Review 页已能展示题型和 `relatedNoteId`。

## 后续建议

- 第 3 周：拿 3 个离线 pipeline 输出 JSON 跑前端渲染预检，记录字段缺口。
- 第 3 周：确定 `citation` 是否需要页码、段落序号、字符范围等定位字段。
- 第 4 周：接入真实 API 前，保留一份公开样例返回 JSON 作为联调基准。
