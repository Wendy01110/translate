# macOS 原生 OCR 首次提醒验收

> 日期：2026-10-06（Asia/Shanghai）

## 结果与改动

Requester 要求“先验证好，然后更新好文档，然后看看项目要如何继续优化和精简一下”，本轮先继续此前准备的 macOS 隔离原生验收。普通 OCR 与实时 OCR 均准确识别合成英文，首次提醒各触发一次，实时路径未打开普通翻译窗口。

原生绘制发现实时字幕条把普通工作区的长提醒截成一行，后半段不可见。`paddle_first_load_message()` 新增仅供紧凑视图使用的文案选择；App 组合入口在实时路径使用「本地 OCR 首次加载中，请稍候…」，普通工作区保留所选模型、可能下载与后续复用说明。没有改变 OCR 路由、客户端、配置、依赖或窗口尺寸。

## 实际验证

- 使用项目 `.venv` 的 Python 3.13.14、PaddleOCR 3.7.0 与 PaddlePaddle 3.3.0，从现有官方缓存加载 PP-OCRv6 small 检测与识别模型；合成 720×170 白底英文图片，原文为 `LOCAL OCR REMINDER CHECK 2026`。
- 进程内阻止 socket 连接，禁用模型源检查并显式传入缓存模型目录；翻译使用 Fake 端口，捕图/圈选使用合成输入，不读取屏幕或剪贴板，不调用任何外部 OCR/翻译、不下载模型、不修改真实 `.env`。
- 原生 `NSMenu.performActionForItemAtIndex_()` 通过项目菜单 controller 分别触发普通与实时监听器，再进入真实 `PaddleOcrEngine` 与原生 presenter。两种路径都准确识别原文，各提醒一次；普通窗口显示完整说明，实时提醒和结果均留在字幕条。
- 在最小 280 宽度下检查字幕文字的原生 cell 尺寸不超过可见区域，并把窗口内容自行绘制成 PDF/PNG 回读，确认短提示和结果完整显示；没有截取桌面屏幕。原先透明文字图在黑色预览背景下看似空白，复核 alpha 与白底原生绘制后确认实际问题是长文裁切。
- 默认沙箱中的 AppKit 注册曾以 SIGABRT 退出，堆栈停在 `_RegisterApplication` / `NSApplication.sharedApplication`，尚未初始化模型；同一隔离验收以受控工具许可在原生会话中执行后成功，未重启已有 App 或服务。
- 新提醒合同在修改实现前复现 2 项失败；修复后 App、普通/实时 presenter 与 Paddle 定向测试 63 项通过，完整 Python 离线套件 535 项通过。`pip check` 无依赖冲突，`git diff --check` 通过。

隔离验收输出位于临时目录 `/private/tmp/ai-translate-review-20261006-native/`；临时脚本与图片未加入仓库。它们是本次验证辅助材料，长期结论保存在本文与对应计划中。

## 文档与状态

同步用户 README、OCR 分流设计、屏幕实时 OCR 设计、文档入口、计划索引和原四层 OCR 计划；原计划移至 [completed](../../plan/completed/2026-08-20-tiered-ocr-routing.md)，所有相关链接同步移动。开放 Issue 目录没有条目，本轮无需关闭 Issue。

本轮证明当前源码的菜单 action、真实本地 OCR 与原生提醒绘制链路可用；没有把程序化菜单 action 写成物理点击，也没有复验安装 App 的热键、真实截屏、跨应用/全屏、双屏或外部提供方。那些边界与已有历史证据分别保留，不作为本次结果。
