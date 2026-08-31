# Windows 桌面设计

本文适用于 Windows 11 x64 的常驻桌面入口，面向实现者。某次 Windows 机器、热键冲突或安装结果不属于本文。

## 目标与非目标

- 目标：让 Windows 系统托盘、全局热键、选区复制、输入窗口、区域截屏、普通浮窗和实时字幕条复用现有翻译与 OCR 用例。
- 目标：Windows 平台代码不导入 AppKit、Quartz、Vision 或 `fcntl`，macOS 平台代码不因 Windows 依赖而改变安装结果。
- 非目标：Windows 本机 OCR、MSIX、代码签名、自动更新、开机启动、Windows 10/ARM64 正式兼容和管理员权限运行。

## 权威来源

| 内容 | 权威位置 |
| --- | --- |
| 平台组合 | `app.py` 的 `_build_windows_services` |
| 剪贴板、模拟复制、截屏和单实例 | `infrastructure/windows_desktop.py` |
| 热键、Tk 主循环、圈选、浮窗、字幕条和托盘 | `interfaces/windows_desktop.py` |
| 设置和输入窗口 | `interfaces/windows_views.py` |
| 源码安装入口 | `scripts/install-windows.ps1`、`windows/launcher.pyw` |

## 依赖与组合

- Windows 依赖只通过 `sys_platform == 'win32'` 安装：Pillow、pystray 和 pywin32。Pillow 只负责图片和托盘图标；pystray 只负责系统托盘；pywin32 只负责 Unicode 文本剪贴板。
- `DesktopListener` 继续编排划词、单次 OCR、实时开停和忙碌门禁；Windows 只注入热键、文本来源、图片来源和展示器。
- Tk 根窗口、所有 Tk 控件和区域圈选只在 UI 主线程创建或更新。模型请求和热键动作在后台线程运行，通过有界队列回到 UI 线程。
- `ai-translate listen` 使用同一 Tk 主循环但不创建托盘；`ai-translate app` 增加托盘和单实例互斥。

## 热键与选区

- 三组热键继续读取 `HOTKEY_SELECTION`、`HOTKEY_OCR` 和 `HOTKEY_LIVE_OCR`，使用 Windows `RegisterHotKey` 和 `MOD_NOREPEAT`；注册失败必须指出冲突组合并停止启动，不能静默回退成键盘 Hook。
- Windows 支持字母、数字、F1-F24、Space、Enter、Tab 和 Esc 作为主键；`cmd`/`win` 规范化为 Windows 键。设置仍要求至少一个修饰键，三组组合不得相同。
- 划词路径保存 Unicode 文本剪贴板，写入哨兵，等待修饰键松开后用 `SendInput` 模拟 `Ctrl+C`，读取后恢复原文本剪贴板。
- Windows UIPI 可能阻止普通权限进程向更高权限窗口注入按键。模拟复制失败或剪贴板未变化时，可以使用触发前已有的文本剪贴板；界面提示用户先手动复制，不要求程序以管理员身份运行。
- 测试不得读取真实剪贴板或发送真实按键。

## 圈选、截屏与坐标

- 进程必须在创建首个窗口前请求 Per-Monitor V2 DPI awareness；圈选、固定截屏和字幕条统一使用 Windows 虚拟桌面的物理像素坐标，原点在虚拟桌面左上，副屏坐标可以为负。
- 圈选器是覆盖整个虚拟桌面的透明顶层 Tk 窗口。Esc、超时、重复圈选或小于最小尺寸都返回取消；窗口销毁后才允许截屏。
- 单次 OCR 和实时 OCR 复用 `WindowsRectCapture`；Pillow 只截取规范化矩形并编码 PNG，继续执行最小尺寸和最大图片字节门禁。
- 实时字幕条优先放在圈选矩形下方，空间不足再放上方；窗口设置为不激活，关闭按钮触发现有 `stop_live`。

## 托盘、窗口与设置

- 托盘只显示划词、截图、实时开停、输入、设置和退出，不展示模型诊断、密钥或原始图片。
- 普通结果浮窗可以获得焦点以便选择和复制文字；每次查询显示时来到前面，但默认不是持续置顶，用户切换到其它窗口后可以落到后面。浮窗提供「置顶/取消置顶」按钮，置顶状态只在当前进程内保留；实时字幕条继续保持置顶且不得抢焦点。两个窗口都只显示业务结果和必要错误。
- Windows 设置页使用翻译、OCR、语言与热键三个页签；密钥字段遮挡。OCR 提供 `auto`、`paddle`、`standard` 和 `model`，不显示不可用的“只本地普通 Vision”。
- 设置写入 `resolve_env_path()` 选中的文件；应用后重建原有用例并重新注册热键，不创建第二套 HTTP 客户端语义。
- 单实例使用当前登录会话内的命名互斥量；退出时停止实时循环、热键、托盘和 Tk 主循环。

## 配置、OCR 与安装

- Windows 用户配置目录是 `%APPDATA%\AI Translate\.env`。项目 `.env` 仍高于用户目录；启动器只设置项目根目录和主机名，不把密钥打进启动器。
- Windows 暂无本地普通 OCR。`OCR_ENGINE=auto` 先尝试已安装的本地高级 PaddleOCR，再进入 API 普通 OCR.space 和 API 高级模型；`paddle`、`standard` 和 `model` 可分别强制对应单层。`OCR_ENGINE=vision` 保留为 macOS 配置，在 Windows 不得伪装就绪。PaddleOCR 3.7.0 / PaddlePaddle 3.3.0 的 Windows CPU 路径必须传入 `enable_mkldnn=False`，避开 oneDNN 新执行器不支持模型属性的运行时错误；macOS 保持上游默认。
- `scripts/install-windows.ps1` 只接受 Python 3.12+，创建或复用项目 `.venv`、执行 editable 安装，并用项目 `.venv` 的 `pythonw.exe` 启动 `windows/launcher.pyw`。脚本包含中文消息时必须保存为带 BOM 的 UTF-8，使 Windows PowerShell 5.1 不会按本地代码页破坏字符串和引号边界。
- 源码安装、本地离线测试和 Windows 真机验收是不同证据；未经单独授权不生成发布包、不签名、不调用真实模型。

## 变更与验证要求

- 修改 Windows 平台依赖、配置目录或入口时，同步 `pyproject.toml`、`.env.example`、根 README 和配置测试；安装脚本测试必须守住 UTF-8 BOM 与项目 `.venv` 入口。
- 修改热键支持范围、圈选坐标或字幕条位置时，同步本文件和 Windows 纯函数测试。
- 默认离线测试使用假剪贴板、假矩形、假截屏和 Fake 端口。Windows 真机至少验证托盘、热键冲突、手动复制降级、单/多屏 DPI、圈选取消、实时停止和设置重启。
