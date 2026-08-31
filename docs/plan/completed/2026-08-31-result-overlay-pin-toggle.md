# 普通结果浮窗置顶切换计划

> 状态：已完成；普通结果浮窗支持进程内置顶切换，macOS 全屏/Space 策略随状态同步，实时字幕条保持固定置顶
>
> 创建日期：2026-08-31（Asia/Shanghai）
>
> 更新日期：2026-09-01（Asia/Shanghai）

> 后续说明：本计划只闭合窗口层级和按钮状态；macOS 普通浮窗的顶部按钮与纵向旧布局已由 [普通结果浮窗 UI 纠偏](./2026-08-31-result-overlay-ui-correction.md) 后续替换。

## 目标

让 macOS 与 Windows 的普通划词/OCR 结果浮窗默认只在新结果出现时来到前面，而不是持续压在其它窗口上方；用户需要持续查看时可以点击「置顶」，再点击「取消置顶」恢复普通窗口层级。macOS 普通态必须能进入鼠标所在显示器的全屏 Space，但失焦后应立即收起；置顶态才持续保持在所有 Space 最前。实时 OCR 字幕条继续保持置顶且不抢焦点。

## 当前依据

- 普通结果浮窗原先在 macOS 使用 `NSFloatingWindowLevel`、Windows 使用 `-topmost=True`，因此用户切换到其它窗口后结果仍持续遮挡。
- 当前工作区已有未提交候选：macOS 增加进程内 `_pinned` 状态和「置顶/取消置顶」按钮；Windows 增加同一按钮，并在每次显示时短暂置顶、`lift()` 后通过 idle 回调恢复用户选择的层级。
- 候选已同步根 README、架构、macOS/Windows 桌面设计和 Windows MVP 进度，但现有测试主要覆盖标题文案与底层层级 setter，尚未闭合按钮状态切换和再次显示行为。
- `live_overlay.py` 与 `WindowsLiveOverlayPresenter` 是独立实时字幕条路径，必须继续固定置顶，不能复用普通浮窗的可取消状态。
- 后续全屏实测发现 macOS 未置顶窗口仍无条件携带 `CanJoinAllSpaces | FullScreenAuxiliary`，所以即使 level 已恢复 normal，仍会盖在其它 App 的全屏 Space 上；集合策略必须纳入同一状态切换。
- 第一轮回归修复改用 `FullScreenNone` 后，用户双屏实测又确认副屏全屏 Space 无法弹出浮窗；恢复 `FullScreenAuxiliary` 并尝试失焦 `orderBack` 后，用户继续确认窗口仍可见。最终语义保留普通态的全屏辅助能力，但用确定的 `orderOut` 在失焦时收起。

## 范围与非目标

- 范围：macOS AppKit 普通结果浮窗、Windows Tk 普通结果浮窗、共享按钮文案、进程内状态、每次显示的前置行为和相关离线测试。
- 范围：用 Fake 窗口验证 macOS 按钮切换、窗口层级、Space/全屏集合策略和文案；用 Fake Tk runtime 验证 Windows 未置顶时 `True → idle → False`、已置顶时保持 `True`。
- 范围：在 macOS 使用 Fake 业务内容渲染普通结果浮窗，检查按钮位置、文字区可用空间和置顶/取消置顶状态，不调用翻译或 OCR。
- 非目标：把置顶选择写入 `.env`、跨进程持久化、修改普通浮窗正文语义、重做实时字幕条、修改 AppleScript fallback、安装依赖或执行 Windows 真机 GUI。

## 执行步骤

1. 回读现有候选 diff，固定普通浮窗与实时字幕条的层级边界以及进程内状态语义。
2. 补充 macOS backend 的按钮切换测试，验证状态、按钮下一动作文案、层级更新和前置动作。
3. 补充 Windows presenter 的显示序列测试，验证默认短暂前置后恢复、用户置顶后持续置顶以及按钮文案同步。
4. 使用 Fake 内容渲染 macOS 普通浮窗，在默认与置顶状态下完成原生快照和窗口 level 检查。
5. 更新计划、完成日志和文档入口，运行浮窗/字幕条/Windows UI 定向测试、完整离线套件和 `git diff --check`。
6. 根据多轮全屏实测回归，把 macOS 普通态改为 `MoveToActiveSpace | FullScreenAuxiliary`，失去 key 状态后主动 `orderOut`；首次显示或失焦后的下一次查询按鼠标所在显示器重新居中。置顶态使用 `CanJoinAllSpaces | FullScreenAuxiliary` 且失焦不收起。

