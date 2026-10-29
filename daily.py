"""The day's summary: once a day, at the time set in Kai's settings, the island
shows what the day was. Kai reads it like a report (views/summary.ts).

Everything comes from this computer: the Claude Code transcripts of today,
the ratings received, the queue and tomorrow's calendar. Nothing is sent.
"""

from __future__ import annotations

import glob
import json
import os
import threading
import time
from collections import Counter

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
# A long session's transcript can be big: only its end is read, which is today.
TAIL = 24 * 1024 * 1024

_lock = threading.Lock()
_state: dict = {"building": False, "ready": None}


def _today_start() -> float:
    return time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))


def _stamp(text: str) -> float:
    from datetime import datetime

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def claude_today(since: float) -> dict:
    """Prompts, replies, output tokens, files edited and the busiest project today."""
    root = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    prompts = replies = tokens = 0
    files: set[str] = set()
    projects: Counter = Counter()
    seen: set[str] = set()
    for path in glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True):
        try:
            if os.path.getmtime(path) < since:
                continue
            with open(path, "rb") as handle:
                handle.seek(0, os.SEEK_END)
                handle.seek(max(0, handle.tell() - TAIL))
                chunk = handle.read()
        except OSError:
            continue
        for line in chunk.splitlines():
            if b'"timestamp"' not in line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict) or _stamp(str(row.get("timestamp") or "")) < since:
                continue
            message = row.get("message") if isinstance(row.get("message"), dict) else {}
            kind = row.get("type")
            content = message.get("content")
            typed = isinstance(content, str) or (
                isinstance(content, list)
                and any(isinstance(p, dict) and p.get("type") == "text" for p in content)
                and not any(isinstance(p, dict) and p.get("type") == "tool_result" for p in content)
            )
            if kind == "user" and not row.get("isMeta") and typed:
                # Typed by the person, not a tool result coming back.
                prompts += 1
                cwd = str(row.get("cwd") or "")
                if cwd:
                    projects[os.path.basename(cwd.rstrip("\\/")) or cwd] += 1
            elif kind == "assistant":
                key = f"{message.get('id')}:{row.get('requestId')}"
                if key in seen:
                    continue
                seen.add(key)
                replies += 1
                used = message.get("usage") if isinstance(message.get("usage"), dict) else {}
                tokens += int(used.get("output_tokens") or 0)
                for part in message.get("content") or []:
                    if isinstance(part, dict) and part.get("type") == "tool_use" and part.get("name") in EDIT_TOOLS:
                        target = (part.get("input") or {}).get("file_path") or (part.get("input") or {}).get("notebook_path")
                        if target:
                            files.add(os.path.normcase(str(target)))
    top = projects.most_common(1)[0][0] if projects else ""
    return {"prompts": prompts, "replies": replies, "tokens": tokens, "files": sorted(files), "project": top}


def _short(n: int) -> str:
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def build(settings) -> dict:
    """The report: a title and up to six lines, each with its icon."""
    turkish = getattr(settings, "language", "tr") == "tr"
    L = lambda tr, en: tr if turkish else en  # noqa: E731
    since = _today_start()
    lines = []
    claude = claude_today(since)
    if claude["prompts"] or claude["replies"]:
        lines.append({"icon": "💬", "text": L(
            f"Claude'a {claude['prompts']} iş verdin, {claude['replies']} yanıt geldi ({_short(claude['tokens'])} token).",
            f"You gave Claude {claude['prompts']} tasks and got {claude['replies']} replies ({_short(claude['tokens'])} tokens).")})
        if claude["files"]:
            names = ", ".join(os.path.basename(f) for f in claude["files"][:3])
            more = len(claude["files"]) - 3
            names += L(f" ve {more} tane daha", f" and {more} more") if more > 0 else ""
            lines.append({"icon": "📝", "text": L(f"{len(claude['files'])} dosya değişti: {names}.", f"{len(claude['files'])} files changed: {names}.")})
        if claude["project"]:
            lines.append({"icon": "📂", "text": L(f"En çok {claude['project']} üstünde çalıştın.", f"You worked mostly on {claude['project']}.")})
    else:
        lines.append({"icon": "🌿", "text": L("Bugün Claude'la iş yapmadın, sakin bir gündü.", "No work with Claude today, a calm day.")})
    try:
        import feedback

        today = [r for r in feedback.inbox() if float(r.get("at") or 0) >= since and not r.get("crash")]
        if today:
            stars = sum(int(r.get("stars") or 0) for r in today) / len(today)
            lines.append({"icon": "⭐", "text": L(f"{len(today)} değerlendirme geldi, ortalama {stars:.1f} yıldız.", f"{len(today)} ratings came in, {stars:.1f} stars on average.")})
    except Exception:
        pass
    try:
        import taskqueue

        waiting = len(taskqueue.items())
        if waiting:
            lines.append({"icon": "🎯", "text": L(f"Sırada {waiting} iş bekliyor.", f"{waiting} tasks wait in the queue.")})
    except Exception:
        pass
    try:
        import kaicalendar

        tomorrow = kaicalendar.describe_day(settings, 1)
        # Only when something is on: the "link your calendar" hint is not news.
        if tomorrow and "bir şey yok" not in tomorrow and "Nothing on" not in tomorrow:
            lines.append({"icon": "📅", "text": tomorrow[:150]})
    except Exception:
        pass
    return {"title": L("Günün özeti", "Your day") + " · " + time.strftime("%d.%m"), "lines": lines[:6]}


def _shown_path() -> str:
    from settings import v2_file

    return v2_file("summary_shown.txt")


def due(settings) -> bool:
    """Past today's time and not shown today yet."""
    if not getattr(settings, "summary_enabled", True):
        return False
    hours, minutes = (int(p) for p in settings.summary_time.split(":"))
    now = time.localtime()
    if (now.tm_hour, now.tm_min) < (hours, minutes):
        return False
    try:
        with open(_shown_path(), encoding="utf-8") as handle:
            return handle.read().strip() != time.strftime("%Y-%m-%d")
    except OSError:
        return True


def take(settings) -> dict | None:
    """The report once it is ready, built in the background; None the rest of the time.

    Called by the island on its timer: reading the transcripts must not hold it up.
    """
    with _lock:
        if _state["ready"] is not None:
            report, _state["ready"] = _state["ready"], None
            return report
        if _state["building"] or not due(settings):
            return None
        _state["building"] = True
        # Marked first: a report that fails to build is not retried every 400 ms.
        try:
            with open(_shown_path(), "w", encoding="utf-8") as handle:
                handle.write(time.strftime("%Y-%m-%d"))
        except OSError:
            pass

    def work() -> None:
        try:
            report = build(settings)
        except Exception:
            report = None
        with _lock:
            _state["building"] = False
            _state["ready"] = report

    threading.Thread(target=work, name="kai-daily", daemon=True).start()
    return None
