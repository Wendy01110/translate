# 项目框架与文档体系搭建

> 完成日期：2026-08-19（Asia/Shanghai）
>
> 计划：[项目框架与文档体系搭建计划](../../plan/completed/2026-08-19-project-framework-bootstrap.md)

## 任务边界

本次从空目录开始建立文档框架和可安装的 Python 骨架。工作区开始时不是 Git 仓库，也没有既有 WIP。任务范围包括基础文档、双模型配置、用例边界、CLI `config-check`、离线测试和首次本地提交。

## 完成内容

- 新增文档入口、产品范围、架构、配置和文档框架说明，以及计划/Issue/归档目录。
- 将划词与 OCR 的首期实现写成待进行计划；本任务本身作为已完成计划保留。
- 新增 `ai_translate` 包：`TRANSLATE_*` 与 `OCR_*` 独立加载，feature 不互相引用，组合只发生在 `bootstrap` 和 `app.py`。
- CLI 目前只有 `config-check`；密钥只输出 `set`/`unset`。
- HTTP 客户端已按 OpenAI 兼容 Chat Completions 写好请求形状，默认测试只用 mock，不访问上游。

## 验证结果

- 环境：项目根 `.venv`，Python 3.14.5，`ai-translate 0.1.0`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider`：`27 passed in 0.12s`。
- `.venv/bin/ai-translate config-check`：翻译和 OCR 均 `ready: false`，`api_key: unset`，输出中没有密钥内容。该结果只证明未配置时的回读行为，不证明上游可调用。
- `.venv/bin/ai-translate --version`：`ai-translate 0.1.0`。
- 本记录写入后将做本地 `git init` 与首次提交；精确 revision 以提交后的 Git 历史为准。

## 限制与未执行项

- 未实现划词热键、选区读取、截屏圈选和结果浮窗。
- 未执行真实翻译调用、真实 OCR 调用、健康检查或付费请求。
- 未读取本机真实 `.env` 去探测上游。
- 未设置 Git remote，也未推送。
