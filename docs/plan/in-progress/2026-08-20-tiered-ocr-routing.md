# 本地与 API 四层 OCR 分流计划

> 状态：进行中
>
> 创建日期：2026-08-20（Asia/Shanghai）
>
> 更新日期：2026-08-21（Asia/Shanghai）

## 目标

把 OCR 明确分为本地普通、本地高级、API 普通和 API 高级四层。macOS Vision 继续作为本地普通层；PP-OCRv6 作为 macOS/Windows 共用的可选本地高级层；OCR.space 与现有 Unlimited-OCR 分别作为 API 普通和 API 高级层。翻译端口、结果契约和 OCR 后翻译语义保持不变。

## 当前依据

- 当前 `OCR_STANDARD_*` 与 OCR.space 客户端已实现 API 普通层，现有 `OCR_*` 与 `HttpOcrEngine` 继续作为 API 高级层并保持当前 `.env` 兼容。
- [PaddleOCR 官方 PP-OCRv6 说明](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/algorithm/PP-OCRv6/PP-OCRv6.en.md)提供 tiny、small、medium 三档，并给出 macOS、Windows、Linux 和 CPU 支持；small 定位移动/桌面平衡档。
- [PaddleOCR 官方 Python 用法](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html)通过 `PaddleOCR.predict()` 返回 `rec_texts` 与 `rec_scores`，可以适配现有 `OcrResult` 而不改变 core 端口。
- 当前项目 `.venv` 已切换为 Python 3.13.14 arm64，并安装 PaddleOCR 3.7.0 与 PaddlePaddle 3.3.0；原 Python 3.14 环境保留在项目内备份目录，未删除。
- 当前工作区同时有 Windows MVP、实时 OCR 和 macOS 图标/构建 WIP，本计划只扩展 OCR 分流、必要设置和对应文档，不覆盖其它改动。

## 范围与非目标

- 范围：新增 `LocalAdvancedOcrSettings` 与 `OCR_LOCAL_ADVANCED_*`；PaddleOCR 作为可选依赖，未安装时自动模式立即跳过，不影响 API 两层。
- 范围：`OCR_ENGINE=auto` 顺序为本地普通 → 本地高级 → API 普通 → API 高级。macOS 本地普通是 Vision；Windows 暂无本地普通，从 PaddleOCR 开始。
- 范围：新增 `OCR_ENGINE=paddle` 只走本地高级；保留 `vision`、`standard`、`model` 分别强制本地普通、API 普通和 API 高级，避免破坏现有配置。
- 范围：本地高级默认 PP-OCRv6 tiny、CPU、懒加载；从内存解码图片，原图不落盘；模型初始化失败只返回稳定错误码，不泄漏本地路径或异常详情。
- 非目标：在本轮实现 Windows 本地普通 OCR、模型质量比较、并行竞速、自动重试、缓存、GPU 调优、FastAPI 多进程服务或把 PaddleOCR 打进发布包。
- 非目标：把“依赖可导入”写成真实识别成功，或让某一 API 层借用另一层地址、密钥、模型和超时。

## 路由规则

| 模式 | 路径 |
| --- | --- |
| `auto` | 本地普通 → 本地高级 → API 普通 → API 高级；任一层结果合格即停止 |
| `vision` | 只用 macOS Vision |
| `paddle` | 只用本地 PP-OCRv6 |
| `standard` | 只用 API 普通 OCR.space；多页或单张超过 1 MB 返回明确失败 |
| `model` | 只用现有 API 高级模型 |

两个本地层使用 `OCR_MIN_CONFIDENCE`；API 普通没有统一置信度可供可靠升级判断。任何一层“返回了文字”都不能证明文字正确，用户需要保留强制选择本地高级或 API 高级的入口。

## 执行步骤

1. 增加本地高级配置、可选依赖、PaddleOCR 懒加载适配和稳定错误边界。
2. 增加本地两层组合，把现有远程两层明确改称 API 两层，组成四层自动顺序。
3. 更新 macOS/Windows 设置页、`config-check`、`.env.example`、README 和稳定设计。
4. 用假 Paddle pipeline 覆盖模型参数、结果解析、置信度、复用和异常；用 Fake 端口覆盖四层顺序与停止条件。
5. 运行定向测试、完整离线套件、`pip check` 和 `git diff --check`。
6. 经单独授权后，在 Python 3.12/3.13 项目环境安装可选依赖并下载 PP-OCRv6 small；用用户提供的非敏感图片验证本地高级识别文本、首次加载时间和后续时延。
7. 经另行授权后，再分别验证 OCR.space 与现有 API 高级模型；真实上传前重新确认额度和数据边界。

