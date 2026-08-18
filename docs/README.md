# 文档入口

> 更新时间：2026-08-19（Asia/Shanghai）

本页是项目维护文档的唯一默认入口，只保留当前状态、活动任务和权威资料路由。面向使用者的最短路径见 [项目 README](../README.md)；日期化事实放在计划或日志，不在本页重复维护。

## 当前状态

- 仓库已建立文档框架、Agent 规则和可安装的 Python 骨架。
- 翻译模型与 OCR 模型通过独立环境变量配置；`ai-translate config-check` 可以回读配置就绪状态，但不调用上游。
- 划词翻译和 OCR 翻译的用例边界已用 Fake 端口覆盖；桌面划词、截屏圈选和真实模型调用尚未实现。
- 当前没有进行中计划，也没有开放 Issue。下一阶段实现见待进行计划。

## 当前工作

当前没有进行中计划。

需要选择后续工作时，从 [计划状态索引](./plan/README.md) 的待进行项读取，不要把已完成的框架搭建或历史日志当成下一步指令。

## 按任务查找

| 任务 | 入口 |
| --- | --- |
| 安装并检查配置 | [项目 README](../README.md) |
| 确认首期做什么、不做什么 | [产品范围](./design/product-scope.md) |
| 修改分层、端口或执行链 | [架构设计](./design/architecture.md) |
| 修改环境变量或双模型边界 | [配置设计](./design/configuration.md) |
| 更新计划、Issue 或日志 | [文档框架](./design/documentation-framework-guide.md) |
| 执行仓库任务 | [AGENTS.md](../AGENTS.md) |

## 机器权威

| 内容 | 权威来源 |
| --- | --- |
| 项目版本 | [pyproject.toml](../pyproject.toml) |
| 环境变量名和默认值 | [.env.example](../.env.example)、[config.py](../src/ai_translate/config.py) |
| 结果状态和字段 | [core/models.py](../src/ai_translate/core/models.py) |
| 端口 | [core/ports.py](../src/ai_translate/core/ports.py) |
| 依赖方向 | [架构测试](../tests/architecture/test_dependency_rules.py) |
| 当前任务状态 | [计划状态索引](./plan/README.md) 及唯一状态目录中的原文件 |

静态配置、离线测试、真实模型调用和桌面验收是不同证据层，不能相互替代。

## 文档状态约定

- `design/` 保存长期稳定规则；`plan/in-progress/` 和 `plan/pending/` 保存当前任务状态；`issues/open/` 保存尚未闭合的问题。
- `logs/YYYYMM/` 保存日期化结果与验证；`completed/`、`closed/`、`archive/` 和 Git 历史只在追溯时读取。
- 状态变化时移动原文件并同步引用，不复制并存，不用历史日志证明当前能力。

## 历史查找

完成计划见 [plan/completed/](./plan/completed/)，日期日志见 [logs/](./logs/)，关闭 Issue 见 [issues/closed/](./issues/closed/)，精选历史证据见 [archive/](./archive/)；需要旧版本细节时再按日期或 Git 历史追溯。
