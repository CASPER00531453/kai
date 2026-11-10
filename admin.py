"""Kai's owner. A fresh Kai speaks to everyone plainly; the owner types the admin
code in the chat once and from then on Kai calls them "patron" and shows the
ratings inbox in the Kai window.

Only a slow hash of the code is in here (scrypt, salted): the code cannot be
read out of Kai's source, and guessing it would take a lifetime. The flag is
kept in the settings sealed to this Windows account (settings.py). The inbox
itself still needs the server key, which only the owner's Kai holds.
"""

from __future__ import annotations

import hashlib

CODE_SALT = "576d5aa2068c725969a62458394c234c"
CODE_SCRYPT = "da478ebd7c68d04f17a4d33dc4c6ef3b41fcc9f382602e9ca984c84843f6dfbe"
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
    if not _matches(line):
        return "Bu kod tutmadı." if turkish else "That code didn't match."
    _set(settings, True)
    return (
        "Hoş geldin patron. Bundan sonra sana patron diyeceğim; değerlendirmeler Kai penceresinde açıldı."
        if turkish
        else "Welcome back, boss. From now on you're the boss; the ratings inbox is open in the Kai window."
    )


def _matches(line: str) -> bool:
    import hmac

    # Typed in lower case on a phone keyboard is the same code.
    line = "admin:" + line[6:].strip().upper()
    digest = hashlib.scrypt(line.encode("utf-8"), salt=bytes.fromhex(CODE_SALT), n=2**15, r=8, p=1, maxmem=64 * 1024 * 1024, dklen=32)
    return hmac.compare_digest(digest.hex(), CODE_SCRYPT)


def _set(settings, on: bool) -> None:
    from settings import push_cmd

    settings.admin = on
    settings.save()
    # The main process and the Kai window read their settings again.
    push_cmd("settings")
