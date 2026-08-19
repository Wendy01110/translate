# AI Translate

本地 AI 翻译工具：划词翻译选中的外文，OCR 翻译屏幕或图片里的文字。翻译和 OCR 分开配置，互不借用。

## 现在能不能用

代码已经接上热键、浮窗、设置页和翻译源。本机若已安装 `~/Applications/AI Translate.app`：先点「译 → 退出」再打开，设置里把翻译来源改成 **Google（内置）**（或 Bing/DeepL 内置），保存后选中文字、松开 Option，再按 `Option+E`。内置源不用密钥。Google 请求必须带 `dt=t`；Bing 走翻译页 token。网页接口仍可能被限制。自动复制选区要给 **AI Translate** 开辅助功能；圈选 OCR 要开屏幕录制。离线测试已通过。官方付费 API 未在本机验收。

## 适用场景

- 阅读网页、文档或聊天时，把选中的外文译成目标语言。
- 圈选屏幕、打开截图或照片，先识别文字再翻译。
- 用免密钥网页源，或自己的 OpenAI 兼容 / 官方 API。

当前已提供配置检查、文本翻译、macOS 热键划词/OCR、菜单栏 App、设置页和精简浮窗。OCR 默认先用本机 Vision，不够再走模型。输入框、历史和视频字幕尚未提供。

本工具不做文档级对照翻译、同声传译、浏览器扩展或多人在线服务。

## 安装

