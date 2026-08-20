# 默认内置翻译源与输入框翻译

> 完成日期：2026-08-20（Asia/Shanghai）
>
> 计划：[默认内置翻译源与输入框翻译](../../plan/completed/2026-08-20-default-provider-and-input-box.md)

## 任务边界

把未配置时的翻译来源改成 `google_web`，并增加菜单输入窗口。不实施输入热键、历史或真实网页调用。

## 完成内容

- `TranslateSettings` / `AppPreferences` 默认 `TRANSLATE_PROVIDER=google_web`，无密钥即就绪。
- 菜单「输入翻译…」打开输入窗口；`DesktopListener.handle_typed_text` 复用 `SelectionTranslateService`；空文本不调用上游；忙碌时返回 `busy`，不打断已有热键锁。
- 产品范围改为三种指出方式；README、配置设计和 TTime 后续清单已同步。

## 验证结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider`：`152 passed in 0.49s`。

## 限制与未执行项

- 未打开已安装 App 做真实输入窗口或网页翻译验收。
- 未提交、未推送。
