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

## 保留边界

当前安全自动化仍不能把任务栏通知区域识别为可点击窗口，因此只声明真实 `QSystemTrayIcon` 可用/可见和激活信号验证，不声称发送过物理托盘点击。Windows 源码 MVP 已完成，但这不等于 MSIX、签名、自动更新或正式发布验收。
