"""API anahtarı düz yazı olarak durmaz: Windows'ta bu kullanıcıya mühürlenir (DPAPI)."""

from __future__ import annotations

import base64
import os

from . import db


def save_api_key(key: str) -> None:
    key = key.strip()
    if not key:
        db.set_setting("api_key", "")
        return
    if os.name == "nt":
        try:
            import win32crypt

            blob = win32crypt.CryptProtectData(key.encode("utf-8"), "Casper", None, None, None, 0)
            db.set_setting("api_key", "dpapi:" + base64.b64encode(blob).decode("ascii"))
            return
        except Exception:
            pass
    db.set_setting("api_key", "plain:" + key)


def load_api_key() -> str:
    env = os.environ.get("ANTHROPIC_API_KEY")
    if env:
        return env
    stored = db.get_setting("api_key") or ""
    if stored.startswith("dpapi:"):
        try:
            import win32crypt

            return win32crypt.CryptUnprotectData(base64.b64decode(stored[6:]), None, None, None, 0)[1].decode("utf-8")
        except Exception:
            return ""
    if stored.startswith("plain:"):
        return stored[6:]
    return ""


def has_api_key() -> bool:
    return bool(load_api_key())
