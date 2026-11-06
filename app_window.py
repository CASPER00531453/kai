"""The Kai window: Flow (dictation, notes, statistics, dictionary, snippets,
styles) and every setting of the island, in one place.

It is a taskbar app, opened when Kai is started by hand (not when it starts
with Windows), from the tray, or by starting Kai again while it runs. It runs
in a process of its own; the main process does the listening and recording
and is asked through settings.push_cmd.
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
import threading
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
# 64-bit window handles; this process does not load the modules that used to set these.
user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
TITLE = "Kai"
_state: dict = {}

SECRETS = ("api_key", "groq_key", "elevenlabs_key", "github_token", "vercel_token", "stripe_key", "mail_password", "calendar_ics")
TEXTS = ("mail_address", "mail_server")
CHOICES = {
    "phone_route": ("lan", "tailscale", "cloudflare"),
    "stt_engine": ("online", "whisper", "parakeet"),
    "ok_kai_sense": ("low", "mid", "high"),
}
FLAGS = ("dictation", "ok_kai", "app_on_launch", "show_clock", "alerts_all_pills", "feels_pc", "claude_desktop_chat", "update_checks", "summary_enabled", "mute_others", "plan_in_compact", "phone_link", "phone_answers", "phone_view")


def _settings():
    from settings import Settings

    return Settings()


def _all() -> dict:
    """Everything the window shows, read fresh."""
    import models
    import other_agents
    import updater
    from menu_window import _prefs
    from settings import PROVIDERS, read_status

    s = _settings()
    island = json.loads(_prefs(s))
    upd = updater.status()
    return {
        "island": island,
        "flow": {
            "dictation": s.dictation,
            "dictation_key": s.dictation_key,
            "stt_engine": s.stt_engine,
            "ok_kai": s.ok_kai,
            "ok_kai_sense": s.ok_kai_sense,
            "app_on_launch": s.app_on_launch,
            "tour_done": s.tour_done,
            "show_clock": s.show_clock,
            "alerts_all_pills": s.alerts_all_pills,
            "feels_pc": s.feels_pc,
            "claude_desktop_chat": s.claude_desktop_chat,
            "update_checks": s.update_checks,
            "summary_enabled": s.summary_enabled,
            "summary_time": s.summary_time,
            "mute_others": s.mute_others,
            "plan_in_compact": s.plan_in_compact,
            "phone_link": s.phone_link,
            "phone_answers": s.phone_answers,
            "phone_view": s.phone_view,
            "phone_route": s.phone_route,
            "mail_address": s.mail_address,
            "mail_server": s.mail_server,
        },
        "brain": {
            "provider": s.provider,
            "providers": [[k, v[0]] for k, v in PROVIDERS.items()],
            "api_url": s.api_url,
            "api_model": s.api_model if s.provider != "groq" else s.groq_model,
            "keys": {k: bool(getattr(s, k, "")) for k in SECRETS},
        },
        "models": models.status(),
        "agents": other_agents.status(),
        "status": read_status(),
        "version": upd.get("current") or "",
        "update": upd,
        "language": s.language,
    }


class AppApi:
    def state(self) -> str:
        return json.dumps(_all(), ensure_ascii=True)

    def status(self) -> str:
        """Recording, dictation and OK Kai, as the main process last reported them."""
        import models
        from settings import read_status

        return json.dumps({"status": read_status(), "models": models.status()}, ensure_ascii=True)

    def set(self, key, value) -> str:
        from settings import push_cmd

        key = str(key)
        s = _settings()
        if key in FLAGS:
            setattr(s, key, bool(value))
        elif key in CHOICES and value in CHOICES[key]:
            setattr(s, key, value)
        elif key == "provider":
            from settings import PROVIDERS

            if value in PROVIDERS:
                s.provider = value
        elif key == "api_model":
            if s.provider == "groq":
                s.groq_model = str(value)[:120]
            else:
                s.api_model = str(value)[:120]
        elif key == "api_url":
            s.api_url = str(value)[:300]
        elif key in TEXTS:
            setattr(s, key, " ".join(str(value or "").split())[:200])
        elif key == "tour_done":
            s.tour_done = True
        elif key == "dictation_key":
            from hook import parse_keys

            if parse_keys(str(value)):
                s.dictation_key = str(value)
        elif key == "summary_time":
            from settings import clock_time

            s.summary_time = clock_time(value, s.summary_time)
        else:
            # The island's own settings (language, mascot, colour…) go through its API.
            from menu_window import IslandApi

            IslandApi().set_pref(key, value)
            push_cmd("settings")
            return self.state()
        s.save()
        push_cmd("settings")
        return self.state()

    def secret(self, key, value) -> str:
        """A key is written, never read back: the window only learns whether one is saved."""
        if key in SECRETS:
            s = _settings()
            setattr(s, key, str(value or "").strip())
            s.save()
        return self.state()

    def check_key(self) -> str:
        try:
            from welcome import check_key

            s = _settings()
            return json.dumps(check_key(s.provider, s.groq_key if s.provider == "groq" else s.api_key), ensure_ascii=True)
        except Exception:
            return json.dumps("unknown", ensure_ascii=True)

    def phone(self, action="status", url="", access="") -> str:
        """Kai window › Phone: the link's state, a new pairing code, or unpairing."""
        import phone_link

        action = str(action)
        out = {}
        if action == "pair":
            out = phone_link.pair_again()
            self.log("telefon: yeni eşleştirme kodu")
        elif action == "unpair":
            phone_link.unpair()
            self.log("telefon: eşleşme kaldırıldı")
        elif action == "code":
            out = phone_link.pairing()
        elif action == "relay":
            # The relay's address and access key, pasted in the Kai window (or set by server/relay/deploy.ps1).
            import relay_link

            try:
                relay_link.save_relay(str(url).strip(), str(access).strip())
                self.log("telefon: aracı sunucu kaydedildi")
            except ValueError:
                out = {"error": "relay"}
        out.update(phone_link.status())
        return json.dumps(out, ensure_ascii=True)

    def list_models(self) -> str:
        """The models the saved key can use, for the model field's suggestions."""
        try:
            from welcome import list_models

            s = _settings()
            key = s.groq_key if s.provider == "groq" else s.api_key
            return json.dumps(list_models(s.provider, key, s.api_url), ensure_ascii=True)
        except Exception:
            return json.dumps([], ensure_ascii=True)

    def feedback(self, stars, text) -> str:
        """Settings → Rating & wishes: sends the stars and the wish."""
        import feedback

        error = feedback.send(stars, text, _settings().language)
        return json.dumps({"ok": error is None, "error": error or ""}, ensure_ascii=True)

    def feedback_inbox(self, fetch=False) -> str:
        """The developer's Kai: ratings received, after a fresh look at the server if asked."""
        import feedback

        current = _settings()
        # Only for Kai's owner, unlocked with the admin code in the chat (admin.py).
        if not current.admin:
            return json.dumps({"enabled": False, "items": [], "error": ""}, ensure_ascii=True)
        key = (current.feedback_key or "").strip()
        self.log(f"gelen kutusu: {'anahtar var' if key else 'anahtar yok'}{', sunucuya bakılıyor' if fetch else ''}")
        if not key:
            import settings as settings_module

            if settings_module.UNSEAL_ERROR:
                self.log(f"gelen kutusu anahtarı okunamadı: {settings_module.UNSEAL_ERROR}")
            # Open all the same: what already came in is shown, and why no more can.
            return json.dumps({"enabled": True, "items": feedback.inbox(), "error": "nokey"}, ensure_ascii=True)
        error = ""
        if fetch:
            try:
                feedback.collect(key)
            except Exception as exc:
                error = type(exc).__name__
        return json.dumps({"enabled": True, "items": feedback.inbox(), "error": error}, ensure_ascii=True)

    def open_license(self) -> None:
        """Kai's license (installed next to Kai.exe as LICENSE.txt), in the text editor."""
        if getattr(sys, "frozen", False):
            path = os.path.join(os.path.dirname(sys.executable), "LICENSE.txt")
        else:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "LICENSE")
        if os.path.isfile(path):
            os.startfile(path)

    def feedback_delete(self, note_id) -> str:
        """Removes received ratings from this Kai: one by its id, or all of them with "all"."""
        import feedback
        import notes

        wanted = str(note_id or "")
        for item in feedback.inbox():
            if wanted == "all" or item["id"] == wanted:
                notes.delete(item["id"])
        return self.feedback_inbox(False)

    def mail_test(self) -> str:
        """Sends one short email to the user's own address, on their click."""
        import extras

        s = _settings()
        if not extras.mail_ready(s):
            return json.dumps({"ok": False, "text": "Önce adresi ve uygulama şifresini kaydet."}, ensure_ascii=True)
        try:
            extras.send_mail(s, s.mail_address, "Kai deneme", "Merhaba, bu Kai'den bir deneme e-postası. Gelmişse her şey yolunda.")
        except RuntimeError as exc:
            return json.dumps({"ok": False, "text": str(exc)}, ensure_ascii=True)
        return json.dumps({"ok": True, "text": f"Deneme e-postası {s.mail_address} adresine gitti."}, ensure_ascii=True)

    def calendar_test(self) -> str:
        import kaicalendar

        return json.dumps(kaicalendar.describe_day(_settings(), 0), ensure_ascii=True)

    def report(self, note) -> str:
        """Kai's logs in a zip on the Desktop and a filled-in GitHub issue to attach it to."""
        import report

        return json.dumps(report.make(str(note or "")[:2000]), ensure_ascii=True)

    # ── Models ──────────────────────────────────────────────────────────────

    def model_download(self, model) -> str:
        import models

        models.download(str(model))
        return self.status()

    def model_remove(self, model) -> str:
        import models

        models.remove(str(model))
        return self.status()

    # ── Flow data ───────────────────────────────────────────────────────────

    def flow_get(self) -> str:
        import flow

        return json.dumps(
            {
                "dictionary": flow.dictionary(),
                "snippets": flow.snippets(),
                "styles": flow.styles(),
                "settings": flow.flow_settings(),
                "stats": flow.stats(),
            },
            ensure_ascii=True,
        )

    def flow_set(self, what, data) -> str:
        import flow

        what = str(what)
        if what == "dictionary":
            flow.set_dictionary(data)
        elif what == "snippets":
            flow.set_snippets(data)
        elif what == "styles":
            flow.set_styles(data)
        elif what == "settings":
            flow.set_flow_settings(data)
        elif what == "clear_history":
            flow.clear_history()
        return self.flow_get()

    def paste_last(self) -> None:
        from settings import push_cmd

        push_cmd("paste_last")

    def try_style(self, text, style) -> str:
        import flow

        return json.dumps(flow.clean_up(str(text)[:2000], str(style)), ensure_ascii=True)

    # ── Notes ───────────────────────────────────────────────────────────────

    def record(self, on) -> str:
        from settings import push_cmd

        push_cmd("record_start" if on else "record_stop")
        time.sleep(0.6)
        return self.status()

    def notes(self) -> str:
        import notes

        return json.dumps(notes.listing(), ensure_ascii=True)

    def note(self, note_id) -> str:
        import notes

        return json.dumps(notes.load(str(note_id)), ensure_ascii=True)

    def note_rename(self, note_id, number, name) -> str:
        import notes

        return json.dumps(notes.rename_speaker(str(note_id), str(number), str(name)), ensure_ascii=True)

    def note_delete(self, note_id) -> str:
        import notes

        notes.delete(str(note_id))
        return self.notes()

    def note_markdown(self, note_id) -> str:
        import notes

        note = notes.load(str(note_id))
        return json.dumps(notes.markdown(note, _settings().language == "tr") if note else "", ensure_ascii=True)

    def note_export(self, note_id) -> str:
        """Saves the note as a Markdown file where the user picks."""
        import webview

        import notes

        note = notes.load(str(note_id))
        window = _state.get("window")
        if not note or window is None:
            return json.dumps("", ensure_ascii=True)
        name = "".join(c for c in (note.get("title") or note["id"]) if c.isalnum() or c in " -_")[:60] or note["id"]
        target = window.create_file_dialog(webview.SAVE_DIALOG, save_filename=f"{name}.md", file_types=("Markdown (*.md)",))
        if not target:
            return json.dumps("", ensure_ascii=True)
        path = target if isinstance(target, str) else target[0]
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(notes.markdown(note, _settings().language == "tr"))
        return json.dumps(path, ensure_ascii=True)

    # ── Agents, update, links ───────────────────────────────────────────────

    def agent_set(self, agent, on) -> str:
        import other_agents

        other_agents.set_installed(str(agent), bool(on))
        return self.state()

    def update(self, action) -> str:
        import updater

        if action == "check":
            updater.check()
        elif action == "install" and updater.status()["available"]:
            updater.install()
        return self.state()

    def open_url(self, url) -> None:
        import webbrowser

        url = str(url or "")
        if url.startswith("https://"):
            webbrowser.open(url)

    def open_folder(self, which) -> None:
        import flow
        import notes

        folder = notes.notes_dir() if which == "notes" else flow.folder()
        os.startfile(folder)

    def log(self, message) -> None:
        folder = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
        try:
            with open(os.path.join(folder, "kai.log"), "a", encoding="utf-8") as handle:
                handle.write(time.strftime("%H:%M:%S ") + "uygulama: " + str(message)[:400] + "\n")
        except OSError:
            pass


