# 官方翻译源接入计划

> 状态：已完成；官方客户端、设置页切换和离线 mock 已落地，未做真实付费调用
>
> 创建日期：2026-08-19（Asia/Shanghai）

## 目标

在不改翻译端口语义的前提下，让划词和 OCR 翻译可以切换到少数官方翻译 API。不接非官方网页抓取，不做多源同时展示或插件市场。

## 当前依据

- TTime 内置多翻译源；本项目此前只有 OpenAI 兼容 Chat Completions。
- 用户要求参考 TTime、先只接几个权威来源。
- 待进行清单里「多翻译源市场」仍不做；本轮只做官方 API 切换。

## 范围与非目标

- 范围：`TRANSLATE_PROVIDER=openai|deepl|microsoft|google`，设置页切换，复用现有 `Translator` 端口。
- 范围：DeepL Translate v2、Azure Translator v3、Google Cloud Translation v2 的官方 HTTP 合同。
- 非目标：有道/百度/腾讯、一次请求打多个源、离线包。免密钥网页源见单独计划。

## 已完成

1. `TRANSLATE_PROVIDER` 与按来源区分的就绪条件。
2. DeepL / Microsoft / Google 官方客户端，复用 `Translator` 端口。
3. 设置页「翻译来源」和 Microsoft 区域；`config-check` 回读 `provider`。
4. 离线 mock 测试覆盖官方合同与未就绪不发请求。

## 剩余工作

无。真实付费调用不在完成本计划所需范围内。

## 验收条件

- OpenAI 兼容源行为不变；其它源只读 `TRANSLATE_*`，不得借用 OCR 配置。
- 未就绪的源不发请求；默认测试用 HTTP mock。
- 设置页和 `config-check` 能回读当前来源。

## 授权与停止边界

- 允许：官方客户端、配置、设置页、文档和离线测试。
- 需要额外授权：真实调用 DeepL/Microsoft/Google。
- 出现必须抓网页或引入 Electron 时停止。
