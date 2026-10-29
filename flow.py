"""Flow: what happens to dictated words before they are pasted, and what is kept after.

Dictionary  names spelled as written, and replacements (« klod kod » → « Claude Code »)
Snippets    say a short phrase, a whole text is pasted, untouched
Styles      an optional clean-up by the chosen model, per app
History     every dictation, for Statistics, kept as long as chosen

Everything lives in %APPDATA%\\Kai\\flow\\ as JSON, on this computer only.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time

STYLES = ("as_said", "natural", "polished")
KEEP = (0, 1, 7, 30, 90)  # days; 0 keeps everything
TYPING_WPM = 40  # what a dictated word saves, against typing it

_lock = threading.Lock()


def folder() -> str:
    from settings import settings_path

    path = os.path.join(os.path.dirname(settings_path()), "flow")
    os.makedirs(path, exist_ok=True)
    return path


def _read(name: str, default):
    try:
        with open(os.path.join(folder(), name), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def _write(name: str, data) -> None:
    path = os.path.join(folder(), name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ── Dictionary ──────────────────────────────────────────────────────────────

def dictionary() -> list[dict]:
    """[{"word": "Kai"}] for names, [{"from": "klod kod", "to": "Claude Code"}] for replacements."""
    items = _read("dictionary.json", [])
    return [i for i in items if isinstance(i, dict) and (i.get("word") or i.get("from"))]


def set_dictionary(items: list) -> list[dict]:
    clean = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        word = " ".join(str(item.get("word") or "").split())[:80]
        source = " ".join(str(item.get("from") or "").split())[:120]
        target = " ".join(str(item.get("to") or "").split())[:200]
        if source and target:
            clean.append({"from": source, "to": target})
        elif word:
            clean.append({"word": word})
    with _lock:
        _write("dictionary.json", clean[:500])
    return clean


def hint() -> str:
    """The names, as a prompt for Whisper: it then spells them the same way."""
    names = [i["word"] for i in dictionary() if i.get("word")]
    names += [i["to"] for i in dictionary() if i.get("to")]
    return ", ".join(names)[:600]


def _fold(text: str) -> str:
    return text.replace("İ", "i").replace("I", "ı").lower()


def apply_dictionary(text: str) -> str:
    for item in dictionary():
        if item.get("from"):
            pattern = r"(?<!\w)" + re.escape(item["from"]) + r"(?!\w)"
            text = re.sub(pattern, item["to"].replace("\\", "\\\\"), text, flags=re.IGNORECASE)
        elif item.get("word"):
            # A name heard in other letter case is put back the way it is written.
            pattern = r"(?<!\w)" + re.escape(item["word"]) + r"(?!\w)"
            text = re.sub(pattern, item["word"].replace("\\", "\\\\"), text, flags=re.IGNORECASE)
    return text


# ── Snippets ────────────────────────────────────────────────────────────────

def snippets() -> list[dict]:
    items = _read("snippets.json", [])
    return [i for i in items if isinstance(i, dict) and i.get("trigger") and i.get("text")]


def set_snippets(items: list) -> list[dict]:
    clean = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        trigger = " ".join(str(item.get("trigger") or "").split())[:80]
        body = str(item.get("text") or "")[:8000]
        if trigger and body.strip():
            clean.append({"trigger": trigger, "text": body})
    with _lock:
        _write("snippets.json", clean[:300])
    return clean


def _plain(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", _fold(text)).split())


def snippet_for(text: str) -> str | None:
    """The whole text of a snippet when what was said is its trigger, and nothing else."""
    said = _plain(text)
    for item in snippets():
        if _plain(item["trigger"]) == said:
            return item["text"]
    return None


# ── Styles ──────────────────────────────────────────────────────────────────

def styles() -> dict:
    data = _read("styles.json", {})
    if not isinstance(data, dict):
        data = {}
    apps = data.get("apps") if isinstance(data.get("apps"), dict) else {}
    return {
        "enabled": bool(data.get("enabled", False)),
        "default": data.get("default") if data.get("default") in STYLES else "natural",
        "apps": {str(k)[:60].lower(): v for k, v in apps.items() if v in STYLES},
    }


def set_styles(data: dict) -> dict:
    current = styles()
    if isinstance(data, dict):
        if "enabled" in data:
            current["enabled"] = bool(data["enabled"])
        if data.get("default") in STYLES:
            current["default"] = data["default"]
        if isinstance(data.get("apps"), dict):
            current["apps"] = {str(k)[:60].lower(): v for k, v in data["apps"].items() if v in STYLES}
    with _lock:
        _write("styles.json", current)
    return current


PROMPTS = {
    "natural": (
        "You clean up dictated text. Remove filler words (ee, ııı, şey, yani when it is filler, um, uh), "
        "stuttered and repeated words, and apply the speaker's own corrections (\"yarın, yok perşembe\" → "
        "\"perşembe\"). Keep their words, tone and language. Add normal punctuation. Do not answer, "
        "summarise, translate or add anything. Reply with the cleaned text only."
    ),
    "polished": (
        "You turn dictated text into well-written text in the same language. Remove fillers and repetitions, "
        "apply the speaker's corrections, fix grammar and punctuation, and split into sentences or short "
        "paragraphs where it helps. Keep the meaning and every fact; do not add anything, do not answer it. "
        "Reply with the text only."
    ),
}


def clean_up(text: str, style: str, app: str = "") -> str:
    if style not in PROMPTS or not text.strip():
        return text
    from brain import ask
    from settings import Settings

    where = f" It will be pasted into {app}." if app else ""
    try:
        out = ask(Settings(), text, system=PROMPTS[style] + where, timeout=20)
    except Exception:
        return text
    out = (out or "").strip().strip('"').strip()
    # A model that answers instead of cleaning, or returns nothing, is ignored.
    if not out or len(out) > len(text) * 2.2 + 40:
        return text
    return out


def style_for(app: str) -> str:
    data = styles()
    if not data["enabled"]:
        return "as_said"
    return data["apps"].get((app or "").lower(), data["default"])


def process(raw: str, app: str = "") -> tuple[str, str]:
    """(text to paste, how it was made: snippet, or a style)."""
    text = " ".join(raw.split())
    if not text:
        return "", "as_said"
    body = snippet_for(text)
    if body is not None:
        return body, "snippet"
    text = apply_dictionary(text)
    style = style_for(app)
    if style != "as_said":
        text = apply_dictionary(clean_up(text, style, app))
    return text, style


# ── History and statistics ──────────────────────────────────────────────────

def _settings_keep() -> int:
    data = _read("settings.json", {})
    days = data.get("keep_days", 0) if isinstance(data, dict) else 0
    return days if days in KEEP else 0


def flow_settings() -> dict:
    data = _read("settings.json", {})
    if not isinstance(data, dict):
        data = {}
    return {"keep_days": _settings_keep()}


def set_flow_settings(data: dict) -> dict:
    current = flow_settings()
    if isinstance(data, dict) and data.get("keep_days") in KEEP:
        current["keep_days"] = data["keep_days"]
    with _lock:
        _write("settings.json", current)
    prune()
    return current


def record(text: str, raw: str, app: str, seconds: float, engine: str, style: str) -> None:
    entry = {
        "at": time.time(),
        "text": text,
        "raw": raw,
        "app": app,
        "words": len(text.split()),
        "seconds": round(seconds, 2),
        "engine": engine,
        "style": style,
    }
    with _lock:
        with open(os.path.join(folder(), "history.jsonl"), "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def history(limit: int = 0) -> list[dict]:
    out = []
    try:
        with open(os.path.join(folder(), "history.jsonl"), encoding="utf-8") as handle:
            for line in handle:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    keep = _settings_keep()
    if keep:
        edge = time.time() - keep * 86400
        out = [e for e in out if e.get("at", 0) >= edge]
    return out[-limit:] if limit else out


def prune() -> None:
    keep = _settings_keep()
    if not keep:
        return
    entries = history()
    with _lock:
        path = os.path.join(folder(), "history.jsonl")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            for e in entries:
                handle.write(json.dumps(e, ensure_ascii=False) + "\n")
        os.replace(tmp, path)


def clear_history() -> None:
    with _lock:
        try:
            os.remove(os.path.join(folder(), "history.jsonl"))
        except OSError:
            pass


def stats() -> dict:
    entries = history()
    words = sum(int(e.get("words") or 0) for e in entries)
    spoken = sum(float(e.get("seconds") or 0) for e in entries)
    typed = words / TYPING_WPM * 60
    per_day: dict[str, int] = {}
    apps: dict[str, int] = {}
    for e in entries:
        day = time.strftime("%Y-%m-%d", time.localtime(e.get("at", 0)))
        per_day[day] = per_day.get(day, 0) + int(e.get("words") or 0)
        name = e.get("app") or "?"
        apps[name] = apps.get(name, 0) + int(e.get("words") or 0)
    days = []
    for back in range(13, -1, -1):
        day = time.strftime("%Y-%m-%d", time.localtime(time.time() - back * 86400))
        days.append({"day": day, "words": per_day.get(day, 0)})
    return {
        "dictations": len(entries),
        "words": words,
        "saved_seconds": max(0, round(typed - spoken)),
        "wpm": round(words / (spoken / 60)) if spoken > 5 else 0,
        "days": days,
        "apps": sorted(({"app": k, "words": v} for k, v in apps.items()), key=lambda a: -a["words"])[:8],
        "recent": [{k: e.get(k) for k in ("at", "text", "app", "words", "style")} for e in entries[-30:]][::-1],
    }
