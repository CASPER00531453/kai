"""Kai settings and the Windows startup entry."""

from __future__ import annotations

import json
import os
import sys
import uuid
import winreg

import i18n

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "Kai"

# id -> (label, url, default model, wire)
PROVIDERS = {
    "groq": ("Groq", "https://api.groq.com/openai/v1", "qwen/qwen3.8-27b", "openai"),
    "openai": ("OpenAI", "https://api.openai.com/v1", "gpt-4o-mini", "openai"),
    "anthropic": ("Anthropic", "https://api.anthropic.com/v1", "claude-haiku-4-5", "anthropic"),
    "gemini": ("Gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash", "openai"),
    "mistral": ("Mistral", "https://api.mistral.ai/v1", "mistral-small-latest", "openai"),
    "deepseek": ("DeepSeek", "https://api.deepseek.com", "deepseek-chat", "openai"),
    "xai": ("xAI", "https://api.x.ai/v1", "grok-3", "openai"),
    "openrouter": ("OpenRouter", "https://openrouter.ai/api/v1", "openai/gpt-4o-mini", "openai"),
    "custom": ("Özel adres", "", "", "openai"),
}


def settings_path() -> str:
    root = os.environ.get("APPDATA") or os.path.expanduser("~")
    folder = os.path.join(root, "Kai")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "settings.json")


def launch_command() -> str:
    # --startup: started with Windows, so the app window stays shut.
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --startup'
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), "main.py"))
    return f'"{sys.executable}" "{script}" --startup'


def startup_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, RUN_NAME)
            return bool(value)
    except OSError:
        return False


def set_startup(enabled: bool) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, launch_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_NAME)
            except OSError:
                pass


def _seal(secret: str) -> str:
    """The mail password is kept encrypted for this Windows user (DPAPI), not as plain text."""
    if not secret:
        return ""
    try:
        import base64

        import win32crypt

        blob = win32crypt.CryptProtectData(secret.encode("utf-8"), "Kai", None, None, None, 0)
        return "dpapi:" + base64.b64encode(blob).decode("ascii")
    except Exception:
        return ""


def _unseal(stored: str) -> str:
    if not stored.startswith("dpapi:"):
        return ""
    try:
        import base64

        import win32crypt

        return win32crypt.CryptUnprotectData(base64.b64decode(stored[6:]), None, None, None, 0)[1].decode("utf-8")
    except Exception as exc:
        global UNSEAL_ERROR
        UNSEAL_ERROR = f"{type(exc).__name__}: {exc}"[:200]
        return ""


# Why the last sealed value could not be read, for the logs.
UNSEAL_ERROR = ""


