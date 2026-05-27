# AgentResult 数据契约

前端页面统一消费 `AgentResult`。后端可以返回近似结构，但进入页面前必须经过 `normalizeAgentResult`。

## 顶层结构

```json
{
  "id": "demo-logistic-regression",
  "topic": "Logistic Regression",
  "summary": "主题摘要",
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

缺失字段会由 `normalizeAgentResult` 用演示数据或默认值兜底。

