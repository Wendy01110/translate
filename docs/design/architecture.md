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
├── config.py             # 从环境变量加载两套模型配置
├── bootstrap/            # 构造客户端和用例
├── core/                 # 契约、错误、端口
├── features/             # 划词翻译、OCR 翻译
├── infrastructure/       # 模型 HTTP、选区剪贴板、截屏
└── interfaces/           # CLI、热键常驻、菜单栏、设置、输入窗口、浮窗、区域圈选和字幕条
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

- 翻译客户端只接收 `TranslateSettings`；OCR 客户端只接收 `OcrSettings`。
- `Translator` 和 `OcrEngine` 是两条端口。OCR 翻译用例可以依赖两个端口，但不得把图像直接交给翻译端口，除非产品范围先修改。
- 公共业务状态只有 `success`、`partial`、`failure`。
- 真实上游、截屏和剪贴板访问只能从 `infrastructure` 出发，并由组合入口注入。

## 主流程与失败边界

划词翻译由 `SelectionTranslateService` 编排：拒绝空文本，再调用 `Translator`。输入窗口走同一用例，结果留在窗口内，不改走划词浮窗。`bootstrap.translator_for` 按 `TRANSLATE_PROVIDER` 构造网页内置源或官方/兼容客户端，界面不得直接选协议。

OCR 翻译由 `OcrTranslateService` 编排：先调用 `OcrEngine`，识别文本为空则失败并停止；识别成功后再调用 `Translator`。翻译失败时返回 `partial` 并保留 OCR 文本。区域实时 OCR 也由该用例的 `advance_live` 编排：指纹未变则跳过 OCR，文本未变则跳过翻译，失败不得沿用上一句成功译文。

CLI 接入 `config-check`、`text`、`ocr`、`ocr-translate`、`listen` 和 `app`。`ocr` 只走 OCR 端口；划词、输入窗口、单次 `ocr-translate` 和实时 OCR 必须走同一个翻译端口。`listen` 和菜单栏 App 把热键接到选区来源、区域截屏、实时区域循环和浮窗，不在 interface 里直接打 HTTP。菜单「输入翻译…」打开输入窗口；「实时翻译」圈选区域后开始有界循环。菜单栏设置页只改写允许的环境变量并重建现有用例。macOS `.app` 用嵌入式启动器加载同一套 `app:main`，不另写翻译语义。配置文件由 `resolve_env_path()` 选出一份，启动器只提供仓库路径，不把密钥或 `.env` 路径打进包内。

OCR 由 `RoutingOcrEngine` 分流：默认先 `VisionOcrEngine`，再 `HttpOcrEngine`。图片文件读取位于 `infrastructure/image_file.py`。interfaces 不得直接调用 `httpx` 或拼装 OCR payload。浮窗只展示原文和译文；点选后 `Command+C` 复制当前栏，未选中则复制全文。

## 变更与验证要求

- 修改分层或允许的依赖时，同步本文、`AGENTS.md` 和架构测试。
- 修改结果字段或状态语义时，同步 `core/models.py`、两个 feature、用户文档和 `tests/features/`。
- 新增入口时必须汇入现有 feature，不得在 `interfaces/` 里直接调用 `httpx`。
