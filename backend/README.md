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

以下命令假设你已经在 Windows 上克隆了本仓库。不要依赖固定盘符；从仓库根目录进入 `backend` 即可。

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
copy .env.example .env
python run.py
```

`python run.py` 会先检查当前 Python 环境是否已安装 `requirements.txt` 中的依赖；缺失或版本不匹配时会自动执行 `python -m pip install -r requirements.txt`，再启动后端。

默认监听：

```text
http://0.0.0.0:8000
```

健康检查：

```powershell
curl http://127.0.0.1:8000/health
```

## 蓝心配置

推荐复制 `backend/.env.example` 为 `backend/.env` 后填写蓝心 Key。也可以在 `backend/api` 文件中配置，文件格式同 `.env`。

```text
MODEL_PROVIDER=lanxin
LANXIN_API_KEY=your-key
LANXIN_BASE_URL=https://api-ai.vivo.com.cn/v1
LANXIN_MODEL=Doubao-Seed-2.0-mini
MODEL_TIMEOUT_MS=90
LANXIN_RETRIES=1
```

交付时不要提交 `.env`、`api` 或任何真实密钥；让队友在自己的电脑上配置 Key。

## API

```text
GET  /health
GET  /api/providers/status
POST /api/agent/run
POST /api/agent/run-file
GET  /api/agent/result/{result_id}
POST /api/agent/chat
POST /api/agent/validate
POST /api/rag/query
```

推荐前端和 demo 使用文件上传接口，不需要关心后端电脑上的文件路径：

```powershell
curl -X POST http://127.0.0.1:8000/api/agent/run-file `
  -F "file=@C:/path/to/your/sample.pdf" `
  -F "pipeline=hybrid" `
  -F "sourceTitle=课程资料"
```

也可以直接提交文本：

```json
{
  "sourceText": "# RAG\n\nRAG 使用检索结果约束生成，并提供可回链引用。",
  "pipeline": "hybrid",
  "provider": "lanxin"
}
```

如果后端本机脚本要传 `filePath`，文件必须位于 `BACKEND_ALLOWED_INPUT_ROOT` 允许的目录下。默认示例使用当前 `backend` 目录；如需读取其他资料目录，请在 `.env` 中改成自己的本机目录，例如 `BACKEND_ALLOWED_INPUT_ROOT=C:/path/to/your/materials`。

```json
{
  "filePath": "C:/path/to/your/materials/material.docx",
  "pipeline": "hybrid",
  "provider": "lanxin",
  "strictProvider": true,
  "topK": 2
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
  "filePath": "C:/path/to/your/input.pdf",
  "pipeline": "hybrid",
  "ocrTextDir": "C:/path/to/your/ocr_outputs/text"
}
```

## 测试

```powershell
cd backend
.\.venv\Scripts\activate
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
cd backend
.\.venv\Scripts\activate
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
