# 仓库工作规则

## 任务入口与工作区

- 每个任务开始时，先阅读 `docs/README.md`，再阅读其中“当前工作”链接的进行中计划；暂无进行中计划且需要选择后续工作时，才从 `docs/plan/README.md` 的待进行项选择。不得先从实现文件或历史记录开始。
- `docs/plan/skipped/` 和 `docs/issues/skipped/` 表示用户明确要求暂时跳过的事项，不属于当前上下文；默认不得打开正文、准备方案、执行、复核时效性事实或据此安排下一步。只有用户明确重新纳入，并将计划移至 `docs/plan/pending/`、将 Issue 移至 `docs/issues/open/` 后，才开始准备。
- 开始修改前运行 `git status --short`，并按需回读相关 diff。工作区中的已有修改属于用户或并行工作；不得覆盖、清理、stash、rebase、合并或纳入当前提交，除非用户明确授权且范围已经核对。
- 计划用于需要持续跟踪的实施任务；简单问答、只读检查和可一次完成的小改动无需创建仓库计划，但实施任务应先明确目标、影响面、验收条件、外部副作用和停止边界，再逐步执行。
- 先使用当前代码、测试、`.env.example` 和配置加载路径确认实际行为，不根据文件名、旧文档或记忆猜测实现。

## 项目目标与取舍

- 当前阶段以本地可用的早期桌面翻译工具为目标，依次优先保证：双模型配置可检查、划词翻译、OCR 翻译、代码清晰和方便继续修改。
- 翻译模型和 OCR 模型必须保持独立配置与独立客户端。缺少某一侧配置时，只关闭对应能力，不得用另一侧的 `BASE_URL`、`API_KEY` 或 `MODEL` 顶替。
- 采用简单、直接、低依赖的实现。没有经过验证的消费者和明确需求时，不得添加桌面框架、浏览器扩展、服务端多租户、缓存层或“以后可能需要”的扩展点。
- 只修改需求范围内的文件。写代码前先按现有分层放置职责；新增抽象必须减少重复或隔离稳定边界，只为缩短文件而分层不算收益。

## 架构与代码放置

- 项目是模块化单体，依赖方向为 `interfaces -> features -> core`、`infrastructure -> core`；composition 只在 `bootstrap` 和 `app.py` 完成。`tests/architecture/test_dependency_rules.py` 负责检查这些边界。
- `core/` 放结果契约、错误和端口，不依赖项目内其它层；`features/` 放划词翻译和 OCR 翻译用例，feature 之间不直接引用；`infrastructure/` 处理模型 HTTP、剪贴板和截屏，不决定业务状态如何展示给用户；`interfaces/` 只做 CLI 或后续桌面协议适配，不得直接构造 HTTP 客户端。
- 划词路径是“文本来源 -> 翻译端口”；OCR 翻译路径是“图像来源 -> OCR 端口 -> 翻译端口”。两条路径必须复用同一个翻译端口实现，不得为 OCR 再写一套译文语义。
- 稳定架构以 `docs/design/architecture.md` 为准；实现与文档冲突时先核对当前代码和测试，再同步修正文档，不在本文件复制易漂移的模块清单。

## 公共契约与改动闭合

| 内容 | 权威来源 |
| --- | --- |
| 项目版本 | `pyproject.toml` |
| 环境变量名、默认值和双模型边界 | `.env.example` 与 `src/ai_translate/config.py` |
| 结果状态和字段 | `src/ai_translate/core/models.py` |
| 端口与依赖方向 | `src/ai_translate/core/ports.py` 与架构测试 |
| 当前任务状态 | `docs/plan/` 中唯一状态目录下的原文件 |

- 修改公共 CLI、结果状态、配置名或端口时，同步定义、实现、用户文档、`.env.example` 和契约测试；这些内容一致前不得标记完成。
- 修改配置时，同步默认值、示例、加载路径、`config-check` 回读和 [配置设计](docs/design/configuration.md)。
- 包 `__version__` 必须与 `pyproject.toml` 的 `version` 一致。

## 数据、安全与副作用

