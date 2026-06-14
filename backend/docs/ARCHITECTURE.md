# Backend Architecture

## 目标

`backend` 是 Week1、Week2、Week3 能力的统一项目级后端。它的目标不是保存历史周目录，而是把可复用能力沉淀成清晰模块：

- Week1：多场景 Agent prompt 与模块编排。
- Week2：蓝心 Provider、OCR/Office OCR sidecar 输入。
- Week3：RAG 分块、召回、引用定位、AgentResult 修复与校验。

## 目录职责

```text
backend/
  app/
    main.py              # FastAPI 路由
    service.py           # Pipeline 编排与持久化
    contracts.py         # AgentResult/请求模型契约边界
    normalization.py     # 输出归一化与契约校验
    agents/              # Week1 模块化 Agent 编排
    prompts/             # Week1 prompt registry
    providers/           # Week2 模型 Provider：lanxin
    parsers/             # Week2 OCR/Office sidecar 合并解析
    rag/                 # Week3 parser/chunker/retriever/grounding
  docs/
  scripts/
  tests/
```

## 主流程

```text
POST /api/agent/run
  -> AgentService._resolve_input
  -> M1 parse/chunk
       app/rag/parsing.py + app/rag/chunking.py
       or app/parsers/sidecar_parser.py
  -> hybrid:
       app/agents/orchestrator.py
         M2 topic/summary
         M3 structured notes
         M4 mindmap
         M6 review
       app/rag/grounding.py
         M5 citation grounding
  -> rag-only:
       app/rag/result_builder.py
  -> app/normalization.py
  -> runtime/{resultId}/result.json + chunks.json
```

## 为什么 M5 用程序化 Grounding

Week1 prompt 中包含 M5 引用回链，但引用定位对可靠性要求高。当前实现让模型生成学习内容，让后端程序负责引用：

- `HybridRetriever` 根据笔记和题目检索最相关 chunk。
- `ground_result` 重建 `sources`、`citations` 和 citationIds。
- `validate_result` 输出覆盖率、来源有效率、quote 命中率等诊断指标。

这样即使蓝心模型输出缺少引用或引用格式不稳定，最终 `AgentResult` 仍能满足前端契约。

## Provider 策略

Provider 接口支持两类调用：

- `generate_json()`：保留 Week2 单次生成兼容能力。
- `generate_module_json()`：当前 `hybrid` 主路径使用，按 M2/M3/M4/M6/M7 分模块调用。

`lanxin` Provider 调用 OpenAI-compatible chat completions 接口。模型调用失败会直接抛错，避免静默产生非真实模型结果。

## API 契约

`/api/agent/run` 返回 `AgentResult/1.0` 核心字段：

```text
id, topic, summary, agentStages, sources, notes, citations, mindMap, review
```

允许额外扩展字段，例如：

```text
keywords, outline, citationDiagnostics, warnings, _meta
```

## 后续迭代方向

1. 输入层：增加 multipart 文件上传，避免调用方传服务器本地路径。
2. 存储层：将 `runtime/` 文件存储替换为数据库与对象存储。
3. 执行层：将同步 API 改造成 job 队列，适配大文件和慢模型。
4. 检索层：在 `app/rag/retrieval.py` 内替换为 BM25 + embedding + reranker，不改变上层契约。
5. Prompt 层：为 `PromptRegistry` 增加版本号、A/B 配置和灰度切换。
