# 普通结果浮窗置顶切换完成日志

> 完成日期：2026-08-31（Asia/Shanghai）
>
> 计划：[普通结果浮窗置顶切换](../../plan/completed/2026-08-31-result-overlay-pin-toggle.md)

> 后续说明：本日志记录置顶语义闭合时的界面快照；macOS 顶部按钮与纵向旧布局已由 [普通结果浮窗 UI 纠偏](./2026-08-31-result-overlay-ui-correction.md) 后续替换。

## 任务边界

让 macOS 与 Windows 的普通划词/OCR 结果浮窗默认只在新结果出现时来到前面，并提供进程内「置顶/取消置顶」切换；实时 OCR 字幕条继续固定置顶。不修改业务结果、翻译/OCR 端口、配置文件或 AppleScript fallback。

## 完成内容

- 共享 `overlay_pin_button_title()` 返回下一动作：未置顶显示「置顶」，已置顶显示「取消置顶」。
- macOS `_AppKitBackend` 保存 `_pinned` 状态，按钮通过唯一复用的 Objective-C controller 调用 `toggle_pin()`；普通态使用 `NSNormalWindowLevel` 与 `MoveToActiveSpace | FullScreenAuxiliary`，置顶态使用 `NSFloatingWindowLevel` 与 `CanJoinAllSpaces | FullScreenAuxiliary`。
- macOS 首次显示或未置顶失焦后的下一次查询按鼠标所在显示器的 `visibleFrame` 居中并调用 `orderFrontRegardless()`；未置顶窗口失去 key 状态后主动 `orderOut`，置顶窗口失焦不收起。取消置顶恢复普通层级、当前 Space 和失焦收起语义。
- Windows `WindowsOverlayPresenter` 保存同一进程内状态；默认显示先临时置顶并 `lift()`，随后在 idle 恢复普通层级，用户置顶后不安排恢复回调。
- 普通浮窗增加顶部按钮空间，原文/译文分栏继续可滚动；实时字幕条沿原路径保持固定置顶且不增加按钮。
- 根 README、架构、macOS/Windows 桌面设计、Windows MVP 进度、文档入口和计划索引已同步。

## 验证结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/interfaces/test_overlay.py tests/interfaces/test_live_overlay.py tests/interfaces/test_windows_ui.py`：47 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider`：272 passed。
- macOS Fake 原生预览：默认按钮为「置顶」且 `level == NSNormalWindowLevel`；切换后按钮为「取消置顶」且 `level == NSFloatingWindowLevel`；再次切换恢复普通层级。默认与置顶快照均确认按钮未遮挡原文/译文区域。
- 后续沙箱外 Fake 原生回归实际读取到 2 块屏幕：普通态为 `MoveToActiveSpace | FullScreenAuxiliary`，窗口按鼠标所在屏幕居中；delegate 失焦路径执行 `orderOut` 后 `isVisible=false`，下一次结果恢复可见与 key 状态；通过按钮 target/action 置顶后变为 `CanJoinAllSpaces | FullScreenAuxiliary` 且失焦仍可见。用户随后重开 App，确认副屏全屏弹出、未置顶失焦收起和再次划词重新弹出均符合预期，macOS 该路径完成真机验收。
- Windows Fake presenter：默认显示顺序为 `topmost=True → lift → idle → topmost=False`；用户置顶后再次显示保持 `topmost=True` 且不安排恢复回调。
- `git diff --check`：通过。
- 2026-09-01 交付前在合并 macOS 统一工作区与 Windows 置顶候选后的当前分支复验：定向普通浮窗/字幕条/Windows UI 测试 56 passed，完整离线套件 284 passed，`git diff --check` 通过。

## 限制与未执行项

- Windows 未执行真机 GUI，因此前后层级、任务栏切换和按钮点击仍需在 Windows MVP 交互桌面验收；离线 Fake 不能替代。
- 未重启已安装 App，未调用真实翻译/OCR，未读取剪贴板、选区或业务截图，未安装依赖。
- 任务闭合时未提交、推送、发布或部署；输入翻译窗口 UI 和其它既有 WIP 均已保留，后续提交与推送状态按独立授权补记。

## 交付补记

- 2026-09-01 经后续独立授权，本实现已在保留远端 Windows 真机验收提交 `74172b3` 的前提下 rebase 为 `c0fa082`，并与 macOS 统一工作区提交 `74f2e9b`、Windows UI 后续计划提交 `a7d82cb` 一起正常推送到 `origin/main`；未使用强推，Windows 置顶按钮真机验收、部署和发布仍未执行。
