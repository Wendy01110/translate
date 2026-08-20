# 配置设计

本文适用于翻译模型和 OCR 模型的环境变量边界，面向实现者和部署本机环境的维护者。某次 `.env` 里的真实地址、密钥和模型名不属于本文。

## 目标与非目标

- 目标：用两套前缀把翻译和 OCR 配成两个独立上游。
- 目标：让 `config-check` 能回读就绪状态，且不泄漏密钥。
- 非目标：在配置层做模型自动发现、密钥托管、多套 profile 切换或远程配置中心。设置页的模型列表只读 `TRANSLATE_MODELS` / `OCR_MODELS` 和当前模型名。网页内置源不是官方合同，失败时不得改走官方密钥。
- 非目标：为两套模型提供互为默认值的别名。

## 权威来源

| 内容 | 权威位置 |
| --- | --- |
| 变量名和仓库示例 | `.env.example` |
| 默认值、类型和加载 | `src/ai_translate/config.py` |
| 就绪判定 | `Settings.translate_ready` / `Settings.ocr_ready` |
| 面向用户的最短说明 | 根 `README.md` 的配置节 |

字段清单以代码和 `.env.example` 为准。本文只解释语义和禁止项，不手工维护第二份默认值表。

## 核心约束

- 翻译只读取 `TRANSLATE_` 前缀；OCR 只读取 `OCR_` 前缀。
- 就绪条件按翻译来源区分：`google_web` / `bing_web` / `deepl_web` 无需密钥；`openai` 需要 `BASE_URL` 与 `MODEL`；`deepl` / `google` 需要 `API_KEY`；`microsoft` 需要 `API_KEY` 与 `REGION`。OCR 仍是 `BASE_URL` 与 `MODEL` 非空。不得用 OCR 配置顶替翻译源。
- 一侧未就绪不得读取另一侧的 `BASE_URL`、`API_KEY`、`MODEL` 或超时。
- 配置加载只读一个文件，不合并多个 `.env`，也不把 `.env.example` 当作可写配置。查找顺序见下文「加载路径」。
- 测试必须通过环境变量注入或显式 `env_file=None`，不得依赖开发者本机真实 `.env`。
- 密钥在内存中按 `SecretStr` 保存；对外回读只允许 `set` 或 `unset`。

## 当前变量语义

翻译：

- `TRANSLATE_PROVIDER`：`google_web` / `bing_web` / `deepl_web` 为免密钥网页源（Google 用 `client=gtx` 且必须带 `dt=t`；Bing 用翻译页 token 再调 `ttranslatev3`；DeepL 用 jsonrpc）；代码默认 `google_web`。`openai` 为 OpenAI 兼容；`deepl` / `microsoft` / `google` 为官方 API。网页源可能随时被对方限制。
- `TRANSLATE_BASE_URL`：`openai` 时为 Chat Completions 地址，通常以 `/v1` 结尾。其它来源可留空，使用官方默认地址；填写则覆盖默认。
- `TRANSLATE_API_KEY`：当前翻译来源的密钥。
- `TRANSLATE_MODEL`：仅 `openai` 使用的模型名。
- `TRANSLATE_MODELS`：设置页可选的翻译模型列表，逗号分隔。当前 `TRANSLATE_MODEL` 会自动加入列表。不向网关查询模型。
- `TRANSLATE_REGION`：仅 `microsoft` 使用的 Azure 区域，例如 `eastus`。
- `TRANSLATE_TIMEOUT_SECONDS`：单次翻译请求超时。
- `TRANSLATE_SOURCE_LANG`：源语言，默认 `auto`。
- `TRANSLATE_TARGET_LANG`：目标语言，默认 `zh`。

OCR：

- `OCR_ENGINE`：`auto`（默认）、`vision` 或 `model`。`auto` 先用本机 Vision，不够再走模型。
- `OCR_MIN_CONFIDENCE`：`auto` 接受本机结果的最低置信度，默认 0.5。
- `OCR_BASE_URL`：OpenAI 兼容 Chat Completions 的基础地址，通常以 `/v1` 结尾。
- `OCR_API_KEY`：调用 OCR 上游的密钥。
- `OCR_MODEL`：OCR 模型名，默认 `Unlimited-OCR`。
- `OCR_MODELS`：设置页可选的 OCR 模型列表，逗号分隔。当前 `OCR_MODEL` 会自动加入列表。不向网关查询模型。
- `OCR_TIMEOUT_SECONDS`：单次 OCR 请求超时，默认 180。
- `OCR_MAX_TOKENS`：单次 OCR 最大输出 token，默认 24000。
- `OCR_IMAGE_MODE`：视觉切图模式。空或 `auto` 表示单图 `gundam`、多图 `base`；也可显式设为 `tiny`、`small`、`base`、`large` 或 `gundam`。多图不得使用 `gundam` 或 `large`。

