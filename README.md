# AI Translate

本机划词翻译和截图翻译。选中外文按热键即可看到译文；圈选屏幕可以先识别文字再翻译；也可以锁定一块区域做实时识别；还可以在输入窗口里粘贴或键入后再译。macOS 版本已经过本机试用，实时翻译已完成双屏圈选、动态更新和停止验收；Windows 11 x64 已完成源码安装、托盘进程、设置窗口、单实例、`Alt+E` 划词与剪贴板恢复、`Alt+W` / `Alt+Q` 圈选层开关、固定区域截屏、双屏负坐标/DPI、本地 PaddleOCR、OCR.space、本机 Router 高级 OCR 和实时固定帧核心链路真测。Windows 实际鼠标拖拽圈选、托盘菜单/输入窗口和桌面字幕条关闭仍待完整交互验收。

## macOS 安装

需要 macOS 13+ 和 Python 3.12+。在仓库根目录执行：

```bash
./scripts/install.sh
```

脚本会创建 `.venv`、安装依赖，并把 `AI Translate.app` 装到 `~/Applications`，然后打开它。本机只保留这一份 App。改完源码后先点菜单「退出」，再重新打开；启动器会加载仓库里的代码，一般不用重新打包。

本地高级 PaddleOCR 是可选大依赖，目前官方运行时要求 Python 3.9–3.13；项目使用 Python 3.12 或 3.13 时可额外安装 `.[local-ocr]`。设置页可在 `tiny`（默认）、`small` 和 `medium` 间切换；桌面端第一次实际加载所选档位前会先提醒，尚未缓存时会自动下载对应 PP-OCRv6 模型，后续识别会复用当前进程中的 pipeline。未安装依赖时自动模式会直接跳到 API 两层。

## Windows 安装候选

需要 Windows 11 x64 和 Python 3.12+。在 PowerShell 的仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-windows.ps1
```

脚本会创建项目 `.venv`、安装 Windows 平台依赖，并用该环境的 `pythonw.exe` 启动系统托盘 App。设置保存在 `%APPDATA%\AI Translate\.env`；若仓库已经有 `.env`，仍优先使用仓库文件。该入口已在 Windows 11 x64、Python 3.13.15 上完成源码安装、托盘进程、设置窗口、单实例、三组热键实际触发/取消和双屏固定区域 OCR 首轮验证；无标题的全屏圈选层无法由当前安全自动化工具接管鼠标，托盘菜单、输入窗口和完整字幕条开停仍待人工交互验收，当前不能替代正式发布包。

## 第一次使用

1. macOS 在「系统设置 → 隐私与安全性」里，把 **AI Translate** 勾进辅助功能和屏幕录制；Windows 不需要对应授权，但普通权限程序不能自动复制管理员窗口里的选区。
2. 选中文字，松开热键修饰键，再按 macOS `Option+E` 或 Windows `Alt+E`。翻译默认使用 **Google（内置）**，不用填密钥。
3. 要改来源、密钥或热键，从菜单栏「译」或 Windows 托盘打开「设置…」。也可以改成 Bing / DeepL 内置，或 OpenAI 兼容 / 官方 API。

OCR 分成四层：本地普通、本地高级、API 普通和 API 高级。本地普通在 macOS 使用 Vision；本地高级使用可选 PP-OCRv6；API 普通使用 OCR.space；API 高级继续使用现有视觉模型。自动模式按这个顺序串行尝试；Windows 没有 Vision，从本地 PaddleOCR 开始。未安装或失败的本地层会跳过，API 两层继续保持独立配置。

## 日常使用

默认热键：macOS 为划词 `Option+E`、截图 `Option+W`、实时翻译 `Option+Q`；Windows 对应 `Alt+E`、`Alt+W`、`Alt+Q`。必须带修饰键，三组不能相同；macOS 在设置里录制组合键，Windows 首版填写 `alt+e` 这类字符串。

| 你想做的事 | 怎么做 |
| --- | --- |
| 划词翻译 | 选中文字，松开 Option，再按 `Option+E` |
| 截图翻译 | 按 `Option+W`，圈选区域 |
| 实时翻译 | 按 `Option+Q` 或菜单「实时翻译」，可在任意一块屏幕拖拽圈定区域；字幕条会出现在区域外侧。再按一次或关闭字幕条停止 |
| 从菜单触发 | 「译」→「划词翻译」「截图翻译」或「实时翻译」 |
| 输入或粘贴后再译 | 菜单/托盘「输入翻译…」，点「翻译」；macOS 可用 `Command+Return`，Windows 可用 `Ctrl+Enter` |
| 改来源、模型、密钥或热键 | 菜单/托盘「设置…」；「应用」立即生效并留在窗口，「保存」写入后关闭 |
| 退出 | 菜单栏「译 → 退出」或 Windows 托盘「退出」 |

实时翻译约每 0.8 秒开始一轮，截屏、OCR 和翻译保持串行；某轮处理超过 0.8 秒时不会并发请求。画面不变会跳过 OCR，识别文字不变会跳过翻译。自动 OCR 的顺序是本地普通 → 本地高级 → API 普通 → API 高级；任一层成功后不会同时调用后续层。

浮窗上面是原文，下面是译文，可滚动。获得焦点后可用平台复制快捷键复制选中的文字；macOS 未选中时会复制当前栏全部文字。

## 权限

macOS 热键本身不需要辅助功能；没有辅助功能时，先 `Command+C` 再按 `Option+E`，会翻译剪贴板。圈选翻译和实时翻译需要屏幕录制，授权对象必须是 **AI Translate**，不是 Cursor 或 python。Windows 没有对应权限页；自动复制被管理员窗口阻止时，先手动 `Ctrl+C` 再按热键。

## 配置

翻译和 OCR 分开配置，互不借用；本地高级使用 `OCR_LOCAL_ADVANCED_*`，API 普通使用 `OCR_STANDARD_*`，API 高级沿用 `OCR_*`。设置页的「本地 Paddle 档位」会保存为 `OCR_LOCAL_ADVANCED_MODEL_TIER`；点「应用」后下一次 OCR 使用新档位。设置保存在本机的一份 `.env` 里，不会打进 App。密钥用密文框填写；不要提交到 Git，也不要在终端里长期 `export TRANSLATE_*` / `OCR_*`，否则设置页看起来会没保存成功。

仓库里如果已经有 `.env`，App 会优先用它。进阶字段见 `.env.example`。

### 本机 LLM Token Router

若本机已在 `127.0.0.1:8000` 运行 `llm-token-router`，可把翻译和 API 高级 OCR 分别接到它；两侧仍各写自己的地址和模型，不互借配置。当前本地网关不校验调用方密钥时，项目的两个 `API_KEY` 可以留空。简单翻译可使用 Router 中已配置的低延迟文本模型，高级 OCR 应选择已确认支持图片输入的模型；`auto` 适合让 Router 自行选路。Router 停止时这两条远程能力会按各自超时返回失败，本地 PaddleOCR 不受影响。

```dotenv
TRANSLATE_PROVIDER=openai
TRANSLATE_BASE_URL=http://127.0.0.1:8000/v1
TRANSLATE_API_KEY=
TRANSLATE_MODEL=auto
TRANSLATE_TIMEOUT_SECONDS=120

