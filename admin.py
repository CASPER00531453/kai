"""Kai's owner. A fresh Kai speaks to everyone plainly; the owner types the admin
code in the chat once and from then on Kai calls them "patron" and shows the
ratings inbox in the Kai window.

Only the code's hash is in here, so it cannot be read out of Kai. The flag is
kept in the settings sealed to this Windows account (settings.py). The inbox
itself still needs the server key, which only the owner's Kai holds.
"""

from __future__ import annotations

import hashlib

CODE_SHA256 = "ee4c70ddf3f007a83f79f6647bf95fbe4e7af9f271d615a8cda66534613265b3"
LOCK_WORDS = {"admin:kapat", "admin:off", "admin:çıkış", "admin:cikis"}


def handle(settings, text: str) -> str | None:
    """The answer when the chat line is the admin code (or the word to lock it); else None.

    Checked before anything else, so the code never reaches the model or the memory.
    """
    line = (text or "").strip()
    if not line.lower().startswith("admin:"):
        return None
    turkish = getattr(settings, "language", "tr") == "tr"
    if line.lower() in LOCK_WORDS:
        _set(settings, False)
        return "Tamam, yönetici modu kapandı." if turkish else "Okay, owner mode is off."
    if hashlib.sha256(line.encode("utf-8")).hexdigest() != CODE_SHA256:
        return "Bu kod tutmadı." if turkish else "That code didn't match."
    _set(settings, True)
    return (
        "Hoş geldin patron. Bundan sonra sana patron diyeceğim; değerlendirmeler Kai penceresinde açıldı."
        if turkish
        else "Welcome back, boss. From now on you're the boss; the ratings inbox is open in the Kai window."
    )


def _set(settings, on: bool) -> None:
    from settings import push_cmd

    settings.admin = on
    settings.save()
    # The main process and the Kai window read their settings again.
    push_cmd("settings")
