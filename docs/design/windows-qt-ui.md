# Windows Qt 界面规范

本文定义 Windows 桌面界面的视觉、布局和交互约束。业务状态、配置字段和屏幕坐标仍分别以公共结果契约、配置设计和 [Windows 桌面设计](./windows-desktop.md) 为准。

## 框架选择

Windows 活动界面使用 PySide6、Qt Quick 和 QML。Qt 提供单一事件循环、原生 HWND、系统托盘、键盘焦点、无障碍树、Per-Monitor DPI 和可组合控件；QML 负责视觉与交互，Python Presenter 只投递已经格式化的状态并连接业务回调。

Tk/ttk 与 pystray 不再参与活动 Windows 组合，也不保留运行时回退。项目不引入 Electron、WebView、第三方 QML 主题、外部图标包或第二套前端状态模型。

## 视觉方向

- 整体使用冷白窗口底、白色内容面、浅灰边框和钴蓝主色，避免厚重卡片、渐变背景、玻璃拟态和装饰性侧栏。
- 中文和拉丁文本统一使用 `Microsoft YaHei UI`，让 Qt 在 Windows 上稳定得到无衬线中文；标题只使用两级字号和 DemiBold，不用超大营销标题。
- 主色只用于主要动作、焦点、选中导航和圈选边框；普通按钮保持白底，危险色只用于错误状态。
- 工作区保持开放式双文本面，不增加历史、收藏、模型诊断或额外工具栏；设置页只显示现有配置字段。
- 图标使用项目内 SVG，尺寸为 18～25 逻辑像素；按钮仍提供明确文字，不依赖图标猜测语义。

## 设计 token

| Token | 值 | 用途 |
| --- | --- | --- |
| Window | `#F7F9FC` | 主窗口和设置正文底色 |
| Surface | `#FFFFFF` | 文本区、字段和字幕条 |
| Muted surface | `#F2F5F9` | Hover、禁用和次级面 |
| Primary text | `#151A23` | 标题、正文和按钮文字 |
| Secondary text | `#667085` | 来源、说明和元数据 |
| Border | `#D7DEE8` | 字段、文本区和分隔线 |
| Accent | `#0A67E8` | 主按钮、焦点和选择 |
| Accent soft | `#E8F1FE` | 选中导航与文本选择 |
| Radius | 8 / 12 px | 字段按钮 / 字幕卡片 |

这些值由 `interfaces/qml/Theme.qml` 统一提供；组件不得各自复制近似颜色。

## 界面

历史使用独立 `History.qml` 窗口，包含保存开关、记录选择、两栏只读滚动预览、状态、复用和确认清空；共享当前主题和组件，普通工作区不增加历史侧栏。历史关闭时隐藏并复用窗口，数据规则见[本地翻译历史](./translation-history.md)。

### 翻译工作区

默认客户区为 800×560。顶栏依次放目标语言、弹性空白、翻译、置顶和复制；正文宽度至少 700 逻辑像素时左右双栏，低于阈值时上下排列。原文可编辑，译文只读，两栏独立滚动；来源、忙碌状态和 `Ctrl+Enter` 提示位于底部状态行。

### 设置

默认客户区为 780×680，最小为 700×560。左侧固定 226 像素导航和安全提示，右侧标题、可滚动正文、状态、分隔线和底部动作区。翻译、OCR、语言与热键三个分组保持现有字段顺序，密钥使用 Password echo mode。

### 实时字幕条

默认宽度 720 逻辑像素，高度按内容有界计算。窗口无标题栏、固定置顶且不抢焦点；第一行是 App 图标、实时 OCR、来源状态和停止，后续按原文与译文两行展示。长文本换行后增加高度，不把停止按钮挤出窗口。

### 区域选择

每个物理显示器一个无边框覆盖层。未拖动时显示深色遮罩、简短说明和 Esc；拖动后选区内部透明，外部继续遮罩，钴蓝边框配四个白色端点，并在指针附近显示物理像素尺寸。

