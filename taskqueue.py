"""The task queue: what Claude Code should do next, typed on the island while it works.

When a turn ends, the Stop hook asks Kai (agents.py) for the next task; Kai
hands it over and Claude Code goes on with it instead of stopping (the Stop
hook's "block" decision, kai_hook.py). Kept in a file next to the settings,
since the island writes it and the main process reads it.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid

_lock = threading.Lock()
MAX = 20


def _path() -> str:
    from settings import v2_file

    return v2_file("task_queue.json")


def items() -> list[dict]:
    try:
        with open(_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    return [i for i in data if isinstance(i, dict) and isinstance(i.get("text"), str)] if isinstance(data, list) else []


def _save(rows: list[dict]) -> None:
    path = _path()
    with open(path + ".tmp", "w", encoding="utf-8") as handle:
        json.dump(rows[:MAX], handle, ensure_ascii=False)
    os.replace(path + ".tmp", path)


def add(text: str) -> list[dict]:
    text = " ".join(str(text or "").split())[:1500]
    with _lock:
        rows = items()
        if text and len(rows) < MAX:
            rows.append({"id": uuid.uuid4().hex[:8], "text": text, "at": time.time()})
            _save(rows)
        return rows


def remove(item_id: str) -> list[dict]:
    with _lock:
        rows = [i for i in items() if i.get("id") != item_id]
        _save(rows)
        return rows


def clear() -> list[dict]:
    with _lock:
        _save([])
        return []


def take() -> str | None:
    """The next task, taken off the queue; None when there is none."""
    with _lock:
        rows = items()
        if not rows:
            return None
        first = rows.pop(0)
        _save(rows)
        return first["text"]
