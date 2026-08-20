# 用户 README 与快捷安装

> 完成日期：2026-08-20（Asia/Shanghai）
>
> 计划：无单独计划；一次性文档与安装入口整理。

## 任务边界

把根 `README.md` 收成给使用者看的最短路径，并提供一条安装命令。不改翻译默认来源，不执行真实热键或模型验收。

## 完成内容

- 根 README 去掉维护状态、计划/架构/Agent 入口、离线测试和网页接口实现细节，只保留安装、第一次使用、热键、权限、配置、命令行和常见问题。
- 新增 `scripts/install.sh`：检查 Python 3.12+、创建 `.venv`、安装运行依赖、调用打包脚本并打开 `~/Applications/AI Translate.app`。
- `scripts/build-macos-app.sh` 按当前解释器解析 `Python.framework`，不再写死 Homebrew `python@3.14`。
- `docs/README.md` 指向该安装入口。

## 验证结果

- `bash -n scripts/install.sh scripts/build-macos-app.sh`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider`：`141 passed in 0.75s`。

## 限制与未执行项

- 未运行 `scripts/install.sh` 全量安装，避免覆盖正在使用的 App。
- 未改 `TRANSLATE_PROVIDER` 代码默认值（仍为 `openai`）；与 `.env.example` / 设置页 fallback 的 `google_web` 不一致，见回复中的后续优化项。
- 未执行真实热键、截屏、权限或上游调用。
- 未提交、未推送。
