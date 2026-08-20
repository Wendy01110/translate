# Windows 桌面版 MVP 计划

> 状态：进行中
>
> 创建日期：2026-08-20（Asia/Shanghai）
>
> 更新日期：2026-08-21（Asia/Shanghai）

## 目标

在不复制翻译和 OCR 业务语义的前提下，让现有划词翻译、输入翻译、单次区域 OCR 翻译和区域实时 OCR 翻译能够从 Windows 11 x64 桌面入口运行。首版面向本地内部使用，优先保证源码安装、系统托盘、全局热键、圈选截屏、浮窗和设置可检查，并保留 macOS 现有行为。

## 当前依据

- `core`、`features`、翻译客户端、四层 OCR 适配和实时 OCR 的去重/停止语义不依赖 AppKit，可以跨平台复用。
- `app.py` 当前直接组合 macOS 选区、截屏、菜单栏和浮窗；`DesktopListener.run()`、配置用户目录、单实例和全部桌面窗口仍绑定 macOS。
- Windows 没有本地普通 Vision，自动模式从可选本地高级 PaddleOCR 开始，再进入 API 普通 OCR.space 和 API 高级模型；两套 API 不得互借配置。
- Windows 全局热键、模拟复制、屏幕坐标、DPI、系统托盘和打包只能在 Windows 交互桌面验证；macOS 离线测试不能替代。
- 当前工作区已有 macOS 图标和构建脚本 WIP，本计划不得覆盖、清理或混入这些改动。

## 范围与非目标

- 范围：Windows 11 x64、Python 3.12+；系统托盘；三组全局热键；选区模拟 `Ctrl+C` 与剪贴板恢复；输入窗口；设置页；单次区域圈选；固定矩形截屏；普通浮窗和实时字幕条；单实例；Windows 用户配置目录；本地源码安装入口。
- 范围：继续复用 `SelectionTranslateService`、`OcrTranslateService`、`Translator`、`OcrEngine` 和现有结果契约；Windows `auto` OCR 跳过 Vision，按本地高级、API 普通、API 高级顺序使用可用层。
- 范围：平台 I/O 可注入，默认离线测试不得读取真实剪贴板、注册真实热键、截屏或调用上游。
- 非目标：Windows 本机 OCR、MSIX、代码签名、自动更新、开机启动、Windows 10/ARM64 正式兼容、Electron、系统音频转写。
- 非目标：修改 macOS 已有交互、把 OCR 配置借给翻译或把翻译配置借给 OCR。

## 执行步骤

1. 为桌面组合增加平台选择，把 macOS 主线程调度、热键、权限提示和事件循环从共享监听编排中隔离。
2. 增加 Windows 剪贴板/模拟复制、全局热键、虚拟桌面区域圈选、单次与固定矩形截屏。
3. 增加 Windows Tk 桌面主机：系统托盘、设置、输入窗口、普通结果浮窗和实时字幕条；所有 Tk 更新回到 UI 线程。
4. 增加 Windows 用户配置路径、单实例和 PowerShell 源码安装/启动入口；依赖使用平台标记，不影响 macOS 安装。
5. 同步产品范围、架构、桌面设计、OCR 分流、配置、根 README、CLI 文案和文档索引。
6. 增加平台选择、Windows 适配和公共行为的离线测试；运行定向测试、完整离线套件和 `git diff --check`。
7. 在 Windows 11 x64 交互桌面完成热键、剪贴板、圈选、多屏/DPI、托盘、设置、实时停止和安装验收；真实模型调用仍需单独授权。

## 验收条件

- macOS 原有入口和离线测试保持通过；Windows 平台选择不导入 AppKit、Quartz 或 `fcntl`。
- Windows 能启动单实例托盘，三组热键可注册、更新和释放；注册冲突能给出可执行错误，不静默失效。
- 划词会恢复原剪贴板；无法向更高权限窗口模拟复制时，保留手动复制降级路径，不把旧剪贴板冒充当前选区。
- 单次圈选取消不调用 OCR；固定区域截屏有尺寸和字节上限；实时停止后不开始新的截屏、OCR 或翻译。
- 普通浮窗和字幕条不在后台线程直接操作 Tk；字幕条位于圈选区域外侧并避免进入下一帧。
- Windows 配置写入用户目录，密钥只显示 `set`/`unset`；Windows 设置页不提供不可用的“只本地普通 Vision”，但提供可选本地高级 PaddleOCR。
- 默认离线测试不触发真实桌面或上游；Windows 真机未验收前，计划保持进行中且不得宣称 Windows 版可用。

## 授权与停止边界

- 允许：本地代码、测试、文档、Windows 源码安装脚本和离线验证。
- 需要额外授权：创建/安装依赖环境、真实翻译或 OCR 调用、Windows 真机 GUI 操作、生成发布包、提交、推送、签名和发布。
- 出现以下情况停止：需要引入 MSIX/本机 OCR、要求管理员权限运行、默认上传剪贴板或整屏、破坏 macOS 现有路径、需要修改当前项目以外的文件。

## 当前进度

- 已完成现状核对、Windows MVP 边界和稳定设计；现有 macOS 图标/构建 WIP 未被修改或纳入。
- 已完成平台组合、Windows Unicode 文本剪贴板、`SendInput` 模拟复制、`RegisterHotKey`、虚拟桌面圈选、Pillow 截屏、Tk 普通浮窗/字幕条/设置/输入窗口、pystray 托盘、单实例和 `%APPDATA%` 配置路径。
- 已在 Windows 11 x64 安装 Python 3.13.15 AMD64，并由 `scripts/install-windows.ps1` 创建项目 `.venv`、安装平台依赖和启动 `windows/launcher.pyw`。首次真机执行发现无 BOM UTF-8 脚本会被 Windows PowerShell 5.1 按本地代码页误读并解析失败；脚本改为带 BOM 的 UTF-8，并由安装合同测试固定。
- 已确认托盘宿主进程使用项目 `.venv\Scripts\pythonw.exe`，第二实例以退出码 1 明确拒绝；Windows 设置窗口的翻译、OCR、语言与热键三页完成真机显示核对。Google 内置源真实文本翻译成功；未通过工具可靠操作托盘菜单或输入翻译窗口，不据此声明其交互验收完成。
- 已安装 PaddleOCR 3.7.0 与 PaddlePaddle 3.3.0；Windows CPU 默认 oneDNN 路径真实预测失败后，适配器仅在 Windows 传入 `enable_mkldnn=False`。PP-OCRv6 tiny 本地图片识别和 OCR 后 Google 翻译均已成功，桌面首次加载提醒仍未验证。
- Windows 配置、安装合同、平台 UI/基础设施、CLI、架构和文档定向测试 70 项通过；当前完整 Windows 离线套件 244 项通过、2 项仅因 PyObjC/macOS 专属路径跳过，`pip check` 与 Paddle CPU 自检通过。
- 尚未完成 Windows 全局热键、剪贴板恢复/UIPI、圈选与真实区域截屏、单/多屏 DPI、托盘菜单、输入窗口结果展示、实时停止和 Paddle 桌面首次提醒。区域截图复验开始前桌面进入锁屏，按安全边界停止 UI 操作；本计划继续保持进行中，不能声明 Windows 桌面版整体可用。
