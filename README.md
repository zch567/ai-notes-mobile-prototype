# AI 笔记移动端原型

这是一个基于 React + Vite + Tailwind CSS 的移动端前端原型，用于展示“智序知识助手”的 AI 学习闭环。

## 当前结构

```text
src/app/          应用入口、导航状态
src/components/   通用组件
src/data/         输入样例数据
src/features/     业务页面
src/services/     API 与运行模式
docs/             协作与接口文档
android-shell/    Android 原生 WebView 壳
backend/          FastAPI 真实后端，与前端同仓库记录
```

核心数据结构是 `AgentResult`。页面统一消费归一化后的 `AgentResult`，后端字段变化优先在 `src/features/ai/agentTypes.js` 处理。

## 本地运行

前端：

```bash
npm install
npm run dev
```

后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

当前版本只保留真实后端模式。复制 `.env.example` 为 `.env` 后配置 API 地址：

```text
VITE_DEMO_MODE=false
VITE_API_BASE_URL=http://127.0.0.1:8000
```

APK/WebView 包安装到手机后，可以在“我的 > 后端连接”里填写电脑局域网后端地址，例如：

```text
http://192.168.1.23:8000
```

点击“测试并启用”后，AI 生成页会调用该真实后端。

Android WebView 壳建议切换为全屏应用模式：

```text
VITE_APP_SHELL_MODE=webview
```

默认 `preview` 模式会保留桌面预览用的手机壳、圆角和居中留白；`webview` 模式会铺满 WebView，隐藏假状态栏，并为底部导航保留安全区。

## 构建

```bash
npm run build
```

WebView 专用构建：

```bash
npm run build:webview
```

`build:webview` 会使用相对资源路径，并默认使用：

```text
VITE_DEMO_MODE=false
VITE_APP_SHELL_MODE=webview
```

真实后端地址不需要写入 APK 包内；运行时在“我的”页配置即可。

## Android WebView Demo

Android demo app 位于：

```text
android-shell/
```

它是一个原生 Android WebView 壳，会把 Vite 打包后的静态资源放进 APK 本地 assets，并支持在运行时填写局域网后端地址进行真实联调。

构建 debug APK：

```powershell
cd android-shell
.\gradlew.bat assembleDebug --no-daemon
```

生成路径：

```text
android-shell/app/build/outputs/apk/debug/app-debug.apk
```

APK/AAB 是可再生成的构建产物，已经被 git 忽略；不建议提交到仓库。

Android 运行要点：

- WebView 加载本地资源：`file:///android_asset/web/index.html`。
- APK 只保留真实后端链路；在“我的 > 后端连接”测试并启用后会调用真实后端。
- Android 壳已开启 `INTERNET`、局域网 HTTP 和本地资源跨源请求能力，用于访问 `http://电脑IP:8000`。
- 顶部内容在 WebView 模式下会保留状态栏安全距离。
- 思维导图详情页会请求横屏；如果设备仍为竖屏，会隐藏导图内容并提示用户切换横屏。

## Demo 本地存储

Demo 阶段没有云端数据库。前端使用 `src/services/localDemoFs.js` 在浏览器或 Android WebView 的本地存储中保存本机数据。

当前会保存：

- 当前激活的真实后端 `AgentResult`。
- 输入页草稿，包括输入类型、文本内容和标题。
- 笔记设置，包括复习模式、引用显示和自动保存提示。
- 笔记内容修改，包括标题、章节标题和正文，会实时写回 `AgentResult.topic` 和 `AgentResult.notes`。
- 思维导图编辑，包括新增节点、同级节点、重命名和隐藏分支，会实时写回 `AgentResult.mindMap`。
- 复习进度，包括已完成题目和最近复习时间。

存储 key 统一使用 `zhixu:demo:*` 前缀。Android 包中这些数据写入 App 自己的 WebView 本地数据区，不会提交到仓库，也不会上传云端。卸载 App、清除 App 数据或清理 WebView 存储后，这些 demo 数据会丢失。

页面组件不要直接访问 `localStorage`；需要读写本地 demo 数据时，统一走 `src/services/localDemoFs.js`。

## 文档

- `docs/frontend-architecture.md`：前端模块边界。
- `docs/agent-result-contract.md`：后端返回数据契约。
- `docs/frontend-adapter-checklist.md`：第二周 C 任务前端适配清单。
- `docs/backend-api-interface.md`：前后端接口联调说明。
- `docs/collaboration-checklist.md`：多人协作检查清单。
