# 计划状态索引

> 更新时间：2026-08-21（Asia/Shanghai）

本页逐条索引全部进行中、待进行和暂时跳过计划，但只保留最近 5 项已完成计划。它不替代 `docs/README.md` 的默认入口，也不复制计划正文。状态变化时移动原计划并同步全部引用：

- `in-progress/`：正在执行；
- `pending/`：待进行，已经纳入考虑，可以开始核对现状和准备方案，但尚未实施；
- `skipped/`：暂时跳过，不属于当前上下文，默认不打开正文、不准备、不执行；只有用户明确重新纳入并将文件移至 `pending/` 后才恢复；
- `completed/`：计划目标及其约定验证已经完成。

## 进行中

- [Windows 桌面版 MVP](./in-progress/2026-08-20-windows-mvp.md)：Windows 11 x64 源码安装、托盘进程、设置、单实例、三组热键注册和本机 Router CLI 核心链路已完成首轮真机验证；等待热键实际触发、圈选、多屏/DPI 与实时停止验收。
- [本地与 API 四层 OCR 分流](./in-progress/2026-08-20-tiered-ocr-routing.md)：macOS PP-OCRv6 small、Windows PP-OCRv6 tiny 和 Router API 高级实图已通过；等待 Windows 桌面提醒/截屏与 OCR.space 成功真测。

## 待进行

- [TTime 对照后的后续能力](./pending/2026-08-19-ttime-inspired-follow-on.md)：历史、工具栏和剪贴板监听等；菜单栏 App 和输入框已拆出单独实施。
- [视频字幕实时识别](./pending/2026-08-19-live-video-subtitles.md)：路径 A 的屏幕实时 OCR 已完成；本文件只留系统音频转写，本轮不实施。

## 暂时跳过

当前没有暂时跳过的计划。

## 最近完成

- [屏幕实时 OCR 翻译](./completed/2026-08-20-live-screen-ocr.md)：macOS 双屏圈选、动态翻译更新和再次热键停止已完成真机验收。
- [macOS 菜单栏 App](./completed/2026-08-19-macos-menu-bar-app.md)：菜单栏 `.app` 已能构建安装；用户本机试用报告基本可用。
- [划词翻译与 OCR 翻译首期实现](./completed/2026-08-19-selection-and-ocr-implementation.md)：热键划词、热键 OCR 和浮窗已落地；用户本机试用报告基本可用。
- [默认内置翻译源与输入框翻译](./completed/2026-08-20-default-provider-and-input-box.md)：默认 `google_web`；菜单「输入翻译…」复用现有翻译端口。
- [内置网页翻译源](./completed/2026-08-19-web-translate-sources.md)：Google/Bing/DeepL 免密钥网页源；Google 补 `dt=t`，Bing 改页面 token。

完整已完成计划见 [completed/](./completed/)，对应完成日志见 [../logs/](../logs/)。默认索引不逐条重复历史记录；需要追溯旧状态时，再按日期打开对应文件或查看 Git 历史。
