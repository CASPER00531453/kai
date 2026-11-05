"""Coucou island menu, hosted as Kai. Mascot is blue. Name is Kai.

The window hugs the island. It is not a taskbar app, and it is only
resized when the menu actually changes size. A timer that moved the
window every frame was what stuttered the machine.
"""

from __future__ import annotations

import os
import sys
import time
import ctypes
import ctypes.wintypes  # _fit's RECT; this process no longer loads it by way of main.py

user32 = ctypes.windll.user32
# Handles are 64-bit: without these, ctypes passes them as 32-bit ints and the
# calls fail without a word. (They used to be set by island.py, which this
# process no longer loads.)
user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.SetWindowPos.restype = ctypes.wintypes.BOOL
user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.GetDpiForWindow.argtypes = [ctypes.c_void_p]
user32.GetDpiForWindow.restype = ctypes.c_uint
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW = 0x0040
SW_HIDE = 0

# Coucou's launch greeting is drawn in a 640×150 canvas. The window has to be
# that big from the first frame, or the island springs open inside a sliver
# and all you see is the black line.
_GREET_W = 660
_GREET_H = 170
# The window takes a couple of seconds to appear and the greeting runs five more.
_GREET_HOLD = 8.0
_state = {"hwnd": 0}

_SIZE_JS = """
(() => {
  const el = document.getElementById('island');
  if (!el) return [0, 0];
  const w = Math.ceil(el.offsetWidth);
  const h = Math.ceil(el.offsetHeight);
  return [w, h];
})()
"""


def ui_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(getattr(sys, "_MEIPASS"), "island_ui")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "_coucou_ui", "dist")


def _find_form() -> int:
    """WinForms handle. The layered island is a different class, so it is skipped."""
    from ctypes import wintypes

    found: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _lp):
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        if not cls.value.startswith("WindowsForms10.Window.8"):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        if title.value != "Kai":
            return True
        # The Kai window is called Kai too, and after an install it opens at the
        # same moment: only this process's own form is the island.
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value != os.getpid():
            return True
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        if rect.top > 400:
            return True
        found.append(int(hwnd))
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else 0


def _as_tray(hwnd: int) -> None:
    if not hwnd:
        return
    get_long = user32.GetWindowLongPtrW
    set_long = user32.SetWindowLongPtrW
    get_long.restype = ctypes.c_ssize_t
    set_long.restype = ctypes.c_ssize_t
    get_long.argtypes = [ctypes.c_void_p, ctypes.c_int]
    set_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
    style = get_long(hwnd, GWL_EXSTYLE)
    style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
    set_long(hwnd, GWL_EXSTYLE, style)
    user32.SetWindowPos(
        hwnd, HWND_TOPMOST, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED,
    )


