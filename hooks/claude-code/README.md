# Claude Code 上下文水位提醒与收工 hook

## 这是什么

这组三个 Python 标准库脚本为 Claude Code 提供上下文水位提醒和会话交接：到 25% 时软提醒「做完这步就收工、刷新 WIP-NOW.md」，每 10 分钟最多提醒一次；到 40% 后每轮强制收工，不再开新活，刷新 WIP-NOW.md 并请用户执行 `/clear`。`SessionStart` 的 `startup`、`clear`、`resume` 会把 WIP-NOW.md 注入新会话。它补充了 [`收工两拍`](../../docs/architecture/handoff.md#收工两拍)：换窗本身仍由人按 `/clear` 完成。

百分比优先读取 `statusLine` 的 `context_window.used_percentage` 旁路文件；没有新鲜值时，读取 transcript 最后一条主线 assistant 的 usage（`input_tokens + cache_creation_input_tokens + cache_read_input_tokens`），除以 `CTX_WINDOW_TOKENS`。两种来源都不可用时不提醒。

## 怎么装

1. 将 `hooks/claude-code/` 放入项目仓库。
2. 将 `settings.example.json` 的 `hooks` 与 `statusLine` 配置合并进项目的 `.claude/settings.json`。若已有自己的 `statusLine`，保留它并可不安装 `statusline_ctx.py`；提醒脚本会尝试 transcript 兜底。
3. 在仓库根目录创建 `WIP-NOW.md`，写明现在做什么、下一步、欠账与未验收。
4. 在 Claude Code 输入 `/hooks`，确认 `UserPromptSubmit` 和 `SessionStart` hook 已加载。

## 可调参数

- `CTX_WARN_PCTS`：提醒线，默认 `25,40`。
- `CTX_WINDOW_TOKENS`：transcript 兜底的窗口 token 数，默认 `200000`；1M 模型设为 `1000000`。旁路文件带有 statusLine 百分比时无需依赖此值。
- `WIP_FILE`：交接文件名或相对路径，默认 `WIP-NOW.md`。

## 注意事项

- hook 不会自动换窗；用户需要在收工后按 `/clear`。
- statusLine 百分比旁路文件超过 15 分钟会视为过期，再尝试 transcript 兜底。
- 公司或组织的 managed settings 可能限制项目 hook；此时配置可能不生效，可通过 `/hooks` 检查。
- 脚本不记录 prompt 正文，只使用 Python 标准库；异常时静默放行。
