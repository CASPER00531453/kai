"""WhatsApp "Sohbeti dışa aktar" dosyaları (.txt ya da içinde .txt olan .zip).

Tanınan biçimler (telefonun diline göre değişir):
    19.11.2026 14:32 - Ahmet: mesaj
    19/11/2026, 14:32 - Ahmet: mesaj
    11/19/26, 2:32 PM - Ahmet: mesaj
    [19.11.2026 14:32:05] Ahmet: mesaj        (iPhone)
Birden çok satırlı mesajlar bir önceki mesaja eklenir. Gönderensiz satırlar
(şifreleme bildirimi, "X gruba katıldı") atlanır.
"""

from __future__ import annotations

import os
import re
from datetime import datetime

from . import Thread, read_sources

LINE = re.compile(
    r"^\[?(\d{1,4})[./-](\d{1,2})[./-](\d{1,4}),?\s+(\d{1,2})[:.](\d{2})(?:[:.](\d{2}))?\s*([AaPp]\.?\s?[Mm]\.?|ÖÖ|ÖS)?\]?\s*(?:-\s+)?(.*)$"
)
MEDIA = {
    "<medya dahil edilmedi>", "<media omitted>", "medya dahil edilmedi", "görüntü dahil edilmedi",
    "image omitted", "video omitted", "audio omitted", "sticker omitted", "gif omitted",
    "ses dahil edilmedi", "video dahil edilmedi", "çıkartma dahil edilmedi",
}
DELETED = {"bu mesaj silindi", "this message was deleted", "bu mesajı sildiniz", "you deleted this message"}
INVISIBLE = dict.fromkeys(map(ord, "‎‏‪‫‬‭‮﻿"), None)


def _clean(line: str) -> str:
    return line.translate(INVISIBLE).replace(" ", " ").replace(" ", " ").rstrip("\r")


def _title_from(name: str) -> str:
    base = os.path.splitext(os.path.basename(name))[0]
    for prefix in ("WhatsApp Sohbeti - ", "WhatsApp Chat with ", "WhatsApp Chat - ", "WhatsApp Sohbeti -"):
        if base.startswith(prefix):
            return base[len(prefix):].strip()
    return base


def _date_order(heads: list[tuple[int, int, int]]) -> str:
    """'dmy', 'mdy' ya da 'ymd'. Türkiye'de varsayılan gün önce."""
    if any(a > 31 for a, _b, _c in heads):
        return "ymd"
    if any(a > 12 for a, _b, _c in heads):
        return "dmy"
    if any(b > 12 for _a, b, _c in heads):
        return "mdy"
    return "dmy"


def parse_text(text: str, title: str) -> Thread:
    lines = [_clean(line) for line in text.splitlines()]
    matches = [(i, LINE.match(line)) for i, line in enumerate(lines)]
    heads = [(int(m.group(1)), int(m.group(2)), int(m.group(3))) for _i, m in matches if m]
    order = _date_order(heads)
    thread = Thread(id=title, title=title, platform="whatsapp")
    current: dict | None = None
    for i, m in matches:
        if not m:
            if current is not None and lines[i].strip():
                current["text"] += "\n" + lines[i]
            continue
        a, b, c = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if order == "ymd":
            year, month, day = a, b, c
        elif order == "mdy":
            month, day, year = a, b, c
        else:
            day, month, year = a, b, c
        if year < 100:
            year += 2000
        hour, minute, second = int(m.group(4)), int(m.group(5)), int(m.group(6) or 0)
        ampm = (m.group(7) or "").lower().replace(".", "").replace(" ", "")
        if ampm in ("pm", "ös") and hour < 12:
            hour += 12
        elif ampm in ("am", "öö") and hour == 12:
            hour = 0
        try:
            ts = datetime(year, month, day, hour, minute, second).timestamp()
        except ValueError:
            if current is not None:
                current["text"] += "\n" + lines[i]
            continue
        rest = m.group(8)
        if ": " not in rest:
            current = None  # sistem satırı
            continue
        sender, body = rest.split(": ", 1)
        sender = sender.strip()
        body = body.strip()
        if body.lower() in MEDIA:
            body = "[medya]"
        elif body.lower() in DELETED:
            body = "[silinen mesaj]"
        current = {"sender": sender, "ts": ts, "text": body}
        thread.messages.append(current)
    for msg in thread.messages:
        msg["text"] = msg["text"].strip()
    return thread


def parse_paths(paths: list[str]) -> list[Thread]:
    threads = []
    for name, data in read_sources(paths, lambda n: n.lower().endswith(".txt")):
        text = data.decode("utf-8-sig", errors="replace")
        title = _title_from(name)
        if os.path.basename(name).lower() == "_chat.txt":  # iPhone zip'i
            title = next((_title_from(p) for p in paths if p.lower().endswith(".zip")), title)
        threads.append(parse_text(text, title))
    # Aynı başlık iki kez gelirse kimlikleri ayır.
    seen: dict[str, int] = {}
    for t in threads:
        seen[t.id] = seen.get(t.id, 0) + 1
        if seen[t.id] > 1:
            t.id = f"{t.id} ({seen[t.id]})"
    return threads
