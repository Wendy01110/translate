# 配置设计

本文适用于翻译模型和 OCR 模型的环境变量边界，面向实现者和部署本机环境的维护者。某次 `.env` 里的真实地址、密钥和模型名不属于本文。

## 目标与非目标

- 目标：用两套前缀把翻译和 OCR 配成两个独立上游。
- 目标：让 `config-check` 能回读就绪状态，且不泄漏密钥。
- 非目标：在配置层做模型自动发现、密钥托管、多套 profile 切换或远程配置中心。
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
- 就绪条件是对应的 `BASE_URL` 与 `MODEL` 去掉首尾空白后均非空。`API_KEY` 是否必填由上游决定，缺省为空字符串，不阻止本地加载。
- 一侧未就绪不得读取另一侧的 `BASE_URL`、`API_KEY`、`MODEL` 或超时。
- 配置加载可以读取项目根 `.env`，但测试必须通过环境变量注入，不得依赖开发者本机真实 `.env`。
- 密钥在内存中按 `SecretStr` 保存；对外回读只允许 `set` 或 `unset`。

## 当前变量语义

翻译：

- `TRANSLATE_BASE_URL`：OpenAI 兼容 Chat Completions 的基础地址，通常以 `/v1` 结尾。
- `TRANSLATE_API_KEY`：调用翻译上游的密钥；本地不校验的网关可以使用占位值。
- `TRANSLATE_MODEL`：翻译模型名。
- `TRANSLATE_TIMEOUT_SECONDS`：单次翻译请求超时。
- `TRANSLATE_SOURCE_LANG`：源语言，默认 `auto`。
- `TRANSLATE_TARGET_LANG`：目标语言，默认 `zh`。

OCR：

- `OCR_BASE_URL`：OpenAI 兼容 Chat Completions 的基础地址，通常以 `/v1` 结尾。
- `OCR_API_KEY`：调用 OCR 上游的密钥。
- `OCR_MODEL`：OCR / 视觉模型名。
- `OCR_TIMEOUT_SECONDS`：单次 OCR 请求超时。

OCR 不读取源/目标语言。语言只作用于翻译端口。

## 主流程与失败边界

```text
进程启动或 config-check
  -> 分别构造 TranslateSettings 与 OcrSettings
  -> 计算两侧 ready
  -> 输出脱敏状态
```

- 缺少 `.env` 不是错误；此时两侧均为未就绪。
- 未知环境变量忽略，不失败。
- 超时必须是正数；非法值按 pydantic 校验失败，CLI 以非零退出。
- 本阶段 `config-check` 不探测上游健康检查，也不发送 Chat Completions。

## 变更与验证要求

- 增删或重命名变量时，同步 `.env.example`、`config.py`、本文、根 README 和 `tests/test_config.py`。
- 改变就绪条件时，同步 `config-check` 输出测试。
- 不得在测试里写入真实密钥，也不得把本机 `.env` 提交到 Git。
