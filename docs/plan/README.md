# 计划状态索引

> 更新时间：2026-09-04（Asia/Shanghai）

本页逐条索引全部进行中、待进行和暂时跳过计划，但只保留最近 5 项已完成计划。它不替代 `docs/README.md` 的默认入口，也不复制计划正文。状态变化时移动原计划并同步全部引用：

- `in-progress/`：正在执行；
- `pending/`：待进行，已经纳入考虑，可以开始核对现状和准备方案，但尚未实施；
- `skipped/`：暂时跳过，不属于当前上下文，默认不打开正文、不准备、不执行；只有用户明确重新纳入并将文件移至 `pending/` 后才恢复；
- `completed/`：计划目标及其约定验证已经完成。

## 进行中

- [本地与 API 四层 OCR 分流](./in-progress/2026-08-20-tiered-ocr-routing.md)：macOS PP-OCRv6 small、Windows 真实圈选 PP-OCRv6 tiny、OCR.space API 普通和 Router API 高级均有成功真测；API 高级 OCR 的 Router 思考默认关闭，macOS 实时首次提醒已改由字幕条承接，仅等待 macOS 桌面首次提醒复验。

## 待进行

- [TTime 对照后的后续能力](./pending/2026-08-19-ttime-inspired-follow-on.md)：历史、工具栏和剪贴板监听等；菜单栏 App 与输入能力已实施，macOS 输入入口现与划词/OCR 共用翻译工作区。
- [视频字幕实时识别](./pending/2026-08-19-live-video-subtitles.md)：路径 A 的屏幕实时 OCR 已完成；本文件只留系统音频转写，本轮不实施。

## 暂时跳过

当前没有暂时跳过的计划。

## 最近完成

- [Windows 桌面版 MVP](./completed/2026-08-20-windows-mvp.md)：Windows 11 x64 源码安装、Qt 工作区/设置/圈选/字幕、三组热键、普通与管理员窗口划词、双屏/DPI、四层 OCR、实时停止、Router 思考关闭和真实时延均已闭合。
- [Windows Qt 桌面 UI 迁移](./completed/2026-09-01-windows-ui-optimization.md)：活动 Windows UI 已从 Tk/ttk 与 pystray 迁移到 PySide6、Qt Quick/QML 和 `QSystemTrayIcon`；四界面、真实控件、全局 `Alt+E`、Router 译文、150%/200% 缩放、物理圈选坐标和视觉对照均已验证。
- [普通结果浮窗 UI 纠偏](./completed/2026-08-31-result-overlay-ui-correction.md)：macOS 菜单输入、划词和单次 OCR 已统一为同一个翻译工作区，三种原文均可编辑并可直接再译，译文只读；左上标题位已替换为目标语言栏，翻译、图钉、复制、焦点与同窗复用已完成 Fake AppKit 验证。
- [普通结果浮窗置顶切换](./completed/2026-08-31-result-overlay-pin-toggle.md)：macOS/Windows 普通浮窗支持进程内置顶切换；macOS 普通态可进入鼠标所在副屏全屏 Space 并在失焦后收起，置顶态加入所有 Space，双屏原生路径、用户全屏复验与完整离线套件均通过。
- [输入翻译窗口 UI 更新](./completed/2026-08-31-input-window-ui-refresh.md)：原独立 macOS 输入窗口曾按高保真视觉稿完成；后续已由统一「翻译」工作区取代，菜单入口继续保留但不再创建第二个窗口。

完整已完成计划见 [completed/](./completed/)，对应完成日志见 [../logs/](../logs/)。默认索引不逐条重复历史记录；需要追溯旧状态时，再按日期打开对应文件或查看 Git 历史。