OCR_BASE_URL=http://127.0.0.1:8000/v1
OCR_API_KEY=
OCR_MODEL=auto
```

`OCR_MODEL=Unlimited-OCR` 时客户端保留 Unlimited-OCR 的专用提示词与切图参数；其它模型使用标准 OpenAI `image_url` 消息，并明确要求只返回识别文字。修改 `.env` 后重启桌面 App，或在设置页点「应用」立即重建运行时。

## 命令行

macOS 安装后也可以用命令行：

```bash
.venv/bin/ai-translate config-check
.venv/bin/ai-translate text "Hello"
.venv/bin/ai-translate ocr --image page.png
.venv/bin/ai-translate ocr-translate --screenshot
.venv/bin/ai-translate listen
```

`config-check` 只表示配置被读到，不表示翻译一定能通。`listen` 在终端里注册同一组热键，用 `Ctrl+C` 退出。

Windows PowerShell 使用：

```powershell
.\.venv\Scripts\ai-translate.exe config-check
.\.venv\Scripts\ai-translate.exe text "Hello"
.\.venv\Scripts\ai-translate.exe ocr --image page.png
.\.venv\Scripts\ai-translate.exe ocr-translate --screenshot
.\.venv\Scripts\ai-translate.exe listen
```

## 常见问题

- **设置打不开或改完没变化**：点「应用」或「保存」后才会生效。仍不对就先「退出」再打开 App。
- **划词没读到选区**：macOS 给 AI Translate 打开辅助功能并先松开 Option；Windows 若目标程序以管理员身份运行，先手动复制；两边都可先复制再按热键。
- **OCR 没反应**：打开屏幕录制；取消圈选不会识别。实时翻译请圈一块字幕或文字区域，不要整屏；画面不变时不会反复请求。
- **OCR 识别不准**：可在设置中强制选择本地高级 PaddleOCR 或 API 高级模型。自动模式只能根据可用性、置信度、单/多页、1 MB 边界、失败或空结果升级，无法可靠判断一段错误文字是否“看起来成功”。
- **热键变成了奇怪字符**：macOS 在设置里点按钮录制，不要手填 Option 产生的符号；Windows 填 `alt+e` 这类规范字符串。
- **浮窗里复制没反应**：先点一下原文或译文，再使用平台复制快捷键。macOS 未选中时会复制当前栏全部文字。
- **网页翻译失败**：内置源可能被限流。可换官方密钥源，或稍后再试。
- **本机 Router 调用失败**：先确认 `http://127.0.0.1:8000/health` 返回正常，再用 `config-check` 核对两侧地址和模型；静态 `ready` 不代表 Router 或上游本次一定可用。

划词会短暂改写剪贴板并在结束后恢复，翻译过程中不要同时复制其它内容。

## 目前没有的功能

历史记录还没有；Windows 本地普通 OCR 也尚未实现，安装 PaddleOCR 后可使用本地高级层。本工具不做全书对照翻译、系统音频同传、浏览器扩展或多人在线服务。

## 文档

维护入口：[docs/README.md](docs/README.md)。
