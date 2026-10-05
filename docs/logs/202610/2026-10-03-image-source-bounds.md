# 图像输入与截屏边界优化记录

> 日期：2026-10-03（Asia/Shanghai）
>
> 范围：当前项目本地代码、文档与离线验证

## 目标与实际改动

按 Requester 的“先写文档，再改代码”要求，先创建 [优化计划](../../plan/completed/2026-10-03-image-source-bounds.md) 并更新文档入口，再补充回归和修改实现。任务开始时工作区已有未提交改动，本轮按初始文件快照回读差异，保留原有实现；本轮不重新归属或提交此前的 WIP。

- 图片文件读取保留元数据大小预检查，实际最多读取 20 MiB + 1 字节，再检查非空与实际大小；文件增长、变空、读取期间消失和权限/I/O 失败均有稳定错误码。
- macOS 单次截图复用同一图片读取路径；截屏命令启动失败、180 秒超时、临时文件创建/处理和截图读取失败归为 `screenshot_failed`，取消保持 `screenshot_cancelled`，继续在命令/读取完成后清理临时文件。
- 图片字节与区域面积常量归入 `core/limits.py`；macOS 固定区域加入 Windows 已有的面积前置检查，两端共用同一常量。矩形拒绝非有限坐标及规范化溢出，负坐标显示器和反向拖拽仍受支持。
- 区域面积上限为 40,000,000 坐标单位平方：Windows 按物理像素、macOS 按 AppKit 点计。该检查不证明 Retina 图像实际像素或原生抓图内存有同一上限，抓图后仍执行 20 MiB 字节检查。

## 验证

使用当前项目 `.venv/bin/python`（Python 3.13.14），未安装依赖、修改环境或调用真实上游。

| 验证 | 实际结果 |
| --- | --- |
| 改动前完整离线套件 | 357 项通过 |
| 新增回归在修复前运行 | 32 个用例复现文件/截屏/坐标缺口 |
| 定向验证：矩形、图片、两端截屏、CLI、架构、文档 | 83 项通过 |
| 完整离线套件 | 399 项通过 |
| `git diff --check` | 通过 |

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/core/test_screen_rect.py tests/infrastructure/test_image_file.py tests/infrastructure/test_screenshot.py tests/infrastructure/test_windows_infrastructure.py tests/interfaces/test_cli.py tests/architecture tests/docs
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider
git diff --check
```

全部回归使用合成图片字节、临时文件、Fake 截屏或受控 I/O 错误。覆盖恰好字节/面积上限、元数据检查后增长与变空、open/read/stat 失败、截屏超时与临时文件清理、非有限坐标和规范化溢出；CLI 的读取错误只打印错误码并停止，不调用 Fake OCR/翻译。

## 文档与状态同步

- 已同步根 README 的输入限制与失败处理、架构设计、OCR 分流设计、实时 OCR 设计，以及 `docs/README.md` 和计划索引。
- 原计划移至 `completed/`，按唯一状态目录保存，最近完成索引继续最多保留 5 项。
- 本轮没有关联开放 Issue，不新增 Issue；没有配置名、默认配置值、环境加载、公共结果字段或 CLI 参数变更，配置设计与 `.env.example` 不需要本轮改动。

## 未验证与剩余边界

本轮只验证本地实现与离线契约，未执行真实截图、读取用户剪贴板/选区、真实 OCR/翻译、App 重启、Git 提交/推送、发布或部署。原 [四层 OCR 计划](../../plan/in-progress/2026-08-20-tiered-ocr-routing.md) 仍缺 macOS 桌面首次加载提醒的实际显示证据，继续保持进行中；本轮不将离线测试提升为桌面或业务验收。