需要 macOS 13+ 和 Python 3.12+。在仓库根目录执行：

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
scripts/build-macos-app.sh
open "$HOME/Applications/AI Translate.app"
```

本机只保留一份 App：`~/Applications/AI Translate.app`。改完源码后先点菜单「退出」，再重新打开 App；启动器从仓库 `src/` 加载代码，一般不用重新打包。重新打包后才会更新启动器本身。

用命令行而不是 App 时，可跳过打包，直接：

```bash
cp .env.example .env
.venv/bin/ai-translate config-check
```

## 配置存在哪里

程序**只读一个**配置文件，不会把多个 `.env` 合并。也不把 `.env.example` 当成可写配置。查找顺序：

1. 若设置了 `AI_TRANSLATE_ENV_FILE`，只用这个路径。
2. 否则若项目 `.env` 存在，用它。项目目录来自 `AI_TRANSLATE_PROJECT_ROOT`（菜单栏 App 由启动器写入仓库路径）；未设置时用当前工作目录。
3. 否则若 `~/Library/Application Support/AI Translate/.env` 存在，用它。
4. 若两处都不存在：菜单栏 App 会把设置保存到 Application Support 下的文件；命令行则仍使用项目 `.env`（可先 `cp .env.example .env`）。

设置页保存到**当前选中的那一个文件**。密钥只写进该文件，不打进 `.app`。用 `ai-translate config-check` 查看 `config.env_file`，确认读写的是哪一份。

进程环境里的 `TRANSLATE_*` / `OCR_*` / `HOTKEY_*` 会覆盖文件里的同名项。不要在 shell 配置里长期 `export` 这些变量，否则设置页保存了也看不到。

## 第一次使用

1. 打开 `AI Translate.app`，点菜单栏「译」→「设置…」。
2. 翻译来源可选 **Google / Bing / DeepL（内置）**，不用填密钥，和 TTime 一样走网页接口。也可以选 OpenAI 兼容或 DeepL/Microsoft/Google 官方（官方需要密钥；Microsoft 还要区域）。OCR 仍单独填。
3. 可选：在仓库 `.env` 里写 `TRANSLATE_MODELS=模型A,模型B` 和 `OCR_MODELS=...`，设置页下拉列表会用这些名字；不会向网关查询模型。
4. 点保存。密钥是密文框，保存后 `config-check` 只显示 `set` / `unset`。
5. 再跑一次 `config-check`，确认 `env_file` 和 `provider`。内置网页源无需密钥即为 `ready: true`，不表示网页接口一定能通。官方源按密钥/地址判断。OCR 在 `engine=auto` 且本机 Vision 可用时也可以是 `ready: true`。

也可以不打开设置页，直接编辑项目 `.env`（先从 `.env.example` 复制）。字段名以 `.env.example` 和 [配置设计](docs/design/configuration.md) 为准。

## 日常使用

默认热键：划词 `Option+E`（`alt+e`），OCR `Option+W`（`alt+w`）。可在设置页点热键按钮后按下新组合录制；必须带修饰键；两组不能相同。

| 你想做的事 | 怎么做 |
| --- | --- |
| 划词翻译 | 选中文字，松开 Option，再按 `Option+E`。浮窗先出原文再出译文。 |
| 截图翻译 | 按 `Option+W`，圈选区域。取消圈选不会识别。 |
| 从菜单触发 | 点「译」→「划词翻译」或「截图翻译」。 |
| 改翻译来源、模型、密钥、热键 | 「译」→「设置…」，保存后立即生效。 |
| 看配置是否读到 | `ai-translate config-check` |
| 翻译一段指定文本 | `ai-translate text "Hello"` |
| 识别本地图片 | `ai-translate ocr --image page.png` |
| 圈选后再识别 | `ai-translate ocr --screenshot` |
| 识别并翻译 | `ai-translate ocr-translate --image page.png` 或 `--screenshot` |
| 终端里听热键 | `ai-translate listen`，用 `Ctrl+C` 退出 |
| 退出 App | 「译」→「退出」 |

浮窗上面是原文，下面是译文，可滚动、可复制。截图文字清晰时走本机识别；识别为空或把握不够才调用 OCR 模型。

## 权限

热键本身不需要辅助功能。划词要自动复制当前选区时，需要给 **AI Translate**（不是 Cursor 或 python）打开辅助功能。没有该权限时，先 `Command+C` 再按 `Option+E`，会翻译剪贴板。OCR 圈选需要屏幕录制权限。未授权时菜单会显示「辅助功能：未开启」，点它可以打开系统设置。

## 配置字段

翻译和 OCR 使用两套前缀，互不顶替。缺少一侧只关闭对应能力。

| 用途 | 前缀 | 必要变量 |
| --- | --- | --- |
| 翻译 | `TRANSLATE_` | 内置网页源无需密钥；`openai` 要地址和模型；官方 `deepl`/`google` 要密钥；`microsoft` 要密钥和区域 |
| OCR | `OCR_` | `OCR_BASE_URL`、`OCR_MODEL` |
| 热键 | `HOTKEY_` | `HOTKEY_SELECTION`、`HOTKEY_OCR` |

`API_KEY` 是否必填由上游决定。不要把真实密钥写入文档、日志、测试或 Git。权威清单见 `.env.example`。

## 结果与错误

公共业务状态只有 `success`、`partial` 和 `failure`。

- `success`：本次得到可用结果。
- `partial`：OCR 已得到文本，但翻译没有成功；识别文本仍保留。
- `failure`：没有可用结果，浮窗或命令行会说明原因。
- `config-check` 成功只证明配置被读到，不证明上游可调用，也不证明译文正确。

## 常见问题

- **设置打不开或改完没变化**：先「退出」再打开 App。`config-check` 看 `env_file` 是不是你正在改的那份。
- **划词失败 / 没读到选区**：给 AI Translate 打开辅助功能；先松开 Option 再等浮窗；或先复制再按热键。
- **OCR 没反应**：给 AI Translate 打开屏幕录制；取消圈选不会识别。
- **命令行和 App 配置不一致**：两者应读同一个文件。若仓库里有 `.env`，它优先于 Application Support 里的文件。
- **热键变成了奇怪字符**：设置页请点按录制，不要手填 Option 产生的 `´`、`∑`。
- **网页翻译失败**：内置源依赖对方网页接口，可能被限流。可改用官方密钥源，或稍后再试。
- **想用官方 DeepL / Microsoft / Google**：设置里选带「官方」的来源并填密钥；Microsoft 还要填区域。

离线测试：

```bash
.venv/bin/python -m pytest
```

## 限制与安全

- 不要在未明确授权时发起真实模型调用、付费请求、截屏或外发剪贴板。
- 不要把 API key、Authorization、原始图片或未脱敏上游响应写入仓库、普通日志或文档。
- 划词会短暂改写剪贴板并在结束后恢复；翻译过程中不要同时复制其它内容。
- `listen` 和 App 只在按下热键或点菜单后读取选区或截屏。

## 更多文档

| 文档 | 内容 |
| --- | --- |
| [当前文档入口](docs/README.md) | 当前工作、权威来源和维护入口 |
| [产品范围](docs/design/product-scope.md) | 首期能力、非目标和术语 |
| [架构设计](docs/design/architecture.md) | 分层、依赖方向和执行链 |
| [配置设计](docs/design/configuration.md) | 环境变量、加载顺序和双模型边界 |
| [桌面热键](docs/design/desktop-hotkeys.md) | 划词/OCR 热键和权限 |
| [OCR 分流](docs/design/ocr-routing.md) | 本机 Vision 与模型如何选择 |
| [计划状态索引](docs/plan/README.md) | 进行中、待进行和最近完成 |
| [文档框架](docs/design/documentation-framework-guide.md) | 文档职责、状态流转和收尾 |
| [仓库工作规则](AGENTS.md) | Agent 执行契约 |
