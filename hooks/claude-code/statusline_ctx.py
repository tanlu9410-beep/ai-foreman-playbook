#!/usr/bin/env python3
"""statusLine：显示上下文百分比，并把它写给 ctx_closeout.py 读。"""
import json, sys, time, tempfile
from pathlib import Path

try:
    data = json.load(sys.stdin)
    cw = data.get("context_window") or {}
    pct = cw.get("used_percentage")
    model = (data.get("model") or {}).get("display_name", "")
    if pct is not None:
        state = Path(tempfile.gettempdir()) / "claude-ctx"
        state.mkdir(parents=True, exist_ok=True)
        sid = str(data.get("session_id") or "nosession")
        (state / f"{sid}.json").write_text(json.dumps(
            {"used_percentage": pct, "size": cw.get("context_window_size"), "ts": time.time()}), encoding="utf-8")
        print(f"{model}  ctx {float(pct):.0f}%")
    else:
        print(model)
except Exception:
    print("")
