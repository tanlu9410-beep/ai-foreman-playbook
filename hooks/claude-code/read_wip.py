#!/usr/bin/env python3
"""SessionStart（startup/clear/resume）：把 WIP-NOW.md 注入新会话开局。"""
import json, os, sys
from pathlib import Path

try:
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    wip = root / os.environ.get("WIP_FILE", "WIP-NOW.md")
    if wip.is_file():
        text = wip.read_text(encoding="utf-8", errors="ignore")
        if len(text) > 4000:
            text = text[:4000] + "\n…（已截断，全文请直接读 WIP-NOW.md）"
        ctx = "【上一个会话留下的 WIP-NOW】先读它再开工：\n" + text
    else:
        ctx = "【提示】仓库根目录没有 WIP-NOW.md。开工前先建一个：现在做什么 / 下一步 / 欠账与未验收。"
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                             "additionalContext": ctx}}, ensure_ascii=False))
except Exception:
    pass
sys.exit(0)
