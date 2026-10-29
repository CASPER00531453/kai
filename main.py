"""Kai. Resting island, AltGr listen, file drop, Groq or API."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import math
import os
import queue
import subprocess
import sys
import threading
import time
import traceback

# The island menu and the Kai window are processes of their own and need none of
# the listening, camera and speech code imported below: they start before it is
# loaded, so starting Kai does not load all of it three times over.
if __name__ == "__main__" and ("--island-menu" in sys.argv or "--app" in sys.argv):
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Kai.DynamicIsland")
    except Exception:
        pass
    if "--island-menu" in sys.argv:
        from menu_window import main as _window_main
    else:
        from app_window import main as _window_main
    _window_main()
    sys.exit(0)

import agents
import control
from audio import Microphone
import boxes
import camera_view
import live_view
from coding import DiffWatch
import lol
from remote_chat import ChatBox
from brain import TYPE_PERSONA, ask, ask_image, converse, decide, file_prompt
from control import direct_command, handle, intent, perform, watch_intent
import media
import updater
import reminders
from typer import parse as parse_type
from typer import type_into
from drop_target import attach, detach
from ears import transcribe
from hook import AltGrHook
import notes
import stt
import voicelevel
import extras
import kaicalendar
import wake
from dictation import Dictation
from i18n import t
from island import Island, enable_dpi
from settings import Settings, push_v2, push_v2_hook, set_startup, settings_path, v2_file
from settings_ui import open_settings
from tray import Tray
from pointer import Pointer, act as pointer_act
from screen import ScreenWatch, grab_frame
from voice import is_free, speak
from watch import cursor_pos, game_name, playing_game

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WM_APP = 0x8000
MSG_ALT_DOWN = WM_APP + 1
MSG_ALT_UP = WM_APP + 2
MSG_OTHER = WM_APP + 3
MSG_SHOW = WM_APP + 4
MSG_MUSIC = WM_APP + 5
MSG_QUIT = WM_APP + 6
MSG_SELFTEST_DONE = WM_APP + 7
MSG_APPLY_DYNAMIC = WM_APP + 9
MSG_ANSWER = WM_APP + 10
MSG_SCREEN = WM_APP + 11
MSG_HEARD = WM_APP + 12
MSG_AGENT = WM_APP + 13
MSG_CODE = WM_APP + 15
MSG_LOL = WM_APP + 17
MSG_REMIND = WM_APP + 19
MSG_DICT_DOWN = WM_APP + 20
MSG_DICT_UP = WM_APP + 21
MSG_ESC = WM_APP + 22
MSG_WAKE = WM_APP + 23

ARM_DELAY = 0.14
_NOT_A_SONG = {
    "bunu", "şunu", "sunu", "onu", "şarkı", "sarki", "şarkıyı", "sarkiyi", "şarkısı",
    "olan", "durdurulmuş", "durdurulmus", "duraklatılmış", "duraklatilmis", "çalan", "calan",
    "parça", "parca", "parçayı", "müzik", "muzik", "şeyi", "seyi", "bir", "o", "şu", "su",
}


def push_cmd_record() -> None:
    """Alt+Shift+N: through the command file, so it lands on the main thread like the app's button."""
    from settings import push_cmd

    push_cmd("record_toggle")


def _permit_word(text: str) -> str | None:
    folded = " ".join(text.lower().replace("'", "").split())
    deny = ("not allow", "izin verme", "kabul etme", "reddet", "redd", "hayır", "hayir", "iptal", "deny")
    allow = ("onaylıyorum", "onayliyorum", "onay", "kabul", "izin ver", "allow", "evet")
    if any(word in folded for word in deny):
        return "deny"
    if any(word in folded for word in allow):
        return "allow"
    return None


def _song_name(query: str) -> bool:
    words = [word for word in query.lower().split() if word not in _NOT_A_SONG]
    return len(" ".join(words)) >= 2


LOOK_PROMPT = (
    "Bu kullanıcının şu anki ekran görüntüsü. Sorusu: \"{q}\". "
    "Ekranda gördüğüne bakarak cevap ver; uygulamayı, sayfayı ve önemli yazıları söyle. "
    "Kai'nin kendi siyah adasını ve sohbet kutusunu yok say. En fazla iki kısa cümle."
)
ERROR_ALREADY_EXISTS = 183

kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.wintypes.BOOL, ctypes.wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = ctypes.wintypes.HANDLE
kernel32.GetLastError.restype = ctypes.wintypes.DWORD
user32.GetMessageW.argtypes = [ctypes.POINTER(ctypes.wintypes.MSG), ctypes.wintypes.HWND, ctypes.wintypes.UINT, ctypes.wintypes.UINT]
user32.GetMessageW.restype = ctypes.c_int
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostMessageW.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.UINT, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM]
user32.PostMessageW.restype = ctypes.wintypes.BOOL

_mutex = None


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def log(message: str) -> None:
    try:
        with open(os.path.join(app_dir(), "kai.log"), "a", encoding="utf-8") as handle:
            handle.write(time.strftime("%H:%M:%S ") + message + "\n")
    except Exception:
        pass


def _crashed(kind, value, trace) -> None:
    """An error nothing caught still ends up in kai.log, for the Hata raporu button,
    and is kept for the next start, which offers to send it (_offer_crash_report)."""
    import traceback

    text = "".join(traceback.format_exception(kind, value, trace))[-4000:]
    log("ÇÖKME " + text)
    try:
        import json as _json

        with open(v2_file("crash_pending.json"), "w", encoding="utf-8") as handle:
            _json.dump({"at": time.time(), "version": updater.VERSION, "trace": _scrub(text)}, handle)
    except Exception:
        pass


def _scrub(text: str) -> str:
    """Nothing about the user in a report: their name in paths, e-mail addresses."""
    import re

    home = os.path.expanduser("~")
    text = text.replace(home, "~").replace(home.replace("\\", "/"), "~")
    name = os.environ.get("USERNAME") or ""
    if len(name) > 2:
        text = re.sub(re.escape(name), "<user>", text, flags=re.IGNORECASE)
    return re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "<e-posta>", text)


sys.excepthook = _crashed
threading.excepthook = lambda args: _crashed(args.exc_type, args.exc_value, args.exc_traceback)


def message_box(text: str) -> None:
    user32.MessageBoxW(None, text, "Kai", 0x40)