def _hwnd() -> int:
    # The island's window is called Kai too: this one is found by its own handle.
    window = _state.get("window")
    try:
        return int(window.native.Handle.ToInt64())
    except Exception:
        return 0


def _rect() -> str:
    from ctypes import wintypes

    r = wintypes.RECT()
    user32.GetWindowRect(_hwnd(), ctypes.byref(r))
    return f"{r.right - r.left}x{r.bottom - r.top}"


def _set_icon() -> None:
    """Kai's icon in the title bar and on the taskbar, not Python's."""
    hwnd = _hwnd()
    if not hwnd:
        return
    user32.LoadImageW.restype = ctypes.c_void_p
    user32.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    ctypes.windll.shell32.ExtractIconW.restype = ctypes.c_void_p
    ctypes.windll.shell32.ExtractIconW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint]
    user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p]
    if getattr(sys, "frozen", False):
        icon = ctypes.windll.shell32.ExtractIconW(None, sys.executable, 0)
    else:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kai.ico")
        icon = user32.LoadImageW(None, path, 1, 0, 0, 0x0010 | 0x0040)  # IMAGE_ICON, LR_LOADFROMFILE | LR_DEFAULTSIZE
    if icon:
        user32.SendMessageW(hwnd, 0x0080, 0, icon)  # WM_SETICON, small
        user32.SendMessageW(hwnd, 0x0080, 1, icon)  # big


