# 文档入口

> 更新时间：2026-08-21（Asia/Shanghai）

本页是项目维护文档的唯一默认入口，只保留当前状态、活动任务和权威资料路由。面向使用者的最短路径见 [项目 README](../README.md)；日期化事实放在计划或日志，不在本页重复维护。

## 当前状态

- 仓库已建立文档框架、Agent 规则和可安装的 Python 骨架。macOS 安装入口是 `./scripts/install.sh`，构建已接入项目应用图标；Windows 11 x64 源码入口 `scripts/install-windows.ps1` 已完成 Python 3.13.15 x64 建环境、安装依赖和启动托盘进程的首轮真机验证，交互桌面验收仍未闭合。
- 翻译与 OCR 通过独立环境变量配置；OCR 内部分为本地普通、本地高级、API 普通和 API 高级四层。翻译默认 Google 内置网页源（免密钥），也可选用 Bing/DeepL 内置或官方/OpenAI 兼容源；只读一个配置文件；`config-check` 回读路径和分层静态状态，但不调用模型或上游。
- macOS OCR 自动顺序是 Vision、可选 PP-OCRv6、OCR.space、Unlimited-OCR；Windows 暂无本地普通层，从可选 PP-OCRv6 开始。PaddleOCR 未安装时跳过；macOS PP-OCRv6 small 与 Windows PP-OCRv6 tiny 均已完成本地实图验证，Windows 关闭 oneDNN 后使用普通 Paddle CPU 后端。API 普通只尝试单张 1 MB 内图片，失败、超限或多页时转 API 高级。CLI 支持本地图片和平台圈选截屏。
- 划词和 OCR 可通过 `listen` 热键或桌面 App 触发；macOS 使用菜单栏，Windows 候选使用系统托盘。输入窗口、设置、普通浮窗和实时字幕条复用同一业务用例，不在界面层另写翻译语义。
- 用户在 macOS 本机试用菜单栏 App，报告热键划词和圈选 OCR 基本可用。屏幕实时 OCR 已改为异步圈选和约 0.8 秒目标起点间隔，待重启 App 复验。Windows 已验证源码安装、托盘进程、单实例、设置三页、真实 Google 文本翻译、本地图片 PaddleOCR 与 OCR 后翻译；热键、剪贴板恢复、圈选截屏、多屏/DPI、实时停止和托盘菜单交互仍未验收，不能声明 Windows 桌面版整体可用。历史尚未实施。当前没有开放 Issue。
- 正在收尾 [屏幕实时 OCR 翻译](./plan/in-progress/2026-08-20-live-screen-ocr.md)，并实施 [Windows 桌面版 MVP](./plan/in-progress/2026-08-20-windows-mvp.md) 与 [本地/API 四层 OCR 分流](./plan/in-progress/2026-08-20-tiered-ocr-routing.md)；系统音频转写仍待进行。下一档其它产品能力见 [待进行](./plan/pending/2026-08-19-ttime-inspired-follow-on.md) 的复制译文与有界历史。

## 当前工作

- [屏幕实时 OCR 翻译](./plan/in-progress/2026-08-20-live-screen-ocr.md)
- [Windows 桌面版 MVP](./plan/in-progress/2026-08-20-windows-mvp.md)
- [本地与 API 四层 OCR 分流](./plan/in-progress/2026-08-20-tiered-ocr-routing.md)

## 按任务查找

| 任务 | 入口 |
| --- | --- |
| 安装并检查配置 | [项目 README](../README.md)（macOS `./scripts/install.sh`；Windows `scripts/install-windows.ps1`） |
| 确认首期做什么、不做什么 | [产品范围](./design/product-scope.md) |
| 修改分层、端口或执行链 | [架构设计](./design/architecture.md) |
| 修改环境变量或双模型边界 | [配置设计](./design/configuration.md) |
| 修改 macOS 热键、菜单栏或浮窗 | [桌面热键设计](./design/desktop-hotkeys.md) |
| 修改 Windows 热键、托盘或浮窗 | [Windows 桌面设计](./design/windows-desktop.md) |
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
