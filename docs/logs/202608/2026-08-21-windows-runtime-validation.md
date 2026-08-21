# Windows 运行环境与核心链路真机验证

> 记录日期：2026-08-21（Asia/Shanghai）
>
> 计划：[Windows 桌面版 MVP](../../plan/in-progress/2026-08-20-windows-mvp.md)、[本地与 API 四层 OCR 分流](../../plan/in-progress/2026-08-20-tiered-ocr-routing.md)

## 本次边界

在 Windows 11 x64 真机从缺少项目环境开始安装 Python 和依赖，执行源码安装入口、离线套件、桌面宿主与设置窗口检查，并用非敏感固定文本和本地生成图片验证真实 Google 翻译、PP-OCRv6 tiny、本机 LLM Token Router 文本翻译、API 高级 OCR 与 OCR 后翻译。真实区域截屏、热键实际触发和剪贴板验收只在桌面可交互且应用控制获准时继续；外部服务失败不伪造成功。

## 环境与修复

- 系统为 Windows NT 10.0.26200.0、AMD64；通过 `winget` 安装用户级 Python 3.13.15 x64，并由仓库脚本创建 `D:\projects\translate\.venv`。基础、开发与 `local-ocr` 可选依赖均安装在该项目环境中，没有使用 MSYS2 Python 3.11.9 代替。
- `scripts/install-windows.ps1` 首次在 Windows PowerShell 5.1 解析失败；根因是包含中文字符串的 UTF-8 文件没有 BOM，被本地代码页误读后破坏引号边界。脚本改为带 BOM 的 UTF-8，并增加字节级安装合同测试；重新执行后成功创建环境、安装依赖和启动托盘 App。
- 原有配置路径测试把 macOS 用户目录写死，macOS 菜单栏、AppKit 浮窗和截图测试也未声明平台条件。测试已固定目标平台或使用假 AppKit 常量；只有必须加载真实 PyObjC 的两项在 Windows 跳过，Windows 完整套件可以稳定收集和执行。
- PaddleOCR 3.7.0 / PaddlePaddle 3.3.0 在 Windows CPU 默认 oneDNN 路径预测时抛出 `ConvertPirAttribute2RuntimeAttribute` 未实现错误。适配器现在只在 Windows 传入 `enable_mkldnn=False`，使用普通 Paddle CPU 后端；macOS 不覆盖上游默认，并由双平台参数测试守住边界。
- 本机 `llm-token-router` 在 `127.0.0.1:8000` 提供 OpenAI 兼容 Chat Completions。项目原 API 高级客户端把 Unlimited-OCR 私有参数发送给所有模型，通用视觉模型虽能识别测试图，却会附加说明和 Markdown；客户端现仅对 `Unlimited-OCR` 保留旧合同，其它模型使用标准图片消息和纯文本 OCR 提示。

## 验证结果

- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-windows.ps1` 成功；托盘宿主的命令行指向项目 `.venv\Scripts\pythonw.exe` 与 `windows\launcher.pyw`。第二实例返回 `AI Translate is already running` 和退出码 1。
- Windows 设置窗口的翻译、OCR、语言与热键三页完成真机显示核对；当前静态配置为 Google 内置翻译、`OCR_ENGINE=auto`、PP-OCRv6 tiny、三组默认热键。密钥字段未输出明文。
- `ai-translate text "Windows desktop validation: the translation path is working."` 调用真实 Google 网页翻译源并以退出码 0 返回中文。
- `paddle.utils.run_check()` 确认 PaddlePaddle 3.3.0 在 1 个 CPU 上可运行。PP-OCRv6 tiny 检测与识别模型已下载到当前用户的 PaddleX 官方缓存；修复后的正式 `ocr --image` 在 3.363 秒内完整识别 `WINDOWS OCR VALIDATION`、`Hello 2026` 和 `中文识别测试`。
- 纯英文测试图经正式 `ocr-translate --image` 先走本地 PaddleOCR，再调用真实 Google 网页翻译源，3.869 秒返回“敏捷的棕色狐狸跳过了懒狗”，退出码 0。
- Router 健康检查返回 200；15 条已启用模型路由均显示可用。无敏感短句的直接 Chat Completions 由 Router 成功选路并返回中文；合成两行图片由视觉模型准确返回 `ROUTER OCR 2026` 与 `Local vision test`。
- 项目 `.env` 已配置为翻译使用 Router 的低延迟文本模型和 120 秒超时，API 高级 OCR 使用已验证的视觉模型；两个客户端地址独立填写，密钥均留空且 `config-check` 只显示 `unset`。正式 `text`、强制 `OCR_ENGINE=model` 的 `ocr` 和 `ocr-translate` 均以退出码 0 成功，最终 OCR 后翻译在 11.006 秒返回“敏捷的棕色狐狸 / 跳过了懒狗。”。使用 `auto` 文本模型与原 30 秒边界的首次组合测试曾真实返回 `timeout`，未把失败计为通过。
- 托盘宿主已停止旧的两个项目 `pythonw` 进程并从项目 `.venv` 隐藏重启；LLM Token Router 与其它 Python 服务未被停止。重启后同会话对 `Alt+E`、`Alt+W`、`Alt+Q` 的重复注册均返回 Windows 1409，证明三组组合已被宿主持有。
- OCR.space API 普通层使用官方公共 `helloworld` 测试 key 和两张两行合成图先后发起两次真实 Engine 2 请求，服务均返回 HTTP 503；该 key 没有写入 `.env`，本次只证明请求到达外部服务，未形成成功识别证据，第二次后停止重试。
- Windows 定向离线测试 70 项通过；新增 Router 视觉请求合同测试后，最终完整离线套件为 `245 passed, 2 skipped`，两项跳过均要求真实 PyObjC/macOS 环境。`pip check` 返回 `No broken requirements found`，`git diff --check` 通过。

## 限制与剩余工作

- 桌面设置页验证完成后机器曾进入 Windows 锁屏；本轮只读探针恢复为交互桌面后，应用控制又在激活测试窗口前等待授权超时，未发送任何键盘或文字。因此仍没有完成真实区域圈选/截屏、热键实际触发、剪贴板恢复/UIPI、多屏 DPI、托盘菜单、输入窗口结果展示、实时停止和 Paddle 桌面首次提醒。
- API 高级 OCR 已成功真测；OCR.space API 普通层仍因公共测试请求 HTTP 503 而未成功。不能把 Router/Paddle 成功表述为四层上游全部验收。
- 本次没有生成发布包、签名或部署。Windows 两个相关计划继续保留在 `in-progress/`，直到剩余交互桌面与 API 条件得到验证。
