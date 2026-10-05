# 文档入口

> 更新时间：2026-10-06（Asia/Shanghai）

本页是项目维护文档的唯一默认入口，只保留当前状态、活动任务和权威资料路由。面向使用者的最短路径见 [项目 README](../README.md)；日期化事实放在计划或日志，不在本页重复维护。

## 当前状态

- 本地早期桌面翻译工具，macOS 使用菜单栏，Windows 11 x64 使用 PySide6 / Qt Quick 系统托盘；两端输入、划词和单次 OCR 复用同一翻译工作区。安装入口、操作方式和已知限制见[项目 README](../README.md)，平台规则见[桌面热键](./design/desktop-hotkeys.md)与[Windows 桌面](./design/windows-desktop.md)。
- 翻译默认 Google 内置网页源，也支持其它内置、官方与 OpenAI 兼容来源；翻译与四层 OCR 独立配置，不互借地址、密钥、模型或超时。只读一份配置，`config-check` 只回读静态状态；设置应用按受影响侧更新客户端，保留未变配置的已加载模型，见[配置设计](./design/configuration.md)。
- OCR 自动顺序为 macOS Vision、可选 PP-OCRv6、OCR.space 和 API 高级；Windows 从 PP-OCRv6 开始。API 普通有单张/1 MB 边界，Paddle 未安装时直接跳过；强制模式、图片预算与降级规则见[OCR 分流](./design/ocr-routing.md)。首次加载提醒在普通工作区显示完整说明，在实时字幕条显示简短提示。
- 区域实时 OCR 支持异步圈选、画面/文字去重、有限翻译补试和停止；旧会话/旧语言结果不能回写，设置应用需重新圈选。字幕条保持置顶、不抢焦点、位于圈选区域外侧，见[屏幕实时 OCR](./design/live-screen-ocr.md)。
- 翻译输入、图片/页数、截图区域与最终 HTTP 响应均有预算；系统输入命令与异常响应返回稳定失败，OCR 后翻译失败保留原文。共享运行时与依赖方向见[架构设计](./design/architecture.md)，状态契约以 `core/models.py` 为准。
- 四层 OCR 分流、Windows MVP 和 Qt UI 迁移已完成；当前没有开放 Issue。后续优化与产品能力按[计划索引](./plan/README.md)逐项推进，不同时扩展全部能力。

验证证据按层级保存：本轮 macOS [首次提醒验收](./logs/202610/2026-10-06-native-ocr-reminder-verification.md)使用原生菜单 action、缓存模型与合成输入，未重启安装 App 或复验物理热键/真实截屏；Windows Qt 信号也不等于物理托盘点击。macOS 正式 App 的跨应用/双屏全屏焦点行为仍保留[既有复验边界](./logs/202609/2026-09-08-overlay-focus-loss.md)。离线测试、原生隔离显示、真实提供方和业务验收不能互相替代。

## 当前工作

当前没有进行中的计划；后续工作从[计划状态索引](./plan/README.md)进入。

## 按任务查找

| 任务 | 入口 |
| --- | --- |
| 安装并检查配置 | [项目 README](../README.md)（macOS `./scripts/install.sh`；Windows `scripts/install-windows.ps1`） |
| 确认首期做什么、不做什么 | [产品范围](./design/product-scope.md) |
| 修改分层、端口或执行链 | [架构设计](./design/architecture.md) |
| 修改环境变量或双模型边界 | [配置设计](./design/configuration.md) |
| 修改 macOS 热键、菜单栏或浮窗 | [桌面热键设计](./design/desktop-hotkeys.md) |
| 修改 Windows 热键、托盘或浮窗 | [Windows 桌面设计](./design/windows-desktop.md) |
| 修改 Windows Qt 视觉或 QML 组件 | [Windows Qt 界面规范](./design/windows-qt-ui.md) |
| 修改区域实时 OCR | [屏幕实时 OCR](./design/live-screen-ocr.md) |
| 修改 OCR 本机/模型分流 | [OCR 分流](./design/ocr-routing.md) |
| 更新计划、Issue 或日志 | [文档框架](./design/documentation-framework-guide.md) |
| 执行仓库任务 | [AGENTS.md](../AGENTS.md) |

## 机器权威

| 内容 | 权威来源 |
| --- | --- |
| 项目版本 | [pyproject.toml](../pyproject.toml) |
| 环境变量名和默认值 | [.env.example](../.env.example)、[config.py](../src/ai_translate/config.py) |
| 结果状态和字段 | [core/models.py](../src/ai_translate/core/models.py) |
| 端口 | [core/ports.py](../src/ai_translate/core/ports.py) |
| 依赖方向 | [架构测试](../tests/architecture/test_dependency_rules.py) |
| 当前任务状态 | [计划状态索引](./plan/README.md) 及唯一状态目录中的原文件 |

静态配置、离线测试、真实模型调用和桌面验收是不同证据层，不能相互替代。

## 文档状态约定

- `design/` 保存长期稳定规则；`plan/in-progress/` 和 `plan/pending/` 保存当前任务状态；`issues/open/` 保存尚未闭合的问题。
- `logs/YYYYMM/` 保存日期化结果与验证；`completed/`、`closed/`、`archive/` 和 Git 历史只在追溯时读取。
- 状态变化时移动原文件并同步引用，不复制并存，不用历史日志证明当前能力。

## 历史查找

完成计划见 [plan/completed/](./plan/completed/)，日期日志见 [logs/](./logs/)，关闭 Issue 见 [issues/closed/](./issues/closed/)，精选历史证据见 [archive/](./archive/)；需要旧版本细节时再按日期或 Git 历史追溯。