- 所有外部输入、图片字节、文本长度、超时和并发都必须有界。当前默认超时来自配置；没有上限的截屏、剪贴板或模型响应不得直接进入公共结果。
- API key、Authorization、原始图片、剪贴板全文和未脱敏上游响应不得进入普通日志、文档、测试断言消息或 Git。`config-check` 对密钥只输出 `set`/`unset`。
- 真实翻译调用、真实 OCR 调用、屏幕截取、读取用户选区/剪贴板、付费请求、提交和推送都必须事先获得明确授权。离线测试、代码修改或历史授权不自动扩大本次权限。
- 默认测试只使用 Fake 端口或 HTTP mock，不得读取本机 `.env` 中的真实密钥去打上游。

## 计划、Issue 与文档收尾

- 每次任务结束前回读最终改动，并同步所有受影响的用户文档、稳定设计、当前状态说明、计划和 Issue。代码、配置、CLI 或验收结果发生变化时，不得让文档继续描述旧行为。
- 任务由计划跟踪时，部分完成或阻塞要更新原计划的当前进度、已验证内容、剩余工作和停止原因；全部完成后将原文件从 `in-progress/` 或 `pending/` 移至 `completed/`，同步全部引用以及 `docs/README.md`、`docs/plan/README.md`，不得复制并存版本或提前标记完成。用户要求暂时跳过时，将原计划移至 `skipped/` 并停止后续准备；恢复时必须先移至 `pending/`，不得从 `skipped/` 直接开始实施。
- 任务关联开放 Issue 时，未解决要更新 `docs/issues/open/` 中的当前证据、边界和下一步；达到关闭条件后将原文件移至 `docs/issues/closed/`，写明结论、验证和对应完成日志指针。用户要求暂时跳过时，将原 Issue 移至 `docs/issues/skipped/`。不得只修代码而遗留过期 Issue 状态。
- 需要持续追踪、改变公共契约或关闭 Issue 的完成任务，在 `docs/logs/YYYYMM/` 记录实际改动和验证。一次性小改动没有对应计划或 Issue 时无需创建空文件，但仍须确认相关文档已更新，并在最终回复中说明 plan/issue 不适用。
- `docs/README.md` 只列当前进行中计划、`docs/plan/README.md` 状态入口和稳定设计；`docs/plan/README.md` 列出全部进行中、待进行与暂时跳过计划，“最近完成”最多保留 5 项。暂时跳过项只登记状态，不进入默认上下文。
- 项目 Markdown 文档（根 `README.md`、`AGENTS.md` 与 `docs/**/*.md`）采用“一个逻辑段落一行”，不按固定列宽硬换行；标题、段落、列表、表格、引用和 fenced code block 之间保留一个空行。仅做排版整理时不得改写正文、链接、代码块或证据值。
- 新建任务型文档使用 `YYYY-MM-DD-<task-slug>.md`，日期取 Asia/Shanghai；状态变化时移动原文件并同步引用，不复制、不创建 `docs/plan/current.md` 别名。

## 验证与交付

- 使用项目本地 `.venv` 和 Python 3.12+，不使用全局或 Conda 环境代替。先运行与改动直接相关的最小测试；配置、结果契约、分层或 CLI 变化时，再运行完整离线套件。
- 配置变化时检查 `tests/test_config.py` 与 `tests/interfaces/test_cli.py`；用例变化时检查 `tests/features/`；模型客户端变化时检查 `tests/infrastructure/`；分层变化时运行 `tests/architecture/`；文档入口或计划状态变化时运行 `tests/docs/`。
- 完整 Python 离线套件：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider
```

- 交付前运行 `git diff --check`，回读最终 diff，并检查 `git status --short` 是否混入范围外内容。不得声称执行过未实际执行的测试；外部条件不可用时，明确区分已完成、未验证、原因和最安全的下一步。
- 在文档、Plan 和 Issue 状态与实际结果一致前不得声称完成。最终回复必须列出本次同步内容，或明确说明哪些类别不适用。未经明确授权不得推送、发布或调用真实模型。
