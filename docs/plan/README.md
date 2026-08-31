# 计划状态索引

> 更新时间：2026-09-01（Asia/Shanghai）

本页逐条索引全部进行中、待进行和暂时跳过计划，但只保留最近 5 项已完成计划。它不替代 `docs/README.md` 的默认入口，也不复制计划正文。状态变化时移动原计划并同步全部引用：

- `in-progress/`：正在执行；
- `pending/`：待进行，已经纳入考虑，可以开始核对现状和准备方案，但尚未实施；
- `skipped/`：暂时跳过，不属于当前上下文，默认不打开正文、不准备、不执行；只有用户明确重新纳入并将文件移至 `pending/` 后才恢复；
- `completed/`：计划目标及其约定验证已经完成。

## 进行中

- [Windows 桌面版 MVP](./in-progress/2026-08-20-windows-mvp.md)：Windows 11 x64 源码安装、划词/剪贴板恢复、三组热键、固定区域截屏、双屏 DPI 和 Router 核心链路已完成真机验证；等待实际鼠标圈选、托盘菜单、输入窗口和字幕条关闭验收。
- [本地与 API 四层 OCR 分流](./in-progress/2026-08-20-tiered-ocr-routing.md)：macOS PP-OCRv6 small、Windows 双屏 PP-OCRv6 tiny、OCR.space API 普通和 Router API 高级均有成功真测；等待两端桌面首次提醒的最终交互复验。

## 待进行

- [TTime 对照后的后续能力](./pending/2026-08-19-ttime-inspired-follow-on.md)：历史、工具栏和剪贴板监听等；菜单栏 App 与输入能力已实施，macOS 输入入口现与划词/OCR 共用翻译工作区。
- [视频字幕实时识别](./pending/2026-08-19-live-video-subtitles.md)：路径 A 的屏幕实时 OCR 已完成；本文件只留系统音频转写，本轮不实施。

## 暂时跳过

当前没有暂时跳过的计划。

## 最近完成

- [普通结果浮窗 UI 纠偏](./completed/2026-08-31-result-overlay-ui-correction.md)：macOS 菜单输入、划词和单次 OCR 已统一为同一个翻译工作区，三种原文均可编辑并可直接再译，译文只读；左上标题位已替换为目标语言栏，翻译、图钉、复制、焦点与同窗复用已完成 Fake AppKit 验证。
- [普通结果浮窗置顶切换](./completed/2026-08-31-result-overlay-pin-toggle.md)：macOS/Windows 普通浮窗支持进程内置顶切换；macOS 普通态可进入鼠标所在副屏全屏 Space 并在失焦后收起，置顶态加入所有 Space，双屏原生路径、用户全屏复验与完整离线套件均通过。
- [输入翻译窗口 UI 更新](./completed/2026-08-31-input-window-ui-refresh.md)：原独立 macOS 输入窗口曾按高保真视觉稿完成；后续已由统一「翻译」工作区取代，菜单入口继续保留但不再创建第二个窗口。
- [屏幕实时 OCR 翻译](./completed/2026-08-20-live-screen-ocr.md)：macOS 双屏圈选、动态翻译更新和再次热键停止已完成真机验收。
- [macOS 菜单栏 App](./completed/2026-08-19-macos-menu-bar-app.md)：菜单栏 `.app` 已能构建安装；用户本机试用报告基本可用。

完整已完成计划见 [completed/](./completed/)，对应完成日志见 [../logs/](../logs/)。默认索引不逐条重复历史记录；需要追溯旧状态时，再按日期打开对应文件或查看 Git 历史。
