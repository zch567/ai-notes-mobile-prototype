# Learning Unit 前端适配设计

## 目标

在 `feature/backend-learning-unit-rag-upgrade` 的后端升级基础上，让前端完整保留并展示语义化笔记和带类型的思维导图关系，同时兼容旧版 `AgentResult`。

本次范围包括：

- 归一化 `notes[].summary`、`keyPoints`、`examples`、`relations`、`blocks`、`sourceRefs`。
- 归一化顶层 `reportPlan`。
- 归一化思维导图节点的 `sourceRefs`，以及边的 `type`、`label`、`reason`、`confidence`、`sourceRefs`。
- 在笔记详情页渐进展示摘要、知识点和结构块。
- 在思维导图画布上展示关系类型短标签，并在节点详情区域补充相关关系信息。
- 更新 `docs/agent-result-contract.md`。
- 修复后端升级造成的两项旧测试断言。

不在本次范围内：

- 不改变后端生成算法。
- 不合入 `main` 新增的测试资料。
- 不重做笔记详情页或思维导图整体视觉设计。
- 不新增编辑语义块的复杂交互；现有正文编辑仍只更新 `title` 和 `content`。

## 数据适配

`normalizeAgentResult` 继续作为页面唯一的数据入口。

笔记归一化结果新增：

```text
summary: string
keyPoints: string[]
examples: object[]
relations: object[]
blocks: NoteBlock[]
sourceRefs: string[]
```

`citationIds` 仍表示可点击引用，并继续兼容 `source_refs`、`sourceRefs` 和 `refs`。`sourceRefs` 单独保留后端原始证据关联，避免语义字段在前端被丢弃。

结构块采用宽松可扩展模型，保留未知字段，并归一化常用字段：

```text
type, title, text, items, structuredItems
```

顶层新增可选 `reportPlan`，沿用 outline 项的 `id/title/brief/refs` 结构。

思维导图边新增：

```text
type, label, reason, confidence, sourceRefs
```

缺失新字段时统一回退为空字符串、空数组或默认关系类型，确保旧结果正常渲染。

## 笔记详情展示

现有笔记章节布局保持不变，每个章节按有值才显示的方式加入：

1. 摘要：简短高亮区域。
2. 核心知识点：紧凑列表。
3. 结构块：根据 `type` 显示标题、正文、普通列表或父子结构列表。
4. 正文和引用：保留现有可编辑正文及引用浮层。

为避免 `contentEditable` 修改结构化展示内容，新增区域设置为不可编辑；用户编辑仍作用于标题和正文。旧结果没有新字段时，页面外观与当前版本基本一致。

## 思维导图展示

`createPresentableMindMap` 必须保留边的扩展字段，不再压缩为只有 `from/to`。

画布在每条有效边的中点附近显示短标签，优先使用 `edge.label`，其次使用关系类型的中文映射。标签使用轻量胶囊样式，避免遮挡节点。

选中节点后，详情区域展示与该节点相连的关系摘要，包括方向、标签和原因。没有扩展关系字段的旧边只显示基础连线，不额外制造说明。

用户新增子节点或同级节点时，创建默认 `hierarchy` 关系；隐藏分支等现有操作保持兼容。

## 契约文档

更新 `docs/agent-result-contract.md`，明确：

- 新增笔记字段和结构块格式。
- `reportPlan` 的用途。
- 思维导图边的关系类型与扩展字段。
- snake_case/camelCase 别名规则。
- 新字段均为可选扩展，旧版最小返回结构继续有效。

## 测试与验收

后端：

- 更新思维导图转换测试，验证扩展边字段而非旧版精确对象。
- 更新路径穿越测试，断言 `BadRequestError`。
- 后端测试应达到全部通过，允许原有集成测试跳过。

前端：

- 增加基于 Node 内置测试运行器的归一化测试，不引入第三方测试框架。
- 测试新字段保留、字段别名、结构块和思维导图边扩展字段。
- `npm run build` 必须通过。

人工检查：

- 新版笔记能显示摘要、知识点和结构块。
- 旧版只有 `title/content/citationIds` 的笔记仍能正常显示。
- 导图边标签可见，选中节点能看到关系说明。
- 现有引用点击、正文编辑和导图编辑操作不受影响。
