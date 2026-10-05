# OCR.space 异常响应与自动降级验证

> 日期：2026-10-05（Asia/Shanghai）

## 结果

先写 [实施计划](../../plan/completed/2026-10-05-ocr-space-response-failures.md)，再添加回归与修改代码。OCR.space 两级状态码被返回为列表/对象时不再抛出 `TypeError`；过深 JSON 的解码递归失败归为现有 `invalid_json`。异常响应进入既有失败结果后，自动模式可继续 API 高级层，强制普通模式保留失败。

## 实际改动

- `infrastructure/ocr_space.py` 的两处状态码判断改用无需哈希的比较，保留原有有效码与缺省单条状态语义。整次状态异常时返回 `empty_ocr_text`，单条异常时跳过并继续收集其它合法文字。
- 仅在 JSON 解码边界增加 `RecursionError` 归类，复用 `invalid_json`；原有响应字节预算、HTTP/超时错误、API 请求和分流条件保持不变。
- 新增 22 项客户端/消费者回归，使用具体普通客户端的 HTTP mock 和既有高级 OCR/翻译 Fake；验证上游异常文字不进入失败结果或后续翻译，合法结果顺序保持。
- 同步 README、OCR 分流设计、文档入口和计划索引，原计划移动至 `completed/`。无关联开放 Issue；配置、端口和公共结果契约未变化，配置示例与其它稳定设计无需修改。

## 已执行的验证

所有 Python 命令均使用项目 `.venv/bin/python`（Python 3.13.14），设置 `PYTHONDONTWRITEBYTECODE=1` 并禁用 pytest 缓存；所有上游响应、图片与文字均为合成数据，未读取真实 `.env` 打上游。

| 阶段 | 范围 | 实际结果 |
| --- | --- | --- |
| 改动前基线 | `test_ocr_space.py`、`test_ocr_routing.py`、`test_ocr_translate.py` | 47 项通过 |
| 新增回归复现 | 两级异常状态码、异常条目与有效条目共存、JSON 深嵌套及自动/强制模式 | 17 项失败、5 项合法状态码兼容回归通过；实际抛出 `TypeError` / `RecursionError` |
| 修复后定向 | 与基线相同的三个测试模块 | 69 项通过 |
| 完整离线 | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider` | 520 项通过，包含架构与文档验证 |
| 最终差异 | 相对本轮快照回读代码/测试/文档，执行 `git diff --check` | 通过；实现只改动普通客户端的三处判断/异常捕获 |
| WIP 范围 | 63 个初始 WIP 文件哈希与完整状态路径核对 | 范围外内容变化 0、意外状态路径 0 |

自动模式的回归实际经过普通 HTTP mock 失败、高级 Fake 成功及 OCR 翻译用例，确认高级只调用一次、只把其文字交给翻译。强制普通模式回归确认本地、高级和翻译均未调用。异常条目后仍有合法文字时保持顺序；失败对象不携带合成上游文字、错误详情或原始响应。

## 对抗复核与边界

已检查普通客户端外的路由和用例无需增加宽泛异常捕获；修复发生在具体外部响应边界。合法整数/字符串状态码及省略单条状态码继续通过；不新增严格类型转换或其它提供方协议假设。过深 JSON 的回归小于现有字节上限，只证明递归解码失败能归类，不声明为固定嵌套层数或全进程内存上限。

本轮快照在 `/private/tmp/translate-ocr-space-response-20261005-malf9nvy`，包含初始 Git 状态、WIP 哈希与 7 个相关文件副本。最终范围是这 7 个已有文件及本计划/日志，不暂存、提交或混入其它已有改动。

未执行真实 OCR/翻译、截图、剪贴板/选区访问、用户按键、Paddle 初始化/下载、依赖变更、真实 `.env` 修改、App/服务重启、Git 提交/推送、发布或部署。没有本轮必需的额外受控动作；原 [四层 OCR 计划](../../plan/completed/2026-08-20-tiered-ocr-routing.md) 仍只等待 macOS 桌面首次加载提醒复验，本次离线证据不替代该验收。
