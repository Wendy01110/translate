# 实时翻译状态与结果完整性优化记录

> 日期：2026-09-22（Asia/Shanghai）

## 实际改动

- DesktopListener 对语言与不可变去重记忆取一致快照，切换目标语言后旧 OCR/翻译任务不能回写或显示结果；切换回原语言同样使旧任务失效。状态提交与切换使用短临界区，网络请求保持在锁外，实时循环继续下一轮。
- 实时 OCR 成功后的翻译遇到 timeout、http_error、HTTP 408/429/500/502/503/504 时最多补试两次，分别在前次失败完成后至少 2 秒、5 秒。相同画面复用已识别文字与来源，画面变化但文字相同保留次数和截止时间；成功、文字变化、显式重开或切语言重置相应状态，停止取消补试。
- OpenAI 兼容翻译和 OCR 共用内容与完成原因解析；翻译 finish_reason=length 返回 failure、translate_output_truncated 和空译文。OCR 后翻译仍返回 partial 并保留原文，两端共用桌面提示「译文未生成完整，请缩短原文后重试。」。
- 保留现有架构、公共端口、三种结果状态及双模型独立配置；未增加依赖或环境变量。原有浮窗失焦修改及其测试、文档保持原样。

## 验证

- 使用项目 .venv 的 Python 3.13.14；定向执行 features/test_ocr_translate、interfaces/test_listen、infrastructure/test_model_clients、interfaces/test_overlay 和 interfaces/test_live_overlay，共 120 项通过。
- 执行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider`，完整离线套件 315 项通过，1.10 秒；包含新增的 19 个测试用例（含参数化）。
- Fake 时钟覆盖两次等待边界、补试上限、相同文本的变化帧、成功后去重、非暂态错误不补试和停止；事件同步的并发测试覆盖 OCR/翻译在途切语言、切回原语言及下一轮继续；HTTP mock 覆盖非空/空/缺失正文的 length 响应及 OCR 原文保留。
- git diff --check 通过。最终复核确认已有浮窗失焦 WIP 未被覆盖，未修改真实 .env；没有新增开放 Issue。

## 文档与状态

已同步根 README、架构设计、配置设计、屏幕实时 OCR 设计、文档入口与计划索引；[本任务计划](../../plan/completed/2026-09-22-live-translation-reliability.md) 已移动至 completed，原四层 OCR 计划继续保持进行中。配置变量与结果字段未改变，.env.example 与 core 契约定义不需修改。

## 验证边界

全部调用均为 Fake 或 HTTP mock，没有真实翻译/OCR、模型下载、截屏、选区或剪贴板访问。本轮没有重启/构建 App、提交或部署；因此只能证明本地实现与离线行为，不能作为已运行 App、真机交互或上游质量验收。
