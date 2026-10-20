#!/usr/bin/env python3
"""UserPromptSubmit：上下文到线就提醒收工。只读；不记录 prompt 正文；任何异常都静默放行。"""
import json, os, sys, time, tempfile
from pathlib import Path

PCTS = sorted({int(x) for x in os.environ.get("CTX_WARN_PCTS", "25,40").split(",") if x.strip().isdigit()})
WINDOW = int(os.environ.get("CTX_WINDOW_TOKENS", "200000"))
COOLDOWN = 600          # 软线每 10 分钟最多提一次；硬线每轮都提
STALE = 900             # statusLine 旁路文件超过 15 分钟当过期
STATE = Path(tempfile.gettempdir()) / "claude-ctx"
KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def sidecar_pct(sid):
    try:
        d = json.loads((STATE / f"{sid}.json").read_text(encoding="utf-8"))
        if time.time() - float(d.get("ts", 0)) < STALE and d.get("used_percentage") is not None:
            return float(d["used_percentage"])
    except (OSError, ValueError, TypeError):
        pass
    return None


def transcript_pct(path):
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            lines = fh.readlines()[-500:]
    except (OSError, TypeError):
        return None
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict) or row.get("type") != "assistant" or row.get("isSidechain"):
            continue
        msg = row.get("message")
        usage = msg.get("usage") if isinstance(msg, dict) else None
        if isinstance(usage, dict):
            used = sum(int(usage.get(k) or 0) for k in KEYS)
            if used:
                return 100.0 * used / WINDOW
    return None


def main():
    data = json.load(sys.stdin)
    sid = str(data.get("session_id") or "nosession")
    pct = sidecar_pct(sid)
    if pct is None:
        pct = transcript_pct(data.get("transcript_path"))
    if pct is None or not PCTS or pct < PCTS[0]:
        return
    hard = len(PCTS) > 1 and pct >= PCTS[-1]
    mark = STATE / f"{sid}.warned"
    if not hard:
        try:
            if time.time() - mark.stat().st_mtime < COOLDOWN:
                return
        except OSError:
            pass
    if hard:
        msg = (f"【换窗提示】上下文已到 {pct:.0f}%。本轮必须收工：不开新活，"
               "先把 WIP-NOW.md 刷新（现在做什么/下一步/欠账与未验收），然后请用户 /clear 换新会话。")
    else:
        msg = (f"【换窗提示】上下文已到 {pct:.0f}%。做完手上这一步就收工："
               "刷新 WIP-NOW.md，写清下一个会话先看哪个文件，再请用户 /clear。")
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        mark.touch()
    except OSError:
        pass
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                             "additionalContext": msg}}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
