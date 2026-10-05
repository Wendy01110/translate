# 项目复核、异常响应修复与 Git 交付记录

> 日期：2026-10-06（Asia/Shanghai）
>
> 结果：代码复核与离线验证通过，Git 交付准备完成；macOS 首次 OCR 提醒真实验收仍待本次授权

## 当前进度与范围

Requester 要求检查项目、完成必要工作、测试、同步文档、提交并推送。首先从文档入口和四层 OCR 进行中计划核对进度，保存 67 个初始 WIP 路径的哈希，确认暂存区为空。当前主要功能已实现，四层 OCR 计划仍只缺 macOS 桌面首次加载提醒的实际显示验收；历史、工具栏、剪贴板监听和系统音频转写继续留在待进行状态，本轮没有启动新产品能力。没有关联开放 Issue，Issue 状态不适用。

本轮审阅并保留自 2026-09-08 起积累的同项目修复，包括失焦后保留工作区、设置应用时复用客户端、实时 OCR 语言/圈选会话隔离及有限补试、8000 字符翻译上限、HTTP 响应有界读取、图片/截屏/剪贴板失败归类、OCR 单次 10 页与原始图片合计 20 MiB 上限，以及 OCR.space 异常响应降级。既有完成计划和日期日志随对应实现纳入本次已授权的 Git 交付。

## 本轮新增修复

- OpenAI 兼容、官方翻译和网页翻译的 JSON 解码原先未处理 `RecursionError`，过深但仍在字节预算内的响应会逃逸为异常；API 高级 OCR 共用 OpenAI 路径，同样受影响。现于这三个具体解码边界返回既有 `invalid_json`，保持 HTTP 状态、超时、响应大小和流关闭合同。
- DeepL 官方客户端直接对响应调用 `.get()`，列表、字符串、数字或布尔顶层会抛 `AttributeError`。现先确认对象类型，其它非空类型返回既有 `empty_translation`，不保留错误正文或残缺译文。
- 新增 14 项合成 HTTP 回归，覆盖七种翻译来源、两种 API OCR 的过深 JSON 和五种 DeepL 非对象响应。网页源的普通非 JSON 文本解析继续支持 Bing HTML 会话页。
- 同步用户 README 的失败行为，并校正实时 OCR 去重与到期补试的说明；更新配置设计、文档入口、当前 OCR 计划及本轮计划。没有改变环境变量、默认值、CLI 参数、端口、版本或公共结果字段；既有 `.env.example` 的 OCR 预算注释保留。

## 实际验证

全部 Python 验证均使用当前项目 `.venv` 的 Python 3.13.14；测试使用 Fake、合成图片字节和 HTTP mock，不读取真实 `.env` 调用上游。

| 阶段 | 实际结果 |
| --- | --- |
| 当前 WIP 定向基线 | features、infrastructure、listener、overlay、CLI 与桌面运行时共 384 项通过 |
| 新增回归修复前 | 13 项失败、1 项通过；复现 8 个递归解码异常与 5 个 DeepL 类型异常，已有 OCR.space 递归错误回归通过 |
| 修复后客户端定向 | 请求边界、官方/网页/兼容翻译、OCR.space 与路由共 114 项通过 |
| 完整离线套件 | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider`：534 项通过，包含配置、版本、架构与文档验证 |
| 依赖 | `.venv/bin/python -m pip check`：未发现依赖冲突 |
| CLI 静态回读 | 当前版本 `0.1.0`、OCR 帮助 10 页/20 MiB、临时配置路径与独立就绪状态通过；三个 API key 均为 `unset`，无上游调用 |
| 差异格式 | `git diff --check` 通过 |

## 对抗复核与未验证边界

已核对修复落在外部响应适配边界，不在 listener 增加宽泛异常捕获；有效 JSON、各来源成功结果、Bing HTML、API OCR 分流与流关闭回归通过。过深 JSON 样例不足 2,000,000 字节，验证的是递归解码失败归类，不声明固定嵌套层数或进程内存上限。最终只提交已审阅的同项目实现、测试、文档和完成计划，不含真实 `.env`、临时验收脚本、原图、依赖缓存或构建产物。

已准备 `/private/tmp/ai-translate-review-20261006-native-reminder.py`：仅生成 `LOCAL OCR REMINDER CHECK 2026` 英文测试图，使用已缓存 PP-OCRv6 small，禁用网络、翻译为 Fake；由项目监听器和原生 presenter 验证普通/实时提醒。按照 `AGENTS.md` 对真实 OCR 的明确授权要求单独询问后，尚未收到本次许可，因此未执行。未读取屏幕、选区或剪贴板，未调用外部翻译/OCR，未安装依赖、下载模型、修改真实配置、重启既有 App、发布或部署；现有真实桌面和提供方验收不能由本轮离线结果更新。

## Git 交付

当前分支为 `main`，远端为 `https://github.com/Wendy01110/translate.git`。远端 `main` 读取为 `b485677c6bf86626b983be1b2b812d239667f550`，与本地 `origin/main` 一致；本地已有 `c140bfd` 和 `73dd0a1` 两个待推送提交，本次推送包含它们。默认 Git HTTP 连接首次出现 TLS 连接错误，单次命令使用 `http.version=HTTP/1.1` 后成功读取远端，不改全局配置或系统代理。提交和推送的实际结果在执行后补记。

对应 [本轮计划](../../plan/in-progress/2026-10-06-project-review-and-git-delivery.md)；原 [四层 OCR 计划](../../plan/in-progress/2026-08-20-tiered-ocr-routing.md) 仍保持进行中。
