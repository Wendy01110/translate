# 桌面热键设计

本文适用于 macOS 本机常驻的划词翻译和 OCR 翻译，面向实现者。某次辅助功能授权状态和一次热键实调结果不属于本文。

## 目标与非目标

菜单「历史记录…」在菜单跟踪结束后沿用保留的控制器延迟打开独立历史窗口；复用记录回到现有工作区，不增加热键或触发模型请求，保存规则见[本地翻译历史](./translation-history.md)。

- 目标：用可配置热键分别触发划词翻译、单次区域截屏 OCR 翻译，以及锁定区域后的实时 OCR 翻译。
- 目标：复用现有 `SelectionTranslateService` 与 `OcrTranslateService`，不把热键层做成第二套翻译语义。
- 非目标：在本文复制 Windows 热键、托盘和坐标规则；Windows 以 [Windows 桌面设计](./windows-desktop.md) 为准。划词工具栏、剪贴板监听和开机启动仍见待进行计划。输入翻译由菜单打开同一个翻译工作区，不占用全局热键；窗口内 `Command+Return` 只执行当前原文的文本翻译。
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
- `pbpaste` / `pbcopy` 分别保持 2 秒超时，Quartz 不可用时的 `osascript` 保持 5 秒超时；命令非零退出、启动失败、超时及文本编解码失败分别归入 `clipboard_read_failed`、`clipboard_write_failed` 或 `copy_simulation_failed`，界面只展示既有提示，错误结果不包含原始命令输出，普通 traceback 不展示原始异常链。模拟复制路径仍在 `finally` 恢复原剪贴板，恢复失败明确报告写入失败；任一步失败都不调用翻译，故障解除后可再次触发。
- OCR 热键只截取用户圈选的区域，使用系统 `screencapture -i`；用户取消视为 `screenshot_cancelled`，不调用 OCR。
- 实时 OCR 热键先在 AppKit 主线程异步拖拽圈定矩形，不得用手写 `NSRunLoop` 轮询阻塞主线程；圈选中再次按下同一热键会取消圈选。取消或区域过小不截屏。运行中再次按下同一热键、点菜单「停止实时翻译」或关闭字幕条都会结束循环。字幕条放在矩形外侧，更新时不得把应用抢到前台。
- 取消后重开只接受本轮圈选结果；已经排队的旧启动和旧回调都按会话代次丢弃。应用设置会取消待完成圈选并停止实时循环，需要重新圈选开始；工作区目标语言栏切换继续当前循环。会话规则见 [屏幕实时 OCR](./live-screen-ocr.md)。
- 热键处理必须串行：上一次未结束时忽略新触发，避免重复付费调用。实时循环占用自己的运行标志，不得与另一次实时循环并行；单次划词仍可进行。
- macOS 翻译工作区是菜单输入、划词和单次 OCR 共用的精简窗口：`app.py` 只创建一个 `OverlayPresenter` / `NSPanel`，默认内容区 720×520，使用真白背景、冷灰圆角文本区和系统字体；宽度不小于 640 时原文/译文左右并排，低于阈值时上下排列。内容区不显示独立的「翻译」大标题；标题行左侧直接放置「目标语言」标签与原生下拉栏，宽屏下拉宽 120，紧凑布局缩为 104，来源脚注使用其与右侧动作之间的剩余空间，省下的第二行用于增高文本区。选项直接复用设置页的中文、英语、日语、韩语；自定义当前代码不在固定选项中时追加原值显示。切换只调用 `DesktopListener.set_target_lang()`，不自动请求、不写配置；下一次菜单输入、划词、单次 OCR、实时 OCR 或手动再译使用新目标。目标变化时清空实时 OCR 去重记忆，确保相同识别文字会按新目标重新翻译；设置页保存后同时同步 listener 与栏位。菜单输入会清空两栏并把焦点放到原文；划词和 OCR 填入各自结果，OCR 来源脚注保留。三种入口的原文均启用编辑、粘贴与撤销，所有译文只读；编辑本身不自动重新翻译，标题区在图钉左侧显示 72×32 的蓝紫「翻译」按钮，点击或按 `Command+Return` 都把当前原文交给组合入口注入的 `DesktopListener.handle_typed_text`，后台线程完成后在主线程更新当前译文和翻译来源脚注。翻译中按钮改为「翻译中…」并与目标语言栏一同禁用，避免重复请求或中途改变语义；加载提示等临时状态保持只读并隐藏翻译按钮。标题区另并排放置 32×32 的图钉与复制译文图标，不保留底部动作栏，也不放历史、设置、可见快捷键提示或额外诊断。图钉默认使用浅蓝紫底 `pin`，置顶后切成蓝底白色 `pin.fill`；复制使用轻灰底 `doc.on.doc`，只复制当前译文，成功后以浅蓝紫底 `checkmark` 显示 1.2 秒再恢复。三个按钮都保留原生 momentary 按压态。未置顶时使用 `NSNormalWindowLevel` 与 `NSWindowCollectionBehaviorMoveToActiveSpace | NSWindowCollectionBehaviorFullScreenAuxiliary`，首次显示或失焦后的下一次查询按鼠标所在 `NSScreen.visibleFrame` 居中，因此可以进入副屏全屏 Space；窗口失去 key 状态后保留可见性，由普通窗口层级允许其它窗口覆盖，不主动 `orderOut`；仅记录下一次查询需要重新前置。点击图钉后切为 `NSFloatingWindowLevel` 与 `NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorFullScreenAuxiliary`，失焦时不收起；取消置顶恢复普通层级、当前 Space 与失焦后保留在后台的行为。置顶状态只在当前进程内保存，不写入配置。原文和译文可选中复制、各自滚动，窗口可拉大，不得用固定高度裁掉正文。不展示密钥或原始图片。菜单栏 App 是 `LSUIElement`，窗口必须 `hidesOnDeactivate=false` 且 `becomesKeyOnlyIfNeeded=false`；应用安装隐藏的 Edit 菜单，把 `Command+C` / `Command+A` 接到 `copy:` / `selectAll:`，未选中时 `copy:` 复制当前栏全文。失焦后的下一次查询可跟随鼠标切换显示器并重新前置；划词必须先读选区，再弹出或更新窗口，避免模拟复制打到自己身上。实时字幕条继续保持独立浮动路径，确保锁定区域翻译期间可见。
- `listen` 和菜单栏 App 只在 macOS 上运行。启动时不调用上游。
- macOS 工作区与实时字幕条共用原生文本复制行为：有选区时只复制选中文字，无选区时复制当前栏全文。AppKit 的 `NSRange` 按 UTF-16 code unit 计数，复制辅助函数按同一单位截取，确保 emoji 及其后的文字不会错位；复制内容仍通过现有纯文本写入路径处理。
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
