# 文档入口

> 更新时间：2026-10-06（Asia/Shanghai）

本页是项目维护文档的唯一默认入口，只保留当前状态、活动任务和权威资料路由。面向使用者的最短路径见 [项目 README](../README.md)；日期化事实放在计划或日志，不在本页重复维护。

## 当前状态

- 仓库已建立文档框架、Agent 规则和可安装的 Python 骨架。macOS 安装入口是 `./scripts/install.sh`，构建已接入项目应用图标；Windows 11 x64 源码入口 `scripts/install-windows.ps1` 使用 Python 3.13.15 x64、PySide6、Qt Quick/QML 和 `QSystemTrayIcon`，工作区、设置、逐屏圈选、字幕条、三组热键、真实翻译/OCR 与高 DPI 验收均已有证据。安全自动化不能直接点击任务栏通知区域，已分别记录图标可见/Qt 激活信号与未发送的物理点击边界。
- 翻译与 OCR 通过独立环境变量配置；OCR 内部分为本地普通、本地高级、API 普通和 API 高级四层。翻译默认 Google 内置网页源（免密钥），也可选用 Bing/DeepL 内置或官方/OpenAI 兼容源；只读一个配置文件；`config-check` 回读路径和分层静态状态，但不调用模型或上游。
- macOS OCR 自动顺序是 Vision、可选 PP-OCRv6、OCR.space、API 高级视觉模型；Windows 暂无本地普通层，从可选 PP-OCRv6 开始。PaddleOCR 未安装时跳过；macOS PP-OCRv6 small 与 Windows PP-OCRv6 tiny 均已完成本地实图验证，Windows 关闭 oneDNN 后使用普通 Paddle CPU 后端。API 普通只尝试单张 1 MB 内图片，失败、超限或多页时转 API 高级；其异常状态字段和 JSON 解码失败返回稳定结果，自动模式继续高级层、强制普通模式停止，响应边界见 [OCR 分流](./design/ocr-routing.md)。Unlimited-OCR 保留专用请求合同，其它模型使用标准 OpenAI 视觉消息。CLI 支持本地图片和平台圈选截屏。
- 划词和 OCR 可通过 `listen` 热键或桌面 App 触发；macOS 使用菜单栏，Windows 使用系统托盘。两端的桌面输入、划词和单次 OCR 都复用各自平台的同一个翻译工作区；设置、工作区和实时字幕条复用既有业务用例，不在界面层另写翻译语义。
- macOS 剪贴板读写与模拟复制命令的启动、超时及文本编解码失败进入既有失败结果和界面提示，不继续调用翻译；原剪贴板恢复失败明确报告写入失败。错误边界见 [桌面热键设计](./design/desktop-hotkeys.md)。
- macOS 菜单输入、划词和单次 OCR 已统一到同一个 `OverlayPresenter` / `NSPanel`；内容区不再显示「翻译」大标题，左上直接使用目标语言标签与下拉栏。三种入口的原文均可编辑，译文只读，标题区翻译、图钉、复制、`Command+Return`、目标语言栏、失焦和双屏行为完全共用。临时状态保持只读；OCR 修正文案后只重跑文本翻译，不再次调用 OCR。
- macOS 统一「翻译」窗口默认 720×520，Windows Qt Quick 工作区默认 800×560；两端都使用宽屏双栏、窄屏上下排列，并让目标语言、翻译、置顶和复制共用顶栏。目标语言切换只更新当前 `DesktopListener`，不自动请求、不直接写配置；设置保存后会反向同步栏位，实时 OCR 的去重记忆也会重置。原独立 macOS 输入窗口实现及 Windows Tk/pystray UI 已退出活动组合，旧输入窗口代码和专属测试已清理；两端菜单输入分别复用各自的普通翻译工作区。
- macOS/Windows 普通结果浮窗已支持「置顶/取消置顶」进程内切换：macOS 新结果按鼠标所在显示器居中，未置顶时可进入该屏幕的全屏 Space，失去焦点后保留在后台并在下次查询重新前置；置顶后加入所有 Space 且不收起。实时字幕条继续固定置顶。macOS 已有双屏 Fake 原生层级/集合策略验证，2026-09-08 按用户反馈移除失焦隐藏，独立原生窗口已验证失焦保留可见、下次显示恢复焦点及置顶后失焦可见，正式 App 跨应用点击与双屏全屏仍待复验，见[失焦修复记录](./logs/202609/2026-09-08-overlay-focus-loss.md)；Windows 已实际点击置顶/取消置顶，并用其它窗口核对前后层级恢复。
- 翻译与 API 高级 OCR 连接默认本机 `llm-token-router` 地址时，客户端分别默认发送 `thinking=false`；显式 `true` 仍可开启，自定义 Router 地址可分别显式配置，普通 OpenAI 兼容地址不会自动收到 Router 私有字段。macOS 与 Windows 的工作区格式已共用同一函数；macOS 实时 OCR 首次加载 Paddle 时，提示现在留在实时字幕条，不再误弹普通翻译窗。
- 用户在 macOS 本机试用菜单栏 App，报告热键划词和圈选 OCR 基本可用。屏幕实时 OCR 已完成异步圈选、约 0.8 秒目标起点间隔、双屏副屏圈选、动态更新和停止真机验收。Windows Qt 迁移已完成四个 QML 界面、真实控件、150%/200% 缩放、物理圈选坐标、系统托盘可用/可见、正式 `Alt+E` Router 翻译和复制验证；管理员记事本中手动复制后触发普通权限 App 的 UIPI 降级也已真测。翻译 Router 显式关闭思考后，固定短句从 46.212 秒/2387 completion tokens 降到 2.695 秒/6 completion tokens。Windows MVP 已完成，当前没有开放 Issue。
- 实时 OCR 切换目标语言后会丢弃旧任务并继续下一轮；暂态翻译错误最多补试两次，同一画面复用 OCR 结果。兼容模型报告译文截断时明确失败，OCR 后翻译仍保留原文；具体边界见[屏幕实时 OCR](./design/live-screen-ocr.md)与[配置设计](./design/configuration.md)。
- 实时圈选发起、排队启动和完成回调按会话代次隔离，停止后重开时旧回调不影响新一轮；应用设置同时取消待完成圈选和已运行循环，需要重新圈选开始。工作区目标语言栏切换仍继续当前循环，具体规则见 [屏幕实时 OCR](./design/live-screen-ocr.md)。
- 设置应用按翻译/OCR 配置分别更新客户端，只改语言、热键或候选列表会复用已加载的 Paddle。翻译输入统一限制为 8000 字符，最终 HTTP 响应进入解析前按解码后大小检查；使用与失败边界见[配置设计](./design/configuration.md)。
- 全部翻译来源与 API OCR 对过深 JSON 返回稳定失败；DeepL 官方响应顶层类型错误不再抛异常，Bing HTML 会话解析保持原合同。默认验证继续使用 Fake 与 HTTP mock，真实提供方验收单独记录。
- OCR 每次最多 10 页，单张与全部原始图片合计均最多 20 MiB；CLI 在读文件前检查页数，累计超限停止继续读取，用例、路由与各层适配在初始化/编码/请求前共同拒绝。macOS 单次截图继续复用有界文件读取，固定区域截屏在两端检查有限坐标及区域面积。预算、坐标单位与失败边界见 [OCR 分流](./design/ocr-routing.md)。
- 当前实施 [本地/API 四层 OCR 分流](./plan/in-progress/2026-08-20-tiered-ocr-routing.md)；[Windows 桌面版 MVP](./plan/completed/2026-08-20-windows-mvp.md) 与 [Windows Qt 桌面 UI 迁移](./plan/completed/2026-09-01-windows-ui-optimization.md) 已完成。系统音频转写仍待进行；其它产品能力见 [TTime 后续计划](./plan/pending/2026-08-19-ttime-inspired-follow-on.md) 的有界历史、划词工具栏与可选剪贴板监听。

## 当前工作

- [项目复核、异常响应收口与 Git 交付](./plan/in-progress/2026-10-06-project-review-and-git-delivery.md)
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
