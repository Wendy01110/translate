# OCR 分流

本文适用于截屏和本地图片的文字识别路径，面向实现者。某次 Vision、PaddleOCR、OCR.space 或高级模型的识别结果不属于本文。

## 目标与非目标

- 目标：把 OCR 明确分为本地普通、本地高级、API 普通和 API 高级四层，默认优先在本机完成识别。
- 目标：macOS 用 Vision 作为本地普通层；可选 PP-OCRv6 作为 macOS/Windows 共用的本地高级层；OCR.space 与现有视觉模型分别作为 API 普通和 API 高级层。
- 非目标：根据文本长度或字符形态猜识别质量、并行竞速四层，或让任一 API 层借用另一层密钥。

## 权威来源

| 内容 | 权威位置 |
| --- | --- |
| `OCR_ENGINE`、四层配置与大小边界 | `.env.example`、`config.py`、`infrastructure/ocr_space.py` |
| 图片输入页数/字节与固定区域面积上限 | `core/limits.py`、`core/ocr_input.py`、`infrastructure/image_file.py`、两端截屏适配 |
| 分流 | `infrastructure/ocr_routing.py` |
| 本地普通 | `infrastructure/vision_ocr.py` |
| 本地高级 | `infrastructure/paddle_ocr.py` |
| API 普通 | `infrastructure/ocr_space.py` |
| API 高级 | `infrastructure/ocr_client.py` |

## 核心约束

- `auto`：本地普通成功且置信度达到阈值则停止；否则尝试本地高级；本地高级成功且置信度达到阈值则停止；之后对单张、非空且不超过 1,000,000 字节的图片尝试 API 普通；最后才使用 API 高级。
- macOS 的本地普通是 Vision；Windows 暂无本地普通实现，直接从可选 PaddleOCR 开始。PaddleOCR 未安装时必须立即跳过，不得阻塞 API 两层。
- `vision`：只用 macOS Vision；`paddle`：只用本地 PP-OCRv6；`standard`：只用 OCR.space；`model`：只用现有 API 高级模型。旧有 `standard` 与 `model` 的配置语义保持不变。
- 先应用项目级输入预算：最多 10 页，每张与全部原始图片合计均最多 20 MiB；空图或全局超限立即失败，不进入任一 OCR 层。预算内的有效输入再按提供方能力分流。
- API 普通只支持单张且不超过 1 MB；预算内的多页、非支持格式或超过 1 MB 时不调用它。强制 `standard` 时返回明确失败，`auto` 时继续 API 高级。
- macOS 设置页显示五种方法；Windows 不显示 `vision`，显示 `auto`、`paddle`、`standard`、`model`。两端设置页都提供 PP-OCRv6 `tiny`、`small`、`medium` 档位；写入 `OCR_ENGINE` 与 `OCR_LOCAL_ADVANCED_MODEL_TIER` 后立即重建分流引擎。
- `OCR_MIN_CONFIDENCE` 同时约束两个本地层；API 普通没有本项目可依赖的统一置信度。任一层返回了非空文字不等于文字一定准确，用户可强制选择本地高级或 API 高级。
- PaddleOCR 在主进程内懒加载，不经过远程接口；可选依赖未安装时 `config-check` 显示不可用。桌面监听路径在每个新 Paddle 引擎实例第一次真正初始化前显示一次提醒；普通 OCR 的提醒进入翻译工作区，实时 OCR 的提醒进入实时字幕条，不得另弹普通窗口。并发首次调用、同一实例初始化失败后的重试均不得重复提醒，提醒显示失败也不得中断 OCR。首次实际初始化可能下载所选 PP-OCRv6 模型；普通图片 CLI 不弹桌面提醒，安装与真实初始化均不属于默认离线测试。Windows CPU 使用 `enable_mkldnn=False` 和普通 Paddle 后端，避开 PaddlePaddle 3.3.0 oneDNN 新执行器的属性转换失败；其它平台不覆盖上游默认。
- API 高级模型名为 `Unlimited-OCR` 时使用原有专用提示词、`skip_special_tokens` 和 `images_config.image_mode`；其它模型按标准 OpenAI 视觉消息发送图片，并用明确提示约束只返回识别文字。两种合同共用同一 `HttpOcrEngine`、大小/超时边界和结果清理，不为本机 Router 复制 OCR 业务语义。
- 用户取消截屏时任何 OCR 层都不调用；原始图片、模型异常详情和未脱敏上游响应不得进入普通日志。

## API 普通响应与失败边界

OCR.space 最终响应进入解析前仍受 2,000,000 字节的解码后大小限制，超限返回 `ocr_response_too_large`。JSON 语法、编码或过深嵌套导致解码失败时返回现有 `invalid_json`，非对象 JSON 也按该错误处理；字节上限不等于固定的 JSON 嵌套层数或进程内存上限。