class KaiApp:
    def __init__(self, selftest: bool) -> None:
        self.selftest = selftest
        self.settings = Settings()
        self.mic = Microphone()
        self.island = Island(self.on_message)
        self.island.show_dot = self.settings.show_dot
        self.island.size_percent = self.settings.island_scale
        self.island.media = media.current
        self.island.played = media.played
        self.pointer = Pointer()
        self._media_quiet = 0
        self.song_live = False
        self.hook = AltGrHook(self.island.hwnd, MSG_ALT_DOWN, MSG_ALT_UP, MSG_OTHER, (MSG_DICT_DOWN, MSG_DICT_UP, MSG_ESC))
        self.dictation = Dictation(lambda: self.settings, lambda: self.listening or self.alt_down or self.thinking)
        self.recorder = notes.Recorder(lambda: self.settings)
        self.dictation.on_record = lambda: push_cmd_record()
        self.wake = wake.WakeWord(self._wake_heard, self._wake_request, self._wake_paused, self.settings.ok_kai_sense)
        self.app_proc = None
        self._cmd_stamp = self._cmd_mtime()
        self._status_at = 0.0
        self._status_last = ""
        self._apply_flow()
        self.hook_text = ""
        self.diff_until = 0.0
        self.chat_box: ChatBox | None = None
        self.lol: lol.QueueAccept | None = None
        self._lol_wait = False
        self.permit_points = None
        self.permit_word = ""
        self.code_queue: queue.Queue = queue.Queue()
        self._decision_stamp = self._decision_mtime()
        agents.raw_sink = self._hook_to_v2
        agents.start(self._agent_event)
        self.diffs = DiffWatch(self._code_event)
        self._due: queue.Queue = queue.Queue()
        reminders.start(self._reminder_due)
        kaicalendar.start(lambda: self.settings, self._reminder_due)
        # A reply ready in the Claude desktop app: its pill on the island says so.
        import desktop_chat

        desktop_chat.Watcher(lambda: self.settings.claude_desktop_chat and not self.paused, self._desktop_reply).start()
        # The developer's Kai: ratings and wishes people send land in the Notetaker.
        import feedback

        feedback.start(lambda: self.settings, self._feedback_arrived)
        threading.Thread(target=self._offer_crash_report, daemon=True).start()
        self.diffs.start()
        if not agents.hooks_installed() and agents._python():
            threading.Thread(target=self._install_hooks_quiet, daemon=True).start()
        threading.Thread(target=self._startup_update_check, daemon=True).start()
        if self.settings._new_device:
            self.settings.save()
        self.drop = None
        self.alt_down = False
        self.armed = False
        self.cancelled = False
        self.arm_at: float | None = None
        self.listening = False
        self.thinking = False
        self.drag_hover = False
        self.drop_lock = False
        self.mode = "idle"
        self.hide_at: float | None = None
        self.fake_level = False
        self.listen_started = False
        self.exit_code = 0
        self.answer = ""
        self.heard_text = ""
        self.screen_line = ""
        self.paused = False
        self.hover_at = 0.0
        self.pending_media = False
        self.pending_screen = None
        self.last_answer = ""
        self._media_poll = 0
        self._think_at: float | None = None
        self._mic_broken = False
        self._settings_stamp = 0.0
        self._told_eleven = False
        self.screen = ScreenWatch(self.settings, self._queue_screen, log)
        self.tray = Tray(
            {
                "dynamic": self.toggle_dynamic,
                "dynamic_on": lambda: self.settings.dynamic_island,
                "mode": self.set_mode,
                "mode_is": lambda mode: self.settings.kai_mode == mode,
                "screen": self.post_toggle_screen,
                "screen_on": lambda: self.screen.active,
                "dot": self.toggle_dot,
                "dot_on": lambda: self.settings.show_dot,
                "chat": self.toggle_chat,
                "chat_on": lambda: self.settings.chat,
                "mic": self.toggle_mic,
                "mic_on": lambda: self.settings.mic_always,
                "voice": self.set_voice,
                "voice_is": lambda vid: self.settings.elevenlabs_voice == vid,
                "model": self.set_model,
                "model_is": lambda mid: self.settings.elevenlabs_model == mid,
                "size": self.set_size,
                "size_is": lambda percent: self.settings.island_scale == percent,
                "startup": self.toggle_startup,
                "startup_on": lambda: self.settings.start_with_windows,
                "settings": self.open_app,
                "music": self.post_music,
                "hooks": self.install_hooks,
                "update": self.run_update,
                "update_label": self.update_label,
                "version_label": lambda: t("upd.version", v=updater.VERSION),
                "pause": self.toggle_pause,
                "pause_on": lambda: self.paused,
                "quit": self.post_quit,
            }
        )
        threading.Thread(target=self.tray.run, daemon=True).start()
        try:
            self.drop = attach(self.island.hwnd, self.on_drag_enter, self.on_drag_leave, self.on_files)
            log("dosya bırakma açık")
        except Exception as exc:
            log(f"dosya bırakma kurulamadı: {exc}")
        self.menu_proc = None
        if self.settings.kai_mode == "v2":
            self._start_menu()
        elif self.settings.dynamic_island:
            self.island.wake_idle()
            self.island.greet_ticks = 75
            self.island.looking = True
            self.island.start_timer()
        self._settings_stamp = self._settings_mtime()
        log("kai açıldı")
        # Older Run entries have no --startup; write it the current way.
        if self.settings.start_with_windows and not selftest:
            try:
                set_startup(True)
            except OSError:
                pass
        if not selftest and "--startup" not in sys.argv and self.settings.app_on_launch:
            self.open_app()
        if selftest:
            threading.Thread(target=self._selftest, daemon=True).start()

    def _hook_to_v2(self, payload: dict) -> None:
        # What each coding session did last, for « OK Kai, what are my agents doing? »
        try:
            sid = str(payload.get("session_id") or "")[:40]
            if sid:
                seen = getattr(self, "_sessions", {})
                seen[sid] = {
                    "at": time.time(),
                    "event": str(payload.get("hook_event_name") or ""),
                    "tool": str(payload.get("tool_name") or ""),
                    "where": os.path.basename(str(payload.get("cwd") or "")),
                    "agent": str(payload.get("coucou_agent") or "Claude Code"),
                }
                self._sessions = seen
        except Exception:
            pass
        if self.settings.kai_mode == "v2" and not self.paused:
            push_v2_hook(payload)

    def _offer_crash_report(self) -> None:
        """The last run crashed: ask once whether the report may go to Kai's developer."""
        import json as _json

        import feedback

        path = v2_file("crash_pending.json")
        try:
            with open(path, encoding="utf-8") as handle:
                report = _json.load(handle)
            os.remove(path)
        except (OSError, ValueError):
            return
        trace = str(report.get("trace") or "")
        if not trace:
            return
        time.sleep(12)
        tr = self.settings.language == "tr"
        question = (
            "Kai son çalışmasında bir hatayla karşılaştı.\n\nHata raporunu Kai'nin geliştiricisine gönderelim mi? "
            "Raporda sadece hatanın teknik kaydı ve sürüm numarası olur; adın, dosyaların ya da konuşmaların gönderilmez."
            if tr else
            "Kai ran into an error last time.\n\nSend the error report to Kai's developer? It holds only the technical "
            "record of the error and the version; nothing about you, your files or your conversations."
        )
        # Yes / No, a question icon, on top of other windows.
        if user32.MessageBoxW(None, question, "Kai", 0x4 | 0x20 | 0x40000) != 6:
            log("çökme raporu gönderilmedi (kullanıcı istemedi)")
            return
        error = feedback.send_crash(trace, self.settings.language)
        log(f"çökme raporu {'gönderildi' if error is None else 'gönderilemedi: ' + error}")
        if error is None:
            self.tray.notify("Teşekkürler, rapor gönderildi." if tr else "Thanks, the report was sent.")

    def _feedback_arrived(self, items: list) -> None:
        best = max(int(item.get("stars") or 0) for item in items)
        log(f"değerlendirme geldi: {len(items)}")
        if self.settings.language == "tr":
            self.tray.notify(f"{len(items)} yeni değerlendirme geldi patron (en yüksek {best}★). Not alıcıda duruyor.")
        else:
            self.tray.notify(f"{len(items)} new rating(s), boss (best {best}★). They are in the Notetaker.")

    def _desktop_reply(self) -> None:
        log("Claude Desktop: yanıt hazır")
        if self.settings.kai_mode == "v2":
            tr = self.settings.language == "tr"
            push_v2_hook({
                "hook_event_name": "Stop",
                "coucou_agent": "claude-desktop",
                "session_id": "claude-desktop",
                "last_assistant_message": "Yanıt hazır" if tr else "Reply ready",
            })

    def _agents_now(self) -> str:
        tr = self.settings.language == "tr"
        now = time.time()
        live = [s for s in getattr(self, "_sessions", {}).values() if now - s["at"] < 1800]
        if not live:
            return "Şu an çalışan bir ajan yok." if tr else "No agent is working right now."
        parts = []
        for s in sorted(live, key=lambda x: -x["at"]):
            ago = int((now - s["at"]) // 60)
            done = s["event"] in ("Stop", "SessionEnd")
            where = s["where"] or "?"
            if tr:
                state = "bitirdi" if done else (f"{s['tool']} kullanıyor" if s["tool"] else "çalışıyor")
                parts.append(f"{s['agent']} {where} klasöründe {state}" + (f" ({ago} dk önce)" if ago else ""))
            else:
                state = "finished" if done else (f"is using {s['tool']}" if s["tool"] else "is working")
                parts.append(f"{s['agent']} in {where} {state}" + (f" ({ago} min ago)" if ago else ""))
        return "; ".join(parts[:4]) + "."

    def _stripe_today(self) -> str:
        import extras

        return extras.stripe_today(self.settings.stripe_key, self.settings.language == "tr")

    def _draft_email(self, decision: dict) -> str:
        """Opens a draft; nothing is sent until the user sends it."""
        import extras

        return extras.draft_email(decision, self.settings.language == "tr", self.settings)

    def _decision_mtime(self) -> float:
        try:
            return os.path.getmtime(v2_file("v2_decision.json"))
        except OSError:
            return 0.0

    def _read_decision(self) -> None:
        """Allow or deny pressed on the v2 island's approval card."""
        stamp = self._decision_mtime()
        if stamp == self._decision_stamp:
            return
        self._decision_stamp = stamp
        try:
            with open(v2_file("v2_decision.json"), encoding="utf-8") as handle:
                word = str(json.load(handle).get("word") or "deny")
        except (OSError, ValueError, AttributeError):
            return
        self.permit_points = None
        self.island.permit = False
        agents.answer(word)

    def _settings_mtime(self) -> float:
        try:
            return os.path.getmtime(settings_path())
        except OSError:
            return 0.0

    def _reload_settings(self) -> None:
        """The v2 island saves settings from its own process; pick the change up here."""
        stamp = self._settings_mtime()
        if stamp == self._settings_stamp:
            return
        self._settings_stamp = stamp
        self.settings.load()
        self._mic_broken = False
        self.island.size_percent = self.settings.island_scale
        if not self.settings.mic_always and self.listening and not self.alt_down:
            self._drop_mic()
        self._apply_flow()
        self.tray.refresh()

    def _menu_alive(self) -> bool:
        proc = getattr(self, "menu_proc", None)
        return proc is not None and proc.poll() is None

    def _start_menu(self) -> None:
        """Kai v2: Coucou menu, blue mascot. The first Kai stays hidden."""
        if self.selftest or self._menu_alive():
            return
        try:
            if getattr(sys, "frozen", False):
                cmd = [sys.executable, "--island-menu"]
            else:
                cmd = [sys.executable, os.path.abspath(__file__), "--island-menu"]
            self.menu_proc = subprocess.Popen(cmd)
            self.island.conceal()
            self.island.start_timer()
        except Exception as exc:
            log(f"menü açılmadı: {exc}")
            self.menu_proc = None
            self.island.release()

    def _stop_menu(self) -> None:
        proc = getattr(self, "menu_proc", None)
        self.menu_proc = None
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass

    def set_mode(self, mode: str) -> None:
        mode = "v2" if mode == "v2" else "kai"
        if mode == self.settings.kai_mode:
            self.tray.refresh()
            return
        self.settings.kai_mode = mode
        self.settings.save()
        if mode == "v2":
            self._start_menu()
        else:
            self._stop_menu()
            self.island.release()
            if self.settings.dynamic_island and not self.paused:
                self.island.wake_idle()
                self.island.greet_ticks = 75
                self.island.looking = True
                self.island.start_timer()
        self.tray.refresh()

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        agents.set_paused(self.paused)
        if self.paused:
            self.island.conceal()
        elif self.settings.dynamic_island and self.settings.kai_mode != "v2":
            self.island.wake_idle()
        self.tray.refresh()

    def post_music(self) -> None:
        user32.PostMessageW(self.island.hwnd, MSG_MUSIC, 0, 0)

    def _ensure_chat_box(self) -> None:
        if self.chat_box is None:
            self.chat_box = ChatBox(self._friend_typed)

    def _friend_typed(self, text: str) -> None:
        # Only the League champion prompt uses the text box now.
        if self._lol_wait:
            self._lol_wait = False
            threading.Thread(target=self._lol_pick, args=(text,), daemon=True).start()

    def _start_lol(self) -> None:
        if self.lol:
            self.lol.stop()
        self.lol = lol.QueueAccept(self.pointer, self._lol_found)
        self.lol.start()

    def _lol_found(self) -> None:
        user32.PostMessageW(self.island.hwnd, MSG_LOL, 0, 0)

    def _ask_champion(self) -> None:
        self._lol_wait = True
        self._ensure_chat_box()
        question = t("lol_ask")
        if self.chat_box:
            self.chat_box.push("Kai", question)
        self.island.you = ""
        self.island.kai_line = question
        self.island.typing = False
        self.island.chat = True
        self.island.looking = False
        self.island.rest = True
        self.hide_at = None
        self.island.show("listen", "League")
        speak(question, self.settings, self.tray.notify)

    def _lol_pick(self, text: str) -> None:
        try:
            self.answer = lol.pick(self.pointer, text)
        except Exception as exc:
            self.answer = str(exc) or t("cant_pick")
        self.heard_text = text
        user32.PostMessageW(self.island.hwnd, MSG_ANSWER, 0, 0)

    def _reminder_due(self, item: dict) -> None:
        self._due.put(item)
        user32.PostMessageW(self.island.hwnd, MSG_REMIND, 0, 0)

    def _show_reminder(self) -> None:
        """A reminder came due: on the island, as a Windows notification, and aloud if speaking is on."""
        while True:
            try:
                item = self._due.get_nowait()
            except queue.Empty:
                return
            text = str(item.get("text") or "")
            line = t("rem.fire", text=text) if text else t("rem.fire_plain")
            log(f"hatırlatma {text}")
            self.tray.notify(line)
            if self.settings.kai_mode == "v2":
                push_v2("answer", line, "")
            else:
                self.island.you = ""
                self.island.kai_line = line
                self.island.chat = True
                self.island.rest = True
                self.island.show("listen", "")
                self.hide_at = time.monotonic() + 12
            speak(line, self.settings, self.tray.notify)

    def _code_event(self, kind: str, payload) -> None:
        self.code_queue.put((kind, payload))
        user32.PostMessageW(self.island.hwnd, MSG_CODE, 0, 0)

    def _show_code(self) -> None:
        if self.listening or self.island.permit:
            return
        try:
            while True:
                kind, payload = self.code_queue.get_nowait()
                if kind == "lines" and payload:
                    self.island.push_diff(payload)
                    if self.island.subtitle != "thinking":
                        self.island.subtitle = "thinking"
                    self.diff_until = time.monotonic() + 30
                    self.hide_at = None
                    self.island.chat = False
                    self.island.looking = False
                    self.island.rest = True
                    self.island.show("diff", "thinking")
                elif kind == "thinking":
                    self.island.subtitle = "thinking"
                    self.diff_until = time.monotonic() + 12
                    self.hide_at = None if self.island.diff_rows else time.monotonic() + 12
                    self.island.chat = False
                    self.island.rest = True
                    self.island.show("diff", "thinking")
                elif kind == "done":
                    self.island.subtitle = t("done")
                    self.island.cheer_until = self.island.tick + 50
                    self.diff_until = time.monotonic() + 4.5
                    self.hide_at = self.diff_until
                    self.island.show("diff", t("done"))
                    speak(t("done_spoken"), self.settings, self.tray.notify)
        except queue.Empty:
            return

    def _install_hooks_quiet(self) -> None:
        try:
            agents.install_hooks()
            log("claude kancası kuruldu")
        except Exception as exc:
            log(f"kanca kurulamadı {exc}")

    def _agent_event(self, text: str, permission: bool = False, extra: dict | None = None) -> None:
        extra = extra or {}
        if extra.get("pills") is not None:
            self.island.pills = list(extra["pills"])
            if self.island.looking:
                user32.PostMessageW(self.island.hwnd, MSG_AGENT, 3, 0)
            return
        if extra.get("lines"):
            self.code_queue.put(("lines", extra["lines"]))
            user32.PostMessageW(self.island.hwnd, MSG_CODE, 0, 0)
            return
        if extra.get("done") or text == "isteğiniz tamamlandı":
            self.code_queue.put(("done", None))
            user32.PostMessageW(self.island.hwnd, MSG_CODE, 0, 0)
            return
        if text == "thinking":
            self.code_queue.put(("thinking", None))
            user32.PostMessageW(self.island.hwnd, MSG_CODE, 0, 0)
            return
        self.hook_text = text
        if permission:
            self.permit_points = (extra.get("allow"), extra.get("deny"))
        user32.PostMessageW(self.island.hwnd, MSG_AGENT, 1 if permission else 0, 0)

    # ── Updates ────────────────────────────────────────────────────────────
    def update_label(self) -> str:
        state = updater.status()
        return t("upd.install", v=state["latest"]) if state["available"] else t("upd.check")

    def _startup_update_check(self) -> None:
        """A quiet look after start-up, then a few times a day; news is told once per version.

        The island shows its own card for it (Update now, What's new, Later)."""
        time.sleep(20)
        told = ""
        while True:
            if self.settings.update_checks and updater.due():
                updater.check()
                state = updater.status()
                self.tray.refresh()
                if state["available"] and state["latest"] != told:
                    told = state["latest"]
                    self.tray.notify(t("upd.available", v=state["latest"]))
            time.sleep(3600)

    def run_update(self) -> None:
        threading.Thread(target=self._update_worker, daemon=True).start()

    def _update_worker(self) -> None:
        state = updater.status()
        if not state["available"]:
            # First click checks; a second click, once something is found, installs.
            updater.check()
            state = updater.status()
            self.tray.refresh()
            if state["error"] == "no-repo":
                self.tray.notify(t("upd.norepo"))
            elif state["available"]:
                self.tray.notify(t("upd.available", v=state["latest"]))
            elif state["error"]:
                self.tray.notify(t("upd.failed", err=state["error"]))
            else:
                self.tray.notify(t("upd.latest", v=updater.VERSION))
            return
        self.tray.notify(t("upd.downloading"))
        log(f"güncelleme {updater.VERSION} -> {state['latest']}")
        error = updater.install()
        if error:
            self.tray.notify(t("upd.failed", err=error))

    def install_hooks(self) -> None:
        try:
            self.tray.notify(agents.install_hooks())
        except Exception as exc:
            self.tray.notify(str(exc)[:140])

    def _show_agent(self, permission: bool) -> None:
        text = self.hook_text or "Claude"
        self.island.permit = permission
        self.island.looking = False
        self.island.chat = True if permission else False
        self.island.you = ""
        self.island.kai_line = text[:220] if permission else ""
        self.island.rest = True
        self.fake_level = False
        self.hide_at = time.monotonic() + (100.0 if permission else 5.0)
        self.island.show("listen", text[:160])
        if permission:
            speak(t("permit_ask"), self.settings, self.tray.notify)

    def _grant(self, word: str) -> None:
        points = self.permit_points
        self.permit_points = None
        agents.answer(word)
        self.island.permit = False
        self.island.chat = False
        target = None
        if isinstance(points, tuple) and len(points) == 2:
            target = points[0] if word == "allow" else points[1]
        if target:
            from pointer import glide

            threading.Thread(target=glide, args=(self.pointer, target[0], target[1]), daemon=True).start()
        self.island.show("listen", "Allow" if word == "allow" else "Not allow")
        self.hide_at = time.monotonic() + 2.5

    def _voice_permit(self) -> None:
        word = self.permit_word or "deny"
        self._grant(word)
        speak(t("permit_yes") if word == "allow" else t("permit_no"), self.settings, self.tray.notify)

    def post_quit(self) -> None:
        user32.PostMessageW(self.island.hwnd, MSG_QUIT, 0, 0)

    def toggle_dynamic(self) -> None:
        self.settings.dynamic_island = not self.settings.dynamic_island
        self.settings.save()
        self.tray.refresh()
        user32.PostMessageW(self.island.hwnd, MSG_APPLY_DYNAMIC, 0, 0)

    def _busy(self) -> bool:
        return self.listening or self.thinking

    def _queue_screen(self, line: str) -> None:
        self.screen_line = line
        user32.PostMessageW(self.island.hwnd, MSG_SCREEN, 0, 0)

    def post_toggle_screen(self) -> None:
        user32.PostMessageW(self.island.hwnd, MSG_SCREEN, 1, 0)

    def start_screen(self, show: bool = True) -> str:
        self.screen.stop()
        boxes.marks.stop()
        self.island.watching = True
        self.island.looking = True
        self.island.rest = True
        self.island.start_timer()
        if show:
            live_view.open_view(None, "watch")
        self.tray.refresh()
        log("ekran izleme açık")
        return t("watch_screen")

    def start_camera(self, show: bool = True) -> str:
        self.screen.stop()
        boxes.marks.stop()
        camera_view.stop()
        self.island.watching = True
        self.island.looking = True
        self.island.rest = True
        self.island.start_timer()
        if show:
            live_view.open_view(None, "camera")
        return t("watch_camera")

    def stop_screen(self) -> str:
        self.screen.stop()
        boxes.marks.stop()
        camera_view.stop()
        live_view.close_views()
        self.island.watching = False
        self.island.looking = False
        self.island.start_timer()
        self.tray.refresh()
        log("ekran izleme kapalı")
        return t("watch_stop")

    def _screen_comment(self) -> None:
        line = self.screen_line
        if not line or not self.screen.active or self.listening or self.thinking:
            return
        self.island.you = ""
        self.island.kai_line = line[:300]
        self.island.chat = True
        self.island.start_timer()
        self.hide_at = time.monotonic() + 7.0
        speak(line, self.settings, self.tray.notify)

    def toggle_dot(self) -> None:
        self.settings.show_dot = not self.settings.show_dot
        self.settings.save()
        self.island.show_dot = self.settings.show_dot
        self.tray.refresh()
        self.island.start_timer()
        log(f"nokta {'açık' if self.settings.show_dot else 'kapalı'}")

    def toggle_mic(self) -> None:
        self.settings.mic_always = not self.settings.mic_always
        self._mic_broken = False
        self.settings.save()
        if self.settings.kai_mode == "v2" and self.settings.mic_always:
            self._begin_listen()
            self.island.start_timer()
        elif not self.settings.mic_always:
            self._drop_mic()
        self.tray.refresh()

    def _drop_mic(self) -> None:
        self.listening = False
        self.armed = False
        self.mic.stop()

    def toggle_chat(self) -> None:
        self.settings.chat = not self.settings.chat
        self.settings.save()
        if not self.settings.chat:
            self.island.chat = False
            self.island.you = ""
            self.island.kai_line = ""
        self.tray.refresh()
        self.island.start_timer()
        log(f"yazılı sohbet {'açık' if self.settings.chat else 'kapalı'}")

    def set_voice(self, voice_id: str) -> None:
        self.settings.elevenlabs_voice = voice_id
        self.settings.save()
        self.tray.refresh()
        log("ses değişti")
        self._preview_voice()

    def set_model(self, model: str) -> None:
        self.settings.elevenlabs_model = model
        self.settings.save()
        self.tray.refresh()
        log(f"ses kalitesi {model}")
        self._preview_voice()

    def _preview_voice(self) -> None:
        if not is_free(self.settings.elevenlabs_voice) and not self.settings.elevenlabs_key.strip():
            self.tray.notify(t("need_eleven"))
            return
        speak(t("preview"), self.settings, self.tray.notify, force=True)

    def set_size(self, percent: int) -> None:
        self.settings.island_scale = max(40, min(160, int(percent)))
        self.settings.save()
        self.island.size_percent = self.settings.island_scale
        self.tray.refresh()
        self.island.start_timer()
        log(f"ada boyutu %{self.settings.island_scale}")

    def toggle_startup(self) -> None:
        self.settings.start_with_windows = not self.settings.start_with_windows
        self.settings.save()
        self.tray.refresh()
        log(f"açılış {'açık' if self.settings.start_with_windows else 'kapalı'}")

    def open_api(self) -> None:
        def saved() -> None:
            self.island.size_percent = self.settings.island_scale
            if not self.settings.chat:
                self.island.chat = False
                self.island.you = ""
                self.island.kai_line = ""
            self.island.start_timer()
            self.tray.refresh()
            if self.settings.kai_mode == "v2" and self.settings.mic_always and not self.listening:
                self._begin_listen()
            if not self.settings.mic_always:
                self._drop_mic()
            log(f"ayar kaydedildi {self.settings.provider}")

        open_settings(self.settings, saved)

    def on_drag_enter(self) -> None:
        self.drag_hover = True
        self.drop_lock = False
        if self.listening:
            return
        self.fake_level = True
        self.hide_at = None
        self.island.rest = True
        self.island.show("listen", t("drop"))
        self.island.step(0.3)

    def on_drag_leave(self) -> None:
        if self.drop_lock or self.listening or self.thinking:
            return
        self.drag_hover = False
        self.fake_level = False
        self._collapse()

    def on_files(self, paths: list[str]) -> None:
        self.drop_lock = True
        self.drag_hover = False
        self.fake_level = True
        self.thinking = True
        self.hide_at = None
        self._think_at = time.monotonic()
        self.island.poke()
        name = os.path.basename(paths[0])
        if len(paths) > 1:
            name = f"{name} +{len(paths) - 1}"
        self.island.rest = True
        self.island.show("listen", name)
        self.island.step(self.mic.level)
        self.heard_text = name
        log(f"dosya {name}")
        threading.Thread(target=self._think, args=(list(paths),), daemon=True).start()

    def _think(self, paths: list[str]) -> None:
        try:
            self.answer = ask(self.settings, file_prompt(paths)) or t("empty")
        except Exception as exc:
            self.answer = str(exc) or t("no_link")
            log(f"model hatası {self.answer}")
        user32.PostMessageW(self.island.hwnd, MSG_ANSWER, 0, 0)

    def on_message(self, kind, w_param=0) -> None:
        # Raised inside the window procedure, an error would vanish without a trace.
        try:
            self._on_message(kind, w_param)
        except Exception:
            log(f"mesaj {kind} hatası: " + traceback.format_exc().replace("\n", " | ")[-700:])

    def _on_message(self, kind, w_param=0) -> None:
        if kind == "timer":
            if self._menu_alive():
                self._v2_mic()
                return
            self._tick()
            return
        if kind == "watch":
            self._reload_settings()
            self._read_decision()
            self._read_cmd()
            self._write_status()
            if self._menu_alive():
                return
            self._watch()
            return
        if kind == MSG_DICT_DOWN:
            self.dictation.key_down()
            return
        if kind == MSG_DICT_UP:
            self.dictation.key_up()
            return
        if kind == MSG_ESC:
            self.dictation.escape()
            return
        if kind == MSG_WAKE:
            self._wake_begin()
            return
        if kind == MSG_ALT_DOWN:
            self._alt_down()
        elif kind == MSG_ALT_UP:
            self._alt_up()
        elif kind == MSG_OTHER:
            self._other_key()
        elif kind == MSG_SHOW:
            self._present("ready", t("ready"), 2.2, mic=False)
        elif kind == MSG_MUSIC:
            self._show_media(8.0)
        elif kind == MSG_HEARD:
            self._show_heard()
        elif kind == MSG_APPLY_DYNAMIC:
            self._apply_dynamic()
        elif kind == MSG_ANSWER:
            if getattr(self, "_quiet", False):
                self._quiet = False
                self.thinking = False
                self.fake_level = False
                return
            self._show_answer()
        elif kind == MSG_SCREEN:
            if w_param == 1:
                if self.listening or self.thinking:
                    return
                self.heard_text = ""
                self.pending_screen = "stop" if self.screen.active else "start"
                self.answer = ""
                self._show_answer()
            else:
                self._screen_comment()
        elif kind == MSG_AGENT:
            if w_param == 3:
                self.island.start_timer()
            elif w_param == 2:
                self._voice_permit()
            else:
                self._show_agent(w_param == 1)
        elif kind == MSG_CODE:
            self._show_code()
        elif kind == MSG_LOL:
            self._ask_champion()
        elif kind == MSG_REMIND:
            self._show_reminder()
        elif kind == MSG_QUIT:
            self.request_quit(0)
        elif kind == "click":
            self._media_click(w_param)
        elif kind == "poke":
            self.island.poke()
        elif kind == MSG_SELFTEST_DONE:
            self.request_quit(0 if self.listen_started else 1)
        elif kind == WM_APP + 8:
            self.request_quit(1)

    def _v2_mic(self) -> None:
        """v2 hides the first island, so the listen timer has to run on its own."""
        now = time.monotonic()
        if self.arm_at and self.alt_down and not self.cancelled and now >= self.arm_at:
            self.arm_at = None
            self._begin_listen()
        if self.listening and self.mic.error:
            self.mic.error = None
            self.listening = False
            self._mic_broken = True
            self.mic.stop()
            push_v2("answer", t("mic_failed_boss"), "")
            return
        if self.settings.mic_always and not self.paused and not self.alt_down and not self.thinking:
            if not self.listening:
                # Opened without a note, so it never interrupts the launch greeting.
                if not self._mic_broken:
                    self._begin_listen(quiet=True)
                return
            audio = self.mic.poll_phrase()
            if audio is not None:
                self.thinking = True
                self._think_at = now
                push_v2("think", t("looking"))
                threading.Thread(target=self._heard, args=(audio,), daemon=True).start()
        if self.thinking and self._think_at and now - self._think_at > 22:
            self._think_at = None
            if not self.answer:
                self.answer = t("too_slow")
            self._show_answer()

    def _apply_dynamic(self) -> None:
        if self.settings.dynamic_island:
            if not self.listening and self.island.target < 0.2:
                self.island.wake_idle()
        elif not self.listening and not self.thinking and self.island.target < 0.2:
            self.island.conceal()

    def _alt_down(self) -> None:
        if self.alt_down:
            return
        self.alt_down = True
        self.cancelled = False
        self.arm_at = time.monotonic() + ARM_DELAY
        self.mic.start()
        self.island.start_timer()

    def _alt_up(self) -> None:
        self.alt_down = False
        self.arm_at = None
        if self.armed or self.listening:
            self.armed = False
            self._stop_listen()
        else:
            self.mic.stop()

    def _other_key(self) -> None:
        self.dictation.other_key()
        if not self.alt_down:
            return
        self.cancelled = True
        self.arm_at = None
        if self.armed or self.listening:
            self.armed = False
            self._stop_listen()
        else:
            self.mic.stop()

    def _present(self, mode: str, subtitle: str, seconds: float, mic: bool) -> None:
        if self.listening and not mic:
            self.mic.stop()
            self.listening = False
        self.mode = mode
        self.fake_level = mode == "listen" and not mic
        self.hide_at = time.monotonic() + seconds
        self.island.rest = True
        self.island.show(mode if mode != "ready" else "listen", subtitle)
        if mic:
            self.listening = True
            self.mic.start()

    def _begin_listen(self, quiet: bool = False) -> None:
        if self.listening:
            return
        self.armed = True
        self.listen_started = True
        self.fake_level = False
        self.thinking = False
        self.mode = "listen"
        self.hide_at = None
        self.island.rest = True
        if self.settings.kai_mode == "v2":
            if not quiet:
                push_v2("listen", t("listening"))
        else:
            self.island.show("listen", t("listening"))
        self.listening = True
        self.mic.start()
        self._share_level()
        log("dinleme başladı")

    def _share_level(self) -> None:
        """While Kai listens, the island's mascot hops to the microphone's level."""
        if getattr(self, "_level_thread", None) and self._level_thread.is_alive():
            return

        def run() -> None:
            while self.listening:
                voicelevel.put(self.mic.level)
                time.sleep(0.05)
            voicelevel.put(0.0)

        self._level_thread = threading.Thread(target=run, daemon=True)
        self._level_thread.start()

    # ── Dictation, OK Kai, the notetaker and the app window ─────────────────

    def _apply_flow(self) -> None:
        try:
            self.hook.dictation_key = self.settings.dictation_key if self.settings.dictation else ""
            if not self.settings.ok_kai:
                if self.wake.running():
                    self.wake.stop()
                    log("OK Kai kapalı")
                return
            if self.settings.kai_mode != "v2" or getattr(self, "paused", False):
                return
            if stt.models.path("wake") is None:
                log("OK Kai: model indirilmemiş")
                return
            if not self.wake.running() or self.wake.sense != self.settings.ok_kai_sense:
                self.wake.stop()
                self.wake = wake.WakeWord(self._wake_heard, self._wake_request, self._wake_paused, self.settings.ok_kai_sense)
                self.wake.start()
                log("OK Kai açık")
        except Exception:
            log("OK Kai/dikte ayarı hatası: " + traceback.format_exc().replace("\n", " | ")[-600:])

    def _wake_paused(self) -> bool:
        return self.paused or self.listening or self.alt_down or self.thinking or self.dictation.state != "idle" or self.recorder.active

    def _wake_heard(self) -> None:
        user32.PostMessageW(self.island.hwnd, MSG_WAKE, 0, 0)

    def _wake_begin(self) -> None:
        log("OK Kai duyuldu")
        push_v2("listen", t("listening"))

    def _wake_request(self, audio) -> None:
        """The sentence after « OK Kai »: heard on this computer when the model is there."""
        if audio is None:
            push_v2("answer", "", "")
            return
        self.thinking = True
        self._think_at = time.monotonic()
        push_v2("think", t("looking"))
        engine = "whisper" if stt.ready("whisper") and self.settings.language == "tr" else self.settings.stt_engine
        text, used = stt.transcribe(audio, engine=engine, language=self.settings.language)
        log(f"OK Kai [{used}]: {text}")
        self._heard(audio, text)

    def _cmd_mtime(self) -> float:
        try:
            return os.path.getmtime(v2_file("v2_cmd.json"))
        except OSError:
            return 0.0

    def _read_cmd(self) -> None:
        stamp = self._cmd_mtime()
        if stamp == self._cmd_stamp:
            return
        self._cmd_stamp = stamp
        try:
            with open(v2_file("v2_cmd.json"), encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return
        cmd = str(data.get("cmd") or "")
        if cmd == "record_start":
            if self.recorder.start():
                push_v2("record", "")
                log("kayıt başladı")
        elif cmd == "record_stop":
            if self.recorder.stop():
                push_v2("record-end", "")
                log("kayıt bitti")
        elif cmd == "record_toggle":
            if self.recorder.active:
                self.recorder.stop()
                push_v2("record-end", "")
            elif self.recorder.start():
                push_v2("record", "")
        elif cmd == "paste_last":
            threading.Thread(target=self.dictation.paste_last, daemon=True).start()
        elif cmd == "open_app":
            self.open_app(str(data.get("arg") or ""))
        elif cmd == "settings":
            self._reload_settings()

    def _write_status(self) -> None:
        now = time.monotonic()
        busy = self.recorder.active or self.recorder.processing
        if now - self._status_at < (0.5 if busy else 2.0):
            return
        self._status_at = now
        status = {
            "recorder": self.recorder.status(),
            "dictation": self.dictation.state,
            "ok_kai": self.wake.running(),
            "ok_kai_error": self.wake.error,
        }
        raw = json.dumps(status, ensure_ascii=False)
        if raw == self._status_last:
            return
        self._status_last = raw
        try:
            path = v2_file("v2_status.json")
            with open(path + ".tmp", "w", encoding="utf-8") as handle:
                handle.write(raw)
            os.replace(path + ".tmp", path)
        except OSError:
            pass

    def open_app(self, page: str = "") -> None:
        """The Kai window: Flow (dictation, notes…) and every setting."""
        proc = self.app_proc
        if proc is not None and proc.poll() is None:
            # Already open: the window's own process brings itself forward.
            from settings import push_cmd

            push_cmd("app_front", page)
            return
        try:
            args = ["--app"] + ([f"--page={page}"] if page else [])
            if getattr(sys, "frozen", False):
                cmd = [sys.executable, *args]
            else:
                cmd = [sys.executable, os.path.abspath(__file__), *args]
            self.app_proc = subprocess.Popen(cmd)
        except Exception as exc:
            log(f"uygulama açılmadı: {exc}")

    def _stop_listen(self) -> None:
        audio = None
        if self.listening:
            audio = self.mic.stop_and_take()
            self.listening = False
        log("dinleme bitti")
        if audio is not None:
            self.thinking = True
            self.fake_level = True
            self.hide_at = None
            self._think_at = time.monotonic()
            if self.settings.kai_mode == "v2":
                push_v2("think", t("looking"))
            else:
                self.island.subtitle = t("looking")
                self.island.start_timer()
            threading.Thread(target=self._heard, args=(audio,), daemon=True).start()
            return
        self.answer = t("not_heard")
        self.heard_text = ""
        if self.settings.kai_mode == "v2":
            push_v2("answer", self.answer, "")
        else:
            self.hide_at = time.monotonic() + 0.35
            self.island.subtitle = t("ok")

    def _heard(self, audio, text: str | None = None) -> None:
        try:
            heard = text if text is not None else transcribe(audio)
            log(f"duydum: {heard}")
            self.heard_text = heard or ""
            if heard and self.island.permit:
                word = _permit_word(heard)
                if word:
                    self.permit_word = word
                    user32.PostMessageW(self.island.hwnd, MSG_AGENT, 2, 0)
                    return
            quick = extras.before(self.settings, heard) if heard else None
            if quick:
                self.answer = quick
                user32.PostMessageW(self.island.hwnd, MSG_ANSWER, 0, 0)
                return
            forced = direct_command(heard) if heard else None
            watch = watch_intent(heard) if heard else None
            typed = parse_type(heard) if heard else None
            if heard and (watch == "look" or typed):
                user32.PostMessageW(self.island.hwnd, MSG_HEARD, 0, 0)
            if not heard:
                if self.settings.kai_mode == "v2" and self.settings.mic_always:
                    self._quiet = True
                    self.answer = ""
                else:
                    self.answer = t("not_heard")
            elif watch == "look":
                game = game_name()
                question = t("game", game=game, heard=heard) if game else heard
                self.answer = ask_image(self.settings, LOOK_PROMPT.format(q=question), grab_frame()) or t("saw_nothing")
            elif watch:
                self.pending_screen = watch
                self.answer = ""
            elif typed:
                self.answer = self._do_type(typed)
            else:
                user32.PostMessageW(self.island.hwnd, MSG_HEARD, 0, 0)
                decision = forced or self._decide(heard)
                acted = self._run_decision(decision)
                if acted is None:
                    action = intent(heard)
                    if action and action.get("key"):
                        self.answer = handle(heard) or t("empty")
                    else:
                        heard_ai = heard
                        game = game_name()
                        if game:
                            heard_ai = t("playing_game", game=game, heard=heard)
                        self.answer = converse(self.settings, heard_ai) or t("empty")
                else:
                    self.answer = acted
        except Exception as exc:
            self.answer = str(exc) or t("no_link")
            log(f"ses hatası {self.answer}")
        user32.PostMessageW(self.island.hwnd, MSG_ANSWER, 0, 0)

    def _do_type(self, typed: dict) -> str:
        body = (typed.get("text") or "").strip()
        if typed.get("use_last"):
            body = self.last_answer
        elif typed.get("compose"):
            body = ask(self.settings, body or "kısa bir mesaj yaz", TYPE_PERSONA) or ""
        return type_into(typed["app"], body, bool(typed.get("send")))

    def _decide(self, heard: str) -> dict:
        snap = media.current()
        if snap and (snap.get("title") or snap.get("artist")):
            state = "çalıyor" if snap.get("playing") else "duraklatılmış"
            context = f"Spotify'da şu an {snap.get('artist') or ''} - {snap.get('title') or ''}, durum: {state}."
        else:
            context = "Spotify'da seçili bir parça yok."
        if self.settings.favorite_song:
            context += f" Kayıtlı favori şarkı: {self.settings.favorite_song}."
        try:
            return decide(self.settings, heard, context)
        except Exception as exc:
            log(f"karar hatası {exc}")
            return {"do": "chat"}

    def _run_decision(self, decision: dict) -> str | None:
        op = decision.get("do") or "chat"
        if op == "chat":
            return None
        if op == "sys":
            return control.do_system(decision)
        if op == "mem":
            return control.do_memory(decision)
        if op == "rem":
            return control.do_reminder(decision)
        if op in {"resume", "pause", "next", "prev"}:
            self.pending_media = True
            answer = perform({"op": op, "key": "spotify", "raw": ""})
            if not control.last_ok:
                self.pending_media = False
            return answer
        if op == "play":
            query = decision.get("q") or ""
            if _song_name(query):
                self.pending_media = True
                answer = perform({"op": "play", "key": "spotify", "raw": query})
                if not control.last_ok:
                    self.pending_media = False
                return answer
            self.pending_media = True
            answer = perform({"op": "resume", "key": "spotify", "raw": ""})
            if not control.last_ok:
                self.pending_media = False
            return answer
        if op == "favorite_save":
            snap = media.current()
            if not snap or not (snap.get("title") or "").strip():
                return t("fav_none_playing")
            saved = " - ".join(part for part in (snap.get("artist") or "", snap.get("title") or "") if part)
            self.settings.favorite_song = saved[:120]
            self.settings.save()
            return t("fav_saved", song=self.settings.favorite_song)
        if op == "favorite_play":
            query = self.settings.favorite_song
            if not query:
                return t("fav_missing")
            self.pending_media = True
            answer = perform({"op": "play", "key": "spotify", "raw": query})
            if not control.last_ok:
                self.pending_media = False
            return answer
        if op == "email":
            return self._draft_email(decision)
        if op == "stripe":
            return self._stripe_today()
        if op == "agents":
            return self._agents_now()
        if op == "web":
            import web

            return web.act(decision, self.settings.language == "tr")
        if op == "lol_accept":
            self._start_lol()
            return t("lol_on")
        if op == "lol_stop":
            if self.lol:
                self.lol.stop()
            self._lol_wait = False
            return t("lol_off")
        if op in {"open", "close"}:
            app = decision.get("app") or ""
            if not app:
                return None
            action = intent(f"{app} {'kapat' if op == 'close' else 'aç'}")
            if not action or (op == "close" and not action.get("key")):
                if op != "open":
                    return None
                action = {"op": "open", "key": None, "raw": app}
            elif op == "open" and not action.get("key"):
                action = {"op": "open", "key": None, "raw": app}
            return perform(action)
        if op == "click":
            return pointer_act(self.pointer, decision.get("kind") or "play")
        return None

    def _show_heard(self) -> None:
        if self.pending_media or not self.settings.chat:
            self.island.typing = False
            self.island.subtitle = "Spotify" if self.pending_media else t("looking")
            self.island.start_timer()
            return
        self.island.you = " ".join(self.heard_text.split())[:240]
        self.island.kai_line = ""
        self.island.typing = True
        self.island.chat = True
        self.island.looking = False
        self.island.show("listen", "")

    def _show_media(self, seconds: float = 12.0) -> None:
        self.song_live = True
        self._media_quiet = 0
        self.island.typing = False
        self.island.chat = False
        self.island.you = ""
        self.island.kai_line = ""
        threading.Thread(target=media.refresh, daemon=True).start()
        self._park()

    def _media_click(self, name) -> None:
        if name in {"allow", "deny"}:
            self._grant(name)
            return
        if name == "toggle":
            media.toggle()
        elif name == "next":
            media.next_track()
        elif name == "prev":
            media.previous_track()
        else:
            return
        self.island.start_timer()
        threading.Thread(target=media.refresh, daemon=True).start()

    def _show_answer(self) -> None:
        self.thinking = False
        self.fake_level = False
        self.drop_lock = False
        self._think_at = None
        self.island.typing = False
        self.island.chat = False if self.pending_media else self.island.chat
        if self.pending_screen:
            pending, self.pending_screen = self.pending_screen, None
            if pending == "camera":
                self.answer = self.start_camera()
            elif pending == "start":
                self.answer = self.start_screen()
            elif pending == "stop":
                self.answer = self.stop_screen()
            else:
                self.answer = ask_image(self.settings, LOOK_PROMPT.format(q=self.heard_text or "ekranda ne var"), grab_frame()) or t("saw_nothing")
        text = " ".join(self.answer.split())
        self.last_answer = text
        if self.settings.kai_mode == "v2":
            if self.pending_media:
                self.pending_media = False
                self._show_media(12.0)
            you = " ".join(self.heard_text.split())[:240]
            push_v2("answer", text, you)
            self.hide_at = time.monotonic() + min(18.0, max(6.0, len(text) / 12.0))
            return
        if self.pending_media:
            self.pending_media = False
            self._show_media(12.0)
            speak(text, self.settings, self.tray.notify)
            return
        self.island.rest = True
        if self.settings.chat:
            self.island.you = " ".join(self.heard_text.split())[:240]
            self.island.kai_line = text[:500]
            self.island.chat = True
            self.island.looking = False
            self.island.show("listen", "")
        else:
            self.island.chat = False
            self.island.show("listen", text[:180])
        self.hide_at = time.monotonic() + min(18.0, max(6.0, len(text) / 12.0))
        speak(text, self.settings, self.tray.notify)
        if self.settings.speak and not is_free(self.settings.elevenlabs_voice) and not self.settings.elevenlabs_key.strip() and not self._told_eleven:
            self._told_eleven = True
            self.tray.notify(t("eleven_hint"))

    def _park(self) -> None:
        self.hide_at = None
        self.island.chat = False
        self.island.you = ""
        self.island.kai_line = ""
        self.island.typing = False
        self.island.permit = False
        self.mode = "idle"
        self.island.looking = self.island.watching
        if self.settings.dynamic_island or self.island.watching:
            self.island.rest = True
            self.island.mode = "idle"
            self.island.hide()
        else:
            self.island.conceal()

    def _collapse(self) -> None:
        self.pending_media = False
        self._park()

    def _tick(self) -> None:
        now = time.monotonic()
        if self.arm_at and self.alt_down and not self.cancelled and now >= self.arm_at:
            self.arm_at = None
            self._begin_listen()
        if self.listening and self.mic.error and self.island.subtitle == t("listening"):
            self.island.subtitle = t("no_mic")
            self.tray.notify(t("mic_failed"))
            self.mic.error = None
        if self.hide_at and now >= self.hide_at and not self.alt_down:
            self.hide_at = None
            self._collapse()
        if self.thinking and self._think_at and now - self._think_at > 22:
            self._think_at = None
            if not self.answer:
                self.answer = t("too_slow")
            self._show_answer()
        if self.fake_level:
            level = 0.25 + 0.75 * abs(math.sin(now * 7.0))
        else:
            level = self.mic.level
        if self.island.target == 0.0 and self.island.shown < 0.35:
            self.island.mode = "idle"
        self.island.busy = self.thinking or self.fake_level
        self.island.step(level)
        settled = abs(self.island.shown - self.island.target) < 0.02
        media_live = self.island.mode == "media" and self.island.target > 0
        diff_live = self.island.mode == "diff"
        if settled and not self.listening and not self.fake_level and not self.island.looking and self.island.look_shown < 0.02 and self.arm_at is None and self.hide_at is None and not media_live and not diff_live and not self.island.typing and self.island.greet_ticks <= 0 and self.island.tick >= self.island.dizzy_until and self.island.tick >= self.island.poke_until:
            user32.KillTimer(self.island.hwnd, 1)
        if self.selftest and self.island.last_image is not None and self.island.shown > 0.9:
            path = os.path.join(app_dir(), "preview-listen.png")
            if not os.path.exists(path):
                self.island.last_image.save(path)

    def _watch(self) -> None:
        if self.paused:
            return
        if self.settings.kai_mode == "v2":
            if not self.island.suppressed:
                self.island.conceal()
            return
        island = self.island
        island.raise_top()
        if island.permit or time.monotonic() < self.diff_until:
            island.start_timer()
            return
        if self.song_live:
            self._media_poll += 1
            if self._media_poll % 8 == 0:
                threading.Thread(target=media.refresh, daemon=True).start()
            snap = media.current()
            if snap and snap.get("playing"):
                self._media_quiet = 0
            elif snap:
                self._media_quiet += 1
                if self._media_quiet > 22:
                    self.song_live = False
                    if island.mode == "media":
                        self._park()
        if self.song_live and not self.listening and not self.thinking and not playing_game():
            x, y = cursor_pos()
            left, top, right, bottom = island.hit
            inside = right > left and left <= x <= right and top <= y <= bottom
            if inside and island.mode != "media":
                island.looking = False
                island.rest = True
                self.mode = "media"
                island.show("media", "")
            elif not inside and island.mode == "media":
                self._park()
            elif inside:
                island.start_timer()
            elif island.looking and not island.watching:
                island.looking = False
                island.start_timer()
            return
        if self.song_live and island.mode == "media":
            self._park()
        if island.watching or island.greet_ticks > 0:
            if not island.looking and island.target < 0.15:
                island.looking = True
                island.start_timer()
            return
        blocked = self.listening or self.thinking or island.target > 0.15 or playing_game()
        if blocked:
            if island.looking:
                island.looking = False
                island.start_timer()
            return
        x, y = cursor_pos()
        left, top, right, bottom = island.wake_zone()
        inside = left <= x <= right and top <= y <= bottom
        if inside != island.looking:
            island.looking = inside
            island.start_timer()

    def _selftest(self) -> None:
        time.sleep(0.6)
        vk = 0xA5
        scan = user32.MapVirtualKeyW(vk, 0)
        extended = 0x0001
        user32.keybd_event(vk, scan, extended, 0)
        time.sleep(0.55)
        user32.keybd_event(vk, scan, extended | 0x0002, 0)
        time.sleep(1.0)
        user32.PostMessageW(
            self.island.hwnd,
            MSG_SELFTEST_DONE if self.listen_started else WM_APP + 8,
            0,
            0,
        )

    def request_quit(self, code: int) -> None:
        self.exit_code = code
        user32.PostQuitMessage(0)

    def shutdown(self) -> None:
        log(f"kapanış {self.exit_code}")
        try:
            self.wake.stop()
            if self.recorder.active:
                self.recorder.stop()
        except Exception:
            pass
        app = getattr(self, "app_proc", None)
        if app is not None and app.poll() is None:
            try:
                app.terminate()
            except Exception:
                pass
        proc = getattr(self, "menu_proc", None)
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
        try:
            if self.lol:
                self.lol.stop()
        except Exception:
            pass
        try:
            self.diffs.stop()
        except Exception:
            pass
        try:
            agents.stop()
        except Exception:
            pass
        try:
            self.mic.stop()
        except Exception:
            pass
        try:
            detach(self.island.hwnd)
        except Exception:
            pass
        try:
            self.hook.close()
        except Exception:
            pass
        try:
            self.tray.stop()
        except Exception:
            pass
        try:
            self.pointer.destroy()
        except Exception:
            pass
        try:
            self.island.destroy()
        except Exception:
            pass

    def loop(self) -> None:
        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))