## 验收条件

- 四层使用独立适配与配置；任一层缺失或失败时按顺序降级，不借用其它层配置。
- 默认离线测试不请求 Vision 像素识别、不下载 PP-OCRv6、不调用 OCR.space、API 高级模型或真实翻译。
- `auto` 的顺序和停止条件可由 Fake 端口验证；本地高级成功时不调用 API，API 普通成功时不调用 API 高级。
- 四种强制单层模式可分别验证；现有 `OCR_ENGINE=standard` 与 `model` 行为保持不变。
- `config-check` 能区分本地普通、本地高级、API 普通和 API 高级的静态状态，但不把静态就绪声明为真实识别成功。
- macOS PP-OCRv6 真实样例已经通过；Windows 真机验证仍未完成，因此计划保持进行中，不能声称 Windows 四层 OCR 已验收。

## 授权与停止边界

- 允许：当前项目内代码、测试、文档、配置示例和离线 Fake/HTTP mock。
- 需要额外授权：停止 App、重建 `.venv`、安装或升级 PaddleOCR/PaddlePaddle、下载 PP-OCRv6 模型、修改真实 `.env`、真实截屏、调用任一外部 OCR/翻译、提交、推送、部署和发布。
- 出现以下情况停止：需要默认上传原图、默认并行调用多层、无界图片进入模型、用翻译配置代替 OCR、修改当前项目以外文件，或真实依赖要求扩大到未经确认的运行时/系统改动。

## 当前进度

- 已新增 `LocalAdvancedOcrSettings`、`PaddleOcrEngine` 懒加载适配、PP-OCRv6 tiny/small/medium 有界档位和 CPU 边界；默认 tiny，优先降低本地时延。
- 已完成本地 Vision → PaddleOCR 与 API OCR.space → Unlimited-OCR 两组串行分流，并组成四层 `auto`；新增 `paddle` 强制模式，Windows 设置页从本地高级开始。
- 已同步 `.env.example`、README、`config-check`、macOS/Windows 设置和稳定设计；两个桌面设置页均可切换 PP-OCRv6 `tiny`、`small`、`medium`，并把选择写入 `OCR_LOCAL_ADVANCED_MODEL_TIER` 后立即重建运行时。
- 已在 macOS/Windows 桌面监听路径接入 Paddle 首次初始化提醒：只在真正创建所选模型 pipeline 前显示，同一引擎实例在并发调用或初始化失败重试时也只提示一次；提醒器异常不影响 OCR，普通图片 CLI 不弹桌面提醒。
- 项目环境已使用 Python 3.13.14 arm64 重建，安装 PaddleOCR 3.7.0 与 PaddlePaddle 3.3.0；`paddle.utils.run_check()` 确认 PaddlePaddle 可在 1 个 CPU 上运行，`pip check` 无依赖冲突。原 Python 3.14 环境保留为 `.venv-python314-backup-20260820`，没有删除。
- PP-OCRv6 small 检测与识别模型已下载到 PaddleX 官方缓存目录，落盘约 9.6 MB 与 21 MB。用户提供的 1800×1496 PNG 已仅在本机内存中完成两次识别：首次含下载和初始化 18.002 秒，复用同一 pipeline 的第二次 4.300 秒，平均置信度约 0.9603。
- 实图正文、标题和代码块基本完整；已观察到 `OCR` 被识别为 `0CR`、复制图标被识别为 `Q`，因此本次证明本地高级链路可用，不把单张样例提升为普遍精度验收。
- PaddleOCR、四层路由、composition、配置、设置和 CLI 定向测试已通过；其中首次加载提醒相关的 Paddle、composition、overlay 与 App 定向测试 31 项通过，Python 3.13 环境下完整离线套件 249 项通过，`pip check` 与 `git diff --check` 通过。
- macOS App 已重新构建并签名，arm64 启动器链接 Homebrew Python 3.13，嵌入的新项目 site-packages 路径、Info.plist 和代码签名检查通过；打开后进程实际从新环境加载并保持运行。
- 本轮提醒改动未修改真实 `.env`；当前静态回读是 `OCR_ENGINE=paddle`、`PP-OCRv6_tiny`。本轮没有初始化或下载 Paddle 模型，也没有调用 OCR.space、API 高级 OCR 或翻译上游。剩余验证是重开 macOS App 后的提醒界面、本地 tiny 实际时延、Windows 11 x64 真机安装与本地高级识别，以及经单独授权后的两层 API 实测。
