"""How much of the Claude plan is used, for the island.

Two sources. Claude Code in a terminal hands its status line the plan's own
limits (five-hour and seven-day windows, used percentage and reset time);
kai_hook.py --status keeps them in usage.json. The Claude desktop app runs no
status line, so Kai also counts on its own, from Claude Code's transcripts on
this computer: the replies and tokens of the current five-hour window and when
it ends, the way the plan's window is counted. Nothing leaves the computer.
"""

from __future__ import annotations

import glob
import json
import os
import time
from datetime import datetime

WINDOW = 5 * 3600
# The plan's own numbers are trusted while this fresh.
LIMITS_FRESH = 15 * 60
TAIL = 6 * 1024 * 1024
_cache: dict = {"at": 0.0, "value": None}


def _limits() -> dict | None:
    path = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Kai", "usage.json")
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or time.time() - float(data.get("at") or 0) > LIMITS_FRESH:
        return None
    out = {}
    for name in ("five_hour", "seven_day"):
        window = data.get(name)
        if isinstance(window, dict):
            resets = float(window.get("resets") or 0)
            used = float(window.get("used") or 0) if resets > time.time() else 0.0
            out[name] = {"used": round(used), "resets": resets}
    return out or None


def _stamp(text: str) -> float:
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _entries(since: float) -> list[tuple[float, int, int]]:
    """(time, output tokens, all tokens) of each reply after `since`, from every transcript."""
    root = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    seen: set[str] = set()
    out = []
    for path in glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True):
        try:
            if os.path.getmtime(path) < since:
                continue
            with open(path, "rb") as handle:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                handle.seek(max(0, size - TAIL))
                chunk = handle.read()
        except OSError:
            continue
        for line in chunk.splitlines():
            if b'"usage"' not in line or b'"assistant"' not in line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            message = row.get("message") if isinstance(row.get("message"), dict) else {}
            used = message.get("usage") if isinstance(message.get("usage"), dict) else None
            at = _stamp(str(row.get("timestamp") or ""))
            if not used or at < since:
                continue
            key = f"{message.get('id')}:{row.get('requestId')}"
            if key in seen:
                continue
            seen.add(key)
            output = int(used.get("output_tokens") or 0)
            total = output + int(used.get("input_tokens") or 0) + int(used.get("cache_creation_input_tokens") or 0)
            out.append((at, output, total))
    return sorted(out)


def _local() -> dict | None:
    """The current five-hour window, counted the plan's way: it starts at the hour of the
    first reply after the last window ended."""
    now = time.time()
    entries = _entries(now - 2 * WINDOW)
    start = None
    for at, _out, _total in entries:
        if start is None or at >= start + WINDOW:
            start = at - (at % 3600)
    if start is None or now >= start + WINDOW:
        return None
    inside = [e for e in entries if e[0] >= start]
    return {
        "replies": len(inside),
        "output": sum(e[1] for e in inside),
        "tokens": sum(e[2] for e in inside),
        "started": start,
        "resets": start + WINDOW,
    }


def snapshot() -> dict:
    """What the island shows; read at most once a minute."""
    if time.time() - _cache["at"] < 60 and _cache["value"] is not None:
        return _cache["value"]
    value: dict = {"limits": None, "local": None}
    try:
        value["limits"] = _limits()
        value["local"] = _local()
    except Exception:
        pass
    _cache.update(at=time.time(), value=value)
    return value
