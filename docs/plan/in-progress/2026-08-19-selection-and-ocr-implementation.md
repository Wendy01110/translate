# 划词翻译与 OCR 翻译首期实现计划

> 状态：进行中；热键按键码注册且 `Ctrl+C` 可退出，真实热键验收未执行
>
> 创建日期：2026-08-19（Asia/Shanghai）

## 目标

把当前仓库推进到本机可用的两条热键路径：划词翻译和区域截屏 OCR 翻译。翻译模型与 OCR 模型继续使用独立环境变量，互不顶替。

## 当前依据

- OCR 客户端已按 Unlimited-OCR 网关合同接入；CLI 已有本地图片 `ocr` / `ocr-translate`。
- 划词用例 `SelectionTranslateService` 已存在，但没有选区来源、热键和浮窗。
- 本机 Homebrew Python 3.14 没有 `_tkinter`，浮窗走 AppKit；热键走 `pynput`。
- 对照 TTime 后，首期只做热键划词和热键截图翻译，不做悬浮球、工具栏和剪贴板监听。

## 范围与非目标

- 范围：`ai-translate text`、`ai-translate listen`、划词热键、区域截屏热键、结果浮窗、选区剪贴板恢复、取消截屏不调用上游。
- 范围：热键可配置；`config-check` 回读热键；离线测试用假剪贴板、假截屏和假端口。
- 非目标：菜单栏、输入框窗口、历史、TTS、视频循环字幕、Windows/Linux。
- 非目标：默认监听剪贴板，或把图像直接交给翻译模型。

## 已完成

1. Unlimited-OCR 请求合同与本地图片 CLI。
2. `HOTKEY_*` 配置和 [桌面热键设计](../../design/desktop-hotkeys.md)。
3. 选区文本来源（哨兵复制并恢复剪贴板）和 `screencapture -i` 区域截屏。
4. `text`、`ocr --screenshot`、`ocr-translate --screenshot` 和 `listen`。
5. AppKit 浮窗；无 Cocoa 时回退到 AppleScript 对话框。
6. 离线测试覆盖热键解析、剪贴板恢复、取消截屏和串行锁。
7. 精简浮窗：原文/译文分栏，无额外按钮。
8. OCR `auto`：Vision 先行，置信度不足再走 Unlimited-OCR。
9. 默认热键改为划词 `alt+e`（Option+E）、OCR `alt+w`（Option+W）。
10. `listen` 改为可 `Ctrl+C` 退出；热键按物理键码注册，避免 Option+E/W 被当成 `´`/`∑` 而无法触发。
11. 辅助功能不再作为热键前提：无权限时划词改读剪贴板；模拟复制改走 Quartz Command+C。

## 剩余工作

- 在获得授权后于本机运行菜单栏 App 或 `listen`，真实按热键验证划词和圈选 OCR。菜单栏 App 见独立进行中计划。
- 菜单栏、输入框、历史和视频字幕不在本计划，见对应待进行项。

## 验收条件

- 未配置翻译时，划词热键/文本命令不发起请求；未配置 OCR 时，截屏翻译在截屏成功后仍因 OCR 未就绪而失败关闭。
- 选区为空或用户取消截屏时不调用对应上游。
- 热键字符串、默认值和 `config-check` 一致。
- 离线测试通过；默认套件不注册真实全局热键、不截真实屏幕、不打真实模型。
- 根 README 写明 `listen`、默认热键和辅助功能/屏幕录制权限。

## 授权与停止边界

- 允许：实现热键、选区、截屏接口和浮窗；离线测试。
- 需要额外授权：在本机启动 `listen` 并真实按热键、真实圈选、真实模型调用、提交和推送。
- 出现必须引入 Electron 或第二套翻译链时停止。
