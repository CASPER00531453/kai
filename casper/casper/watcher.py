"""Gözcü modu: birkaç saniyede bir öndeki sohbet penceresine bakar, yorum yapar.

- Her 2/3/5 saniyede (ayardan) bir öndeki pencereye bakılır.
- Sadece WhatsApp / Instagram / Discord (ya da ayarda "tüm pencereler") izlenir.
  Kara listedeki başlıklar (banka, şifre, gizli sekme...) asla kaydedilmez.
- Görüntü değişmediyse hiçbir şey yapılmaz. Değiştiyse Windows OCR ile okunur;
  sadece YENİ satırlar kaydedilir.
- Claude'a her karede değil, yeni yazı biriktiğinde ve bekleme süresi (ayardan,
  varsayılan 20 sn) dolduğunda gidilir. Ekran görüntüsü sık, yorum seyrek: ucuz.
- Yorumlar ikinci ekrandaki küçük pencereye ve ana pencereye gider.
"""

from __future__ import annotations

import base64
import io
import os
import threading
import time
from collections import deque

from . import brain, db, llm, ocr, winscreen
from .importers import norm

BROWSERS = ("chrome", "msedge", "firefox", "opera", "brave", "vivaldi", "arc")


def classify(win: winscreen.Window) -> str:
    exe = win.exe.lower()
    title = win.title.lower()
    if "whatsapp" in exe or (exe.startswith(BROWSERS) and "whatsapp" in title):
        return "whatsapp"
    if "discord" in exe or (exe.startswith(BROWSERS) and "discord" in title):
        return "discord"
    if "instagram" in exe or "instagram" in title:
        return "instagram"
    return ""


def _signature(image) -> bytes:
    return image.convert("L").resize((48, 48)).tobytes()


def _changed(a: bytes | None, b: bytes) -> bool:
    if a is None or len(a) != len(b):
        return True
    diff = sum(abs(x - y) for x, y in zip(a, b)) / len(b)
    return diff > 1.5


def match_person(title: str, lines: list[dict]) -> int | None:
    """Sohbetin kiminle olduğunu tahmin et: önce başlık, sonra sohbet başlığı satırları."""
    aliases = [(norm(a["name"]), a["person_id"]) for a in db.all_aliases()]
    aliases = [(n, pid) for n, pid in aliases if len(n) >= 3]
    if not aliases:
        return None
    t = norm(title)
    hits = [(len(n), pid) for n, pid in aliases if n in t]
    if hits:
        return max(hits)[1]
    header = " ".join(norm(l["text"]) for l in lines if l["y"] < 0.18 and l["x"] > 0.25)
    hits = [(len(n), pid) for n, pid in aliases if n and n in header]
    if hits:
        return max(hits)[1]
    return None


