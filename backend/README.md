# AI Notes Unified Backend

这是一个可独立交付、可持续迭代的后端项目。当前 `backend` 已将 Week1、Week2、Week3 的核心能力整合到统一 FastAPI 框架中，不再依赖外部 `week 02` 或 `week3` 目录。

## 已整合能力

| 来源 | 后端落点 | 说明 |
|---|---|---|
| Week1 Agent 场景 | `app/prompts/`、`app/agents/` | 接入 M1-M7 模块化流程：解析清洗、主题摘要、结构化笔记、思维导图、引用定位、复习题、笔记问答。 |
| Week2 模型调用 | `app/providers/`、`app/provider_config.py` | 仅保留 `lanxin` Provider。模型调用失败会直接返回错误，不再降级到 mock。 |
| Week2 OCR/Office sidecar | `app/parsers/` | 支持通过 `ocrTextDir`、`officeOcrDir` 合并已有 OCR/Office OCR 文本。 |
| Week3 RAG | `app/rag/` | 支持结构化解析、分块、Hybrid Retriever、Citation Grounding、AgentResult 构建和校验。 |
| 前端契约 | `app/contracts.py`、`app/normalization.py` | `/api/agent/run` 返回 `AgentResult/1.0`，兼容 `agent-result-contract.md` 核心字段。 |

## Pipeline

### `hybrid` 默认流程

```text
M1 app/rag or app/parsers
  -> M2 topic/summary via Provider
  -> M3 structured notes via Provider
  -> M4 mind map via Provider
  -> M5 programmatic Citation Grounding via app/rag
  -> M6 review questions via Provider
  -> AgentResult normalization + validation
```

说明：M5 不采用模型自由生成引用，而是由后端检索与 Grounding 程序重建 `sources`、`citations`、`notes[].citationIds` 和 `review.questions[].citationIds`，降低幻觉风险。

### `rag-only`

确定性 RAG 结构化生成，不调用大模型。它只用于后端解析/引用链路测试，不作为前端生成兜底。

### M7 笔记问答

`POST /api/agent/chat` 使用已保存的 `resultId` 和 chunks 做检索增强问答。它对应 Week1 的 M7 场景，不改变 `/api/agent/run` 的主返回契约。

## 启动

```powershell
cd D:\AIGC\backend
python -m pip install -r requirements.txt
python run.py
```

默认监听：

```text
http://127.0.0.1:8000
```

健康检查：

```powershell
curl http://127.0.0.1:8000/health
```

## 蓝心配置

可在环境变量或 `D:\AIGC\api` 中配置：

```text
MODEL_PROVIDER=lanxin
LANXIN_API_KEY=your-key
LANXIN_BASE_URL=https://api-ai.vivo.com.cn/v1
LANXIN_MODEL=Doubao-Seed-2.0-mini
MODEL_TIMEOUT_MS=90
LANXIN_RETRIES=1
```

交付时不要把 `D:\AIGC\api` 打包给队友；让队友自行配置 Key。

## API

```text
GET  /health
GET  /api/providers/status
POST /api/agent/run
GET  /api/agent/result/{result_id}
POST /api/agent/chat
POST /api/agent/validate
POST /api/rag/query
```

运行 Agent：

```json
{
  "filePath": "D:/AIGC/ai-notes-mobile-prototype/ai-notes-mobile-prototype/test_set/text/Transformer介绍.docx",
  "pipeline": "hybrid",
  "provider": "lanxin",
  "strictProvider": true,
  "topK": 2
}
```

直接提交文本：

```json
{
  "sourceText": "# RAG\n\nRAG 使用检索结果约束生成，并提供可回链引用。",
  "pipeline": "hybrid",
  "provider": "lanxin"
}
```

基于结果继续问答：

```json
{
  "resultId": "agent-xxxxxx",
  "question": "RAG 如何降低生成幻觉？",
  "provider": "lanxin",
  "topK": 3
}
```

## OCR sidecar

如果 Week2 已经产出 OCR 或 Office OCR sidecar 文本，可直接传入：

```json
{
  "filePath": "D:/AIGC/test/input.pdf",
  "pipeline": "hybrid",
  "ocrTextDir": "D:/AIGC/ocr_outputs/text"
}
```

## 测试

```powershell
cd D:\AIGC\backend
$env:PYTHONDONTWRITEBYTECODE="1"
python -m pytest -q -p no:cacheprovider
```

蓝心真实集成测试默认跳过，避免日常测试消耗额度：

```powershell
$env:RUN_LANXIN_INTEGRATION="1"
python -m pytest tests\test_lanxin_integration.py -q
```

## 蓝心与离线 RAG 对比

```powershell
cd D:\AIGC\backend
python scripts\compare_rag.py
```

输出目录：

```text
backend/evaluation_outputs/lanxin_vs_offline/
```

## 项目规则

- 对外契约只在 `app/contracts.py` 定义，新增字段保持可选扩展。
- Provider、Prompt、Retriever、Grounding 分层独立，后续可分别替换。
- `runtime/` 与 `evaluation_outputs/` 是运行产物，不建议作为代码交付内容。
- 不要把根目录 `api` 或任何真实密钥放入交付包。
