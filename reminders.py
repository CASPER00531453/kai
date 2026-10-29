"""Reminders, alarms and timers.

Kept in %APPDATA%\\Kai\\reminders.json so the chat window (its own process) can
add one and the main process, which owns the clock, still fires it. A reminder
that came due while Kai was closed fires on the next start.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid

_lock = threading.Lock()

_NUMBERS = {
    "bir": 1, "iki": 2, "üç": 3, "uc": 3, "dört": 4, "dort": 4, "beş": 5, "bes": 5, "altı": 6, "alti": 6,
    "yedi": 7, "sekiz": 8, "dokuz": 9, "on": 10, "onbeş": 15, "on beş": 15, "on bes": 15, "yirmi": 20,
    "otuz": 30, "kırk": 40, "kirk": 40, "elli": 50, "yarım": 0.5, "yarim": 0.5, "bir buçuk": 1.5,
}
_UNITS = {"saniye": 1, "sn": 1, "dakika": 60, "dk": 60, "saat": 3600, "gün": 86400, "gun": 86400}
_NUM = r"(\d+(?:[.,]\d+)?|" + "|".join(sorted(map(re.escape, _NUMBERS), key=len, reverse=True)) + r")"

# "20 dakika sonra", "yarım saat", "2 saat içinde"
_RELATIVE = re.compile(_NUM + r"\s*(saniye|sn|dakika|dk|saat|gün|gun)\b(?:\s*(?:sonra|içinde|icinde|lık|lik))?")
# "saat 9", "saat 21:30", "21:30", "9'da", "9da", "7.15'te"
_CLOCK = re.compile(
    r"(?:saat\s*(\d{1,2})(?:[:.](\d{2}))?(?:\s*'?\s*(?:de|da|te|ta))?)"
    r"|(?:\b(\d{1,2})[:.](\d{2})\s*'?\s*(?:de|da|te|ta)?\b)"
    r"|(?:\b(\d{1,2})\s*'?\s*(?:de|da|te|ta)\b)"
)
_TRIGGERS = re.compile(
    r"\b(hatırlat|hatirlat|hatırlatır mısın|hatırlatsana|bana|beni|uyandır|uyandir|alarm|kur|"
    r"zamanlayıcı|zamanlayici|geri sayım|geri sayim|lütfen|lutfen|kai|sonra|içinde|icinde|"
    r"yarın|yarin|bugün|bugun|sabah|akşam|aksam|gece|öğlen|oglen|öğleden|ogleden|saat|için|icin|de|da)\b",
    re.IGNORECASE,
)


def _path() -> str:
    from settings import settings_path

    return os.path.join(os.path.dirname(settings_path()), "reminders.json")


def _load() -> list[dict]:
    try:
        with open(_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    return [item for item in data if isinstance(item, dict) and "due" in item]


def _save(items: list[dict]) -> None:
    path = _path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(sorted(items, key=lambda item: item["due"]), handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _number(word: str) -> float:
    word = word.replace(",", ".")
    try:
        return float(word)
    except ValueError:
        return float(_NUMBERS.get(word, 0))


def parse(text: str, now: float | None = None) -> tuple[float, str] | None:
    """(due time, what to say) from a Turkish sentence, or None when it names no time."""
    now = now or time.time()
    low = text.lower()
    due = None
    spans = []

    rel = _RELATIVE.search(low)
    if rel and not re.search(r"saat\s*\d", low[: rel.start() + 1] if rel.group(2) == "saat" else ""):
        seconds = _number(rel.group(1)) * _UNITS[rel.group(2)]
        if seconds > 0:
            due = now + seconds
            spans.append(rel.span())

    if due is None:
        clock = _CLOCK.search(low)
        if clock:
            groups = clock.groups()
            hour = next(int(g) for g in (groups[0], groups[2], groups[4]) if g)
            minute = int(groups[1] or groups[3] or 0)
            if hour > 23 or minute > 59:
                return None
            if any(w in low for w in ("akşam", "aksam", "öğleden sonra", "ogleden sonra")) and hour < 12:
                hour += 12
            if any(w in low for w in ("gece",)) and 6 <= hour < 12:
                hour += 12
            day = time.localtime(now)
            base = time.mktime((day.tm_year, day.tm_mon, day.tm_mday, hour, minute, 0, 0, 0, -1))
            if "yarın" in low or "yarin" in low:
                base += 86400
            elif base <= now:
                base += 86400   # "9'da" said at 10 means tomorrow at 9
            due = base
            spans.append(clock.span())
        elif ("yarın" in low or "yarin" in low) and "sabah" in low:
            day = time.localtime(now + 86400)
            due = time.mktime((day.tm_year, day.tm_mon, day.tm_mday, 9, 0, 0, 0, 0, -1))

    if due is None:
        return None
    what = text
    for start, end in sorted(spans, reverse=True):
        what = what[:start] + " " + what[end:]
    what = _TRIGGERS.sub(" ", what)
    what = re.sub(r"[^\wçğıöşüÇĞİÖŞÜ' ]", " ", what)
    return due, " ".join(what.split()).strip(" '")


def add(due: float, text: str, kind: str = "reminder") -> dict:
    item = {"id": uuid.uuid4().hex[:8], "due": due, "text": text[:200], "kind": kind}
    with _lock:
        items = _load()
        items.append(item)
        _save(items)
    return item


def upcoming() -> list[dict]:
    with _lock:
        return _load()


def clear() -> int:
    with _lock:
        count = len(_load())
        _save([])
    return count


def take_due(now: float | None = None) -> list[dict]:
    """Remove and return everything that is due."""
    now = now or time.time()
    with _lock:
        items = _load()
        due = [item for item in items if item["due"] <= now]
        if due:
            _save([item for item in items if item["due"] > now])
    return due


def when(due: float, now: float | None = None) -> str:
    """'14:30', 'yarın 09:00' or '20 dk (14:52)' for the reply."""
    from i18n import t

    now = now or time.time()
    clock = time.strftime("%H:%M", time.localtime(due))
    left = due - now
    if left < 3600:
        return t("rem.in_minutes", minutes=max(1, round(left / 60)), clock=clock)
    if time.localtime(due).tm_yday != time.localtime(now).tm_yday:
        return t("rem.tomorrow", clock=clock)
    return clock


def start(on_due) -> None:
    """Check the list every two seconds and hand what is due to on_due(item)."""
    def loop() -> None:
        while True:
            try:
                for item in take_due():
                    on_due(item)
            except Exception:
                pass
            time.sleep(2)

    threading.Thread(target=loop, name="kai-reminders", daemon=True).start()
