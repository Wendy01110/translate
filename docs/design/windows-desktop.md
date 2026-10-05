# Windows 桌面设计

本文适用于 Windows 11 x64 的常驻桌面入口，面向实现者。某次机器、热键冲突或验收结果不属于本文。

## 目标与非目标

- 目标：让 Windows 系统托盘、全局热键、选区复制、统一翻译工作区、区域截屏和实时字幕条复用现有翻译与 OCR 用例。
- 目标：使用 PySide6、Qt Quick 和 QML 提供统一的 Windows 视觉与无障碍树，同时保持物理像素圈选、Per-Monitor DPI、置顶和不抢焦点合同。
- 目标：Windows 平台代码不导入 AppKit、Quartz、Vision 或 `fcntl`，macOS 平台代码不因 Windows 依赖而改变安装结果。
- 非目标：Windows 本地普通 OCR、MSIX、代码签名、自动更新、开机启动、Windows 10/ARM64 正式兼容和管理员权限运行。

## 权威来源

| 内容 | 权威位置 |
| --- | --- |
| 平台组合 | `app.py` 的 `_build_windows_services` |
| 剪贴板、模拟复制、截屏和单实例 | `infrastructure/windows_desktop.py` |
| 热键和物理屏幕坐标纯函数 | `interfaces/windows_desktop.py` |
| `QApplication`、Presenter、圈选、字幕条和托盘 | `interfaces/windows_qt.py` |
| 可交互视图与设计 token | `interfaces/qml/*.qml` |
| 视觉规范与参考图 | [Windows Qt 界面规范](./windows-qt-ui.md) |
| 源码安装入口 | `scripts/install-windows.ps1`、`windows/launcher.pyw` |

## 依赖与组合

- Windows 平台依赖通过 `sys_platform == 'win32'` 安装：PySide6、Pillow 和 pywin32。PySide6 提供 Qt Widgets、Qt Quick、QML 和 `QSystemTrayIcon`；Pillow 只负责屏幕图像；pywin32 只负责 Unicode 文本剪贴板。活动 Windows UI 不再依赖 Tk、ttk 或 pystray。
- `DesktopListener` 继续编排划词、单次 OCR、实时开停和忙碌门禁；Windows 只注入热键、文本来源、图片来源和展示器。
- 实时圈选完成结果由 UI 队列延迟投递，监听器按发起圈选时预留的会话代次接纳结果；旧矩形或取消回调不得影响重开后的新圈选。应用设置会取消待完成圈选并停止已运行循环，用户重新圈选开始；共享规则见 [屏幕实时 OCR](./live-screen-ocr.md)。
- 进程只创建一个 `QApplication` 和一个 `QQmlEngine`。QML 对象只在 UI 主线程创建或更新；模型请求和热键动作在后台线程运行，通过有界队列回到 UI 线程。
- 托盘输入、划词和单次 OCR 只组合一个 `WindowsOverlayPresenter`，并更新同一个 `Workspace.qml` 窗口；不得再创建第二套输入 presenter 或第二套翻译语义。
- `ai-translate listen` 使用同一 Qt 事件循环但不创建托盘；`ai-translate app` 增加 `QSystemTrayIcon` 和单实例互斥。`QApplication.setQuitOnLastWindowClosed(False)` 保证隐藏所有普通窗口时托盘宿主仍保持运行。

## 热键与选区

- 三组热键继续读取 `HOTKEY_SELECTION`、`HOTKEY_OCR` 和 `HOTKEY_LIVE_OCR`，使用 Windows `RegisterHotKey` 和 `MOD_NOREPEAT`；注册失败必须指出冲突组合并停止启动，不能静默回退成键盘 Hook。
- Windows 支持字母、数字、F1-F24、Space、Enter、Tab 和 Esc 作为主键；`cmd`/`win` 规范化为 Windows 键。设置要求至少一个修饰键，三组组合不得相同。
- 划词路径保存 Unicode 文本剪贴板，写入哨兵，等待修饰键松开后用 `SendInput` 模拟 `Ctrl+C`，读取后恢复原文本剪贴板。
- Windows UIPI 可能阻止普通权限进程向更高权限窗口注入按键。模拟复制失败或剪贴板未变化时，只能在剪贴板所有者窗口与当前前台窗口属于同一进程时使用触发前文本，表示用户已在目标程序内手动复制；来源不匹配时返回 `copy_simulation_failed`，不得把其它程序留下的旧剪贴板冒充当前选区。程序本身不要求也不建议以管理员身份运行。
- 默认测试不得读取真实剪贴板或发送真实按键。

## 圈选、截屏与坐标

