# 本地与 API 四层 OCR 分流计划

> 状态：进行中
>
> 创建日期：2026-08-20（Asia/Shanghai）
>
> 更新日期：2026-09-05（Asia/Shanghai）

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
- macOS PP-OCRv6 small 与 Windows PP-OCRv6 tiny 本地图片真实样例已经通过；Windows 真实屏幕圈选、桌面首次提醒与 API 两层也已完成。计划仅因 macOS 桌面首次提醒仍缺点击级显示证据而保持进行中，不能把其中一端的证据替代另一端。

## 授权与停止边界

- 允许：当前项目内代码、测试、文档、配置示例和离线 Fake/HTTP mock。
- 需要额外授权：停止 App、重建 `.venv`、安装或升级 PaddleOCR/PaddlePaddle、下载 PP-OCRv6 模型、修改真实 `.env`、真实截屏、调用任一外部 OCR/翻译、提交、推送、部署和发布。
- 出现以下情况停止：需要默认上传原图、默认并行调用多层、无界图片进入模型、用翻译配置代替 OCR、修改当前项目以外文件，或真实依赖要求扩大到未经确认的运行时/系统改动。

## 当前进度

- 已新增 `LocalAdvancedOcrSettings`、`PaddleOcrEngine` 懒加载适配、PP-OCRv6 tiny/small/medium 有界档位和 CPU 边界；默认 tiny，优先降低本地时延。
- 已完成本地 Vision → PaddleOCR 与 API OCR.space → Unlimited-OCR 两组串行分流，并组成四层 `auto`；新增 `paddle` 强制模式，Windows 设置页从本地高级开始。
- API 高级客户端现在按模型闭合两种 OpenAI 兼容合同：`Unlimited-OCR` 保留原有专用提示词、`skip_special_tokens` 和 `images_config`；其它视觉模型发送标准 `image_url` 消息和只返回原文的明确提示，不再把私有参数透传给通用模型。对应 HTTP mock 合同测试已补齐。
- 已同步 `.env.example`、README、`config-check`、macOS/Windows 设置和稳定设计；两个桌面设置页均可切换 PP-OCRv6 `tiny`、`small`、`medium`，并把选择写入 `OCR_LOCAL_ADVANCED_MODEL_TIER` 后立即重建运行时。
- 已在 macOS/Windows 桌面监听路径接入 Paddle 首次初始化提醒：只在真正创建所选模型 pipeline 前显示，同一引擎实例在并发调用或初始化失败重试时也只提示一次；提醒器异常不影响 OCR，普通图片 CLI 不弹桌面提醒。
- macOS 验收环境曾使用 Python 3.13.14 arm64、PaddleOCR 3.7.0 与 PaddlePaddle 3.3.0；当前 Windows 11 x64 验收环境使用 Python 3.13.15 AMD64 和同版本 Paddle 依赖。两端 `paddle.utils.run_check()` 均确认 PaddlePaddle 可在 1 个 CPU 上运行，`pip check` 无依赖冲突；macOS 原 Python 3.14 环境保留为 `.venv-python314-backup-20260820`，没有删除。
- PP-OCRv6 small 检测与识别模型已下载到 PaddleX 官方缓存目录，落盘约 9.6 MB 与 21 MB。用户提供的 1800×1496 PNG 已仅在本机内存中完成两次识别：首次含下载和初始化 18.002 秒，复用同一 pipeline 的第二次 4.300 秒，平均置信度约 0.9603。
- 实图正文、标题和代码块基本完整；已观察到 `OCR` 被识别为 `0CR`、复制图标被识别为 `Q`，因此本次证明本地高级链路可用，不把单张样例提升为普遍精度验收。
- Windows 首次 PP-OCRv6 tiny 实测下载检测与识别模型后，在 oneDNN 推理阶段触发 PaddlePaddle 3.3.0 `ConvertPirAttribute2RuntimeAttribute` 未实现错误；传入 `enable_mkldnn=False` 后同一缓存模型约 3 秒完成预测，适配器已把该兼容参数限制在 Windows，macOS 仍保留上游默认。
- Windows 正式 CLI 对三行中英文测试图完整识别，缓存模型进程冷启动用时 3.363 秒；纯英文测试图经本地 OCR 后调用 Google 内置翻译源，3.869 秒返回中文。该结果证明 Windows 本地高级与 OCR 后翻译链路可用，不替代真实截图、复杂版面和普遍精度验收。
- PaddleOCR、四层路由、composition、配置、设置和 CLI 定向测试已通过；其中首次加载提醒相关的 Paddle、composition、overlay 与 App 定向测试 31 项通过，Python 3.13 环境下完整离线套件 249 项通过，`pip check` 与 `git diff --check` 通过。
- macOS App 已重新构建并签名，arm64 启动器链接 Homebrew Python 3.13，嵌入的新项目 site-packages 路径、Info.plist 和代码签名检查通过；打开后进程实际从新环境加载并保持运行。
- Windows 项目 `.env` 已保持 `OCR_ENGINE=auto` 与 PP-OCRv6 tiny，并把 API 高级独立配置到本机 `llm-token-router` 的已验证视觉模型。项目客户端真实识别两行合成图时只返回原文；正式 CLI 强制 API 高级 OCR 和 API 高级 OCR 后 Router 翻译均成功。OCR.space 使用官方公共 `helloworld` 测试 key 的前两次 Engine 2 请求返回 HTTP 503，停止重试后在后续独立复试中 1.969 秒准确识别 `OCR SPACE WINDOWS 2026`；公共 key 始终未写入 `.env`，API 普通层现已有成功真测。
- Windows 主屏实际鼠标圈选的三行固定文本经 PP-OCRv6 tiny 完整识别并由 Router 翻译；双屏虚拟桌面的副屏负坐标、DPI 96 客户区也准确识别 `SECOND MONITOR OCR 2026`。普通 OCR 与实时 OCR 的桌面首次加载提醒均已实际显示，来源脚注显示「本地高级」，OCR 原文修正后只重跑文本翻译。Windows 端不再缺 API 两层、真实截屏、鼠标圈选或首次提醒证据；剩余验证仅是 macOS 桌面端首次提醒的实际显示。
- API 高级 OCR 新增独立 `OCR_ROUTER_THINKING`，与翻译侧开关不互借；两条默认本机 Router 路径在省略配置时都显式关闭思考，自定义 Router 可覆盖，普通兼容地址不自动接收私有字段。macOS 实时 OCR 的 Paddle 首次加载提示已改由实时字幕条承接，离线合同已覆盖；实际 macOS 点击级显示仍待复验，因此本计划继续保持进行中。实现与验证见 [macOS 复核与 Router 思考默认关闭记录](../../logs/202609/2026-09-04-macos-review-and-router-thinking-defaults.md)。
- 2026-09-05 完成一次整体代码与文档复核：删除未使用的 OCR 工厂转发函数和导入，删除已退出运行时的独立 `interfaces/input_box.py` 及其专属测试，macOS/Windows 设置保存逻辑合并到共享辅助函数，桌面 `app` / `listen` 路径不再重复构造不会直接使用的 CLI OCR、翻译和选择服务，并把桌面分流限制在第一个 CLI 子命令，避免文本或图片参数恰好叫 `app` / `listen` 时误启桌面组合；配置设计改为指向实际的 `config_status()` / `ocr_capability_ready()` 就绪判定。历史计划、日志和视觉稿保留为追溯记录。完整离线套件、`pip check`、编译检查和 `git diff --check` 均通过。实现细节见 [代码与文档复核记录](../../logs/202609/2026-09-05-code-review-and-redundancy-cleanup.md)。