def _fit(width: int, height: int) -> None:
    """width/height are physical pixels, already multiplied by the page scale."""
    hwnd = _state.get("hwnd") or 0
    if not hwnd or width < 8 or height < 8:
        return
    user32.MonitorFromWindow.restype = ctypes.c_void_p
    user32.MonitorFromWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    user32.GetMonitorInfoW.restype = ctypes.c_bool

    class _MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_uint),
            ("rcMonitor", ctypes.wintypes.RECT),
            ("rcWork", ctypes.wintypes.RECT),
            ("dwFlags", ctypes.c_uint),
        ]

    info = _MONITORINFO()
    info.cbSize = ctypes.sizeof(_MONITORINFO)
    monitor = user32.MonitorFromWindow(hwnd, 2)
    if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        mon = info.rcMonitor
    else:
        mon = ctypes.wintypes.RECT(0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
    mon_w = mon.right - mon.left
    mon_h = mon.bottom - mon.top
    width = min(width, mon_w)
    height = min(height, mon_h)
    x = mon.left + max(0, (mon_w - width) // 2)
    y = mon.top + _top_inset(info) if monitor else mon.top
    user32.SetWindowPos(hwnd, HWND_TOPMOST, x, y, width, height, SWP_SHOWWINDOW)


def _top_inset(info) -> int:
    """How far a taskbar docked at the top of this display pushes the island down
    (Coucou #956): read from the work area, so an auto-hidden taskbar moves nothing."""
    inset = info.rcWork.top - info.rcMonitor.top
    return inset if 0 <= inset < 200 else 0


def _force(hwnd: int, css_w: int, css_h: int) -> None:
    if not hwnd:
        return
    dpi = user32.GetDpiForWindow(hwnd) or 96
    scale = max(1.0, dpi / 96.0)
    width = int(css_w * scale)
    height = int(css_h * scale)
    screen_w = user32.GetSystemMetrics(0)
    x = max(0, (screen_w - width) // 2)
    user32.SetWindowPos(hwnd, HWND_TOPMOST, x, 0, width, height, SWP_SHOWWINDOW)


def _handle(window) -> int:
    """The island's window handle: from pywebview's form, or found by its title."""
    form = getattr(window, "native", None)
    if form is not None:
        try:
            return int(form.Handle.ToInt64())
        except Exception:
            pass
    return _find_form()


def _log(message: str) -> None:
    import time

    folder = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    try:
        with open(os.path.join(folder, "kai.log"), "a", encoding="utf-8") as handle:
            handle.write(time.strftime("%H:%M:%S ") + "ada: " + message[:400] + "\n")
    except OSError:
        pass


def _boot(window) -> None:
    import time

    # The form can take a while to exist on a slow start; until it does, nothing can be sized.
    started = time.monotonic()
    for _ in range(400):
        hwnd = _handle(window)
        if hwnd:
            _state["hwnd"] = hwnd
            _as_tray(hwnd)
            break
        time.sleep(0.05)
    else:
        _log("pencere bulunamadı, ada boyutlanamıyor")
        return
    _log(f"pencere {time.monotonic() - started:.1f} sn'de bulundu")
    # A size the page sent before the handle existed was kept: apply it now,
    # then ask the page for its current one, in case it changed since.
    pending = _state.pop("pending", None)
    if pending:
        _state["size"] = pending
        _fit(*pending)
    for _ in range(3):
        time.sleep(1.0)
        try:
            window.evaluate_js("window.__kaiResize && window.__kaiResize()")
        except Exception:
            continue


def _watch_drops(window) -> None:
    """The page cannot see where a dropped file lives; the host can, and tells it."""
    import json

    from webview.dom import DOMEventHandler

    def dropped(event) -> None:
        import time

        from webview.dom import _dnd_state

        files = (event.get("dataTransfer") or {}).get("files") or []
        paths = [item.get("pywebviewFullPath") for item in files if isinstance(item, dict)]
        paths = [path for path in paths if path and os.path.isfile(path)]
        # pywebview pairs a dropped file with its path by comparing names, and that
        # comparison fails for names with ç, ğ, ı, ö, ş, ü. The paths it could not
        # pair are still in its own list, so take them from there.
        for _ in range(10):
            if paths:
                break
            paths = [path for _name, path in _dnd_state["paths"] if os.path.isfile(path)]
            time.sleep(0.05)
        _dnd_state["paths"].clear()
        window.evaluate_js(f"window.__kaiDrop && window.__kaiDrop({json.dumps(paths)})")

    try:
        window.dom.document.events.drop += DOMEventHandler(dropped, True, False)
    except Exception:
        pass


def _exe_of(pid: int) -> str:
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    process = kernel32.OpenProcess(0x1000, False, pid)
    if not process:
        return ""
    try:
        size = ctypes.c_ulong(512)
        buf = ctypes.create_unicode_buffer(512)
        if not kernel32.QueryFullProcessImageNameW(process, 0, buf, ctypes.byref(size)):
            return ""
        return buf.value.rsplit("\\", 1)[-1].lower()
    finally:
        kernel32.CloseHandle(process)


def _host_in_front(event: dict) -> bool:
    """The session's terminal or editor (found by the relay) is the window in front.

    Compared by window, then by program: a terminal with tabs, or an editor whose
    window belongs to another of its processes, still counts as the one in front.
    """
    user32.GetForegroundWindow.restype = ctypes.c_void_p
    front = user32.GetForegroundWindow() or 0
    if not front:
        return False
    if front == int(event.get("host_hwnd") or 0):
        return True
    exe = str(event.get("host_exe") or "")
    if not exe:
        return False
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    user32.GetWindowThreadProcessId(front, ctypes.byref(pid))
    return _exe_of(pid.value) == exe


def _window_of(pid: int) -> int:
    """The main window of a process: visible, top-level, with a title."""
    found: list[int] = []
    PROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.c_void_p, ctypes.c_void_p)
    user32.GetWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    user32.GetWindow.restype = ctypes.c_void_p
    user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
    user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
    user32.IsIconic.argtypes = [ctypes.c_void_p]
    user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
    user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

    def each(hwnd, _):
        if user32.IsWindowVisible(hwnd) and not user32.GetWindow(hwnd, 4) and user32.GetWindowTextLengthW(hwnd) > 0:
            owner = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value == pid:
                found.append(int(hwnd))
                return False
        return True

    user32.EnumWindows(PROC(each), 0)
    return found[0] if found else 0


def _prefs(settings, agent_note: str = "") -> str:
    import json

    import agents
    import other_agents
    import i18n
    import updater
    from voice import MODELS, voices

    update = updater.status()

    key = settings.groq_key if settings.provider == "groq" else settings.api_key
    return json.dumps(
        {
            "hooks": agents.hooks_installed(),
            "version": update["current"],
            "updateLatest": update["latest"] or "",
            "updateAvailable": bool(update["available"]),
            "updateError": update["error"] or "",
            "api": bool(key.strip()),
            "language": settings.language,
            "languages": [[code, item[0]] for code, item in i18n.LANGUAGES.items()],
            "voice": settings.elevenlabs_voice,
            "voices": [[label, voice_id] for label, voice_id in voices()],
            "model": settings.elevenlabs_model,
            "models": [[i18n.t(key), model_id] for key, model_id in MODELS],
            "mic": bool(settings.mic_always),
            "speak": bool(settings.speak),
            "sfx": bool(settings.sfx),
            "sfx_volume": float(settings.sfx_volume),
            "accessory": settings.accessory,
            "city": settings.weather_city,
            "startup": bool(settings.start_with_windows),
            "hover": bool(settings.open_on_hover),
            "outfit": settings.outfit,
            "mascot": settings.mascot,
            "color": settings.mascot_color,
            "agents": other_agents.status(),
            "agentNote": agent_note,
            "updateNotes": update.get("notes") or "",
            "updateUrl": update.get("page") or "",
            "clock": bool(settings.show_clock),
            "alertsAll": bool(settings.alerts_all_pills),
            "feelsPc": bool(settings.feels_pc),
            "planCompact": bool(settings.plan_in_compact),
        },
        ensure_ascii=True,
    )


class IslandApi:
    """Called by the page whenever the island changes size or asks Kai something."""

    def chat(self, query, context=None) -> str:
        """Same brain as the first island. Returned as ASCII JSON so Turkish survives the bridge."""
        import json

        from brain import converse, file_prompt
        from control import carry_out
        from settings import Settings

        text = " ".join(str(query or "").split())
        if isinstance(context, dict) and context.get("kind") == "file" and context.get("path"):
            # A dropped file is read and answered about; its text is never run as a command.
            from brain import analyze_file

            try:
                answer = analyze_file(Settings(), str(context["path"]), text)
            except Exception as exc:
                answer = str(exc)
            return json.dumps(answer, ensure_ascii=True)
        if not text:
            return json.dumps("", ensure_ascii=True)
        try:
            settings = Settings()
            import admin

            # The owner's code: answered here, never sent to the model nor remembered.
            unlocked = admin.handle(settings, text)
            if unlocked:
                return json.dumps(unlocked, ensure_ascii=True)
            import extras

            acted = extras.before(settings, text) or carry_out(settings, text) or extras.typed_request(settings, text)
            answer = acted if acted else converse(settings, text)
        except Exception as exc:
            answer = str(exc)
        return json.dumps(answer, ensure_ascii=True)

    def prefs(self) -> str:
        """Language and voice choices for the in-island settings, read fresh each time."""
        from settings import Settings

        return _prefs(Settings())

    def set_pref(self, key, value) -> str:
        import i18n
        from settings import Settings
        from voice import MODELS, VOICES, speak

        settings = Settings()
        key = str(key)
        if key == "language" and value in i18n.LANGUAGES:
            settings.language = value
        elif key == "voice" and any(value == voice_id for _label, voice_id in VOICES):
            settings.elevenlabs_voice = value
        elif key == "model" and any(value == model_id for _key, model_id in MODELS):
            settings.elevenlabs_model = value
        elif key == "mic":
            settings.mic_always = bool(value)
        elif key == "speak":
            settings.speak = bool(value)
        elif key == "sfx":
            settings.sfx = bool(value)
        elif key == "mascot":
            settings.mascot = str(value)[:20]
        elif key == "color":
            import re

            if re.fullmatch(r"#[0-9a-fA-F]{6}", str(value)):
                settings.mascot_color = str(value).lower()
        elif key == "outfit":
            settings.outfit = str(value)[:20]
        elif key == "hover":
            settings.open_on_hover = bool(value)
        elif key == "accessory":
            settings.accessory = str(value)[:20]
        elif key == "city":
            settings.weather_city = " ".join(str(value).split())[:60]
        elif key == "startup":
            # save() writes or removes Kai's entry under the Windows Run key.
            settings.start_with_windows = bool(value)
        elif key == "sfx_volume":
            try:
                settings.sfx_volume = max(0.0, min(0.2, float(value)))
            except (TypeError, ValueError):
                return _prefs(settings)
        else:
            return _prefs(settings)
        settings.save()
        if key in ("voice", "model"):
            speak(i18n.t("preview"), settings, force=True)
        return _prefs(settings)

    def hooks(self) -> str:
        """Claude Code hook events that arrived since the last call, as a JSON list."""
        import json
        import time

        from settings import v2_file

        if time.monotonic() < _state.get("quiet_until", 0.0):
            return ""
        path = v2_file("v2_hooks.jsonl")
        try:
            size = os.path.getsize(path)
        except OSError:
            return ""
        at = _state.get("hooks_at", 0)
        if size < at:
            at = 0
        if size == at:
            return ""
        with open(path, "rb") as handle:
            handle.seek(at)
            chunk = handle.read()
        done = chunk.rfind(b"\n") + 1
        _state["hooks_at"] = at + done
        events = []
        for row in chunk[:done].splitlines():
            try:
                event = json.loads(row.decode("utf-8"))
            except ValueError:
                continue
            # A turn that ends while its terminal is in front only takes a badge.
            if isinstance(event, dict) and event.get("hook_event_name") in ("Stop", "StopFailure"):
                event["host_in_front"] = _host_in_front(event)
            events.append(event)
        return json.dumps(events, ensure_ascii=True) if events else ""

    def focus_host(self, pid) -> None:
        """"Change plan": the session's terminal or editor comes forward to type the change."""
        try:
            pid = int(pid or 0)
        except (TypeError, ValueError):
            return
        hwnd = _window_of(pid) if pid else 0
        if hwnd:
            user32.ShowWindow(hwnd, 9 if user32.IsIconic(hwnd) else 5)
            user32.SetForegroundWindow(hwnd)

    def services(self) -> str:
        """GitHub, Vercel and Stripe cards, only when something changed."""
        import json

        import services

        version, cards = services.take(_state.get("services_n", 0))
        if cards is None:
            return ""
        _state["services_n"] = version
        return json.dumps(cards, ensure_ascii=True)

    def poll(self) -> str:
        """Everything the page asks for on its timer, in one trip instead of three:
        service cards, hook events and the latest voice note. Empty when none is new."""
        import json

        from settings import settings_path

        out = {}
        # Settings changed in the Kai window (mascot, colour, language): the page reloads them.
        try:
            written = os.path.getmtime(settings_path())
        except OSError:
            written = 0.0
        if _state.setdefault("settings_seen", written) != written:
            _state["settings_seen"] = written
            out["prefs"] = True
            _state.pop("feels", None)
            _state.pop("daily_settings", None)
        # The main process found a newer Kai: the page reads its prefs again for the card.
        try:
            from settings import v2_file

            checked = os.path.getmtime(v2_file("update.json"))
        except OSError:
            checked = 0.0
        if _state.setdefault("update_seen", checked) != checked:
            _state["update_seen"] = checked
            out["prefs"] = True
        if "feels" not in _state:
            from settings import Settings

            current = Settings()
            _state["feels"] = (current.feels_pc, current.language == "tr")
            if not current.feels_pc:
                out["vitals"] = {"busy": 0, "hot": 0, "full": 0, "tired": 0, "asleep": False, "woke": False, "summary": ""}
        # How much of the Claude plan is used: sent when it changes (usage.py counts once a minute).
        try:
            import usage

            snapshot = json.dumps(usage.snapshot(), sort_keys=True)
            if snapshot != _state.get("usage_sent"):
                _state["usage_sent"] = snapshot
                out["usage"] = json.loads(snapshot)
        except Exception:
            pass
        feels, turkish = _state["feels"]
        if feels:
            import vitals

            try:
                mood = vitals.sample(turkish)
            except Exception:
                mood = None
            if mood:
                out["vitals"] = mood
        # The day's summary, at the time set in the settings: looked at twice a minute.
        now = time.monotonic()
        if now - _state.get("daily_at", 0.0) > 30 or _state.get("daily_building"):
            _state["daily_at"] = now
            try:
                import daily
                from settings import Settings

                if "daily_settings" not in _state:
                    _state["daily_settings"] = Settings()
                report = daily.take(_state["daily_settings"])
                _state["daily_building"] = daily._state["building"]
                if report:
                    out["report"] = report
            except Exception as exc:
                _log(f"günün özeti: {exc}")
        for key, read in (("cards", self.services), ("hooks", self.hooks), ("line", self.line)):
            try:
                value = read()
            except Exception:
                value = ""
            if value:
                out[key] = value
        return json.dumps(out, ensure_ascii=True) if out else ""

    def queue(self, op, arg="") -> str:
        """The task queue: list, add a task, remove one by id, or clear it."""
        import json

        import taskqueue

        op = str(op)
        if op == "add":
            rows = taskqueue.add(str(arg))
        elif op == "remove":
            rows = taskqueue.remove(str(arg))
        elif op == "clear":
            rows = taskqueue.clear()
        else:
            rows = taskqueue.items()
        return json.dumps(rows, ensure_ascii=True)

    def refresh_services(self) -> None:
        import services

        services.refresh()

    def update(self, action) -> str:
        """'check' asks GitHub; 'install' downloads the new setup and runs it."""
        import updater
        from settings import Settings

        if action == "check":
            updater.check()
        elif action == "install" and updater.status()["available"]:
            if _state.get("upd", {}).get("phase") not in ("downloading", "installing"):
                import threading

                _state["upd"] = {"phase": "downloading", "fraction": 0.0, "error": ""}
                threading.Thread(target=self._install_update, daemon=True).start()
        elif action == "page":
            page = str(updater.status().get("page") or "")
            if page.startswith("https://github.com/"):
                import webbrowser

                webbrowser.open(page)
        elif action == "dismiss":
            _state["upd"] = {"phase": "idle", "fraction": 0.0, "error": ""}
        return _prefs(Settings())

    @staticmethod
    def _install_update() -> None:
        import updater

        def progress(fraction: float) -> None:
            _state["upd"] = {"phase": "downloading", "fraction": round(fraction, 3), "error": ""}

        error = updater.install(progress)
        # Once the installer runs it closes Kai and starts the new one by itself.
        _state["upd"] = {"phase": "error" if error else "installing", "fraction": 1.0, "error": error or ""}

    def update_phase(self) -> str:
        """Where the download stands, for the island's update card."""
        import json

        return json.dumps(_state.get("upd") or {"phase": "idle", "fraction": 0.0, "error": ""}, ensure_ascii=True)

    def media_do(self, op) -> None:
        import threading

        import services

        # Finding a song in Spotify takes seconds; the island must not wait for it.
        threading.Thread(target=services.media_do, args=(str(op),), daemon=True).start()

    def launch_game(self, app_id) -> None:
        import services

        services.launch_game(str(app_id))

    def open_url(self, url) -> None:
        import webbrowser

        url = str(url or "")
        if url.startswith("https://"):
            webbrowser.open(url)

    def log(self, message) -> None:
        """Errors from the page, so a broken event leaves a trace in kai.log."""
        import time

        folder = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
        try:
            with open(os.path.join(folder, "kai.log"), "a", encoding="utf-8") as handle:
                handle.write(time.strftime("%H:%M:%S ") + "ada: " + str(message)[:400] + "\n")
        except OSError:
            pass

    def decide(self, word, request_id="") -> None:
        from settings import push_v2_decision

        push_v2_decision(str(word), str(request_id or ""))

    def agent_set(self, agent, on) -> str:
        """Connect or disconnect another coding agent. Only ever called from a click."""
        import other_agents
        from settings import Settings

        return _prefs(Settings(), other_agents.set_installed(str(agent), bool(on)))

    def snip(self) -> None:
        """Pick a part of the screen; it lands on the island like a dropped picture."""
        _snip(_state.get("window"))

    def settings_window(self) -> None:
        """Keys, provider and the rest live in the Kai window."""
        from settings import push_cmd

        push_cmd("open_app", "general")

    def record(self) -> None:
        """The island's record button: starts or stops the notetaker."""
        from settings import push_cmd

        push_cmd("record_toggle")

    def level(self) -> float:
        """The microphone's level while Kai listens, for the mascot's hop."""
        import voicelevel

        return round(voicelevel.get(), 3)

    def line(self) -> str:
        """AltGr notes for the v2 island. Empty once the page has seen the latest one."""
        import json

        from settings import settings_path

        path = os.path.join(os.path.dirname(settings_path()), "v2_line.json")
        try:
            # Asked several times a second: an unchanged file is not read again.
            written = os.path.getmtime(path)
            if written == _state.get("line_seen"):
                return ""
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return ""
        stamp = data.get("n")
        if stamp == _state.get("line_n"):
            _state["line_seen"] = written
            return ""
        import time

        # A note that lands during the launch greeting waits for it to finish.
        if time.monotonic() < _state.get("quiet_until", 0.0):
            return ""
        _state["line_n"] = stamp
        return json.dumps(
            {"kind": data.get("kind") or "", "text": data.get("text") or "", "you": data.get("you") or ""},
            ensure_ascii=True,
        )

    def island(self, width, height) -> None:
        hwnd = _state.get("hwnd") or 0
        if not hwnd:
            # Too early: _boot applies it once the window handle exists.
            try:
                _state["pending"] = (int(float(width)), int(float(height)))
            except (TypeError, ValueError):
                pass
            return
        try:
            w = int(float(width))
            h = int(float(height))
        except (TypeError, ValueError):
            return
        if w < 8 or h < 8:
            if _state.get("size") != (0, 0):
                user32.ShowWindow(hwnd, SW_HIDE)
                _state["size"] = (0, 0)
            return
        if (w, h) == _state.get("size"):
            return
        _state["size"] = (w, h)
        _fit(w, h)


def _last_line_stamp():
    """Stamp of the note left by the previous run, so it is not replayed over the greeting."""
    import json

    from settings import settings_path

    path = os.path.join(os.path.dirname(settings_path()), "v2_line.json")
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle).get("n")
    except (OSError, ValueError, AttributeError):
        return None


TRANSLATE_PROMPT = {
    "tr": "Bu görseldeki bütün yazıları Türkçeye çevir. Sadece çeviriyi yaz, satır düzenini koru. Yazı zaten Türkçeyse İngilizceye çevir.",
    "en": "Translate all the text in this picture into English. Write only the translation and keep the line breaks. If it is already English, translate it into Turkish.",
}


def _snip(window, translate: bool = False) -> None:
    """Runs the screen picker on a thread of its own and hands the picture to the page.

    With `translate`, the picture's text is translated (Alt+Shift+T) and the
    translation lands in the chat, where follow-up questions about it work.
    """
    import json
    import threading

    def work() -> None:
        import snip
        from settings import Settings

        settings = Settings()  # the picker's hint follows the chosen language
        path = snip.select()
        if not path or window is None:
            return
        if not translate:
            window.evaluate_js(f"window.__kaiSnip && window.__kaiSnip({json.dumps(path)})")
            return
        window.evaluate_js(f"window.__kaiTranslate && window.__kaiTranslate({json.dumps(path)}, null)")
        try:
            from brain import analyze_file

            text = analyze_file(settings, path, TRANSLATE_PROMPT["tr" if settings.language == "tr" else "en"])
        except Exception as exc:
            text = str(exc)[:300]
        window.evaluate_js(f"window.__kaiTranslate && window.__kaiTranslate({json.dumps(path)}, {json.dumps(text, ensure_ascii=True)})")

    threading.Thread(target=work, daemon=True).start()


def main() -> None:
    # Sound effects have to play for events too, not only after a click.
    os.environ.setdefault("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--autoplay-policy=no-user-gesture-required")
    import webview

    folder = ui_dir()
    page = os.path.join(folder, "index.html")
    if not os.path.isfile(page):
        return
    _state["line_n"] = _last_line_stamp()
    import time

    _state["quiet_until"] = time.monotonic() + _GREET_HOLD
    try:
        from settings import v2_file

        _state["hooks_at"] = os.path.getsize(v2_file("v2_hooks.jsonl"))
    except OSError:
        _state["hooks_at"] = 0
    width, height = _GREET_W, _GREET_H
    screen_w = user32.GetSystemMetrics(0)
    window = webview.create_window(
        "Kai",
        page,
        x=max(0, (screen_w - width) // 2),
        y=0,
        width=width,
        height=height,
        frameless=True,
        transparent=False,
        on_top=True,
        easy_drag=False,
        background_color="#000000",
        min_size=(48, 16),
        js_api=IslandApi(),
    )
    _state["window"] = window
    import threading
    threading.Thread(target=_boot, args=(window,), daemon=True).start()
    window.events.loaded += lambda: _watch_drops(window)
    import snip

    snip.watch_hotkey(lambda: _snip(window))
    snip.watch_hotkey(lambda: _snip(window, translate=True), "T", snip.TRANSLATE_ID)
    import services

    services.start()

    def look_for_update() -> None:
        import time

        import updater

        time.sleep(15)
        updater.check()

    threading.Thread(target=look_for_update, daemon=True).start()
    webview.start(private_mode=True)


if __name__ == "__main__":
    main()
