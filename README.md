# AI 笔记移动端原型

这是一个基于 React + Vite + Tailwind CSS 的移动端前端原型，用于展示“智序知识助手”的 AI 学习闭环。

## 当前结构

```text
src/app/          应用入口、导航状态
src/components/   通用组件
src/data/         演示数据
src/features/     业务页面
src/services/     API 与运行模式
docs/             协作与接口文档
android-shell/    Android 原生 WebView 壳
```

核心数据结构是 `AgentResult`。页面统一消费归一化后的 `AgentResult`，后端字段变化优先在 `src/features/ai/agentTypes.js` 处理。

## 本地运行

```bash
npm install
npm run dev
```

默认使用演示模式。复制 `.env.example` 为 `.env` 后可切换真实 API：

```text
VITE_DEMO_MODE=false
VITE_API_BASE_URL=http://127.0.0.1:8000
```

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

`build:webview` 会使用相对资源路径，并强制使用：

```text
VITE_DEMO_MODE=true
VITE_APP_SHELL_MODE=webview
```

## Android WebView Demo

Android demo app 位于：

```text
android-shell/
```

它是一个原生 Android WebView 壳，会把 Vite 打包后的静态资源放进 APK 本地 assets，适合离线演示，不依赖后端服务。

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
- 目前 APK 保持 demo 模式，暂不接后端。
- 顶部内容在 WebView 模式下会保留状态栏安全距离。
- 思维导图详情页会请求横屏；如果设备仍为竖屏，会隐藏导图内容并提示用户切换横屏。

## Demo 本地存储

Demo 阶段没有云端数据库。前端使用 `src/services/localDemoFs.js` 在浏览器或 Android WebView 的本地存储中保存演示数据。

当前会保存：

- 当前激活的 `AgentResult`。
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
