"""Dictation anywhere: hold the key, speak, let go, and the words are typed where the cursor is.

Two quick taps keep Kai listening hands-free until the next tap; Escape throws
the recording away; Alt+Shift+V pastes the last dictation again. The key is
watched by hook.AltGrHook, which posts its presses to the main window; this
class only keeps the state and does the work off the window's thread.
"""

from __future__ import annotations

import ctypes
import threading
import time

import flow
import paste
import stt
import voicelevel
from audio import Microphone
from settings import push_v2

TAP = 0.28  # shorter than this is a tap, not a held key
DOUBLE = 0.45  # two taps this close start hands-free dictation
SHORTEST = 0.35  # less audio than this is a slip of the finger


def _log(message: str) -> None:
    try:
        from ears import _log as log

        log(message)
    except Exception:
        pass


class Dictation:
    def __init__(self, settings_getter, busy) -> None:
        """`settings_getter()` gives fresh settings; `busy()` is True while AltGr is listening."""
        self._settings = settings_getter
        self._busy = busy
        self.mic = Microphone()
        self.state = "idle"  # idle, held, maybe_double, hands_free, working
        self.down_at = 0.0
        self.last_tap = 0.0
        self.started = 0.0
        self.last_text = ""
        self._timer: threading.Timer | None = None
        self._level_running = False
        self.on_record = None
        self._watch_paste_hotkey()

    # ── Keys ────────────────────────────────────────────────────────────────

    def enabled(self) -> bool:
        return bool(getattr(self._settings(), "dictation", False))

    def key_down(self) -> None:
        if not self.enabled() or self._busy():
            return
        now = time.monotonic()
        if self.state == "hands_free":
            self._finish()
            return
        if self.state == "maybe_double":
            self._cancel_timer()
            self.state = "hands_free"
            push_v2("dictate", self._t("Eller serbest dinliyorum… (bitirmek için bir kez bas)", "Listening hands-free… (tap once to finish)"))
            return
        if self.state != "idle":
            return
        self.state = "held"
        self.down_at = now
        self._start_mic()

    def key_up(self) -> None:
        if self.state != "held":
            return
        held = time.monotonic() - self.down_at
        if held < TAP:
            # Maybe the first of two taps: keep listening a moment to find out.
            self.state = "maybe_double"
            self.last_tap = time.monotonic()
            self._timer = threading.Timer(DOUBLE, self._single_tap)
            self._timer.daemon = True
            self._timer.start()
            return
        self._finish()

    def other_key(self) -> None:
        """Another key while the dictation key is held: it was a shortcut (Ctrl+C), not dictation."""
        if self.state in ("held", "maybe_double"):
            self._cancel(silent=True)

    def escape(self) -> None:
        if self.state in ("held", "maybe_double", "hands_free"):
            self._cancel(silent=False)

    # ── Recording ───────────────────────────────────────────────────────────

    def _t(self, tr: str, en: str) -> str:
        try:
            import i18n

            return tr if i18n.current() == "tr" else en
        except Exception:
            return tr

    def _start_mic(self) -> None:
        self.started = time.monotonic()
        self.mic.start()
        push_v2("dictate", self._t("Dikte… bırakınca yazarım", "Dictating… let go to type it"))
        self._levels()

    def _levels(self) -> None:
        if self._level_running:
            return
        self._level_running = True

        def run() -> None:
            while self.state in ("held", "maybe_double", "hands_free"):
                voicelevel.put(self.mic.level)
                time.sleep(0.05)
            voicelevel.put(0.0)
            self._level_running = False

        threading.Thread(target=run, daemon=True).start()

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _single_tap(self) -> None:
        if self.state == "maybe_double":
            self._cancel(silent=True)

    def _cancel(self, silent: bool) -> None:
        self._cancel_timer()
        self.state = "idle"
        self.mic.stop()
        push_v2("dictate-end", "" if silent else self._t("Dikte iptal", "Dictation cancelled"))

    def _finish(self) -> None:
        self._cancel_timer()
        spoken = time.monotonic() - self.started
        audio = self.mic.stop_and_take()
        self.state = "working"
        if audio is None or spoken < SHORTEST:
            self.state = "idle"
            push_v2("dictate-end", "")
            return
        app = paste.foreground_app()
        push_v2("dictate-busy", self._t("Yazıyorum…", "Typing…"))
        threading.Thread(target=self._work, args=(audio, spoken, app), daemon=True).start()

    def _work(self, audio, spoken: float, app: str) -> None:
        try:
            settings = self._settings()
            engine = getattr(settings, "stt_engine", "online")
            raw, used = stt.transcribe(audio, engine=engine, language=getattr(settings, "language", "tr"), prompt=flow.hint())
            _log(f"dikte [{used}] {app}: {raw[:80]}")
            if not raw:
                push_v2("dictate-end", self._t("Bir şey duyamadım", "I didn't hear anything"))
                return
            text, style = flow.process(raw, app)
            where = paste.paste(text)
            self.last_text = text
            flow.record(text, raw, app, spoken, used, style)
            if where == "clipboard":
                push_v2("dictate-end", self._t("Yazı alanı yoktu: metin panoda, Ctrl+V ile yapıştır", "No text field: it's on the clipboard, press Ctrl+V"))
            else:
                push_v2("dictate-end", "")
        except Exception as exc:
            _log(f"dikte hatası {type(exc).__name__}: {exc}")
            push_v2("dictate-end", self._t("Dikte olmadı", "Dictation failed"))
        finally:
            self.state = "idle"

    # ── Paste the last one again ────────────────────────────────────────────

    def paste_last(self) -> None:
        if self.last_text:
            paste.paste(self.last_text)
            return
        recent = flow.history(1)
        if recent:
            self.last_text = recent[-1].get("text") or ""
            paste.paste(self.last_text)

    def _watch_paste_hotkey(self) -> None:
        def run() -> None:
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            # Alt+Shift+V pastes the last dictation, Alt+Shift+N starts or stops
            # the notetaker; like Alt+Shift+S for picking from the screen.
            user32.RegisterHotKey(None, 0x4B56, 0x0001 | 0x0004 | 0x4000, ord("V"))
            user32.RegisterHotKey(None, 0x4B4E, 0x0001 | 0x0004 | 0x4000, ord("N"))
            message = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message != 0x0312:
                    continue
                try:
                    if message.wParam == 0x4B56 and self.enabled():
                        self.paste_last()
                    elif message.wParam == 0x4B4E and self.on_record:
                        self.on_record()
                except Exception:
                    pass

        threading.Thread(target=run, daemon=True).start()
