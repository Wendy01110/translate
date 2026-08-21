# Windows 运行环境与核心链路真机验证

> 记录日期：2026-08-21（Asia/Shanghai）
>
> 计划：[Windows 桌面版 MVP](../../plan/in-progress/2026-08-20-windows-mvp.md)、[本地与 API 四层 OCR 分流](../../plan/in-progress/2026-08-20-tiered-ocr-routing.md)、[屏幕实时 OCR 翻译](../../plan/completed/2026-08-20-live-screen-ocr.md)

## 本次边界

在 Windows 11 x64 真机从缺少项目环境开始安装 Python 和依赖，执行源码安装入口、离线套件、桌面宿主与设置窗口检查，并用非敏感固定文本和本地生成图片验证真实 Google 翻译、PP-OCRv6 tiny、本机 LLM Token Router、OCR.space、划词剪贴板、主/副屏固定区域截屏和实时连续帧。真实桌面操作只在应用控制获准且目标窗口可安全定位时继续；外部服务或工具边界不伪造成功。

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
- OCR.space API 普通层使用官方公共 `helloworld` 测试 key 的前两次 Engine 2 请求均返回 HTTP 503，第二次后停止重试；后续单独复试一张只含 `OCR SPACE WINDOWS 2026` 的内存 PNG，1.969 秒准确返回原文。公共 key 和图片均未写入项目或 `.env`，API 普通层现已有成功真测。
- 在新建的无敏感内容记事本页真实触发 `Alt+E`，浮窗正确读取三行选区并由 Router 返回中文。第二轮先把交互桌面剪贴板设为与选区不同的哨兵：浮窗原文仍来自选区，处理结束后哨兵保持不变，守护进程再从内存恢复原剪贴板且从未输出其内容，证明普通窗口的模拟复制与恢复路径成功。
- `Alt+W` 与 `Alt+Q` 均真实打开跨虚拟桌面的半透明圈选层；圈选期间再次按 `Alt+Q` 后界面立即恢复，证明取消路径生效。圈选层是无标题 `overrideredirect` 窗口，Computer Use 能观察却按安全规则拒绝向非目标窗口发送拖拽，因此没有执行替代性的系统级鼠标注入。
- 主屏固定矩形截出 11,180 字节 PNG，PP-OCRv6 tiny 精确返回三行固定文本，首次加载回调触发一次，Router 翻译成功，全链路 74.972 秒。当前机器有两块显示器，虚拟桌面是 `-1080,-258,3640,1920`；副屏负坐标客户区 `-1042,-169,884,181`、DPI 96 截出 4,203 字节并准确识别 `SECOND MONITOR OCR 2026`，临时置顶测试窗随后销毁。
- 固定区域实时验收复用同一 Paddle/Router 实例：首帧 98.089 秒成功，相同截图 0.08 秒命中 `skip_frame`，把第三行改成 `Live OCR frame two 2026.` 后 79.043 秒返回更新译文；停止动作返回 `stopped`，截图计数保持 3→3。
- Windows 定向离线测试 70 项通过；合入 macOS 双屏圈选回归后，最终完整离线套件为 `247 passed, 2 skipped`，两项跳过均要求真实 PyObjC/macOS 环境。`pip check` 返回 `No broken requirements found`，`git diff --check` 通过。

## 限制与剩余工作

- 普通窗口划词、固定矩形截屏、双屏负坐标/DPI、API 两层和实时核心停止已经成功真测；管理员窗口 UIPI 降级尚未验证。
- 当前安全应用控制不能为无标题全屏圈选层取得目标句柄，因此实际鼠标拖拽、拖拽后的普通/实时浮窗、字幕条关闭、托盘菜单和输入窗口结果展示仍未验收。Paddle 首次加载回调已在真实初始化前各触发一次，但桌面提醒本身仍未视觉确认。
- 本次没有生成发布包、签名或部署。三项相关计划继续保留在 `in-progress/`，直到剩余人工交互和 macOS 实时复验完成。
