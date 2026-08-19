# OCR 分流

本文适用于截屏和本地图片的文字识别路径，面向实现者。某次 Vision 或 Unlimited-OCR 的识别结果不属于本文。

## 目标与非目标

- 目标：清晰截图优先用本机 Vision，避免每次都打 OCR 模型。
- 目标：Vision 无字、置信度过低或不可用时，再使用已配置的 Unlimited-OCR。
- 非目标：把图片直接交给翻译模型；不用 Tesseract 再做第三条链。

## 权威来源

| 内容 | 权威位置 |
| --- | --- |
| `OCR_ENGINE`、`OCR_MIN_CONFIDENCE` | `.env.example`、`config.py` |
| 分流 | `infrastructure/ocr_routing.py` |
| 本机识别 | `infrastructure/vision_ocr.py` |
| 模型识别 | `infrastructure/ocr_client.py` |

## 核心约束

- `auto`：先 Vision；成功且置信度达到阈值则停止；否则在模型已配置时调用 Unlimited-OCR。
- `vision`：只走本机，不打模型。
- `model`：只走 Unlimited-OCR。
- 菜单栏设置页可切换这三种方法，写入 `OCR_ENGINE` 后立即重建分流引擎。
- 本机失败不得改走翻译配置。
- 用户取消截屏时两路都不调用。

## 主流程

```text
图片
  -> OCR_ENGINE=auto
      -> macOS Vision
      -> 可用则返回
      -> 否则 Unlimited-OCR（若已配置）
```

## 变更与验证要求

- 修改分流条件时，同步本文、配置说明、`config-check` 和 `tests/infrastructure/test_ocr_routing.py`。
- 默认测试不得调用真实 Vision 像素识别或 Unlimited-OCR。
