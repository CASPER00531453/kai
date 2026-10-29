"""What Kai knows about the user, kept across restarts. Kai forgets nothing.

Facts are what the user asked Kai to remember, in their own words
(memory.json). Every exchange is kept too (conversations.jsonl): the last ones
go along with each question, and older ones that touch it are found again by
recall(). All of it stays in %APPDATA%\\Kai on this computer.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time

# Nothing is dropped; only what goes into one request is bounded.
MAX_FACTS = 100_000
MAX_PROMPT_CHARS = 3000
RECALL_CHARS = 2200
RECALL_TURNS = 4

_lock = threading.Lock()


def _path() -> str:
    from settings import settings_path

    return os.path.join(os.path.dirname(settings_path()), "memory.json")


def _load() -> list[dict]:
    try:
        with open(_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    return [item for item in data if isinstance(item, dict) and str(item.get("text") or "").strip()]


def _save(items: list[dict]) -> None:
    path = _path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(items[-MAX_FACTS:], handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _words(text: str) -> set[str]:
    return set(re.sub(r"[^\wçğıöşü ]", " ", text.lower()).split())


def facts() -> list[str]:
    with _lock:
        return [str(item["text"]) for item in _load()]


def add(text: str) -> bool:
    text = " ".join(text.split()).strip(" .,:;-")
    if len(text) < 3:
        return False
    with _lock:
        items = _load()
        # Saying the same thing twice should not store it twice.
        if any(str(item["text"]).lower() == text.lower() for item in items):
            return True
        items.append({"text": text[:300], "at": time.strftime("%Y-%m-%d %H:%M")})
        _save(items)
    return True


_FILLER = {"olan", "olanı", "olani", "şey", "şeyi", "seyi", "ile", "ilgili", "hakkında", "hakkinda", "o", "bu", "şu"}


def _matches(want: set[str], fact: str) -> bool:
    """Every word asked about starts a word of the fact: 'kahve' finds 'kahveyi'."""
    have = _words(fact)
    return all(any(word.startswith(stem[: max(3, len(stem) - 2)]) for word in have) for stem in want)


def forget(query: str) -> int:
    """Drop every fact that mentions all the words asked about. Returns how many went."""
    want = _keywords(query)
    if not want:
        return 0
    with _lock:
        items = _load()
        keep = [item for item in items if not _matches(want, str(item["text"]))]
        removed = len(items) - len(keep)
        if removed:
            _save(keep)
    return removed


def clear() -> None:
    """Asked for in so many words ("hafızanı sil"): the facts and the conversations go."""
    with _lock:
        _save([])
        try:
            os.remove(_log_path())
        except OSError:
            pass


def _overlap(want: set[str], text: str) -> int:
    """How many of the asked words a text shares, by their stems ('kahve' ~ 'kahveyi')."""
    have = _words(text)
    return sum(1 for stem in want if any(word.startswith(stem[: max(3, len(stem) - 2)]) for word in have))


def _keywords(query: str) -> set[str]:
    return {word for word in _words(query or "") if word not in _FILLER and len(word) >= 3}


def prompt_block(query: str = "") -> str:
    """Appended to the system prompt. Empty when Kai knows nothing yet.

    When everything does not fit, the facts the question touches go first, then
    the newest ones.
    """
    known = facts()
    if not known:
        return ""
    want = _keywords(query)
    order = list(reversed(range(len(known))))
    if want:
        order.sort(key=lambda i: -_overlap(want, known[i]))
    picked = []
    size = 0
    for i in order:
        size += len(known[i]) + 3
        if size > MAX_PROMPT_CHARS:
            break
        picked.append(i)
    lines = [f"- {known[i]}" for i in sorted(picked)]
    return (
        " Kullanıcı hakkında bildiklerin (kendisi söyledi, gerektiğinde kullan, her cevapta sayma): "
        + " ".join(lines)
    )


# ── Every exchange ────────────────────────────────────────────────────────────


def _log_path() -> str:
    return os.path.join(os.path.dirname(_path()), "conversations.jsonl")


def log_turn(you: str, kai: str) -> None:
    """One exchange, appended for good."""
    you, kai = " ".join(str(you or "").split()), " ".join(str(kai or "").split())
    if not you or not kai:
        return
    row = json.dumps({"at": time.strftime("%Y-%m-%d %H:%M"), "you": you[:2000], "kai": kai[:2000]}, ensure_ascii=False)
    with _lock:
        try:
            with open(_log_path(), "a", encoding="utf-8") as handle:
                handle.write(row + "\n")
        except OSError:
            pass


def _turns() -> list[dict]:
    try:
        with open(_log_path(), encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("you") and row.get("kai"):
            out.append(row)
    return out


def last_turns(count: int) -> list[tuple[str, str]]:
    """The newest exchanges, oldest first: the conversation picks up after a restart."""
    return [(row["you"], row["kai"]) for row in _turns()[-count:]]


def recall(query: str, skip_last: int = 12) -> str:
    """Older exchanges the question touches, for the system prompt; empty when none.

    The newest `skip_last` already go along as the conversation itself.
    """
    want = _keywords(query)
    if not want:
        return ""
    turns = _turns()
    older = turns[:-skip_last] if skip_last else turns
    scored = []
    for index, row in enumerate(older):
        score = _overlap(want, row["you"] + " " + row["kai"])
        # At least half of the words asked about: one stray word of a long question is no match.
        if score >= max(1, (len(want) + 1) // 2):
            scored.append((score, index, row))
    if not scored:
        return ""
    scored.sort(key=lambda item: (-item[0], -item[1]))
    lines = []
    size = 0
    for _score, _index, row in sorted(scored[:RECALL_TURNS], key=lambda item: item[1]):
        line = f"[{row['at']}] Kullanıcı: {row['you'][:400]} / Sen: {row['kai'][:400]}"
        size += len(line)
        if size > RECALL_CHARS:
            break
        lines.append(line)
    return " Daha önceki konuşmalarınızdan bununla ilgili olanlar (gerekirse kullan, tarihleriyle): " + " ".join(lines)
