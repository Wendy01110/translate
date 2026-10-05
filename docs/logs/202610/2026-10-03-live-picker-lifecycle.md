# 实时 OCR 圈选会话隔离记录

> 日期：2026-10-03（Asia/Shanghai）
>
> 范围：共享监听器、离线回归及相关文档

## 问题与实际改动

Requester 要求继续优化，并沿用“先写文档，再改代码”的顺序。本轮先创建 [圈选会话隔离计划](../../plan/completed/2026-10-03-live-picker-lifecycle.md)，再修改测试与代码。当前监听器的完成回调原本只检查是否正在圈选；取消后重开时，上一轮延迟的有效矩形可能启动旧区域，取消结果也可能清掉新启动状态。Windows 圈选实现实际延迟 40 ms 投递完成回调，macOS 也有排队到主线程后才开始圈选的路径。

- 发起圈选时在现有状态锁内预留会话代次，排队启动、同步结果和异步完成回调全部带上该代次；取消使旧代次失效，旧回调和旧启动失败不影响新一轮。
- 圈选完成只提交一次有效结果；运行状态提交与 worker 启动前校验使用现有锁，状态显示期间停止后不再启动 worker。旧 worker 退出也在锁内检查代次，避免清理新会话的运行标志。
- 设置应用同时取消尚未完成的圈选和已经运行的循环；用户重新圈选后使用新服务与语言。工作区目标语言栏切换仍保留当前循环，并沿用原有在途结果丢弃、去重与有限补试规则。
- 保留平台 picker、截图、OCR、翻译和公共契约；没有增加依赖、配置、线程种类或新的业务链路。

## 验证

使用项目 `.venv/bin/python`（Python 3.13.14），新增回归仅使用 Fake picker、主线程队列、worker、截图和模型。

| 验证 | 实际结果 |
| --- | --- |
| 修改前监听器基线 | 33 项通过 |
| 新回归在修复前运行 | 6 个失败场景，35 项通过 |
| 修复后监听器 | 41 项通过 |
| 桌面设置、两端 UI、App、运行时、架构、文档定向验证 | 108 项通过 |
| 完整离线套件 | 407 项通过 |
| `git diff --check` | 通过 |
| 初始 WIP 内容哈希对比 | 范围外文件内容保持一致 |

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/interfaces/test_listen.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/interfaces/test_listen.py tests/interfaces/test_settings.py tests/interfaces/test_menubar.py tests/interfaces/test_live_overlay.py tests/interfaces/test_windows_ui.py tests/test_app.py tests/test_desktop_runtime.py tests/architecture tests/docs
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider
git diff --check
```

新增用例验证旧矩形/取消回调、旧排队启动、旧初始化失败、重复完成、当前初始化失败后重试、状态显示期间停止及设置取消；重开后的 Fake 截图只使用新矩形，设置后只调用新 OCR/翻译且使用新语言。既有同步/异步圈选、停止、语言切换、在途任务丢弃和有限补试继续通过。

## 文档与状态同步

- 已同步根 README 的设置应用行为、架构、实时 OCR、macOS 热键和 Windows 桌面设计，以及文档入口和计划索引。
- 原计划移动至 `completed/`，最近完成索引继续最多保留 5 项；已有图像输入与截屏边界优化记录保持原样。
- 本轮没有关联开放 Issue，Issue 不适用；环境变量、配置默认值、加载路径、CLI 参数和公共结果字段未变化，配置设计与 `.env.example` 不需要本轮改动。

## 未验证与剩余边界

本轮完成本地实现与离线契约验证，未执行真实项目桌面操作、截图、选区/剪贴板读取、OCR/翻译、App 重启、Git 提交/推送、发布或部署。原 [四层 OCR 计划](../../plan/in-progress/2026-08-20-tiered-ocr-routing.md) 仍待 macOS 首次加载提醒的实际显示验收，继续保持进行中；Fake 回调验证不替代真实平台时序与桌面验收。
