# Windows Qt 桌面 UI 迁移完成记录

> 日期：2026-09-01（Asia/Shanghai）
>
> 对应计划：[Windows Qt 桌面 UI 迁移](../../plan/completed/2026-09-01-windows-ui-optimization.md)

## 范围

Requester 在 Windows MVP 继续实施与真机验收基础上，认为现有 Tk 界面观感不足，明确选择把活动 Windows UI 更换为 PySide6、Qt Quick 和 QML，并授权依赖安装、界面操作、真实翻译、App 重启、文档、提交和推送。本次只替换当前项目的 Windows 界面与必要 bridge，不修改翻译/OCR 公共语义，不打包、不签名、不发布。

## 实施

- 平台依赖从 pystray 改为 PySide6，QML 与 SVG 通过 setuptools package data 安装；活动源码删除 Tk/ttk、旧输入 presenter、Tk 样式和 pystray 回退。
- 新增单一 `QApplication` / `QQmlEngine` 运行时，持有 QML component 与根窗口，使用有界 UI 队列跨线程调度，并通过 Qt 元对象签名连接动态 QML 信号。
- 新增统一工作区、三组设置、逐显示器圈选和实时字幕条 QML；托盘迁移到真实 `QSystemTrayIcon`。
- 工作区保留目标语言、翻译、置顶、复制、可编辑原文、只读译文和 `Ctrl+Enter`；菜单输入、划词和单次 OCR 更新同一个窗口对象。
- 圈选保留全局物理像素和负坐标，多屏 QML 窗口按 `devicePixelRatio` 换算；会话和首块屏幕先登记再显示，孤立鼠标释放不再取消会话，窗口销毁先检查 Shiboken 对象有效性。
- 字幕条保留置顶与不抢焦点，设置页保留独立配置、密钥遮挡、应用/保存语义和固定底部动作。

## 视觉证据

- 先生成工作区、设置、字幕条和圈选四张概念图，再实现真实 QML 控件；概念图没有作为界面切片使用。
- 最终实现快照由 `QQuickWindow.grabWindow()` 在真实客户区采集，分别为 800×560、780×680、720×146 和 2560×1440；概念与实现均保存在 `docs/assets/windows-qt-ui/`。
- 对照检查覆盖调色板、字体、信息层级、按钮主次、设置导航、圈选遮罩、字幕状态和响应式密度。实现将工作区快捷键提示移到底部、把文本区标签放到边框上方，并让短字幕条按内容收紧高度；这些偏差用于 800×560 和高 DPI 可达性。
- 首轮发现中文字体回退不一致和组合框双箭头，最终统一 `Microsoft YaHei UI` 并使用单一自有下拉 SVG。

## Windows 实际操作

- QTest 控件路径实际触发工作区翻译、置顶、复制，设置应用，字幕停止，圈选拖动和 Esc；固定拖动准确返回 `ScreenRect(x=120, y=130, width=400, height=200)`。
- 带自动退出保护的圈选预览覆盖真实 2560×1440 主屏；曾发现孤立释放造成重复销毁和遮罩不退出，终止测试进程后修复并复验退出码 0。
- 150% 与 200% Qt 强制缩放下，工作区和设置页没有裁切；200% 圈选输出 `ScreenRect(x=240, y=260, width=800, height=400)`，证明物理坐标按 DPR 翻倍。
- 本机 `QSystemTrayIcon.isSystemTrayAvailable()` 为 `True`，图标可见，激活信号打开工作区。Computer Use 不能把任务栏通知区域识别为目标窗口，因此没有声称发送过物理托盘点击。
- 正式托盘宿主使用项目 `.venv\Scripts\pythonw.exe`。重启后在固定测试工作区选中英文并真实按 `Alt+E`，正式窗口先显示忙碌态，随后通过当前 Router 返回「好的工具用起来应该安静、快速、可靠。」；复制按钮写入完全一致的译文。本轮只为该证明发出一次真实翻译请求。

## 验证

- 完整离线套件：292 passed、2 skipped；跳过项为当前 Windows 不可用的 macOS/PyObjC 路径。
- 依赖检查：`No broken requirements found.`
- Qt 控件回归：工作区、设置、字幕、圈选和系统托盘进程均退出码 0。
- QML 与 Windows/App 定向合同包含活动组合无 Tk/pystray、QML 必需文案、单一托盘、忙碌门禁、圈选孤立释放和 package data。

## 剩余边界

Windows MVP 的管理员目标窗口 UIPI 手动复制降级不属于本次 UI 框架迁移。当日安全审查要求在风险说明之后重新取得 Requester 当前明确授权；Requester 次日接受 UAC 后已由 [Windows MVP 完成记录](./2026-09-02-windows-mvp-completion.md) 闭合，没有绕过安全门禁。
