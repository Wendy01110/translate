# 翻译源与桌面配置落地

> 完成日期：2026-08-20（Asia/Shanghai）
>
> 计划：[官方翻译源接入](../../plan/completed/2026-08-19-official-translate-sources.md)、[内置网页翻译源](../../plan/completed/2026-08-19-web-translate-sources.md)

## 任务边界

在已有双模型骨架上接入可切换的翻译来源，并让菜单栏设置页能改来源、密钥和热键。划词/OCR 热键路径与菜单栏 App 仍另有进行中计划，本日志不把它们标成已验收。

## 完成内容

- `TRANSLATE_PROVIDER` 支持 `google_web` / `bing_web` / `deepl_web` 与 `openai` / `deepl` / `microsoft` / `google`。
- 官方客户端按 DeepL v2、Azure Translator v3、Google Cloud Translation v2 mock 覆盖。
- 内置网页源：Google 请求必须带 `dt=t`；Bing 改为翻译页 token + `ttranslatev3`（Edge `/translate/auth` 已 404）；DeepL jsonrpc 保持。
- 设置页按来源只显示需要的字段；配置只读一个 `.env` 文件。

## 验证结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider`：离线套件通过。
- 本机对 `Hello` 试了内置 Google 与 Bing，得到「你好」；用户反馈内置 DeepL 可用。这只证明当时网页合同可通，不证明长期稳定。
- 未执行官方 DeepL / Microsoft / Google 付费调用。
- 未把真实密钥写入日志或 Git。

## 限制与未执行项

- 未关闭划词/OCR 首期与菜单栏 App 计划：真实热键和系统权限验收仍待用户在本机完成。
- 未推送。
