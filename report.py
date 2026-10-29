"""Hata raporu: Kai's logs in one zip on the Desktop, and a GitHub issue page
filled in with the version and the system, to drag the zip into.

Nothing is sent by Kai: the user sees the zip and decides. What the user said
or dictated is cut out of the logs, and anything that looks like a key is masked.
"""

from __future__ import annotations

import ctypes
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import webbrowser
import zipfile

# A log line's words after these markers are what the user said or dictated.
SPOKEN = re.compile(r"^(\S+ (?:duydum|dikte \[[^\]]*\] [^:]*|not|yazdım|typed)):\s.*$", re.M)
KEYS = re.compile(r"\b(sk-[\w-]{12,}|gsk_\w{12,}|rk_\w{12,}|sk_\w{12,}|ghp_\w{12,}|github_pat_\w{12,}|xi-\w{12,}|AIza[\w-]{20,})")
LIMIT = 2_000_000


def _desktop() -> str:
    buffer = ctypes.create_unicode_buffer(260)
    if ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buffer) == 0 and buffer.value:  # CSIDL_DESKTOPDIRECTORY
        return buffer.value
    return os.path.expanduser("~")


def _app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def clean(text: str) -> str:
    text = SPOKEN.sub(lambda m: f"{m.group(1)}: [gizlendi]", text)
    return KEYS.sub("[anahtar gizlendi]", text)


def _tail(path: str) -> str:
    try:
        with open(path, "rb") as handle:
            handle.seek(max(0, os.path.getsize(path) - LIMIT))
            return handle.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _about() -> dict:
    import models
    from settings import Settings
    from version import VERSION

    s = Settings()
    return {
        "kai": VERSION,
        "windows": platform.platform(),
        "python": platform.python_version(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "language": s.language,
        "provider": s.provider,
        "voice": s.elevenlabs_voice,
        "stt_engine": s.stt_engine,
        "dictation": s.dictation,
        "ok_kai": s.ok_kai,
        "speak": s.speak,
        "mascot": s.mascot,
        # Whether a key is there, never the key.
        "keys": {k: bool(getattr(s, k, "")) for k in ("groq_key", "api_key", "elevenlabs_key", "github_token", "vercel_token", "stripe_key", "mail_password", "calendar_ics")},
        "models": {m["id"]: m["ready"] for m in models.status()},
    }


def make(note: str = "") -> dict:
    from version import UPDATE_REPO

    about = _about()
    stamp = time.strftime("%Y%m%d-%H%M")
    target = os.path.join(_desktop(), f"Kai-rapor-{stamp}.zip")
    logs = {
        "kai.log": os.path.join(_app_dir(), "kai.log"),
        "kai-voice.log": os.path.join(tempfile.gettempdir(), "kai-voice.log"),
    }
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("sistem.json", json.dumps(about, ensure_ascii=False, indent=2))
        if note:
            archive.writestr("not.txt", note)
        for name, path in logs.items():
            text = _tail(path)
            if text:
                archive.writestr(name, clean(text))
    subprocess.Popen(["explorer.exe", f"/select,{target}"])
    body = (
        f"**Ne oldu?**\n{note or '(kısaca yaz)'}\n\n"
        f"**Kai** {about['kai']} · {about['windows']}\n\n"
        f"Masaüstündeki `{os.path.basename(target)}` dosyasını buraya sürükle.\n"
        "(Loglarda söylediklerin gizlendi, anahtarlar maskelendi; yüklemeden önce açıp bakabilirsin.)"
    )
    query = urllib.parse.urlencode({"title": f"Kai {about['kai']}: " + (note[:60] or "hata raporu"), "body": body}, quote_via=urllib.parse.quote)
    if UPDATE_REPO:
        webbrowser.open(f"https://github.com/{UPDATE_REPO}/issues/new?{query}")
    return {"zip": target, "text": f"Rapor masaüstünde: {os.path.basename(target)}. Açılan GitHub sayfasına sürükleyip gönder."}