## 验收条件

- 普通浮窗初始按钮为「置顶」，初始层级为普通；macOS 初始集合策略移动到当前 Space 并采用 full-screen auxiliary，新结果按鼠标所在显示器居中，能进入副屏全屏页面。失去 key 状态后主动收起，下次查询重新弹出。
- 点击「置顶」后按钮变为「取消置顶」并切换到浮动/topmost 层级；macOS 同时加入所有 Space 并在失焦时保持。再次点击恢复普通层级、当前 Space、失焦收起和「置顶」文案。
- 用户选择的置顶状态在同一 presenter/backend 生命周期内保留，但不写配置、不跨 App 重启保留。
- macOS 与 Windows 使用同一按钮文案语义；Windows 默认显示序列先 `topmost=True` 并 `lift()`，再在 idle 恢复 `False`，避免普通层级窗口无法被带到前面。
- macOS 实时字幕条继续显式使用 `pinned=True`；Windows 实时字幕条继续 `-topmost=True`，两者都不新增置顶按钮。
- 默认测试不打开真实上游、不读取剪贴板、不截屏、不注册热键；Windows 真机交互未执行时必须明确保留未验收边界。

## 授权与停止边界

- 允许：当前项目内代码、测试、文档、Fake 交互和 macOS 原生窗口预览。
- 需要额外授权：重启已安装 App、Windows 真机 GUI、真实翻译/OCR、读取选区或剪贴板、提交、推送、发布和部署。
- 出现以下情况停止：需要持久化新配置、修改实时 OCR 业务语义、引入第三方依赖、覆盖输入窗口 UI 或其它并行 WIP，或必须依赖真实 Provider 才能验证。

## 完成结果

- macOS 普通结果浮窗默认使用 `NSNormalWindowLevel` 与 `MoveToActiveSpace | FullScreenAuxiliary`，首次显示或失焦后的下一次查询按鼠标所在显示器居中并调用 `orderFrontRegardless()`；未置顶窗口失去 key 状态后 `orderOut`。点击「置顶」切到 `NSFloatingWindowLevel` 与 `CanJoinAllSpaces | FullScreenAuxiliary` 并显示「取消置顶」，再次点击恢复普通态。
- Windows 普通结果浮窗默认在显示时短暂设置 `-topmost=True` 并 `lift()`，随后通过 idle 回调恢复 `False`；用户点击「置顶」后保持 `True`，再次点击恢复默认。
- macOS/Windows 共用「置顶/取消置顶」下一动作语义，状态只保留在当前 backend/presenter 生命周期，不写配置。
- macOS 实时字幕条继续显式传入 `pinned=True`；Windows 实时字幕条继续固定 `-topmost=True`，均未增加可取消按钮。
- 任务闭合时定向普通浮窗/字幕条/Windows UI 测试 47 项通过，完整离线套件 272 项通过，`git diff --check` 通过；2026-09-01 在合并 macOS 统一工作区与 Windows 置顶候选后的当前分支复验，定向测试 56 项、完整离线套件 284 项通过，`git diff --check` 继续通过。
- macOS 沙箱外 Fake 原生验证实际识别到 2 块屏幕，确认窗口按鼠标所在屏幕居中，并走通 `normal/current-space/full-screen-auxiliary → resign/order-out → refocus → floating/all-spaces/full-screen-auxiliary`；用户随后重开 App，确认副屏全屏弹出、未置顶失焦收起和再次划词重新弹出均符合预期。Windows 真机前后层级和按钮交互仍归入 Windows MVP 桌面验收。
- 根 README、架构、macOS/Windows 稳定设计、Windows MVP 进度、文档入口、计划索引和 [完成日志](../../logs/202608/2026-08-31-result-overlay-pin-toggle.md) 已同步；任务闭合时未重启 App、调用真实上游、提交、推送或发布，提交与推送由后续独立授权执行。