热键：

- `HOTKEY_SELECTION`：划词翻译热键，默认 `alt+e`。
- `HOTKEY_OCR`：区域 OCR 翻译热键，默认 `alt+w`。
- `HOTKEY_LIVE_OCR`：屏幕实时 OCR 热键，默认 `alt+q`。再次按下会停止正在运行的实时循环。三组热键在配置加载时统一规范化，并拒绝语义相同的组合（例如 `option+e` 与 `alt+e`）。

OCR 不读取源/目标语言。语言只作用于翻译端口。热键由 `listen` 和菜单栏 App 注册，`config-check` 只回读字符串。

菜单栏「设置」可改写 `TRANSLATE_PROVIDER`、`TRANSLATE_BASE_URL`、`TRANSLATE_API_KEY`、`TRANSLATE_MODEL`、`TRANSLATE_REGION`、`OCR_BASE_URL`、`OCR_API_KEY`、`OCR_MODEL`、`OCR_ENGINE`、`OCR_MIN_CONFIDENCE`、`OCR_IMAGE_MODE`、`TRANSLATE_SOURCE_LANG`、`TRANSLATE_TARGET_LANG`、`HOTKEY_SELECTION`、`HOTKEY_OCR`、`HOTKEY_LIVE_OCR`。两侧地址和密钥必须分开填写，不得互拷。不得改写 `TRANSLATE_MODELS` / `OCR_MODELS`，也不得写入 `AUTHORIZATION`。密钥用密文框编辑，保存到当前解析到的那一个文件；不得进入日志、浮窗或 `config-check` 明文。「应用」写入并立即重建翻译/OCR 用例，窗口保持打开；「保存」在应用成功后关闭窗口。设置页可切换翻译来源和模型；热键点一下再按下组合键录制。三组热键不得相同。

## 加载路径

只选一个文件：

1. `AI_TRANSLATE_ENV_FILE` 非空时，只用该路径。
2. 否则若项目 `.env` 存在则用它。项目目录优先 `AI_TRANSLATE_PROJECT_ROOT`，否则当前工作目录。菜单栏 App 的启动器设置 `AI_TRANSLATE_PROJECT_ROOT` 为仓库路径，不再把某个 `.env` 路径打进包内。
3. 否则若 `~/Library/Application Support/AI Translate/.env` 存在则用它。
4. 若两处都不存在：菜单栏 App（已设置 `AI_TRANSLATE_HOST_NAME`）把设置写到 Application Support；命令行仍使用项目 `.env`。

不得把 `.env.example` 当作运行配置或设置页写入目标。进程环境里的 `TRANSLATE_*` / `OCR_*` / `HOTKEY_*` 覆盖文件中的同名项。`config-check` 输出 `config.env_file`，便于确认实际读写路径。密钥不得写进 `.app`。

当前 OCR 客户端按 Unlimited-OCR 网关合同发送 `document parsing.` / `Multi page parsing.`、`temperature=0`、`skip_special_tokens=false` 和 `images_config.image_mode`，不发送 `custom_logit_processor` 或 `vllm_xargs`，并且 `httpx` 使用 `trust_env=false`。识别文本会去掉 `<|det|>` / `<|ref|>` 版面标记后再交给翻译端口；`finish_reason=length` 视为失败，不返回残缺正文。

## 主流程与失败边界

```text
进程启动或 config-check
  -> 分别构造 TranslateSettings 与 OcrSettings
  -> 计算两侧 ready
  -> 输出脱敏状态
```

- 缺少 `.env` 不是错误。翻译默认 `google_web`，无需密钥即为就绪（就绪不表示网页接口一定能通）。OCR 在未配置模型时仍按引擎判定：`model` 需要地址和模型；`auto`/`vision` 可仅凭本机 Vision 就绪。
- 未知环境变量忽略，不失败。
- 超时必须是正数；非法值按 pydantic 校验失败，CLI 以非零退出。
- `config-check` 不探测上游健康检查，也不发送 Chat Completions。
- `ocr` 和 `ocr-translate` 会按当次命令读取本地图片并调用已配置的上游；未配置或图片不合法时不得发出请求。

## 变更与验证要求

- 增删或重命名变量时，同步 `.env.example`、`config.py`、本文、根 README 和 `tests/test_config.py`。
- 改变加载路径或 `config-check` 字段时，同步 `config.py`、本文、根 README 和配置测试。
- 改变就绪条件时，同步 `config-check` 输出测试。
- 不得在测试里写入真实密钥，也不得把本机 `.env` 提交到 Git。
