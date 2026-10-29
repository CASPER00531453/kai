"""Ratings and wishes: sent from anyone's Kai, collected by the developer's.

Settings → Rating & wishes sends stars (1–5) and a line about what to add
next to the small server in server/feedback (Vercel), with the version and
the language — nothing else about the sender. The developer's Kai, the one
with an inbox key in its settings, collects them every few minutes and keeps
each as a note in the Notetaker list, then removes them from the server.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
import uuid

from version import FEEDBACK_URL, VERSION

EVERY = 600


def _request(method: str, path: str, body: dict | None = None, key: str = "") -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"User-Agent": f"Kai/{VERSION}", "Content-Type": "application/json"}
    if key:
        headers["x-kai-key"] = key
    request = urllib.request.Request(FEEDBACK_URL.rstrip("/") + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8") or "{}")


def send(stars: int, text: str, language: str) -> str | None:
    """None when it went through, else a short reason."""
    if not FEEDBACK_URL:
        return "no-server"
    try:
        stars = int(stars)
    except (TypeError, ValueError):
        return "stars"
    if not 1 <= stars <= 5:
        return "stars"
    try:
        _request("POST", "/api/feedback", {"stars": stars, "text": str(text or "").strip()[:2000], "version": VERSION, "lang": language})
    except Exception as exc:
        return type(exc).__name__
    return None


def send_crash(trace: str, language: str) -> str | None:
    """A crash report the user agreed to send. None when it went through."""
    if not FEEDBACK_URL:
        return "no-server"
    try:
        _request("POST", "/api/feedback", {"kind": "crash", "text": trace[-4000:], "version": VERSION, "lang": language})
    except Exception as exc:
        return type(exc).__name__
    return None


def _as_note(item: dict) -> dict:
    crash = item.get("kind") == "crash"
    stars = 0 if crash else max(1, min(5, int(item.get("stars") or 1)))
    text = str(item.get("text") or "").strip()
    first = " ".join(text.split())[:60]
    at = float(item.get("at") or time.time() * 1000) / 1000
    title = f"Çökme raporu · {item.get('version') or '?'}" if crash else f"{'★' * stars}{'☆' * (5 - stars)} " + (first or "Değerlendirme")
    return {
        "id": "fb-" + uuid.uuid4().hex[:12],
        "title": title,
        "started": at,
        "seconds": 0,
        "speakers": {},
        "transcript": [],
        "summary": text or "(yazı yok, sadece puan)",
        "key_points": ["Çökme raporu" if crash else f"Puan: {stars}/5", f"Sürüm: {item.get('version') or '?'}", f"Dil: {item.get('lang') or '?'}"],
        "todos": [],
        # Which file on the server it came from: never saved twice.
        "fb_id": str(item.get("id") or ""),
        "fb_stars": stars,
    }


def collect(key: str) -> list[dict]:
    """Takes what arrived: saves each as a note, then removes it from the server."""
    import notes

    items = _request("GET", "/api/inbox", key=key).get("items") or []
    known = {note.get("fb_id") for note in inbox()}
    saved, new = [], []
    for item in items:
        if not isinstance(item, dict) or not str(item.get("id") or "").startswith("https://"):
            continue
        if item["id"] not in known:
            notes.save(_as_note(item))
            new.append(item)
        saved.append(item)
    for start in range(0, len(saved), 20):
        query = urllib.parse.urlencode([("id", item["id"]) for item in saved[start:start + 20]])
        _request("DELETE", "/api/inbox?" + query, key=key)
    return new


def inbox() -> list[dict]:
    """The ratings already received, newest first."""
    import notes

    out = []
    for row in notes.listing():
        if not str(row.get("id") or "").startswith("fb-"):
            continue
        note = notes.load(row["id"]) or {}
        out.append({
            "id": row["id"], "fb_id": note.get("fb_id") or "", "at": note.get("started") or 0,
            "stars": note.get("fb_stars") if note.get("fb_stars") is not None else str(note.get("title") or "").count("★"),
            "crash": str(note.get("title") or "").startswith("Çökme raporu"),
            "text": note.get("summary") or "", "meta": " · ".join(note.get("key_points", [])[1:]),
        })
    return sorted(out, key=lambda item: -float(item["at"] or 0))


def start(settings, on_new) -> None:
    """The developer's Kai only: look for new ratings now and then."""

    def run() -> None:
        time.sleep(30)
        while True:
            key = (settings().feedback_key or "").strip()
            if key and FEEDBACK_URL:
                try:
                    found = collect(key)
                    if found:
                        on_new(found)
                except Exception:
                    pass
            time.sleep(EVERY)

    threading.Thread(target=run, daemon=True).start()