class Watcher:
    def __init__(self, on_event) -> None:
        self.on_event = on_event
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._busy = threading.Lock()
        self.state = "kapalı"
        self.last_comment_at = 0.0
        self.comments: deque[str] = deque(maxlen=12)
        self.seen: dict[str, deque] = {}
        self.pending: dict[str, dict] = {}
        self.last_sig: bytes | None = None
        self.frames = 0

    # --- dışarıya açık --------------------------------------------------------

    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="casper-gozcu", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._set_state("kapalı")

    def status(self) -> dict:
        return {
            "running": self.running(),
            "state": self.state,
            "frames": self.frames,
            "ocr": ocr.available(),
            "ocr_error": ocr.last_error(),
        }

    # --- iç işler ----------------------------------------------------------------

    def _set_state(self, state: str) -> None:
        if state != self.state:
            self.state = state
            self.on_event({"type": "state", "state": state})

    def _run(self) -> None:
        if not winscreen.IS_WINDOWS:
            self._set_state("Gözcü modu sadece Windows'ta çalışır.")
            return
        self._set_state("izliyor")
        own_pid = os.getpid()
        while not self._stop.is_set():
            started = time.time()
            try:
                self._tick(own_pid)
                self._flush()
            except Exception as exc:  # gözcü asla çökmesin
                self.on_event({"type": "error", "text": f"Gözcü hatası: {exc}"})
            interval = float(db.get_setting("watch_interval") or 3)
            self._stop.wait(max(0.5, interval - (time.time() - started)))

    def _tick(self, own_pid: int) -> None:
        win = winscreen.foreground()
        if win is None or win.pid == own_pid or winscreen.is_minimized(win.hwnd):
            return
        title_l = win.title.lower()
        if any(b and b.lower() in title_l for b in db.get_setting("watch_blocklist") or []):
            self._set_state("gizli pencere, bakmıyorum")
            return
        app = classify(win)
        if not app:
            if not db.get_setting("watch_all_windows"):
                self._set_state("sohbet penceresi bekliyor")
                return
            app = win.exe.replace(".exe", "") or "pencere"
        elif app not in (db.get_setting("watch_apps") or []):
            self._set_state(f"{app} izlenmiyor (ayarlar)")
            return
        image = winscreen.grab(win.rect)
        if image is None:
            return
        self.frames += 1
        sig = _signature(image)
        if not _changed(self.last_sig, sig):
            self._set_state(f"izliyor: {app}")
            return
        self.last_sig = sig
        self._set_state(f"izliyor: {app}")
        key = f"{app}|{win.title}"

        if ocr.available():
            lines = ocr.read_lines(image)
            seen = self.seen.setdefault(key, deque(maxlen=600))
            seen_set = set(seen)
            new = [l for l in lines if l["text"].strip() and l["text"] not in seen_set]
            for l in new:
                seen.append(l["text"])
            if sum(len(l["text"]) for l in new) < 6:
                return
            person_id = match_person(win.title, lines)
            wid = db.add_watch(app, win.title, person_id, ocr.format_lines(new))
            self.on_event({"type": "seen", "app": app, "title": win.title, "new_lines": len(new)})
            self.pending[key] = {
                "app": app, "title": win.title, "person_id": person_id, "wid": wid,
                "text": ocr.format_lines(lines[-120:]), "image": None,
            }
        else:
            person_id = match_person(win.title, [])
            wid = db.add_watch(app, win.title, person_id, "")
            small = image.copy()
            small.thumbnail((1568, 1568))
            buf = io.BytesIO()
            small.convert("RGB").save(buf, format="PNG")
            self.pending[key] = {
                "app": app, "title": win.title, "person_id": person_id, "wid": wid,
                "text": "", "image": base64.b64encode(buf.getvalue()).decode("ascii"),
            }

        self.pending_key = key

    def _flush(self) -> None:
        """Bekleme süresi dolduysa en son değişen sohbet için yorum iste."""
        key = getattr(self, "pending_key", None)
        if not key or key not in self.pending or self._busy.locked():
            return
        cooldown = float(db.get_setting("watch_cooldown") or 20)
        if time.time() - self.last_comment_at < cooldown:
            return
        job = self.pending.pop(key)
        self.pending.clear()  # eski pencerelerin bekleyenleri bayatladı
        self.last_comment_at = time.time()
        threading.Thread(target=self._comment, args=(job,), daemon=True).start()

    def _comment(self, job: dict) -> None:
        with self._busy:
            self.on_event({"type": "thinking", "app": job["app"], "title": job["title"]})
            try:
                if job["image"]:
                    text = brain.watch_comment_image(job["app"], job["title"], job["image"], job["person_id"], list(self.comments))
                else:
                    text = brain.watch_comment(job["app"], job["title"], job["text"], job["person_id"], list(self.comments))
            except llm.LLMError as exc:
                self.on_event({"type": "error", "text": str(exc)})
                return
            except Exception as exc:
                self.on_event({"type": "error", "text": f"Yorum yapılamadı: {exc}"})
                return
            if not text:
                self.on_event({"type": "quiet"})
                return
            self.comments.append(text)
            db.set_watch_comment(job["wid"], text)
            person = db.person(job["person_id"]) if job["person_id"] else None
            self.on_event({
                "type": "comment",
                "app": job["app"],
                "title": job["title"],
                "person": person["name"] if person else "",
                "text": text,
                "ts": time.time(),
            })
