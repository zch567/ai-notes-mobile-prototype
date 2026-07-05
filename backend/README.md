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

推荐把真实蓝心 Key 放在项目目录外，例如 `D:\AIGC\api`，然后在 `backend/.env` 中只保存密钥文件路径。这样软件打包时不会把 Key 复制进源码目录、前端 bundle 或交付包。

```text
MODEL_PROVIDER=lanxin
BACKEND_SECRETS_FILE=D:\AIGC\api
LANXIN_BASE_URL=https://api-ai.vivo.com.cn/v1
LANXIN_MODEL=Doubao-Seed-2.0-mini
MODEL_TIMEOUT_MS=90
LANXIN_RETRIES=1
```

`D:\AIGC\api` 的内容使用 `.env` 格式：

```text
LANXIN_API_KEY=your-key
```

交付时不要提交 `.env`、`api` 或任何真实密钥；让队友在自己的电脑上配置 Key。前端构建命令已接入 `scripts/check_no_secret_leak.mjs`，会扫描 `dist` / `dist-webview` 并在发现 Key 内容、`.env` 或 `api` 文件进入产物时失败。

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
POST /api/lanxin/query-rewrite
POST /api/lanxin/embedding
POST /api/lanxin/rerank
POST /api/lanxin/translation
```

推荐前端和 demo 使用文件上传接口，不需要关心后端电脑上的文件路径：

```powershell
curl -X POST http://127.0.0.1:8000/api/agent/run-file `
  -F "file=@C:/path/to/your/sample.pdf" `
  -F "pipeline=hybrid" `
  -F "sourceTitle=课程资料"
```

上传支持 `.txt`、`.md`、`.markdown`、`.doc`、`.docx`、`.pdf` 和 `.pptx`。其中 DOCX 由后端直接解析；旧版 DOC 仅在 Windows 上支持，后端会调用本机 Microsoft Word 在 `runtime/_converted` 中转换为临时 DOCX。若未安装 Word 或转换失败，请将文件另存为 DOCX 后重试。

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

## Lanxin OCR

后端也支持直接调用蓝心通用 OCR。默认关闭，避免普通解析消耗外部额度；需要在请求中显式传入 `enableOcr: true`。

```json
{
  "filePath": "C:/path/to/your/input.pptx",
  "pipeline": "rag-only",
  "enableOcr": true
}
```

配置项可写入 `BACKEND_SECRETS_FILE` 指向的文件或环境变量：

```text
LANXIN_OCR_APP_ID=your_AppId
LANXIN_OCR_APP_KEY=your_AppKey
LANXIN_OCR_BUSINESS_ID=aigcyour_AppId
LANXIN_OCR_URL=http://api-ai.vivo.com.cn/ocr/general_recognition
```

PPTX 会抽取幻灯片中的嵌入图片进行 OCR，并保留 `slide`、图片框位置和 OCR 返回的文字区域；PDF 会抽取页面内嵌图片进行 OCR，并保留 `page` 和 OCR 返回的文字区域。生成结果仍使用原有 chunk/citation 回链，新增区域信息位于 `sources[].ocrRegions` 和持久化的 `chunks.json` 中。

## LLM quality review

生成后可显式开启大模型质量审查。后端会先计算本地 `qualityDiagnostics`；当分数低于阈值时，再调用模型从用户学习效果角度审查 NOTE，并用通用语义规则重写笔记。重写不会新增事实或来源，引用仍由后端重新 grounding。

质量提升会形成最多三轮闭环：每轮执行“语义审查 → 定向修复 → 引用回链 → 重新评分”。如果某一轮达到阈值，立即采用该版本；如果三轮后仍未达标，后端会自动采用得分最高的版本，并在 `_meta.qualityReview` 中记录每轮分数和最终选择。

定向修复会根据低分维度选择回退层级：

- `M2`：主题、概要、关键词和核心问题规划不足时重跑。
- `M3`：NOTE 数量不足、要点弱、概要拼接、内容重复或层级混乱时重跑。
- `M4`：NOTE 结构变化后重建思维导图。
- `M5`：每轮都由后端重新 grounding；引用覆盖、quote 命中或原文摘录不足时会提高检索范围并补强回链。
- `M6`：复习题、薄弱点或学习建议不足时重跑。

这些动作由质量维度和语义审查共同驱动，提示词明确要求不要迎合评分字段，不针对单一样本文本硬编码。

```json
{
  "filePath": "C:/path/to/your/input.pdf",
  "pipeline": "hybrid",
  "provider": "lanxin",
  "enableQualityReview": true,
  "qualityReviewThreshold": 85
}
```

该机制不会按具体评分项做硬编码补丁；审查提示词明确要求关注理解、复习、答题和查证价值，避免为了通过某个指标而牺牲泛化能力。

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
- 真实蓝心 Key 应放在项目外部路径，并通过 `BACKEND_SECRETS_FILE` 指向。
