# 本地翻译历史

本文适用于桌面历史的保存、查看和复用规则，不记录某次测试或交付状态。

## 保存范围与预算

保存默认关闭，用户从菜单/托盘「历史记录…」开启。桌面输入、划词、单次 OCR 及工作区手动再译的 `success` 结果才可记录；不保存实时字幕、`partial`、`failure` 或空结果。输入与划词共用 `JobKind.SELECTION`，截图使用 `JobKind.OCR`，不另外推断应用或选区来源。

最多保存 50 条，最新在前；原文和译文每栏最多 8000 字符，UTF-8 JSON 文件最多 1 MiB。超出单栏预算跳过整条，不截断文本；达到条数或字节预算移除最旧完整记录。与最近一条的原文、译文、语言和类别全部相同则不重复保存。

每条只包含 `source_text`、`translated_text`、`source_lang`、`target_lang`、`created_at` 和 `kind`，时间由保存用例生成 UTC ISO 字符串；语言取请求前快照，不能把请求期间切换后的目标写到旧结果上。图片、密钥、配置、模型响应和日志不属于历史。

## 分层与失败

- `core/history.py` 定义不可变 `HistoryEntry` / `HistoryState` 及预算；`core/ports.py` 的 `HistoryStorage` 负责 `load()` 和原子 `save()`，保存返回实际保留的记录。
- `features/history.py` 的 `TranslationHistory` 串行维护开启状态、去重和成功结果门禁，不依赖翻译/OCR feature 或存储实现。
- `infrastructure/history.py` 的 `JsonHistoryStore` 有界读取、校验 JSON、按 UTF-8 字节裁减最旧记录并使用同目录临时文件和 `os.replace` 保存。POSIX 新文件仅当前用户可读写；Windows 继承本机目录 ACL。读取不存在的文件不创建文件或开启保存。
- `app.py` 创建一个历史用例，将记录回调注入 `DesktopListener`，两端历史窗口使用同一 `HistoryBrowser`。接口层不打开文件或构造模型客户端；普通 CLI 的 `text` / `ocr` / `ocr-translate` 不写历史。

macOS 文件位于 `~/Library/Application Support/AI Translate/history.json`，Windows 位于 `%APPDATA%\AI Translate\history.json`；开启状态与记录同存，独立于双模型 `.env`。读取过大、损坏或不符合契约的文件时禁用保存并提示，用户明确清空前不覆盖原文件。写入失败保持旧内存状态和旧文件，提示不包含路径、记录内容或底层异常；历史失败不能影响核心翻译结果。

## 用户操作

历史窗口包含保存开关、记录下拉列表、两栏只读滚动预览、状态、复用和清空。macOS 使用可复用 AppKit 窗口，Windows 使用 `History.qml` 和现有 Qt 主线程调度。打开或操作时刷新记录，背景新增记录不改变已选择记录的复用对象；关闭窗口后再次打开继续复用同一对象。

「放回翻译窗口」只展示已保存原文与译文，并同步 listener 和工作区目标语言；不自动翻译、截屏、读剪贴板或重复保存。listener 正在执行单次翻译、工作区手动翻译尚未应用结果或普通结果仍排队时拒绝复用并提示完成后再试，不改当前工作区或语言；两端普通 presenter 在结果应用后才释放显示等待状态。保存的源语言用于查看记录，再次翻译仍使用当前设置的源语言。关闭保存保留已有记录；「清空历史…」确认后移除全部记录，保留当前开启状态与普通工作区内容。

## 验证要求

默认使用临时文件、Fake 端口和 UI 调度；覆盖成功门禁、请求语言快照、默认关闭、开关/清空、去重、记录和字节预算、损坏保护、原子替换失败及复用无请求。Windows Fake 运行时必须按真实 `WindowsUiRuntime` 的方法和签名约束。原生窗口验收使用合成内容和隔离文件；不得把用户历史、剪贴板或真实图像放入断言、文档或 Git。