def _front(page: str = "") -> None:
    window = _state.get("window")
    if window is None:
        return
    try:
        window.restore()
        window.show()
    except Exception:
        pass
    hwnd = _hwnd()
    if hwnd:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
    if page:
        window.evaluate_js(f"window.__kaiPage && window.__kaiPage({json.dumps(page)})")


def _watch_cmds() -> None:
    """The main process asks this window to come forward when Kai is opened again."""
    from settings import v2_file

    path = v2_file("v2_cmd.json")
    try:
        seen = os.path.getmtime(path)
    except OSError:
        seen = 0.0
    while True:
        time.sleep(0.5)
        try:
            stamp = os.path.getmtime(path)
        except OSError:
            continue
        if stamp == seen:
            continue
        seen = stamp
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        if data.get("cmd") == "app_front":
            _front(str(data.get("arg") or ""))


def main() -> None:
    os.environ.setdefault("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--autoplay-policy=no-user-gesture-required")
    mutex = kernel32.CreateMutexW(None, False, "Local\\Kai.App.Single")
    if kernel32.GetLastError() == 183:
        from settings import push_cmd

        push_cmd("app_front")
        return
    _state["mutex"] = mutex
    import webview

    from menu_window import ui_dir

    page = os.path.join(ui_dir(), "app.html")
    if not os.path.isfile(page):
        return
    start = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--page=")), "")
    url = page
    width, height = 1120, 760
    screen_w, screen_h = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    window = webview.create_window(
        TITLE,
        url,
        width=width,
        height=height,
        x=max(0, (screen_w - width) // 2),
        y=max(0, (screen_h - height) // 2),
        min_size=(860, 560),
        background_color="#05060a",
        js_api=AppApi(),
    )
    _state["window"] = window
    window.events.shown += _set_icon
    window.events.shown += lambda: AppApi().log(f"açıldı, pencere {_rect()}")
    if start:
        # The page to open on: asked for once the page is there to take it.
        window.events.loaded += lambda: (time.sleep(0.4), window.evaluate_js(f"window.__kaiPage && window.__kaiPage({json.dumps(start)})"))
    threading.Thread(target=_watch_cmds, daemon=True).start()
    storage = os.path.join(os.environ.get("LOCALAPPDATA") or "", "Kai", "webview-app")
    _fresh_cache(storage, page)
    webview.start(private_mode=False, storage_path=storage)


def _fresh_cache(storage: str, page: str) -> None:
    """A new Kai drops the window's HTTP cache, or it kept showing the last version's page.

    The profile stays (it is what keeps localStorage); only its caches go, once per build.
    """
    import shutil

    try:
        stamp = str(int(os.path.getmtime(page)))
    except OSError:
        return
    mark = os.path.join(storage, "ui-stamp.txt")
    try:
        with open(mark, encoding="utf-8") as handle:
            if handle.read().strip() == stamp:
                return
    except OSError:
        pass
    profile = os.path.join(storage, "EBWebView", "Default")
    for name in ("Cache", "Code Cache", "GPUCache", "Service Worker"):
        shutil.rmtree(os.path.join(profile, name), ignore_errors=True)
    try:
        os.makedirs(storage, exist_ok=True)
        with open(mark, "w", encoding="utf-8") as handle:
            handle.write(stamp)
    except OSError:
        pass
