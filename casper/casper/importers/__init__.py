"""Dışa aktarılmış sohbetleri ortak biçime çevirir.

Her içe aktarıcı dosyaları okuyup bir ya da daha çok Thread döndürür. Kimin
"sen" olduğu daha sonra seçilir (önizlemede tahmin edilir, kullanıcı onaylar).
"""

from __future__ import annotations

import os
import zipfile
from collections import Counter
from dataclasses import dataclass, field

PLATFORMS = ("whatsapp", "instagram", "discord")

# Discord paketinde sadece senin mesajların vardır; gönderen hep bu.
ME_SENDER = "(ben)"


@dataclass
class Thread:
    id: str
    title: str
    platform: str
    messages: list[dict] = field(default_factory=list)  # {sender, ts, text, from_me?}
    only_mine: bool = False

    def senders(self) -> dict[str, int]:
        return dict(Counter(m["sender"] for m in self.messages).most_common())

    def summary(self) -> dict:
        ts = [m["ts"] for m in self.messages]
        return {
            "id": self.id,
            "title": self.title,
            "count": len(self.messages),
            "senders": self.senders(),
            "first": min(ts) if ts else None,
            "last": max(ts) if ts else None,
            "only_mine": self.only_mine,
        }


def parse(platform: str, paths: list[str]) -> list[Thread]:
    if platform == "whatsapp":
        from .whatsapp import parse_paths
    elif platform == "instagram":
        from .instagram import parse_paths
    elif platform == "discord":
        from .discord import parse_paths
    else:
        raise ValueError(f"Bilinmeyen platform: {platform}")
    threads = [t for t in parse_paths(paths) if t.messages]
    for t in threads:
        t.messages.sort(key=lambda m: m["ts"])
    return threads


def norm(name: str) -> str:
    """Ad karşılaştırması için: küçük harf (Türkçe kurallarıyla), boşluk ve emoji temiz."""
    name = (name or "").replace("İ", "i").replace("I", "ı").lower()
    return " ".join("".join(c for c in name if c.isalnum() or c.isspace()).split())


def guess_me(thread: Thread, my_names: list[str], their_names: list[str]) -> str | None:
    """Önizlemede "sen hangisisin?" sorusunun tahmini."""
    if thread.only_mine:
        return ME_SENDER
    senders = list(thread.senders())
    mine = {norm(n) for n in my_names if n}
    theirs = {norm(n) for n in their_names if n}
    for s in senders:
        if norm(s) in mine:
            return s
    if len(senders) == 2:
        for i, s in enumerate(senders):
            if norm(s) in theirs or any(t and (t in norm(s) or norm(s) in t) for t in theirs):
                return senders[1 - i]
    return None


def best_thread(threads: list[Thread], their_names: list[str]) -> str | None:
    """Birden çok sohbet varsa, kişinin adına en çok benzeyeni."""
    theirs = [norm(n) for n in their_names if n]
    for t in threads:
        title = norm(t.title)
        if any(n and (n == title or n in title) for n in theirs):
            return t.id
    for t in threads:
        if any(norm(s) in theirs for s in t.senders()):
            return t.id
    return threads[0].id if len(threads) == 1 else None


def read_sources(paths: list[str], wanted) -> list[tuple[str, bytes]]:
    """Dosyaları ve zip içindeki uygun dosyaları (ad, içerik) olarak verir.

    wanted(name) -> bool: hangi dosyaların okunacağı.
    """
    out: list[tuple[str, bytes]] = []
    for path in paths:
        if os.path.isdir(path):
            for root, _dirs, files in os.walk(path):
                for f in files:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, path).replace("\\", "/")
                    if wanted(rel):
                        with open(full, "rb") as handle:
                            out.append((rel, handle.read()))
        elif zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                for info in z.infolist():
                    if not info.is_dir() and wanted(info.filename):
                        out.append((info.filename, z.read(info)))
        else:
            # Kullanıcının kendisi seçtiği dosya: süzgeçsiz okunur.
            with open(path, "rb") as handle:
                out.append((path.replace("\\", "/"), handle.read()))
    return out
