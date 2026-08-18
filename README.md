# AI Translate

本地 AI 翻译工具，用划词翻译外文文本，用 OCR 翻译屏幕或图片中的文字。翻译模型和 OCR 模型分开配置，互不借用。

## 适用场景

- 阅读网页、文档或聊天记录时，把选中的外文翻译成目标语言。
- 对截图、照片或屏幕区域做文字识别，再翻译识别结果。
- 在本机用两套独立的 OpenAI 兼容接口分别调用翻译模型和 OCR 模型。

当前版本先提供可安装的项目骨架、环境变量配置检查和离线可验证的翻译/OCR 用例边界。桌面划词浮窗、屏幕圈选和真实模型调用仍按 [首期实现计划](docs/plan/pending/2026-08-19-selection-and-ocr-implementation.md) 跟踪，不在快速开始里假装已经可用。

本工具不做文档级对照翻译、同声传译、浏览器扩展或多人在线服务。

## 快速开始

需要 Python 3.12+。在仓库根目录执行：

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env
.venv/bin/ai-translate config-check
```

成功标准：命令正常退出，并分别打印 `translate` 与 `ocr` 两段配置状态。密钥只显示 `set` 或 `unset`，不会回显内容。`.env` 仍为空时，两段都会显示 `ready: false`；这表示模型尚未配置，不表示安装失败。

当前命令只读取本地环境变量，不访问翻译或 OCR 上游。

## 主要用法

| 任务 | 当前入口 |
| --- | --- |
| 检查翻译和 OCR 是否已分别配置 | `ai-translate config-check` |
| 把选中文本交给翻译模型 | 尚未实现，见 [首期实现计划](docs/plan/pending/2026-08-19-selection-and-ocr-implementation.md) |
| 对截图做 OCR 再翻译 | 尚未实现，见 [首期实现计划](docs/plan/pending/2026-08-19-selection-and-ocr-implementation.md) |

离线测试入口：

```bash
.venv/bin/python -m pytest
```

## 配置

翻译和 OCR 使用两套前缀完全独立的环境变量。权威字段名、默认值和含义以 [配置设计](docs/design/configuration.md) 和 `.env.example` 为准。

| 用途 | 前缀 | 必要变量 |
| --- | --- | --- |
| 翻译模型 | `TRANSLATE_` | `TRANSLATE_BASE_URL`、`TRANSLATE_MODEL` |
| OCR 模型 | `OCR_` | `OCR_BASE_URL`、`OCR_MODEL` |

API key 可以按上游要求填写；调用方库需要占位值时再设置，不要把真实密钥写入文档、日志或测试。两套配置缺少任一侧，只表示对应能力未就绪，不得回退到另一侧的地址、模型和密钥。

## 结果与错误

当前公共业务状态只有 `success`、`partial` 和 `failure`。

- `success`：本次请求在约定范围内得到可用结果。
- `partial`：OCR 已得到文本，但后续翻译没有成功；识别文本仍应保留。
- `failure`：没有得到可用结果，原因见 `error`。
- 空选区、空识别结果、未配置模型或上游失败都要按原边界返回，不得改写成成功或臆造译文。
- `config-check` 成功只证明配置被读到，不证明模型可调用，也不证明译文正确。

## 限制与安全

- 默认不要发起真实模型调用、付费请求、截屏或向外部发送剪贴板内容，除非用户明确授权当次操作。
- 不要把 API key、Authorization、原始图片或未脱敏上游响应写入仓库、普通日志或文档。
- 当前骨架不提供桌面常驻进程，也不监听全局热键。

## 更多文档

| 文档 | 内容 |
| --- | --- |
| [当前文档入口](docs/README.md) | 当前工作、权威来源和维护入口 |
| [产品范围](docs/design/product-scope.md) | 首期能力、非目标和术语 |
| [架构设计](docs/design/architecture.md) | 分层、依赖方向和执行链 |
| [配置设计](docs/design/configuration.md) | 环境变量和双模型边界 |
| [计划状态索引](docs/plan/README.md) | 进行中、待进行和最近完成 |
| [文档框架](docs/design/documentation-framework-guide.md) | 文档职责、状态流转和收尾 |
| [仓库工作规则](AGENTS.md) | Agent 执行契约 |
