# Windows Qt 桌面 UI 迁移计划

> 状态：已完成
>
> 创建日期：2026-09-01（Asia/Shanghai）
>
> 完成日期：2026-09-01（Asia/Shanghai）

## 目标

在不改变翻译、OCR、配置和热键业务语义的前提下，把 Windows 11 x64 界面层从 Tk/ttk 与 pystray 迁移到 PySide6、Qt Quick 和 QML，统一普通翻译工作区、设置、逐屏圈选、实时字幕条和系统托盘体验。

Requester 已明确选择更换框架，并授权项目依赖、代码、文档、Windows 界面、真实翻译/OCR、App 重启、测试、Git 提交与推送。本计划不打包、不签名、不发布安装包，也不改变翻译 Provider、四层 OCR、公共结果或配置字段。

## 完成内容

- `pyproject.toml` 增加 Windows 平台限定的 PySide6 和 QML package data，删除 pystray 依赖；活动源码不再导入 Tk、ttk 或 pystray。
- `interfaces/windows_qt.py` 提供唯一 `QApplication`、`QQmlEngine`、有界跨线程 UI 队列、QML 对象生命周期、剪贴板、原生窗口层级、逐屏物理坐标、Presenter 和 `QSystemTrayIcon`。
- `Workspace.qml` 让托盘输入、划词和单次 OCR 共用 800×560 工作区；原文可编辑、译文只读，目标语言、翻译、置顶、复制和 `Ctrl+Enter` 共用同一状态门禁。
- `Settings.qml` 使用左侧三项导航、可滚动正文和固定底部动作区；密钥遮挡，「应用」保持打开，「保存」成功后隐藏。
- `RegionOverlay.qml` 为每块物理显示器提供深色遮罩、透明选区、蓝色边框、端点、尺寸反馈和 Esc；逻辑像素通过 `devicePixelRatio` 换成全局物理像素。
- `LiveOverlay.qml` 提供不抢焦点的置顶字幕条，明确原文、译文、来源和停止动作，并按内容与 DPI 有界增高。
- `QSystemTrayIcon` 保留划词、截图、实时开停、工作区、设置和退出；左键激活打开工作区。`QApplication` 关闭最后一个普通窗口后仍保持托盘宿主运行。
- 旧 Windows Tk presenter、Tk 运行时、Tk 样式模块和 pystray 组合已删除；`interfaces/windows_desktop.py` 只保留热键和物理屏幕纯函数，`windows_views.py` 仅保留兼容导出。
- 四张概念图、四张真实 Qt 客户区实现快照、设计 token、响应式布局、无障碍对象和对照偏差已写入 [Windows Qt 界面规范](../../design/windows-qt-ui.md)。

## 缺陷修复

- 首轮 `Segoe UI Variable` 在中文字符上产生不一致回退，最终统一为 `Microsoft YaHei UI`。
- Qt 平台组合框与自定义指示叠出双箭头，已改为单一项目 SVG。
- QML 根对象曾随临时 `QQmlComponent` 回收，现由运行时持有 component 并设置 C++ ownership。
- 动态 QML 信号不能按普通 Python 属性连接，现统一通过 Qt 元对象签名连接。
- 圈选启动时收到孤立鼠标释放会错误取消并进入重复销毁，现先登记会话和首块屏幕再显示，只有先收到按下才处理释放，窗口销毁也先检查 Shiboken 对象有效性。

## 验证

- 真实 Qt 渲染快照：工作区 800×560、设置 780×680、字幕条 720×146、区域选择 2560×1440；翻译和设置窗口另由 Windows Computer Use 读取到完整无障碍树。
- QTest 真实控件回归：工作区翻译、置顶和复制；设置应用；字幕停止；圈选 `120,130 → 520,330` 返回 `ScreenRect(x=120, y=130, width=400, height=200)`；Esc 返回 `None`。
- Qt 150% 与 200% 强制缩放下分别重渲染工作区和设置页，客户区按 1200×840 / 1600×1120 与 1170×1020 / 1560×1360 物理像素完整输出；200% 圈选把逻辑拖动映射为 `ScreenRect(x=240, y=260, width=800, height=400)`，没有控件裁切或坐标少乘 DPI。
- 真实 `QSystemTrayIcon`：`isSystemTrayAvailable() == True`、图标 `isVisible() == True`，激活信号调用工作区入口。当前安全自动化工具不能把任务栏通知区域作为目标窗口，因此没有声称发送过物理托盘点击。
- 正式 `pythonw.exe` 托盘宿主重启后，从固定测试文字真实触发全局 `Alt+E`，先显示忙碌态，再通过当前 Router 返回「好的工具用起来应该安静、快速、可靠。」；复制按钮写入完全一致的译文。
- 本轮完整离线套件为 292 passed、2 skipped；跳过项均为当前 Windows 不可用的 macOS/PyObjC 路径。`pip check` 为 `No broken requirements found.`，定向 QML/Windows/App 测试和 `git diff --check` 通过。

## 视觉对照结论

- 冷白底、白色内容面、浅灰边框、钴蓝强调、无衬线字体和 8/12 像素圆角与概念一致。
- 工作区保留目标语言、三项动作、原文、译文和状态；实现把快捷键提示从概念顶栏移到底部状态行，以适配 800 像素宽客户区。
- 设置保留左侧导航、右侧字段和固定底部动作；实现减少概念稿留白以支持高 DPI 小屏。
- 字幕条与圈选器保留概念的信息层级、置顶/不抢焦点和深色遮罩语义；真实短句字幕条按内容收紧高度。
- 概念图没有作为静态界面素材；全部交互由 QML 控件实现并进入 Windows 无障碍树。

## 非目标与剩余边界

- 未生成 MSIX、未签名、未发布、未增加深色主题、历史、TTS、划词工具栏或剪贴板监听。
- Windows MVP 计划中的管理员窗口 UIPI 真实降级不属于 UI 框架迁移本身；Requester 后续在风险说明后明确授权并接受 UAC，已由 [Windows MVP 完成记录](../../logs/202609/2026-09-02-windows-mvp-completion.md) 闭合。
