# 内置网页翻译源计划

> 状态：已完成；内置源已接入，Google 补 `dt=t`，Bing 改为页面 token + `ttranslatev3`
>
> 创建日期：2026-08-19（Asia/Shanghai）

## 目标

让设置里可以选用不填密钥的翻译源，请求合同对齐 TTime 的 Google（内置）、Bing（内置）、DeepL（内置）。官方 API 仍保留。

## 当前依据

- TTime 内置源走网页接口：Google `client=gtx` 且必须带 `dt=t`，Bing 用 `bing.com/translator` 页面 token 再调 `ttranslatev3`，DeepL 用 `www2.deepl.com/jsonrpc`。
- 官方 DeepL / Microsoft / Google 必须用户密钥；用户要求做成 TTime 那样免填。
- 不复制 TTime 写死的有道/小牛/腾讯 token。

## 范围与非目标

- 范围：`google_web`、`bing_web`、`deepl_web`，无密钥即就绪，复用 `Translator` 端口。
- 非目标：有道/百度/腾讯网页、多源同时展示、把网页源设成破坏现有 openai 默认。

## 已完成

1. `google_web` / `bing_web` / `deepl_web` 客户端，合同对齐 TTime 内置源。
2. 无密钥即就绪；设置页用「内置」与「官方」区分。
3. 离线 mock 覆盖 gtx、Bing 页面 token、DeepL jsonrpc。
4. Google 必须带 `dt=t`（httpx 的 `params` 会丢掉 URL 里原有 query）；Bing 改为 `bing.com/translator` + `ttranslatev3`，因 Edge `/translate/auth` 已 404。

## 剩余工作

无。网页合同若再变，另开计划。

## 验收条件

- 默认测试用 HTTP mock，不打真实网页。
- 失败不改走官方源；不借用 OCR 配置。
- 设置页能区分「内置」和「官方」。

## 授权与停止边界

- 允许：网页客户端、配置、设置页、文档和离线测试。
- 需要额外授权：真实调用这些网页接口。
- 网页合同变更导致必须维护复杂逆向时停止。
