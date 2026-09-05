# 代码与文档复核及冗余收口

> 日期：2026-09-05（Asia/Shanghai）

## 范围

在 `git pull --ff-only` 确认远端已是最新后，按当前四层 OCR 计划复核配置、分流、桌面组合、CLI、测试和维护文档；保留本地未推送提交与工作区边界，不调用真实模型、截屏或上游接口。

## 改动

- 删除 `ocr_routing.py` 中没有调用方的 `build_ocr_engine()` 转发工厂，以及 `ocr_client.py` 中未使用的 `chat_completions_url` 导入。
- 删除已退出运行时且没有生产代码引用的 `interfaces/input_box.py` 及其专属测试；保留历史计划、日志和视觉稿作为当时决策与验收记录。
- 把 macOS 与 Windows 重复的设置保存、运行时重建和目标语言同步逻辑合并为 `app.py` 的 `_save_preferences()`。
- 桌面 `app` / `listen` 路径只保留桌面入口需要的服务和来源；CLI OCR、翻译与选择服务不再在同一进程中额外重复构造。macOS 的来源和截屏对象也在组合阶段复用同一实例。
- 把运行时与 Windows UI 分流改为只看第一个 CLI 子命令，避免文字内容或图片文件名为 `app` / `listen` 时误构造桌面服务。
- 配置设计中的就绪判定入口改为实际用于 `config-check` 的 `config_status()` 与 `Settings.ocr_capability_ready()`，避免把只覆盖 API 配置的 `Settings.ocr_ready` 描述成四层总状态。
- 更新 `tests/test_app.py` 的源码审查断言，使其验证共享保存函数而不是绑定已删除的重复闭包。
- 配置校验直接使用 `OCR_IMAGE_MODES`、`OCR_ENGINES` 和 `PADDLE_OCR_MODEL_TIERS`，移除同文件内没有外部调用方的私有别名。

## 验证

- `git pull --ff-only`：Already up to date。
- 定向测试：`77 passed`。
- 完整离线测试：`296 passed`（删除旧输入窗口专属测试 9 项；清理前为 `305 passed`）。
- `.venv/bin/python -m pip check`：`No broken requirements found`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall -q src tests`：通过。
- `git diff --check`：通过。

## 边界

已获用户授权在完整验证后提交本次整理；不推送、不重启桌面 App、不调用真实翻译/OCR、不做 macOS 点击级首次提醒复验，四层 OCR 计划继续保持进行中。
