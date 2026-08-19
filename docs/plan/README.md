# 计划状态索引

> 更新时间：2026-08-20（Asia/Shanghai）

本页逐条索引全部进行中、待进行和暂时跳过计划，但只保留最近 5 项已完成计划。它不替代 `docs/README.md` 的默认入口，也不复制计划正文。状态变化时移动原计划并同步全部引用：

- `in-progress/`：正在执行；
- `pending/`：待进行，已经纳入考虑，可以开始核对现状和准备方案，但尚未实施；
- `skipped/`：暂时跳过，不属于当前上下文，默认不打开正文、不准备、不执行；只有用户明确重新纳入并将文件移至 `pending/` 后才恢复；
- `completed/`：计划目标及其约定验证已经完成。

## 进行中

- [划词翻译与 OCR 翻译首期实现](./in-progress/2026-08-19-selection-and-ocr-implementation.md)：热键按键码注册、`Ctrl+C` 可退出、精简浮窗与 Vision 优先 OCR 已落地；真实热键和截屏验收尚未执行。
- [macOS 菜单栏 App](./in-progress/2026-08-19-macos-menu-bar-app.md)：菜单栏 `.app` 已能构建安装；真实权限和热键验收未执行。

## 待进行

- [TTime 对照后的后续能力](./pending/2026-08-19-ttime-inspired-follow-on.md)：输入框、历史、工具栏和剪贴板监听等；菜单栏 App 已拆出单独实施。
- [视频字幕实时识别](./pending/2026-08-19-live-video-subtitles.md)：先做字幕条有界 OCR，再评估系统音频转写；本轮不实施。

## 暂时跳过

当前没有暂时跳过的计划。

## 最近完成

- [内置网页翻译源](./completed/2026-08-19-web-translate-sources.md)：Google/Bing/DeepL 免密钥网页源；Google 补 `dt=t`，Bing 改页面 token。
- [官方翻译源接入](./completed/2026-08-19-official-translate-sources.md)：DeepL / Microsoft / Google 官方 API 与 OpenAI 兼容源切换。
- [项目框架与文档体系搭建](./completed/2026-08-19-project-framework-bootstrap.md)：建立文档框架、双模型配置、用例边界、CLI `config-check` 和离线测试，并形成首次 Git 提交。

完整已完成计划见 [completed/](./completed/)，对应完成日志见 [../logs/](../logs/)。默认索引不逐条重复历史记录；需要追溯旧状态时，再按日期打开对应文件或查看 Git 历史。
