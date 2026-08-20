# 桌面热键设计

本文适用于 macOS 本机常驻的划词翻译和 OCR 翻译，面向实现者。某次辅助功能授权状态和一次热键实调结果不属于本文。

## 目标与非目标

- 目标：用可配置热键分别触发划词翻译、单次区域截屏 OCR 翻译，以及锁定区域后的实时 OCR 翻译。
- 目标：复用现有 `SelectionTranslateService` 与 `OcrTranslateService`，不把热键层做成第二套翻译语义。
- 非目标：在本文复制 Windows 热键、托盘和坐标规则；Windows 以 [Windows 桌面设计](./windows-desktop.md) 为准。划词工具栏、剪贴板监听和开机启动仍见待进行计划。输入翻译由菜单打开，不占用热键。
- 非目标：在未按热键且未开始实时循环时读取选区、截屏或调用上游。

## 权威来源

| 内容 | 权威位置 |
| --- | --- |
| 热键字符串 | `.env.example` 的 `HOTKEY_SELECTION` / `HOTKEY_OCR` / `HOTKEY_LIVE_OCR` 与 `config.py` |
| 选区读取 | `infrastructure/selected_text.py` |
| 区域截屏 | `infrastructure/screenshot.py` |
| 实时 OCR | [屏幕实时 OCR](./live-screen-ocr.md) |
| 浮窗 | `interfaces/overlay.py`、`interfaces/live_overlay.py` |
| 常驻入口 | `AI Translate.app` 与 `ai-translate app`；终端调试仍可用 `ai-translate listen` |
| 设置页 | `interfaces/settings.py`，保存走 `resolve_env_path()` 选出的那一个文件里允许的键。「应用」写入后不关窗口，「保存」写入后关闭。菜单「设置…」在跟踪结束后，用已保留的菜单控制器 `performSelector:afterDelay:` 打开窗口；不得使用 `AppHelper.callLater`，它在 `NSApp.run()` 下定时器目标会被回收，窗口不会出现。热键控件只录制，不提供文本框。 |

## 核心约束

- 默认热键：划词 `alt+e`，OCR `alt+w`，实时 OCR `alt+q`。书写形式为 `修饰键+键`，修饰键为 `alt`/`option`、`ctrl`、`shift`、`cmd`。设置页点击热键按钮后按下组合键录制；Esc 取消；必须带修饰键；三组热键不得录成同一组。
- 热键按 macOS 物理键码注册，不得按 Option 会产生的字符（例如 `´`、`∑`）去匹配。
- `listen` 的事件循环必须回到 Python，使终端 `Ctrl+C` 能结束进程；不得使用会吞掉 `SIGINT` 的 `NSApplicationMain`。菜单栏 App 使用 `NSApplication.run`，用菜单「退出」结束。
- 划词在已授权辅助功能时，先等 Option 等修饰键松开，再模拟 Command+C。未授权且剪贴板为空时，浮窗和菜单必须提示去开辅助功能，不得只显示 `empty_text`。剪贴板已有文字时仍可翻译剪贴板。
- 模拟复制优先用 Quartz 发送 Command+C，避免再走 `osascript` / System Events 的自动化权限。不得把用户原剪贴板内容留给下游，也不得在日志中写下选区全文。
- OCR 热键只截取用户圈选的区域，使用系统 `screencapture -i`；用户取消视为 `screenshot_cancelled`，不调用 OCR。
- 实时 OCR 热键先在 AppKit 主线程异步拖拽圈定矩形，不得用手写 `NSRunLoop` 轮询阻塞主线程；圈选中再次按下同一热键会取消圈选。取消或区域过小不截屏。运行中再次按下同一热键、点菜单「停止实时翻译」或关闭字幕条都会结束循环。字幕条放在矩形外侧，更新时不得把应用抢到前台。
- 热键处理必须串行：上一次未结束时忽略新触发，避免重复付费调用。实时循环占用自己的运行标志，不得与另一次实时循环并行；单次划词仍可进行。
- 浮窗是精简卡片：标题、原文、译文。可选中复制，不放按钮、历史或设置。原文和译文各自可滚动，窗口可拉大，不得用固定高度裁掉正文。标题可带「本机」或「模型」脚注。不展示密钥或原始图片。菜单栏 App 是 `LSUIElement`，浮窗必须 `hidesOnDeactivate=false`，否则会刚弹出就被系统藏掉。NSPanel 必须 `becomesKeyOnlyIfNeeded=false`，否则点选只读文本不会成为 key window，`Command+C` 进不了浮窗。应用要安装隐藏的 Edit 菜单，把 `Command+C` / `Command+A` 接到 `copy:` / `selectAll:`。未选中时 `copy:` 复制当前栏全文。已有浮窗只更新内容，不得再次 `center()` 成新窗口。划词必须先读选区，再弹出或更新浮窗，避免模拟复制打到自己身上。
- `listen` 和菜单栏 App 只在 macOS 上运行。启动时不调用上游。
- 菜单栏 App 必须是带 `LSUIElement` 的 `.app`，主进程是包内可执行文件，不得 `exec` 成系统 `python3`，否则辅助功能仍会记到 Python。本机只安装一份到 `~/Applications/AI Translate.app`。
- AppKit 的 `NSObject` 子类必须使用唯一类名，并且整个进程只注册一次；不得在窗口构造时反复定义 `_Controller`，否则第二次打开设置会报 `overriding existing Objective-C class`。

## 主流程

划词：

```text
热键 alt+e
  -> 选区文本来源（此时不得抢焦点）
  -> 浮窗显示 translating
  -> SelectionTranslateService
  -> 同一浮窗更新结果，不重新居中
```

OCR：

```text
热键 alt+w
  -> 系统圈选截屏
  -> 取消则停止
  -> 浮窗显示 translating
  -> OcrTranslateService
  -> 浮窗展示结果
```

实时 OCR：

```text
热键 alt+q
  -> 若已在运行则停止
  -> 拖拽圈选矩形
  -> 取消则停止
  -> 字幕条显示识别中
  -> 有界循环：固定矩形截屏 -> advance_live -> 更新字幕条
  -> 再次热键或关闭字幕条停止
```

## 系统权限

- 全局热键走系统 `RegisterEventHotKey`，不需要辅助功能。这是 Alfred、Bob、Easydict 同类工具的常用做法。
- 辅助功能只用于“自动复制当前选区”。未授权时 `Option+E` 改为翻译剪贴板（先 `Command+C` 再按热键）。授权对象是 `AI Translate`；终端调试 `listen` 时才是 Cursor 或终端，不是 `python3`。
- 屏幕录制：`screencapture` 读取单次圈选像素；实时 OCR 读取锁定矩形的像素。两者都不依赖辅助功能，授权对象同样是 `AI Translate`。

未授权时不得反复弹系统权限框：菜单栏 App 启动时最多提示一次，之后用浮窗和菜单说明。`Ctrl+C` 结束 `listen`。菜单栏用「退出」。

## 变更与验证要求

- 修改热键名或默认值时，同步 `.env.example`、`config.py`、`config-check`、本文和 README。
- 选区与截屏逻辑必须可注入剪贴板、复制动作和 `screencapture`，默认测试不得按真实热键或截屏。
- 不得在测试或文档中写入真实选区、截屏或密钥。