class Settings:
    def __init__(self) -> None:
        self.dynamic_island = True
        self.show_dot = True
        self.chat = True
        self.start_with_windows = False
        self.provider = "groq"
        self.api_url = "https://api.openai.com/v1"
        self.api_key = ""
        self.api_model = "gpt-4o-mini"
        self.groq_key = ""
        self.groq_model = "qwen/qwen3.8-27b"
        self.island_scale = 50
        self.elevenlabs_key = ""
        self.elevenlabs_voice = "local:tr"
        self.elevenlabs_model = "eleven_v3"
        self.github_token = ""
        self.vercel_token = ""
        self.stripe_key = ""
        self.device_id = ""
        self.favorite_song = ""
        self.mic_always = False
        self.speak = False
        self.sfx = True
        self.sfx_volume = 0.12
        self.accessory = "none"
        self.weather_city = "İstanbul"
        self.language = i18n.DEFAULT
        self.onboarded = False
        self.open_on_hover = False
        self.outfit = "none"
        self.mascot = "ghost"
        self.mascot_color = "#1a7fd4"
        self.dictation = False
        self.dictation_key = "rctrl"
        self.stt_engine = "online"
        self.ok_kai = False
        self.ok_kai_sense = "mid"
        self.app_on_launch = True
        self.mail_address = ""
        self.mail_password = ""
        self.mail_server = ""
        self.calendar_ics = ""
        self.tour_done = False
        self.show_clock = False
        self.alerts_all_pills = False
        self.feels_pc = True
        self.claude_desktop_chat = False
        self.update_checks = True
        self.summary_enabled = True
        self.summary_time = "21:00"
        self.feedback_key = ""
        self.admin = False
        self.load()

    def load(self) -> None:
        try:
            with open(settings_path(), "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            data = {}
        self.dynamic_island = bool(data.get("dynamic_island", True))
        self.show_dot = bool(data.get("show_dot", True))
        self.chat = bool(data.get("chat", True))
        raw = str(data.get("provider") or "groq")
        if raw == "api":
            raw = "openai" if "openai.com" in str(data.get("api_url") or "") else "custom"
        self.provider = raw if raw in PROVIDERS else "groq"
        self.api_url = str(data.get("api_url") or self.api_url)
        self.api_key = str(data.get("api_key") or "")
        self.api_model = str(data.get("api_model") or self.api_model)
        self.groq_key = str(data.get("groq_key") or "")
        self.groq_model = str(data.get("groq_model") or self.groq_model)
        if self.groq_model in ("llama-3.3-70b-versatile", "llama3.3"):
            self.groq_model = "qwen/qwen3.8-27b"
        try:
            self.island_scale = int(data.get("island_scale", 50))
        except (TypeError, ValueError):
            self.island_scale = 50
        self.island_scale = max(40, min(160, self.island_scale))
        self.elevenlabs_key = str(data.get("elevenlabs_key") or "")
        self.elevenlabs_voice = str(data.get("elevenlabs_voice") or self.elevenlabs_voice)
        self.elevenlabs_model = str(data.get("elevenlabs_model") or "eleven_v3")
        # An ElevenLabs voice cannot speak without a key: Kai's own voice does instead.
        if not self.elevenlabs_key and not (self.elevenlabs_voice.startswith("edge:") or self.elevenlabs_voice.startswith("local:")):
            self.elevenlabs_voice = "local:tr"
        self.github_token = str(data.get("github_token") or "")
        self.vercel_token = str(data.get("vercel_token") or "")
        self.stripe_key = str(data.get("stripe_key") or "")
        self.device_id = str(data.get("device_id") or "")
        self.favorite_song = " ".join(str(data.get("favorite_song") or "").split())[:120]
        self.kai_mode = "v2" if data.get("kai_mode") == "v2" else "kai"
        self.mic_always = bool(data.get("mic_always", False))
        self.speak = bool(data.get("speak", False))
        self.sfx = bool(data.get("sfx", True))
        try:
            self.sfx_volume = max(0.0, min(0.2, float(data.get("sfx_volume", 0.12))))
        except (TypeError, ValueError):
            self.sfx_volume = 0.12
        self.accessory = str(data.get("accessory") or "none")[:20]
        self.weather_city = " ".join(str(data.get("weather_city", "İstanbul")).split())[:60]
        raw_language = str(data.get("language") or i18n.DEFAULT)
        self.language = raw_language if raw_language in i18n.LANGUAGES else i18n.DEFAULT
        i18n.set_language(self.language)
        # The first-start steps were shown (or skipped) on this machine.
        self.onboarded = bool(data.get("onboarded", False))
        self.open_on_hover = bool(data.get("open_on_hover", False))
        self.outfit = str(data.get("outfit") or "none")[:20]
        self.mascot = str(data.get("mascot") or "ghost")[:20]
        self.mascot_color = str(data.get("mascot_color") or "#1a7fd4")[:7]
        self.dictation = bool(data.get("dictation", False))
        key = str(data.get("dictation_key") or "rctrl")
        self.dictation_key = key if key in ("rctrl", "rshift", "ctrlwin") else "rctrl"
        engine = str(data.get("stt_engine") or "online")
        self.stt_engine = engine if engine in ("online", "whisper", "parakeet") else "online"
        self.ok_kai = bool(data.get("ok_kai", False))
        sense = str(data.get("ok_kai_sense") or "mid")
        self.ok_kai_sense = sense if sense in ("low", "mid", "high") else "mid"
        self.app_on_launch = bool(data.get("app_on_launch", True))
        self.mail_address = str(data.get("mail_address") or "").strip()[:200]
        self.mail_password = _unseal(str(data.get("mail_password") or ""))
        self.mail_server = str(data.get("mail_server") or "").strip()[:200]
        self.calendar_ics = str(data.get("calendar_ics") or "").strip()[:2000]
        # The Kai window's first-open tour was shown.
        self.tour_done = bool(data.get("tour_done", False))
        # The date and time in the middle of the compact island.
        self.show_clock = bool(data.get("show_clock", False))
        # Another pill finishing or failing opens the island for a moment.
        self.alerts_all_pills = bool(data.get("alerts_all_pills", False))
        # The mascot shows how the computer feels: processor, memory, battery, heat.
        self.feels_pc = bool(data.get("feels_pc", True))
        # A reply ready in the Claude desktop app (a plain chat runs no hook).
        self.claude_desktop_chat = bool(data.get("claude_desktop_chat", False))
        # A look at GitHub for a newer Kai a few times a day.
        self.update_checks = bool(data.get("update_checks", True))
        # The day's summary on the island, once a day at this time (HH:MM).
        self.summary_enabled = bool(data.get("summary_enabled", True))
        self.summary_time = clock_time(data.get("summary_time"), "21:00")
        # Only the developer's Kai has one: it collects the ratings people send.
        self.feedback_key = _unseal(str(data.get("feedback_key") or ""))
        # Kai's owner, unlocked once in the chat (admin.py): only they are "patron".
        # Sealed to this Windows account, so a copied settings file does not carry it.
        self.admin = _unseal(str(data.get("admin") or "")) == "owner"
        i18n.set_admin(self.admin)
        self._new_device = not self.device_id
        if self._new_device:
            self.device_id = uuid.uuid4().hex
        self.start_with_windows = startup_enabled()

    def save(self) -> None:
        payload = {
            "dynamic_island": self.dynamic_island,
            "show_dot": self.show_dot,
            "chat": self.chat,
            "provider": self.provider,
            "api_url": self.api_url.strip(),
            "api_key": self.api_key.strip(),
            "api_model": self.api_model.strip(),
            "groq_key": self.groq_key.strip(),
            "groq_model": self.groq_model.strip() or "qwen/qwen3.8-27b",
            "island_scale": int(self.island_scale),
            "elevenlabs_key": self.elevenlabs_key.strip(),
            "elevenlabs_voice": self.elevenlabs_voice.strip() or "local:tr",
            "elevenlabs_model": self.elevenlabs_model.strip() or "eleven_v3",
            "github_token": self.github_token.strip(),
            "vercel_token": self.vercel_token.strip(),
            "stripe_key": self.stripe_key.strip(),
            "device_id": self.device_id,
            "favorite_song": self.favorite_song,
            "kai_mode": "v2" if self.kai_mode == "v2" else "kai",
            "mic_always": bool(self.mic_always),
            "speak": bool(self.speak),
            "sfx": bool(self.sfx),
            "sfx_volume": round(float(self.sfx_volume), 3),
            "accessory": self.accessory,
            "weather_city": self.weather_city,
            "language": self.language if self.language in i18n.LANGUAGES else i18n.DEFAULT,
            "onboarded": bool(self.onboarded),
            "open_on_hover": bool(self.open_on_hover),
            "outfit": self.outfit,
            "mascot": self.mascot,
            "mascot_color": self.mascot_color,
            "dictation": bool(self.dictation),
            "dictation_key": self.dictation_key,
            "stt_engine": self.stt_engine,
            "ok_kai": bool(self.ok_kai),
            "ok_kai_sense": self.ok_kai_sense,
            "app_on_launch": bool(self.app_on_launch),
            "mail_address": self.mail_address.strip(),
            "mail_password": _seal(self.mail_password.strip()),
            "mail_server": self.mail_server.strip(),
            "calendar_ics": self.calendar_ics.strip(),
            "tour_done": bool(self.tour_done),
            "show_clock": bool(self.show_clock),
            "alerts_all_pills": bool(self.alerts_all_pills),
            "feels_pc": bool(self.feels_pc),
            "claude_desktop_chat": bool(self.claude_desktop_chat),
            "update_checks": bool(self.update_checks),
            "summary_enabled": bool(self.summary_enabled),
            "summary_time": clock_time(self.summary_time, "21:00"),
            "feedback_key": _seal(self.feedback_key.strip()),
            "admin": _seal("owner") if self.admin else "",
        }
        path = settings_path()
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        i18n.set_language(self.language)
        i18n.set_admin(self.admin)
        set_startup(self.start_with_windows)


def clock_time(value, fallback: str) -> str:
    """A time of day as "HH:MM", or the fallback when it is not one."""
    try:
        hours, minutes = (int(part) for part in str(value or "").strip().split(":"))
    except ValueError:
        return fallback
    return f"{hours:02d}:{minutes:02d}" if 0 <= hours < 24 and 0 <= minutes < 60 else fallback


def v2_file(name: str) -> str:
    return os.path.join(os.path.dirname(settings_path()), name)


def push_v2_hook(payload: dict) -> None:
    """A Claude Code hook event for the v2 island, one JSON object per line."""
    path = v2_file("v2_hooks.jsonl")
    try:
        fresh = os.path.getsize(path) > 2_000_000
    except OSError:
        fresh = True
    with open(path, "w" if fresh else "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def push_v2_decision(word: str) -> None:
    """Allow or deny clicked on the v2 island, for the process that holds the hook pipe."""
    import time

    path = v2_file("v2_decision.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        word = str(word).strip()
        known = word in ("allow", "deny", "ask") or (word.startswith("{") and len(word) < 60000)
        json.dump({"n": time.time(), "word": word if known else "deny"}, handle)
    os.replace(tmp, path)


def push_cmd(cmd: str, arg: str = "") -> None:
    """A request for the main process from the app window or the island (record, open the app…)."""
    import time

    path = v2_file("v2_cmd.json")
    tmp = path + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump({"n": time.time(), "cmd": str(cmd)[:40], "arg": str(arg)[:400]}, handle)
    os.replace(tmp, path)


def read_status() -> dict:
    """What the main process last said about recording, dictation and OK Kai."""
    try:
        with open(v2_file("v2_status.json"), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def push_v2(kind: str, text: str, you: str = "") -> None:
    """A note the v2 island picks up. v1 never reads this."""
    import time

    path = os.path.join(os.path.dirname(settings_path()), "v2_line.json")
    payload = {"n": time.time(), "kind": kind, "text": text[:800], "you": you[:240]}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    os.replace(tmp, path)
