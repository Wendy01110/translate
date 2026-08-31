# 文档入口

> 更新时间：2026-09-01（Asia/Shanghai）

本页是项目维护文档的唯一默认入口，只保留当前状态、活动任务和权威资料路由。面向使用者的最短路径见 [项目 README](../README.md)；日期化事实放在计划或日志，不在本页重复维护。

## 当前状态

- 仓库已建立文档框架、Agent 规则和可安装的 Python 骨架。macOS 安装入口是 `./scripts/install.sh`，构建已接入项目应用图标；Windows 11 x64 源码入口 `scripts/install-windows.ps1` 已完成 Python 3.13.15 x64 建环境、安装依赖、托盘进程、三组热键实际触发/取消、划词剪贴板恢复和双屏固定区域 OCR 的首轮真机验证，完整圈选拖拽与托盘交互仍未闭合。
- 翻译与 OCR 通过独立环境变量配置；OCR 内部分为本地普通、本地高级、API 普通和 API 高级四层。翻译默认 Google 内置网页源（免密钥），也可选用 Bing/DeepL 内置或官方/OpenAI 兼容源；只读一个配置文件；`config-check` 回读路径和分层静态状态，但不调用模型或上游。
- macOS OCR 自动顺序是 Vision、可选 PP-OCRv6、OCR.space、API 高级视觉模型；Windows 暂无本地普通层，从可选 PP-OCRv6 开始。PaddleOCR 未安装时跳过；macOS PP-OCRv6 small 与 Windows PP-OCRv6 tiny 均已完成本地实图验证，Windows 关闭 oneDNN 后使用普通 Paddle CPU 后端。API 普通只尝试单张 1 MB 内图片，失败、超限或多页时转 API 高级；Unlimited-OCR 保留专用请求合同，其它模型使用标准 OpenAI 视觉消息。CLI 支持本地图片和平台圈选截屏。
- 划词和 OCR 可通过 `listen` 热键或桌面 App 触发；macOS 使用菜单栏，Windows 候选使用系统托盘。设置、翻译工作区和实时字幕条复用既有业务用例，不在界面层另写翻译语义。
- macOS 菜单输入、划词和单次 OCR 已统一到同一个 `OverlayPresenter` / `NSPanel`；内容区不再显示「翻译」大标题，左上直接使用目标语言标签与下拉栏。三种入口的原文均可编辑，译文只读，标题区翻译、图钉、复制、`Command+Return`、目标语言栏、失焦和双屏行为完全共用。临时状态保持只读；OCR 修正文案后只重跑文本翻译，不再次调用 OCR。
- 统一「翻译」窗口默认 720×520，宽屏双栏、窄屏上下排列；目标语言与右侧三个动作共用一行，来源脚注使用中间剩余空间，省下的语言专用行已扩展给文本区。选项复用设置页的中文/英语/日语/韩语；切换只更新当前 `DesktopListener`，不自动请求、不直接写配置；设置保存后会反向同步栏位，实时 OCR 的去重记忆也会重置以使用新目标。原生快照已覆盖选择、忙碌禁用和结果恢复。原独立 macOS 输入窗口实现不再由 `app.py` 组合，Windows Tk 输入窗口保持不变。
- macOS/Windows 普通结果浮窗已支持「置顶/取消置顶」进程内切换：macOS 新结果按鼠标所在显示器居中，未置顶时可进入该屏幕的全屏 Space，但失去焦点后直接收起并在下次查询重新弹出；置顶后加入所有 Space 且不收起。实时字幕条继续固定置顶。macOS 已完成双屏 Fake 原生层级/集合策略验证，用户重开后也确认副屏全屏弹出、失焦收起和再次弹出符合预期；Windows 置顶按钮与层级序列仍只有离线合同证据。
- 用户在 macOS 本机试用菜单栏 App，报告热键划词和圈选 OCR 基本可用。屏幕实时 OCR 已完成异步圈选、约 0.8 秒目标起点间隔、双屏副屏圈选、动态更新和停止真机验收。Windows 已验证源码安装、托盘进程、单实例、设置三页、`Alt+E` 真实选区复制/Router 翻译/剪贴板恢复、`Alt+W` 与 `Alt+Q` 打开圈选层、`Alt+Q` 再次触发取消、主屏固定区域 OCR 后翻译、双屏负坐标/DPI 截屏 OCR、实时固定帧显示/去重/更新/停止，以及 OCR.space Engine 2 与 Router API 高级 OCR；无标题全屏圈选层无法由当前安全自动化工具接管鼠标，托盘菜单、输入窗口、Paddle 首次提醒的桌面显示和实际字幕条关闭仍未验收，不能声明 Windows 桌面版整体完成。历史尚未实施。当前没有开放 Issue。
- 当前实施 [Windows 桌面版 MVP](./plan/in-progress/2026-08-20-windows-mvp.md) 与 [本地/API 四层 OCR 分流](./plan/in-progress/2026-08-20-tiered-ocr-routing.md)；Windows 视觉与交互统一已单列为 [待进行计划](./plan/pending/2026-09-01-windows-ui-optimization.md)，需先闭合当前交互基线再实施。系统音频转写仍待进行；其它产品能力见 [TTime 后续计划](./plan/pending/2026-08-19-ttime-inspired-follow-on.md) 的有界历史、划词工具栏与可选剪贴板监听。

## 当前工作

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
