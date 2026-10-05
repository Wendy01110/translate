# 架构设计

本文适用于本仓库的代码分层和执行链，面向后续实现和维护。运行时数量、某次测试结果和桌面交互细节不属于本文。

## 目标与非目标

- 目标：用模块化单体承载划词翻译和 OCR 翻译，让划词、单次 OCR 和区域实时 OCR 复用同一套结果契约和翻译端口。
- 目标：把模型协议、操作系统输入和用户入口隔开，避免 CLI 或后续桌面层直接访问上游 HTTP。
- 非目标：微服务拆分、插件市场、多进程模型网关，或为尚未存在的桌面框架预留空壳层。

## 权威来源

| 内容 | 权威位置 |
| --- | --- |
| 依赖方向 | `tests/architecture/test_dependency_rules.py` |
| 结果契约 | `src/ai_translate/core/models.py` |
| 端口 | `src/ai_translate/core/ports.py` |
| 配置加载 | `src/ai_translate/config.py` |
| 组合入口 | `src/ai_translate/bootstrap/composition.py`、`src/ai_translate/app.py` |

## 目录

```text
src/ai_translate/
├── app.py                # CLI composition root
├── config.py             # 从环境变量加载翻译和四层 OCR 配置
├── bootstrap/            # 构造客户端和用例
├── core/                 # 契约、错误、端口
├── features/             # 划词翻译、OCR 翻译
├── infrastructure/       # 模型 HTTP、平台选区剪贴板、截屏和单实例
└── interfaces/           # CLI、热键常驻、托盘/菜单栏、设置、翻译工作区、区域圈选和字幕条
```

## 依赖方向

```text
interfaces -> features -> core
infrastructure -------> core
bootstrap -> features + infrastructure + interfaces + core
```

- `core` 不依赖项目内其它层。
- feature 之间不直接引用。
- `infrastructure` 处理协议和系统 I/O，不决定用户文案。官方翻译源与 OpenAI 兼容源都实现同一 `Translator` 端口。
- `interfaces` 只做参数解析和输出，不创建 HTTP 客户端，也不读取操作系统密钥以外的配置加载细节。
- `bootstrap` 和 `app.py` 是唯一组合点。

## 核心约束

- 翻译客户端只接收 `TranslateSettings`；PaddleOCR 本地高级适配只接收 `LocalAdvancedOcrSettings`；OCR.space API 普通客户端只接收 `StandardOcrSettings`；API 高级客户端只接收 `OcrSettings`。四者不得互借配置。
- `Translator` 和 `OcrEngine` 是两条端口。OCR 翻译用例可以依赖两个端口，但不得把图像直接交给翻译端口，除非产品范围先修改。
- 公共业务状态只有 `success`、`partial`、`failure`。
- 真实上游、截屏和剪贴板访问只能从 `infrastructure` 出发，并由组合入口注入。

## 主流程与失败边界

`bootstrap.DesktopRuntime` 持有桌面翻译客户端、OCR 组合及两个业务用例，按翻译/OCR 两侧请求配置分别更新；未改变请求配置时复用实例，保留 Paddle 懒加载状态。语言、热键和模型候选列表不参与客户端重建判断；语言继续通过翻译请求传入。两个业务用例使用同一个翻译客户端，界面层只负责应用已组合的运行时。

实时圈选与循环生命周期由 `DesktopListener` 维护，发起圈选时即预留会话代次，平台排队启动与回调都只作用于当前代次。停止或设置替换使旧圈选失效，迟到结果和旧 worker 退出不能回写新会话；设置替换同时取消尚未完成的圈选和已运行循环。工作区目标语言栏切换仍以不可变记忆快照使在途结果失效，保留当前循环。详细状态规则见 [屏幕实时 OCR](./live-screen-ocr.md)。

翻译长度、图片字节、OCR 页数/累计字节和固定区域面积常量放在 `core/limits.py`；翻译长度由用例和客户端共同执行，OCR 后翻译超限保留原文并返回 `partial`。`core/ocr_input.py` 的纯函数统一检查空图、单张 20 MiB、最多 10 页和整批合计 20 MiB；CLI、OCR 翻译用例、路由与各 OCR 适配复用该检查，超限不启动 OCR、本地模型初始化或上游编码/请求，也不继续分流。CLI 先检查页数，再逐张读取并检查累计预算，超限不再读取后续文件。图片文件与 macOS 单次截图继续共用 `infrastructure/image_file.py` 的有界读取，两端固定区域截屏在抓图前检查有限坐标及面积。区域坐标单位和失败语义见 [OCR 分流](./ocr-routing.md)。`infrastructure/http_response.py` 统一限制最终 HTTP 响应进入解析前的解码后字节数，超限时关闭流并向上返回稳定错误码，用户提示仍由界面层决定。

