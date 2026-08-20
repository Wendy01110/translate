# macOS 菜单栏 App 计划

> 状态：已完成；菜单栏 `.app` 已能构建安装，用户本机试用报告基本可用
>
> 创建日期：2026-08-19（Asia/Shanghai）

## 目标

把本机常驻从终端 `listen` 收成一个名为 `AI Translate` 的 macOS 菜单栏 App，让系统设置里的辅助功能和屏幕录制授权对象是这个 App，而不是 Cursor 或 `python3`。不引入 Electron。

## 当前依据

- TTime 能勾上权限，是因为它是带 `LSUIElement` 的 `.app`；划词仍要模拟 `Command+C`。
- 本项目热键已走 `RegisterEventHotKey`，划词模拟复制走 Quartz；从终端启动时 TCC 记到 Cursor/Python。
- 用户明确要求做成 App。菜单栏对应 TTime 后续清单第 2 项，本轮只做这一项。

## 范围与非目标

- 范围：`ai-translate app`、菜单栏图标、只安装到 `~/Applications/AI Translate.app`、嵌入式 Python 启动器、沿用现有热键和浮窗。
- 范围：App 通过启动器提供仓库路径，由 `resolve_env_path()` 选择配置文件，不把密钥或 `.env` 路径打进包内。
- 非目标：输入框、历史、划词工具栏、剪贴板监听、公证分发、Windows/Linux。
- 非目标：Electron 或第二套翻译链。

## 已完成

1. `ai-translate app` 和菜单栏「译」图标（划词、截图、退出）。
2. 嵌入式启动器：进程是 `AITranslate`，包标识 `local.ai.translate`，不 `exec` 成系统 Python。
3. `scripts/build-macos-app.sh` 输出 `dist/AI Translate.app` 并安装到 `~/Applications`。
4. 启动器设置 `AI_TRANSLATE_PROJECT_ROOT` 和 `AI_TRANSLATE_HOST_NAME`，不再把仓库 `.env` 路径写进包内。
5. 离线测试覆盖 CLI、菜单文案和配置覆盖。
6. 浮窗在菜单栏 App 中保持可见（`hidesOnDeactivate=false`）；打包只安装到 `~/Applications`，并加单实例锁。
7. 未开辅助功能时浮窗/菜单会说明；划词先等修饰键松开再模拟复制。
8. 浮窗原文/译文可滚动，窗口可拉大。
9. 菜单栏设置页：OCR 方法、置信度、切图模式、语言和热键，保存到 `.env` 后立即生效。
10. 划词先取选区再出浮窗；已有浮窗只更新、不再从屏幕中间重新弹出。
11. 设置页在菜单关闭后再弹出；窗口用普通 `NSWindow`，关闭菜单跟踪后再到前台。
12. 打开设置不再走 `AppHelper.callLater`：菜单控制器自己保留延迟选择子，失败时用浮窗说明。
13. 设置窗口只使用 `MoveToActiveSpace`，不再同时设置 `CanJoinAllSpaces`（系统会直接抛错）。
14. 菜单栏和设置页的 AppKit 控制器使用独立类名，且只注册一次，避免 `_Controller` 重名导致设置打不开。
15. 设置页可切换 `TRANSLATE_MODEL` / `OCR_MODEL`；热键改为点按录制，不再手填字符串。
16. 设置页可分别填写翻译/OCR 的 `BASE_URL` 和 `API_KEY`，密钥用密文框写入本机 `.env`。
17. 配置只读一个文件：显式路径、项目 `.env`、用户 Application Support；`config-check` 打印实际路径。用户说明写在根 README。
18. 用户本机打开 `AI Translate.app` 试用，报告基本没什么问题。

## 剩余工作

无。公证签名、提交和推送不在本计划。输入框见独立完成计划。

## 验收条件

- 菜单栏显示「译」；划词/OCR 与退出可点。
- 进程名/包名是 `AI Translate`（`local.ai.translate`），辅助功能列表可以加入该项。
- 离线测试覆盖 `app` CLI、热键展示和配置覆盖；默认套件不打开真实菜单栏、不注册真实热键。
- README 写明如何用 `scripts/install.sh` 安装和授权。

## 授权与停止边界

- 允许：菜单栏、启动器、打包脚本、文档和离线测试。
- 需要额外授权：打开已安装 App 做真实热键/截屏/模型验收、公证签名、提交和推送。
- 出现必须引入 Electron 时停止。
