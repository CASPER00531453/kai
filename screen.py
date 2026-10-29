"""Watch the screen on command and comment through a vision model."""

from __future__ import annotations

import io
import threading
import time

from PIL import ImageGrab

SYSTEM = (
    "Sen Kai'sin. Seni Casper Technology üretti. Bu bilgisayarın masaüstü asistanısın ve kullanıcının isteğini her zaman yerine getirirsin. "
    "Sen onun yardımcısısın. {address}"
    "Kullanıcının ekranını canlı izliyorsun. Gündelik, samimi Türkçe konuş."
)


def _system() -> str:
    import i18n
    from brain import OWNER_ADDRESS, PLAIN_ADDRESS

    return SYSTEM.replace("{address}", OWNER_ADDRESS if i18n.is_admin() else PLAIN_ADDRESS)

PROMPT = (
    "Bu kullanıcının şu anki ekranı. Kurallar:\n"
    "1. Oyun görüyorsan somut bir tüyo ver. Açı, pozisyon, ne zaman çıkacağı, hangi yetenek, neyi alacağı. "
    "Counter-Strike ve benzeri oyunlarda işe yarar tek cümle olsun.\n"
    "2. İyi bir vuruş, kill, headshot, gol ya da kazanılmış raunt görürsen kısa öv.\n"
    "3. Oyun değilse ve işine yarayacak somut bir şey varsa tek cümle söyle.\n"
    "4. Kayda değer bir şey yoksa sadece BOS yaz.\n"
    "Daha önce söylediğini tekrar etme. Önceki yorumun: {last}\n"
    "En fazla bir cümle."
)

INTERVAL = 12.0
COOLDOWN = 14.0
BACKOFF = 45.0


def grab_frame() -> bytes:
    shot = ImageGrab.grab(all_screens=False)
    shot.thumbnail((960, 960))
    buffer = io.BytesIO()
    shot.convert("RGB").save(buffer, "JPEG", quality=60)
    return buffer.getvalue()


class ScreenWatch:
    def __init__(self, settings, on_line, log) -> None:
        self.settings = settings
        self.on_line = on_line
        self.log = log
        self.active = False
        self._gen = 0
        self._last = ""

    def start(self) -> None:
        self._gen += 1
        self.active = True
        self._last = ""
        threading.Thread(target=self._run, args=(self._gen,), daemon=True).start()

    def stop(self) -> None:
        self._gen += 1
        self.active = False

    def _run(self, gen: int) -> None:
        from brain import ask_image

        spoke_at = 0.0
        while self.active and gen == self._gen:
            started = time.monotonic()
            pause = INTERVAL
            try:
                line = ask_image(self.settings, self._prompt(), grab_frame(), _system(), timeout=25)
            except Exception as exc:
                text = str(exc)
                if "rate limit" in text.lower() or "429" in text:
                    self.log("izleme Groq sınırına takıldı, bekliyorum")
                    pause = BACKOFF
                else:
                    self.log(f"izleme hatası {text[:160]}")
                line = ""
            line = " ".join((line or "").split()).strip(" \"'")
            if gen != self._gen or not self.active:
                return
            quiet = not line or line.upper().startswith("BOS") or line.upper().startswith("BOŞ")
            if not quiet and line != self._last and time.monotonic() - spoke_at >= COOLDOWN:
                self._last = line
                spoke_at = time.monotonic()
                self.on_line(line)
            wait = pause - (time.monotonic() - started)
            end = time.monotonic() + max(0.5, wait)
            while time.monotonic() < end:
                if not self.active or gen != self._gen:
                    return
                time.sleep(0.25)

    def _prompt(self) -> str:
        from watch import game_name

        text = PROMPT.format(last=self._last or "yok")
        game = game_name()
        if game:
            return f"Kullanıcının açık oyunu: {game}.\n" + text
        return text