划词翻译由 `SelectionTranslateService` 编排：拒绝空文本及超过 8000 字符的输入，再调用 `Translator`。桌面输入与两端翻译工作区内的手动再译都走同一用例；界面只接收组合入口注入的文本翻译回调，不构造客户端或改走热键取词。OCR 初次结果仍来自 `OcrTranslateService`，用户在工作区修正 OCR 原文后只把修正文本交给 `SelectionTranslateService`，不得再次截图或调用 OCR。`bootstrap.translator_for` 按 `TRANSLATE_PROVIDER` 构造网页内置源或官方/兼容客户端，界面不得直接选协议。

平台选区适配通过 `SelectionReadError` 报告无法继续的剪贴板读写或模拟复制失败，共享 listener 在进入翻译用例前展示 `failure`，失败结果不携带剪贴板内容。macOS 命令的启动、超时和文本编解码异常复用既有读、写、复制错误码；恢复原剪贴板失败也作为写入失败停止本次任务，具体命令时限与恢复规则见 [桌面热键设计](./desktop-hotkeys.md)。

OCR 翻译由 `OcrTranslateService` 编排：先调用 `OcrEngine`，识别文本为空则失败并停止；识别成功后再调用 `Translator`。翻译失败时返回 `partial` 并保留 OCR 文本。区域实时 OCR 也由该用例的 `advance_live` 编排：指纹未变则跳过 OCR，文本未变且没有到期的翻译补试则跳过翻译；暂态翻译失败最多补试两次，同一画面复用 OCR 结果，失败不得沿用上一句成功译文。补试状态仅属于当前实时会话，时间与次数边界见[屏幕实时 OCR](./live-screen-ocr.md)。监听器以不可变记忆快照判断在途任务是否仍有效，切换目标语言或停止后旧任务不能回写结果，语言切换不终止实时循环。

CLI 接入 `config-check`、`text`、`ocr`、`ocr-translate`、`listen` 和 `app`。`ocr` 只走 OCR 端口；划词、桌面输入、单次 `ocr-translate` 和实时 OCR 必须走同一个翻译端口。`listen` 和桌面 App 把热键接到选区来源、区域截屏、实时区域循环和界面 presenter，不在 interface 里直接打 HTTP。macOS 与 Windows 的 `app.py` 都只为普通翻译创建一个平台 presenter：桌面输入调用 `show_input()`，划词和单次 OCR 结果调用同一实例的 `show()`；macOS 复用一个 `NSPanel`，Windows 复用一个 PySide6 `QQuickWindow`。两端的菜单输入、划词和 OCR 原文可编辑，译文只读；标题区翻译按钮与平台快捷键从后台线程复用当前 `DesktopListener.handle_typed_text`、语言配置与忙碌锁，再回到 UI 主线程更新同一窗口，临时状态保持只读。工作区目标语言栏复用 `TARGET_LANG_OPTIONS`，选择后只调用 `DesktopListener.set_target_lang()` 更新进程内目标并清空实时 OCR 去重记忆，不自动翻译也不写 `.env`；设置页保存后，`replace_runtime()` 与 presenter 栏位同时回到持久配置。普通窗口默认允许其它窗口覆盖，只在用户点击图钉或「置顶」后保持最前；该状态不进入配置。macOS 未置顶时使用普通层级、移动到当前 Space 并采用 full-screen auxiliary，失去 key 状态后保留在后台，允许其它窗口覆盖；Windows 每次新结果短暂前置后恢复普通层级，并由 QML 在宽屏双栏与紧凑上下布局间切换。两端标题区复制动作只复制当前译文；实时字幕条继续固定置顶且不抢焦点。「实时翻译」圈选区域后开始有界循环；设置页只改写允许的环境变量并按受影响的配置更新用例。macOS `.app` 用嵌入式启动器、Windows 源码入口用项目 `.venv` 的 `pythonw.exe` 加载同一套 `app:main`，都不另写翻译语义。配置文件由 `resolve_env_path()` 选出一份，启动器只提供仓库路径，不把密钥或 `.env` 路径打进包内。

OCR 由 `RoutingOcrEngine`、`TieredLocalOcrEngine` 与 `TieredRemoteOcrEngine` 分流：macOS 自动模式先 `VisionOcrEngine`，Windows 跳过该层；之后尝试可选且懒加载的本地 `PaddleOcrEngine`；再对单张且在 1 MB 边界内的图片尝试 API `OcrSpaceEngine`；最后使用已配置的 API 高级 `HttpOcrEngine`。图片文件读取位于 `infrastructure/image_file.py`。interfaces 不得直接调用 PaddleOCR、`httpx` 或拼装任一 OCR payload。翻译工作区只展示原文和译文；获得焦点后可使用平台复制快捷键复制选中文字，macOS 的划词与单次 OCR 原文都可编辑并触发已注入的文本翻译用例，标题区复制图标直接复制完整译文。

## 变更与验证要求

- 修改分层或允许的依赖时，同步本文、`AGENTS.md` 和架构测试。
- 修改结果字段或状态语义时，同步 `core/models.py`、两个 feature、用户文档和 `tests/features/`。
- 新增入口时必须汇入现有 feature，不得在 `interfaces/` 里直接调用 `httpx`。