- 进程必须在创建首个窗口前请求 Per-Monitor V2 DPI awareness。圈选、固定截屏和字幕条统一使用 Windows 虚拟桌面的物理像素坐标，副屏坐标可以为负；QML 使用逻辑像素，Python bridge 在信号边界按当前窗口 `devicePixelRatio` 换算。
- 圈选器为每块物理显示器分别创建一个 `RegionOverlay.qml` 无边框 `QQuickWindow`，所有覆盖层共享同一个选区会话。每层只覆盖自己的物理矩形；拖拽坐标、边框和尺寸标签统一映射到全局物理像素，因此选区可以跨过显示器边界。
- 鼠标释放只有在同一会话已经收到按下事件时才结束圈选；启动或窗口切换产生的孤立释放事件必须忽略。Esc、超时、重复圈选或小于最小尺寸会让全部覆盖层一起取消；全部隐藏并销毁后才允许截屏。
- 单次 OCR 和实时 OCR 复用 `WindowsRectCapture`；Pillow 只截取规范化矩形并编码 PNG，继续执行最小尺寸和最大图片字节门禁。
- 实时字幕条优先放在圈选矩形下方，空间不足再放上方；`LiveOverlay.qml` 使用无边框置顶工具窗，Windows 扩展样式增加 `WS_EX_NOACTIVATE`，不得抢走目标窗口焦点。字幕条按内容、屏幕和 DPI 有界增高，并明确区分原文、译文、识别状态和「停止」入口。

## 工作区、设置与托盘

- `Workspace.qml` 默认 800×560；宽度充足时原文/译文左右双栏，紧凑宽度改为上下排列。原文可编辑，译文只读；修改划词或 OCR 原文后只调用已注入的 `DesktopListener.handle_typed_text`，不得再次读取选区、截屏或调用 OCR。
- 工作区标题行显示目标语言、翻译、置顶和复制译文；来源与状态位于底部。目标语言切换只更新当前 listener，不自动请求、不直接写配置。翻译按钮与 `Ctrl+Enter` 共用忙碌门禁，请求期间输入和动作禁用；菜单输入、划词和单次 OCR 更新同一个窗口对象。
- 普通工作区可以获得焦点以编辑、选择和复制文字；每次新结果短暂来到最前，随后恢复普通层级。只有用户点击「置顶」后才持续最前，状态只保留到当前进程退出；复制按钮只写当前译文并显示短暂成功反馈。
- `Settings.qml` 使用左侧翻译、OCR、语言与热键导航，右侧正文可独立滚动，底部状态和「应用/保存」固定可达。密钥字段遮挡；OCR 只提供 `auto`、`paddle`、`standard` 和 `model`，不显示 Windows 不可用的本地普通 Vision。
- 「应用」写入配置并按实际变化更新运行时，但保持窗口打开；「保存」成功后隐藏窗口。设置仍写入 `resolve_env_path()` 选中的唯一文件；与 macOS 共用 `DesktopRuntime` 的客户端复用逻辑，只改语言或热键不会重新加载 Paddle，不创建第二套 HTTP 客户端语义。
- 托盘使用 `QSystemTrayIcon`，菜单只显示划词、截图、实时开停、「打开翻译工作区…」、设置和退出；左键单击打开工作区。菜单不得展示模型诊断、密钥、剪贴板原文或图片。
- 单实例使用当前登录会话内的命名互斥量；退出时停止实时循环、热键、托盘和 Qt 事件循环。

## 配置、OCR 与安装

- Windows 用户配置目录是 `%APPDATA%\AI Translate\.env`。项目 `.env` 仍高于用户目录；启动器只设置项目根目录和主机名，不把密钥打进启动器。
- Windows 暂无本地普通 OCR。`OCR_ENGINE=auto` 先尝试已安装的本地高级 PaddleOCR，再进入 API 普通 OCR.space 和 API 高级模型；`paddle`、`standard` 和 `model` 可分别强制对应单层。`OCR_ENGINE=vision` 保留为 macOS 配置，在 Windows 不得伪装就绪。
- PaddleOCR 3.7.0 / PaddlePaddle 3.3.0 的 Windows CPU 路径传入 `enable_mkldnn=False`，避开 oneDNN 新执行器不支持模型属性的运行时错误；macOS 保持上游默认。
- `scripts/install-windows.ps1` 只接受 Python 3.12+，创建或复用项目 `.venv`、执行 editable 安装，并用项目 `.venv` 的 `pythonw.exe` 启动 `windows/launcher.pyw`。脚本包含中文消息时必须保存为带 BOM 的 UTF-8，使 Windows PowerShell 5.1 不会按本地代码页破坏字符串和引号边界。
- 源码安装、本地离线测试和 Windows 真机验收是不同证据；未经单独授权不生成发布包、不签名、不调用真实模型。

## 变更与验证要求

- 修改 Windows 平台依赖、配置目录或入口时，同步 `pyproject.toml`、`.env.example`、根 README 和配置测试；安装脚本测试必须守住 UTF-8 BOM 与项目 `.venv` 入口。
- 修改 QML 公共文案、工作区交互、圈选坐标或字幕条位置时，同步本文件、视觉规范、Presenter 合同和对应 QML 合同测试。
- 默认离线测试使用假剪贴板、假矩形、假截屏和 Fake 端口；不得创建真实窗口、注册热键或调用上游。
- Windows 真机至少分别验证 QML 加载、工作区动作、三页设置、圈选拖动与 Esc、字幕条停止、`QSystemTrayIcon` 可用/可见与激活接线、全局热键、剪贴板恢复、单/多屏 DPI、真实 OCR/翻译和 App 重启。安全自动化无法点击任务栏通知区时，应把 OS 图标可见与 Qt 激活信号证据、物理点击边界分别记录，不得声称发送过未发送的点击。