响应的 `OCRExitCode` 保留原有整数/字符串成功码 `1`、`2` 判断；`FileParseExitCode` 保留 `1`、`"1"` 与缺省/空值判断。列表或对象状态码不能引发集合查找异常：整次状态不接受时返回 `empty_ocr_text`，单条状态不接受时跳过该条，再按原顺序提取其它有效文字，没有有效文字才失败。上游 `ErrorMessage`、异常条目的文字和解码异常详情不进入失败结果或普通日志。

普通层的上述失败由既有分流消费：`auto` 继续已配置的 API 高级层，高级成功后只翻译其识别文字；强制 `standard` 保留普通层失败，不调用高级或翻译。不新增自动重试、不修改请求格式或借用其它层配置。这里说明的是响应结构与失败处理，不能据此证明提供方识别质量。

## 图像来源与失败边界

本地图片和截图的单张输入上限为 20 MiB（20,971,520 字节），定义在 `core/limits.py`。图片文件先按文件元数据拒绝已超限输入，再最多读取上限 + 1 字节并按实际结果检查：检查后增长也不会无界读取，读取时变空仍返回 `empty_image`。不存在或非普通文件返回 `image_not_found`，类型不支持返回 `unsupported_image_type`，超限返回 `image_too_large`，权限或其它 I/O 错误返回 `image_read_failed`，不得输出路径或系统异常详情。CLI 的图片来源失败返回退出码 2，且不进入 OCR/翻译。

整批输入的共享检查在 `core/ocr_input.py`：先拒绝 0 页或超过 10 页，再逐页检查非空、单张字节和累计字节。单张超过 20 MiB 返回 `image_too_large`；各页合法但合计超过 20 MiB 返回 `ocr_batch_too_large`；超过 10 页返回 `ocr_too_many_pages`；边界允许等号。重复图片也按其每次出现计入预算。预算针对原始图片字节，不声明为提供方限额、base64 请求大小、原生解码或进程内存上限。

CLI 的 `ocr` / `ocr-translate --pages` 在读文件前检查页数，读取每张后检查当前累计预算，首次超限立即停止，后续路径不再读取，也不输出已读取图片或路径；单图和截图结果同样校验。CLI 输入预算失败退出码为 2；直接 OCR 端口/用例返回 `failure`。路由、两个 tier 组合、四个直接适配及 OCR 翻译用例复用共享检查；全局失败不触发 fallback，且发生在 Vision 回调、Paddle 提醒/初始化/解码、base64 编码或 HTTP 前。HTTP 适配继续先检查自身配置，未配置时保留原有就绪错误；预算内的有效输入继续遵守 OCR.space 更严格的单图/1 MB 规则。实时 OCR 实际处理新画面时也检查单图字节，超限清空本轮文字与补试记忆并显示失败。

macOS 单次 `screencapture` 复用上述读取。命令返回非零、输出缺失或空图继续使用 `screenshot_cancelled`；命令启动、180 秒超时、临时文件创建/处理或截图读取失败归为 `screenshot_failed`。命令与读取成功或失败后均尝试清理临时文件，清理发生 I/O 失败时同样返回 `screenshot_failed`。字节超限继续保留 `image_too_large`。

两端固定区域截屏使用共享 `MAX_CAPTURE_PIXELS=40_000_000`，在抓图前检查矩形宽 × 高；这里按 `ScreenRect` 坐标面积计，Windows 为物理像素面积，macOS 为 AppKit 屏幕点面积，不宣称这是 Retina 图像的实际像素数或原生抓图内存上限。坐标和尺寸必须有限，规范化后的原点也必须有限；无效或过小区域返回 `region_too_small`，面积超限返回 `image_too_large`。负坐标显示器与反向拖拽继续可用。抓图完成后仍检查非空和 20 MiB 字节上限。

## 主流程

```text
图片
  -> 项目级页数与原始字节预算
  -> OCR_ENGINE=auto（预算内）
      -> macOS Vision；Windows 跳过
      -> 本地 PP-OCRv6（已安装时）
      -> 单张且 <= 1 MB：API 普通 OCR.space
      -> API 高级模型（已配置时）
```

## 变更与验证要求

- 修改分流条件或 Paddle 平台参数时，同步本文、配置说明、`config-check`、`tests/infrastructure/test_ocr_routing.py`、PaddleOCR 适配测试和 OCR.space 客户端测试。
- 修改输入预算时，同步共享常量/校验、CLI 帮助、配置示例、用户提示及 `tests/infrastructure/test_ocr_input_bounds.py`、OCR 用例和 CLI 回归；就绪判定仍只表示配置可用，不新增预算字段。
- 默认测试通过 Fake 端口和假 Paddle 结果验证顺序、解析、首次加载提醒和并发一次性，不得调用真实 Vision 像素识别、下载 PP-OCRv6 模型、上传 OCR.space 或调用 API 高级模型。
