# 计划状态索引

> 更新时间：2026-10-06（Asia/Shanghai）

本页逐条索引全部进行中、待进行和暂时跳过计划，但只保留最近 5 项已完成计划。它不替代 `docs/README.md` 的默认入口，也不复制计划正文。状态变化时移动原计划并同步全部引用：

- `in-progress/`：正在执行；
- `pending/`：待进行，已经纳入考虑，可以开始核对现状和准备方案，但尚未实施；
- `skipped/`：暂时跳过，不属于当前上下文，默认不打开正文、不准备、不执行；只有用户明确重新纳入并将文件移至 `pending/` 后才恢复；
- `completed/`：计划目标及其约定验证已经完成。

## 进行中

- [本地与 API 四层 OCR 分流](./in-progress/2026-08-20-tiered-ocr-routing.md)：macOS PP-OCRv6 small、Windows 真实圈选 PP-OCRv6 tiny、OCR.space API 普通和 Router API 高级均有成功真测；API 高级 OCR 的 Router 思考默认关闭，macOS 实时首次提醒已改由字幕条承接，仅等待 macOS 桌面首次提醒复验；2026-09-05 完成代码复核、桌面服务重复构造收口和已退出输入窗口清理。

## 待进行

- [TTime 对照后的后续能力](./pending/2026-08-19-ttime-inspired-follow-on.md)：历史、工具栏和剪贴板监听等；菜单栏 App 与输入能力已实施，macOS 输入入口现与划词/OCR 共用翻译工作区。
- [视频字幕实时识别](./pending/2026-08-19-live-video-subtitles.md)：路径 A 的屏幕实时 OCR 已完成；本文件只留系统音频转写，本轮不实施。

## 暂时跳过

当前没有暂时跳过的计划。

## 最近完成

- [项目复核、异常响应收口与 Git 交付](./completed/2026-10-06-project-review-and-git-delivery.md)：审阅并提交累积稳定性修复，补齐全部翻译与 API 高级 OCR 的过深 JSON、DeepL 响应类型失败；完整离线 534 项、文档 6 项、CLI 静态回读和依赖检查通过，代码已推送并回读 SHA；macOS 真机验收仍在原 OCR 计划中等待授权。
- [OCR.space 异常响应与自动降级](./completed/2026-10-05-ocr-space-response-failures.md)：普通层异常状态字段与过深 JSON 稳定失败，自动模式继续高级并只翻译其文字，强制普通模式停止；定向 69 项、完整离线 520 项通过，真实提供方与桌面未在本轮验收。
- [OCR 多页输入边界](./completed/2026-10-03-ocr-batch-input-bounds.md)：单次最多 10 页与合计 20 MiB，CLI 首次超限停止继续读文件，用例/路由/四层适配在初始化/编码/请求前共同拒绝；定向 184 项、完整离线 498 项通过，真实桌面与提供方未在本轮验收。
- [划词系统命令失败归类](./completed/2026-10-03-selection-command-failures.md)：macOS 剪贴板与模拟复制的启动、超时、编解码失败进入既有界面错误结果，覆盖恢复失败和故障解除后再次触发；定向 78 项、完整离线 436 项通过，真实桌面与剪贴板未在本轮验收。
- [实时 OCR 圈选会话隔离](./completed/2026-10-03-live-picker-lifecycle.md)：圈选代次提前预留，旧回调和旧启动不影响重开会话，设置应用取消未完成圈选；桌面相关 108 项、完整离线 407 项通过，真实桌面与模型未在本轮验收。

完整已完成计划见 [completed/](./completed/)，对应完成日志见 [../logs/](../logs/)。默认索引不逐条重复历史记录；需要追溯旧状态时，再按日期打开对应文件或查看 Git 历史。