def already_running() -> bool:
    global _mutex
    _mutex = kernel32.CreateMutexW(None, False, "Local\\Kai.DynamicIsland.Single")
    return kernel32.GetLastError() == ERROR_ALREADY_EXISTS


def _sweep_old_unpacks() -> None:
    """Kai up to 2.0.7 was one file that unpacked itself into %TEMP%\\_MEIxxxx on
    every start and left the folder behind when it did not exit cleanly (a few
    hundred MB each). Only Kai's own (they hold island_ui) and only ones older
    than ten minutes are removed: other programs' and running ones stay."""
    import shutil
    import tempfile

    cutoff = time.time() - 600
    root = tempfile.gettempdir()
    try:
        names = [n for n in os.listdir(root) if n.startswith("_MEI")]
    except OSError:
        return
    removed = 0
    for name in names:
        path = os.path.join(root, name)
        try:
            if os.path.isdir(os.path.join(path, "island_ui")) and os.path.getmtime(path) < cutoff:
                shutil.rmtree(path, ignore_errors=True)
                removed += 1
        except OSError:
            continue
    if removed:
        log(f"eski geçici klasör silindi: {removed}")


def main() -> None:
    enable_dpi()
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Kai.DynamicIsland")
    except Exception:
        pass
    if "--island-menu" in sys.argv:
        from menu_window import main as menu_main
        menu_main()
        return
    if "--app" in sys.argv:
        from app_window import main as app_main
        app_main()
        return
    selftest = "--selftest" in sys.argv
    preview = "--preview-idle" in sys.argv
    if preview:
        _preview_idle()
        return
    if not selftest and already_running():
        # Kai is already running: opening it again shows its window.
        from settings import push_cmd

        push_cmd("open_app")
        return
    if not selftest:
        threading.Thread(target=_sweep_old_unpacks, daemon=True).start()
        import welcome

        welcome.run_if_new()
    app = KaiApp(selftest=selftest)
    app.loop()
    app.shutdown()
    if selftest:
        os._exit(app.exit_code)


def _preview_idle() -> None:
    island = Island(lambda *a: None)
    island.rest = True
    island.mode = "idle"
    island.shown = 0.0
    island.target = 0.0
    island.step(0)
    island.last_image.save(os.path.join(app_dir(), "preview-idle.png"))
    island.shown = 1.0
    island.target = 1.0
    island.mode = "listen"
    island.subtitle = "notlar.txt"
    island.smooth = 0.7
    island.step(0.7)
    island.last_image.save(os.path.join(app_dir(), "preview-file.png"))
    try:
        attach(island.hwnd, lambda: None, lambda: None, lambda paths: None)
        log("önizleme drop tamam")
    except Exception as exc:
        log(f"önizleme drop hata {exc}")
    detach(island.hwnd)
    island.destroy()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        text = traceback.format_exc()
        log(text)
        user32.MessageBoxW(None, text[-900:], "Kai hata", 0x10)
        raise
