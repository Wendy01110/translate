# 跨平台桌面与四层 OCR 源码候选

> 记录日期：2026-08-21（Asia/Shanghai）
>
> 计划：[屏幕实时 OCR 翻译](../../plan/in-progress/2026-08-20-live-screen-ocr.md)、[Windows 桌面版 MVP](../../plan/in-progress/2026-08-20-windows-mvp.md)、[本地与 API 四层 OCR 分流](../../plan/in-progress/2026-08-20-tiered-ocr-routing.md)

## 本次边界

把当前已经实现的 Windows 桌面源码候选、四层 OCR 分流、PaddleOCR 首次加载提醒和 macOS 应用图标整理为可提交状态，并同步配置、用户文档、稳定设计和进行中计划。三项计划仍保留在 `in-progress/`，不以 macOS 离线证据替代 Windows 真机或真实桌面验收。

## 已同步内容

- Windows 11 x64 源码候选包含系统托盘、全局热键、Unicode 文本剪贴板、区域圈选与截屏、普通浮窗、实时字幕条、设置、输入窗口、单实例和 PowerShell 安装入口；平台组合继续复用现有划词、OCR 与翻译用例。
- OCR 明确分为 macOS Vision 本地普通、可选 PP-OCRv6 本地高级、OCR.space API 普通和现有视觉模型 API 高级四层；Windows 暂无本地普通层。配置、`config-check`、两端设置页、README 和稳定设计已经同步。
- PP-OCRv6 提供 `tiny`、`small`、`medium` 三档并保持懒加载；桌面端在每个新引擎实例首次真正初始化前显示一次提醒，普通图片 CLI 不弹桌面提醒。
- macOS 构建已接入可编辑 SVG、标准 iconset 和 `AppIcon.icns`，`Info.plist` 与构建脚本使用同一图标资源。

## 验证结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider`：`249 passed in 0.79s`。
- 文档同步后定向运行 `tests/docs/test_documentation_structure.py`：`6 passed in 0.01s`；`git diff --check` 通过。
- `.venv/bin/python -m pip check`：`No broken requirements found`。
- `plutil -lint macos/Info.plist` 与 `bash -n scripts/build-macos-app.sh` 通过；`sips` 回读 `AppIcon.icns` 为 `1024 × 1024` 的 ICNS。
- 上述结果是项目 Python 3.13.14 arm64 环境中的离线证据；默认测试没有读取真实剪贴板、截屏、下载模型或调用外部 OCR/翻译上游。

## 限制与未执行项

- 尚未在 Windows 11 x64 真机执行依赖安装、托盘、热键冲突、UIPI、单/多屏 DPI、圈选、截屏、设置、实时停止或真实模型验收，因此 Windows 候选不能声明可用或已发布。
- 尚未完成 macOS 实时 OCR 重启后交互复验、Paddle `tiny` 首次提醒界面与实际时延验收，也未在本次记录中调用 OCR.space、API 高级 OCR 或翻译上游。
- 本次只交付源码、文档与 Git 历史，不执行部署、发布或服务重启。
