# 设置应用与浮窗复制

> 完成日期：2026-08-20（Asia/Shanghai）
>
> 计划：无单独计划；设置页与浮窗的一次性交互修正。

## 任务边界

设置页增加「应用」，浮窗支持 `Command+C` 复制。不改翻译端口，不实施历史或复制按钮。

## 完成内容

- 设置页「应用」写入配置并立即重建用例，窗口保持打开；「保存」在应用成功后关闭。
- 浮窗 `NSPanel` 关闭 `becomesKeyOnlyIfNeeded`；安装隐藏 Edit 菜单；未选中时 `copy:` 复制当前栏全文。
- 根 README、配置设计和桌面热键说明已同步。

## 验证结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider`：`156 passed in 0.83s`。

## 限制与未执行项

- 未由 Agent 在本机复现点选浮窗后的 `Command+C`。
- 未推送。
