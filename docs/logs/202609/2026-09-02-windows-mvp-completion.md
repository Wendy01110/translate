# Windows MVP 完成记录

> 日期：2026-09-02（Asia/Shanghai）
>
> 对应计划：[Windows 桌面版 MVP](../../plan/completed/2026-08-20-windows-mvp.md)

## 完成范围

Windows 11 x64 源码安装、PySide6/Qt Quick 托盘宿主、统一翻译工作区、设置、三组热键、普通与实时圈选、双屏负坐标、100%～200% DPI、PaddleOCR、OCR.space、Router API 高级 OCR、实时停止、单实例和普通权限/管理员窗口划词均已闭合。本次不生成安装包、不签名、不发布，也不修改其它项目。

## 管理员窗口 UIPI

- Requester 在风险说明后明确允许启动临时管理员记事本并接受 UAC；测试文件只包含固定英文 `Elevated window selection fallback works correctly.`。
- Computer Use 对该窗口只读检查时明确返回目标完整性级别高于自动化助手，因此没有尝试绕过 UIPI，也没有自动操作 UAC 或高权限窗口。
- Requester 在管理员记事本内手动 `Ctrl+A`、`Ctrl+C`，保持窗口前台并按 `Alt+E`。普通权限托盘 App 的 Qt 工作区准确显示固定英文原文和「高权限窗口选择的回退功能运行正常。」译文，证明剪贴板来源/前台进程门禁允许真正的手动复制降级。
- 管理员记事本 PID 经核对后关闭，临时测试文件删除；另一个用户已有记事本窗口没有被关闭或修改。

## 翻译时延修复

- UIPI 真测短句使用 `doubao-seed-2-1-turbo-260628` 时，Router 日志显示 46.212 秒、72 prompt tokens、2387 completion tokens；客户端请求没有传 `reasoning`、`thinking` 或 Router 私有开关，实际沿用了上游默认思考。
- 新增可选 `TRANSLATE_ROUTER_THINKING`。只有显式配置时，`HttpTranslator` 才发送 `router.thinking`；省略时保持原有通用 OpenAI 兼容请求，避免把 Router 私有字段发送给其它服务。
- 当前项目 `.env` 已设 `TRANSLATE_ROUTER_THINKING=false` 并重启托盘宿主。唯一一次修复后短句请求返回成功：Router 延迟 2.695 秒、68 prompt tokens、6 completion tokens、总计 74 tokens；CLI 端到端约 4.07 秒。

## 最终验证

- 配置/请求载荷/CLI 定向离线测试：59 passed。
- 完整离线套件：295 passed、2 skipped；跳过项均为当前 Windows 不可用的 macOS/PyObjC 路径。
- 文档结构测试、`pip check` 与 `git diff --check` 通过。
- `config-check` 脱敏回读当前 `provider=openai`、本地 Router 地址、Turbo 模型和 `router_thinking=false`，两侧 API key 仍只显示 `unset`。

## 统一复核

- 提交前再次从文档入口和唯一进行中计划回读当前状态；Windows MVP 与 Qt UI 计划仍位于 `completed/`，四层 OCR 计划只因 macOS 桌面首次提醒缺少点击级显示证据而保持 `in-progress/`，没有用 Windows 证据替代 macOS 验收。
- `TRANSLATE_ROUTER_THINKING` 在 `.env.example`、配置模型、composition、请求载荷、`config-check`、README、稳定设计与测试中的定义一致；当前脱敏配置仍回读 `router_thinking=false`。项目 `.env` 继续由 `.gitignore` 排除，仓库中没有遗留临时验收文件或提交消息文件。
- Windows 启动器和项目虚拟环境派生的 Python 3.13 桌面子进程均保持运行，启动时间晚于 `.env` 最后修改时间；本地 Router `/health` 返回 `status=ok`。
- 仅追加一条极短真实回归请求：`Unified verification.` 返回「统一验证。」，退出码为 0，端到端 2.675 秒。命令捕获层把同样的本地 Python 中文输出按错误代码页显示为乱码，纯本地 `print` 可稳定复现，因此不把该捕获层编码现象误判为 Router 翻译错误。
- 完整离线套件再次通过 295 项、跳过 2 项（macOS `fcntl` / PyObjC 专属路径），耗时 1.86 秒；`pip check` 报告无损坏依赖，`git diff --check` 通过。复核开始时 `main` 与本地 `origin/main` 均为 `f96c5de`、ahead/behind 为 0/0，工作区干净。

## 保留边界

当前安全自动化仍不能把任务栏通知区域识别为可点击窗口，因此只声明真实 `QSystemTrayIcon` 可用/可见和激活信号验证，不声称发送过物理托盘点击。Windows 源码 MVP 已完成，但这不等于 MSIX、签名、自动更新或正式发布验收。
