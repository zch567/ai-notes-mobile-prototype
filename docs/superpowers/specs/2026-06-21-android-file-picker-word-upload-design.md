# Android 文件选择与 Word 上传设计

## 目标

修复 Android WebView 中点击“选择文件”无反应的问题，并让 AI 生成页面支持上传 `.doc` 和 `.docx` 文件。

本次改动覆盖 Android 壳、前端输入类型、后端上传白名单、旧版 DOC 转换和接口文档。现有 PDF、PPTX、文本输入与后端运行方式保持不变。

## Android 文件选择

`MainActivity` 为 WebView 配置自定义 `WebChromeClient`，实现 `onShowFileChooser`：

- 使用 `WebChromeClient.FileChooserParams.createIntent()` 创建系统文件选择 Intent。
- 使用 Activity Result API 的兼容写法，通过 request code 启动选择器。
- 保存当前 `ValueCallback<Uri[]>`，在选择完成或取消时回传结果。
- 新请求到来时先取消旧回调，避免回调泄漏。
- Activity 销毁时向未完成回调返回 `null`。
- 若系统没有可处理的文件选择器，则返回 `false`，并清理回调。

文件通过 `content://` URI 暴露给 WebView，网页中的 `<input type="file">` 会得到标准 `File` 对象，不需要存储权限。Android Manifest 不新增媒体或外部存储权限。

## 前端输入类型

AI 输入页增加 `word` 类型，与 `text/pdf/pptx` 并列：

```text
text  -> 文本
pdf   -> PDF
pptx  -> PPTX
word  -> Word
```

Word 类型的文件输入接受：

```text
.doc
.docx
application/msword
application/vnd.openxmlformats-officedocument.wordprocessingml.document
```

文件匹配逻辑允许 `.doc` 和 `.docx`。选择文件后继续使用现有 multipart `/api/agent/run-file` 链路，不修改 `agentApi.js`。

## 后端 DOCX 与 DOC 处理

DOCX 继续使用现有 ZIP/XML 原生解析。

DOC 上传后执行以下流程：

1. 上传文件保存到 `backend/runtime/_uploads`。
2. 在解析入口识别 `.doc`。
3. 仅在 Windows 上通过 Microsoft Word COM 自动化转换为临时 `.docx`。
4. 转换结果放入 `backend/runtime/_converted`，使用稳定且无冲突的文件名。
5. 调用现有 `_parse_docx`，生成的 `RawBlock.file_name` 和来源类型仍标识原始 DOC 文件。
6. 转换文件属于运行产物，不提交仓库。

COM 调用优先使用 `pywin32` 的 `win32com.client`。后端依赖增加 Windows 条件依赖：

```text
pywin32>=306; platform_system == "Windows"
```

Word 自动化必须：

- 后台不可见运行。
- 禁止弹出交互对话框。
- 以只读方式打开源文件。
- 在 `finally` 中关闭文档并退出 Word。
- 转换失败时删除不完整产物。

## 错误处理

以下情况返回可读的 400 错误：

- 服务运行在非 Windows 系统。
- 未安装 Microsoft Word。
- `pywin32` 不可用。
- Word 无法打开或转换 DOC。
- 转换后 DOCX 不存在或为空。

错误信息应明确建议用户将文件另存为 DOCX 后重试，不暴露内部堆栈。

## 文档与测试

更新：

- `docs/backend-api-interface.md`
- `README.md` 或后端 README 中的支持文件类型说明

后端测试：

- 上传接口接受 `.doc`。
- DOC 解析调用转换器并沿用 DOCX 解析结果。
- Word 不可用时返回明确错误。

前端验证：

- `npm test`
- `npm run build`
- `npm run build:webview`

Android 验证：

- Gradle debug 构建通过。
- 覆盖安装到 `emulator-5554`。
- 点击 PDF、PPTX、Word 的“选择文件”均能拉起 DocumentsUI。
- 取消选择不会崩溃。
- 选择 DOC/DOCX 后页面显示文件名。

后端服务继续保持运行。修改后需要重启后端进程以加载新代码，但重启完成后保持运行，不在交付时关闭。
