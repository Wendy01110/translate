# 设置运行时复用与请求边界优化记录

> 日期：2026-09-22（Asia/Shanghai）

## 实际改动

- macOS 与 Windows 桌面组合改由 DesktopRuntime 保存翻译客户端、OCR 组合及业务用例。设置未变，或仅修改语言、热键、模型候选列表时复用实例；翻译请求配置变化只替换翻译侧，OCR 配置变化才替换 OCR 侧。普通翻译和 OCR 后翻译复用同一个翻译客户端，已加载 Paddle 不再因无关设置应用而丢失。设置应用仍会停止正在运行的实时 OCR，会话需重新开启。
- core 增加共享的 8000 字符翻译输入上限，用例与全部翻译客户端共同执行。超限不调用翻译端口或 HTTP；OCR 后翻译保留原文并返回 partial，不自动拆分、截断或补试。Google 内置源在长中文经 URL 编码后可能先达到 HTTP 客户端限制，现返回 request_url_too_long，避免未捕获的 InvalidURL 异常。
- HTTP 适配在流式读取最终响应时检查解码后字节，最多允许 2,000,000 字节进入 JSON/文本解析；超限关闭响应流并返回 response_too_large，OCR.space 保留 ocr_response_too_large。HTTP 错误直接保留状态码，不读取或展示上游正文。统一处理覆盖七种翻译来源、Bing 会话页和 API 两层 OCR。
- 沿用现有架构、依赖、配置加载路径与错误展示边界；没有新增环境变量、结果字段或公共端口。保留此前浮窗失焦 WIP 和实时翻译可靠性优化。

## 验证

- 使用项目 .venv 的 Python 3.13.14；运行 DesktopRuntime、app、composition、features 与受影响的 HTTP 客户端定向测试，110 项通过。
- 执行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider`，完整离线套件 357 项通过，1.63 秒；本轮新增 42 个用例（含参数化）。
- Fake Paddle pipeline 覆盖无关配置应用后仅初始化一次、翻译配置变化保留 OCR、OCR 档位变化保留翻译侧、首次提示次数及设置保存语言同步。
- Fake 端口与 HTTP mock 覆盖 8000/8001 字符边界、超限 OCR 原文保留与不补试、Google 长中文 URL、忽略虚假 Content-Length 后仍中止超大响应、错误响应正文零读取、流关闭、压缩响应按解码长度拒绝及恰好 2,000,000 字节接受。
- 完整套件包含架构、配置、CLI、两端界面和文档检查；git diff --check 通过。上述验证均未使用真实模型、图片、选区或剪贴板。

## 文档与状态

已同步根 README、架构设计、配置设计、Windows 桌面设计、文档入口、计划索引及四层 OCR 计划中的设置行为说明；[本任务计划](../../plan/completed/2026-09-22-runtime-reuse-and-request-bounds.md) 已移至 completed。没有关联开放 Issue；原四层 OCR 计划仅等待 macOS 桌面首次提醒复验，继续保持进行中。配置变量和加载合同未变，.env.example 与 config-check 字段无需修改。

## 验证边界

本轮证明客户端复用次数和输入/解析边界，不提供真实时延收益或桌面交互验收。字节上限约束进入解析的最终响应，不等于包含 HTTP 解压等环节在内的进程内存上限。未调用真实上游、读取或修改真实 .env、下载或初始化真实 OCR 模型、截屏、访问选区或剪贴板，也未重启/构建 App、提交或发布。
