# 文档入口

> 更新时间：2026-08-20（Asia/Shanghai）

本页是项目维护文档的唯一默认入口，只保留当前状态、活动任务和权威资料路由。面向使用者的最短路径见 [项目 README](../README.md)；日期化事实放在计划或日志，不在本页重复维护。

## 当前状态

- 仓库已建立文档框架、Agent 规则和可安装的 Python 骨架。使用者安装入口是 `./scripts/install.sh`，会创建 `.venv` 并安装 `~/Applications/AI Translate.app`。
- 翻译与 OCR 通过独立环境变量配置；翻译默认 Google 内置网页源（免密钥），也可选用 Bing/DeepL 内置或官方/OpenAI 兼容源；只读一个配置文件；`config-check` 回读路径和就绪状态，但不调用上游。
- OCR 默认先走本机 Vision，不够再用 Unlimited-OCR。CLI 支持本地图片和 macOS 圈选截屏。
- 划词和 OCR 可通过 `listen` 热键或菜单栏 App 触发；菜单「输入翻译…」打开输入窗口。浮窗只显示原文和译文，点选后可用 `Command+C` 复制。设置页按翻译来源只显示需要的字段；「应用」立即生效并留在窗口，「保存」写入后关闭；内置网页源不用密钥。
- 用户本机试用菜单栏 App，报告热键划词和圈选 OCR 基本可用。历史和视频字幕尚未实施。当前没有开放 Issue。
- 当前没有进行中计划。下一档产品能力见 [待进行](./plan/pending/2026-08-19-ttime-inspired-follow-on.md) 的复制译文与有界历史。

## 当前工作

当前没有进行中计划。

## 按任务查找

| 任务 | 入口 |
| --- | --- |
| 安装并检查配置 | [项目 README](../README.md)（`./scripts/install.sh`） |
| 确认首期做什么、不做什么 | [产品范围](./design/product-scope.md) |
| 修改分层、端口或执行链 | [架构设计](./design/architecture.md) |
| 修改环境变量或双模型边界 | [配置设计](./design/configuration.md) |
| 修改 macOS 热键、菜单栏或浮窗 | [桌面热键设计](./design/desktop-hotkeys.md) |
| 修改 OCR 本机/模型分流 | [OCR 分流](./design/ocr-routing.md) |
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