## 可访问性与状态

- 翻译、设置和字幕动作都使用 Qt Quick Controls，必须出现在 Windows 无障碍树中；关键对象提供稳定 `objectName` 供定向验收。
- 主要动作支持鼠标和键盘；翻译按钮与 `Ctrl+Enter` 连接同一个信号，忙碌时同时禁用。
- 组合框必须只有一个下拉指示，不依赖平台主题叠加默认箭头；密钥不得进入普通 Label、截图文档或测试输出。
- 普通窗口关闭时隐藏并复用，不销毁托盘宿主；圈选覆盖层每次会话销毁，窗口销毁必须容忍 Qt 已经释放底层对象。
- QML 不调用翻译、OCR、剪贴板或文件系统；全部外部动作经 Python Presenter 的有界回调进入现有用例。

## 视觉参考与实现快照

概念图只用于锁定信息层级和视觉语言，运行时必须由 QML 控件实现：

| 界面 | 概念图 | Qt 实现快照 |
| --- | --- | --- |
| 工作区 | [workspace-concept.png](../assets/windows-qt-ui/workspace-concept.png) | [workspace-implementation.png](../assets/windows-qt-ui/workspace-implementation.png) |
| 设置 | [settings-concept.png](../assets/windows-qt-ui/settings-concept.png) | [settings-implementation.png](../assets/windows-qt-ui/settings-implementation.png) |
| 实时字幕条 | [live-overlay-concept.png](../assets/windows-qt-ui/live-overlay-concept.png) | [live-overlay-implementation.png](../assets/windows-qt-ui/live-overlay-implementation.png) |
| 区域选择 | [region-picker-concept.png](../assets/windows-qt-ui/region-picker-concept.png) | [region-picker-implementation.png](../assets/windows-qt-ui/region-picker-implementation.png) |

实现快照由真实 `QQuickWindow.grabWindow()` 在原生客户区尺寸采集，不包含 Windows 系统标题栏；区域选择快照为 2560×1440 物理像素，另外三张分别为 800×560、780×680 和 720×146 客户区。

## 对照结论

1. 调色板一致：概念与实现都使用冷白底、白色输入面、浅灰边框和单一钴蓝强调色，没有引入额外品牌色。
2. 信息层级一致：工作区保留目标语言、三项动作、原文、译文和状态；实现把概念顶栏右侧的快捷键提示移到底部状态行，以避免 800 像素宽窗口拥挤。
3. 控件语义一致：主翻译/保存是蓝底白字，置顶、复制、应用和停止为浅色次级按钮；实现使用可访问的 Qt Controls 和项目 SVG，不把概念图切片当按钮。
4. 设置结构一致：左侧三项导航、右侧字段和固定底部动作完整保留；实现压缩了概念稿的垂直留白，让 680 像素客户区和高 DPI 小屏仍能到达全部字段。
5. 覆盖层一致：实时字幕条保持图标、状态、停止、原文和译文；圈选器保持深色遮罩、透明选区、蓝色边框、端点和尺寸反馈。
6. 字体和密度经真机修正：首轮 `Segoe UI Variable` 对中文回退成不一致字体，最终统一为 `Microsoft YaHei UI`；组合框首轮双箭头也已改为单一项目 SVG。

## 允许的偏差

- 概念图展示完整 Windows 标题栏，QML 实现快照只采客户区；运行时翻译和设置窗口仍使用真实系统标题栏和项目 App 图标。
- 工作区实现把文本区标签放在边框上方，而不是概念图中的内部分隔标题；这样在宽窄布局切换时结构更稳定，也让无障碍树直接暴露「原文」「译文」。
- 实时字幕条以真实内容计算高度，短句会比概念图更紧凑；长句仍按有界规则增高。
- 设置和工作区的实际字号略小于高分辨率概念稿，以适配 100%～200% Windows 缩放和 800×560 默认客户区。
