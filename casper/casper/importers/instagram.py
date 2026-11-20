"""Instagram "Bilgilerini dışa aktar" paketi (JSON biçimi).

Paket ya da açılmış klasör ya da tek tek message_N.json dosyaları verilebilir.
Sohbetler messages/inbox/<kişi_numara>/message_1.json, message_2.json... içinde.
Instagram metni latin-1 sanıp UTF-8 baytlarını kaçırıyor; "Ã¼" gibi bozuk
görünen Türkçe karakterler burada düzeltilir.
"""

from __future__ import annotations

import json
import posixpath
import re

from . import Thread, read_sources

# Gerçek mesaj olmayan sistem satırları (beğeni, tepki, ek bildirimi).
SKIP = re.compile(
    r"^(liked a message|reacted .{1,8} to your message|.{0,60} sent an attachment\.?|"
    r"bir mesajı beğendi|mesajına .{1,8} tepkisini verdi|.{0,60} bir ek gönderdi\.?|"
    r".{0,60} unsent a message|.{0,60} mesajı geri aldı)$",
    re.IGNORECASE,
)


def fix(text: str) -> str:
    if not isinstance(text, str):
        return ""
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def _wanted(name: str) -> bool:
    base = posixpath.basename(name)
    return base.startswith("message_") and base.endswith(".json")


def parse_paths(paths: list[str]) -> list[Thread]:
    threads: dict[str, Thread] = {}
    for name, data in read_sources(paths, _wanted):
        try:
            doc = json.loads(data.decode("utf-8"))
        except ValueError:
            continue
        if not isinstance(doc, dict) or "messages" not in doc:
            continue
        folder = posixpath.dirname(name) or name
        key = posixpath.basename(folder) or folder
        title = fix(doc.get("title") or "") or ", ".join(fix(p.get("name", "")) for p in doc.get("participants", []))
        thread = threads.setdefault(key, Thread(id=key, title=title or key, platform="instagram"))
        for m in doc.get("messages", []):
            sender = fix(m.get("sender_name", ""))
            ts = (m.get("timestamp_ms") or 0) / 1000.0
            content = fix(m.get("content", ""))
            if content and SKIP.match(content.strip()):
                continue
            if not content:
                if m.get("photos") or m.get("videos") or m.get("audio_files") or m.get("share") or m.get("sticker"):
                    share = m.get("share") or {}
                    content = "[paylaşım] " + fix(share.get("share_text", "")) if share else "[medya]"
                else:
                    continue
            if sender and ts:
                thread.messages.append({"sender": sender, "ts": ts, "text": content.strip()})
    # Aynı mesaj iki dosyada olursa (parçalı paketler) bir kez kalsın.
    for t in threads.values():
        unique = {(m["sender"], m["ts"], m["text"]): m for m in t.messages}
        t.messages = list(unique.values())
    return list(threads.values())
