# macOS 复核与 Router 思考默认关闭记录

> 日期：2026-09-04（Asia/Shanghai）
>
> 关联计划：[本地与 API 四层 OCR 分流](../../plan/in-progress/2026-08-20-tiered-ocr-routing.md)

## 范围与结论

- 工作区原本干净，`main` 通过仅快进方式从 `b55b3e8` 更新到 `b485677`；上游主要完成 Windows PySide6/Qt Quick/QML 迁移与验收，本轮没有产生合并提交。
- 拉取中 macOS AppKit 工作区没有被重写；共享变化仅包括忙碌错误文案、Paddle「本地高级」来源脚注、跨平台工作区格式函数，以及仅由 Windows 启用的剪贴板来源校验。
- 复核发现 macOS 实时 OCR 首次加载 Paddle 时仍把提示发到普通翻译工作区，而 Windows 新路径已经发到实时字幕条。本轮让 macOS 复用相同路由规则，并删除只转发到共享格式函数的 `format_macos_translation` 包装；普通 OCR 与实时 OCR 的展示边界保持独立。
- 翻译和 API 高级 OCR 现在分别具有 `TRANSLATE_ROUTER_THINKING` 与 `OCR_ROUTER_THINKING`。两侧连接规范本机 Router 地址 `http://127.0.0.1:8000/v1` 或等价 `localhost` 地址且省略开关时，均按 `false` 发送；显式配置优先。其它 OpenAI 兼容地址在未显式配置时不接收 Router 私有字段，避免为了默认关闭思考破坏通用兼容性。

## 验证

- 修改前完整离线基线：302 passed。
- 配置、模型客户端、CLI、工作区、实时字幕条、App 组合与文档定向测试：126 passed。
- 修改后完整离线套件：305 passed。
- 项目 `.venv` 为 Python 3.13.14；`pip check` 报告 `No broken requirements found`，`git diff --check` 通过。pip 因用户缓存目录不可写而禁用缓存，不影响依赖一致性结论。

## 未执行与剩余边界

- 没有读取或修改真实 `.env`，没有启动或重启桌面 App、Router 或其它服务，没有调用真实翻译/OCR，也没有执行 macOS 原生点击级复验。
- macOS Paddle 首次提醒的实际桌面显示仍未验收，因此关联计划继续保持进行中；本轮离线结果不替代该真机证据。
- Requester 后续明确授权把本轮改动提交到本地 Git；没有推送、构建、部署或发布。
