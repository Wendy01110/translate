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
| 分流 | `infrastructure/ocr_routing.py` |
| 本地普通 | `infrastructure/vision_ocr.py` |
| 本地高级 | `infrastructure/paddle_ocr.py` |
| API 普通 | `infrastructure/ocr_space.py` |
| API 高级 | `infrastructure/ocr_client.py` |

## 核心约束

- `auto`：本地普通成功且置信度达到阈值则停止；否则尝试本地高级；本地高级成功且置信度达到阈值则停止；之后对单张、非空且不超过 1,000,000 字节的图片尝试 API 普通；最后才使用 API 高级。
- macOS 的本地普通是 Vision；Windows 暂无本地普通实现，直接从可选 PaddleOCR 开始。PaddleOCR 未安装时必须立即跳过，不得阻塞 API 两层。
- `vision`：只用 macOS Vision；`paddle`：只用本地 PP-OCRv6；`standard`：只用 OCR.space；`model`：只用现有 API 高级模型。旧有 `standard` 与 `model` 的配置语义保持不变。
- API 普通只支持单张且不超过 1 MB；多页、空图、非支持格式或超限时不调用它。强制 `standard` 时返回明确失败，`auto` 时直接继续 API 高级。
- macOS 设置页显示五种方法；Windows 不显示 `vision`，显示 `auto`、`paddle`、`standard`、`model`。两端设置页都提供 PP-OCRv6 `tiny`、`small`、`medium` 档位；写入 `OCR_ENGINE` 与 `OCR_LOCAL_ADVANCED_MODEL_TIER` 后立即重建分流引擎。
- `OCR_MIN_CONFIDENCE` 同时约束两个本地层；API 普通没有本项目可依赖的统一置信度。任一层返回了非空文字不等于文字一定准确，用户可强制选择本地高级或 API 高级。
- PaddleOCR 在主进程内懒加载，不经过远程接口；可选依赖未安装时 `config-check` 显示不可用。桌面监听路径在每个新 Paddle 引擎实例第一次真正初始化前显示一次提醒；并发首次调用、同一实例初始化失败后的重试均不得重复提醒，提醒显示失败也不得中断 OCR。首次实际初始化可能下载所选 PP-OCRv6 模型；普通图片 CLI 不弹桌面提醒，安装与真实初始化均不属于默认离线测试。
- 用户取消截屏时任何 OCR 层都不调用；原始图片、模型异常详情和未脱敏上游响应不得进入普通日志。

## 主流程

```text
图片
  -> OCR_ENGINE=auto
      -> macOS Vision；Windows 跳过
      -> 本地 PP-OCRv6（已安装时）
      -> 单张且 <= 1 MB：API 普通 OCR.space
      -> API 高级模型（已配置时）
```

## 变更与验证要求

- 修改分流条件时，同步本文、配置说明、`config-check`、`tests/infrastructure/test_ocr_routing.py`、PaddleOCR 适配测试和 OCR.space 客户端测试。
- 默认测试通过 Fake 端口和假 Paddle 结果验证顺序、解析、首次加载提醒和并发一次性，不得调用真实 Vision 像素识别、下载 PP-OCRv6 模型、上传 OCR.space 或调用 API 高级模型。
