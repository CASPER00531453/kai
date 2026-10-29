"""Type text into another app's window from a spoken command."""

from __future__ import annotations

import ctypes
import os
import re
import time
from ctypes import wintypes

from i18n import t

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_RETURN = 0x0D
SW_RESTORE = 9
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MAX_CHARS = 1500

ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _UNION)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SwitchToThisWindow.argtypes = [wintypes.HWND, wintypes.BOOL]
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

# Never type into shells, consoles, registry tools, Run dialogs or Kai itself.
NEVER = {
    "cmd.exe", "powershell.exe", "pwsh.exe", "windowsterminal.exe", "openconsole.exe", "conhost.exe",
    "wt.exe", "regedit.exe", "mmc.exe", "explorer.exe", "kai.exe", "python.exe", "pythonw.exe",
    "taskmgr.exe", "wsl.exe", "bash.exe", "putty.exe", "mintty.exe",
}

TARGETS = {
    "discord": ("Discord", ["discord.exe"], "discord:"),
    "whatsapp": ("WhatsApp", ["whatsapp.exe", "whatsapp.root.exe"], "whatsapp:"),
    "telegram": ("Telegram", ["telegram.exe"], None),
    "notepad": ("Not defteri", ["notepad.exe"], None),
    "not defteri": ("Not defteri", ["notepad.exe"], None),
    "chrome": ("Chrome", ["chrome.exe"], None),
    "brave": ("Brave", ["brave.exe"], None),
    "edge": ("Edge", ["msedge.exe"], None),
    "firefox": ("Firefox", ["firefox.exe"], None),
    "word": ("Word", ["winword.exe"], None),
    "steam": ("Steam", ["steamwebhelper.exe", "steam.exe"], None),
    "spotify": ("Spotify", ["spotify.exe"], None),
    "instagram": ("Instagram", ["instagram.exe"], None),
}
HERE = {"buraya", "şuraya", "suraya", "oraya", "ekrana", "açık", "acik", "pencereye"}
VERBS = {"yaz", "yazsana", "yazar", "yazarmısın", "yazarmisin", "yazıver", "yaziver", "yazın", "yazin",
         "gönder", "gonder", "gönders", "yolla", "yollasana", "at", "atsana"}
SEND_VERBS = {"gönder", "gonder", "yolla", "yollasana", "at", "atsana"}
CASE = ("ya", "ye", "na", "ne", "a", "e", "ına", "ine", "una", "üne", "ına", "inə")
FILLER = {"lütfen", "lutfen", "kai", "hadi", "bi", "şunu", "sunu", "mısın", "misin", "bana", "mesaj", "olarak",
          "ve", "de", "da", "sonra", "hemen", "bir"}
LAST = {"bunu", "onu", "cevabı", "cevabi", "cevabını", "cevabini", "söylediğini", "soyledigini"}
COMPOSE = {"şiir", "siir", "şaka", "saka", "fıkra", "fikra", "özür", "ozur", "tebrik", "kutlama", "hikaye",
           "hikâye", "mesajı", "mesaji", "cümle", "cumle", "paragraf", "yazı", "yazi", "mail", "e-posta", "espri"}


def _fold(token: str) -> str:
    return re.sub(r"[^\wçğıöşü]", "", token.lower().replace("’", "").replace("'", ""))


def _target(token: str) -> str | None:
    word = _fold(token)
    for key in sorted(TARGETS, key=len, reverse=True):
        if " " in key:
            continue
        if word == key:
            return key
        if word.startswith(key) and word[len(key):] in CASE:
            return key
    return None


def parse(text: str) -> dict | None:
    """'Discord'a selam yaz' -> {'app': 'discord', 'text': 'selam', 'send': False}."""
    raw = text.strip().rstrip(".!?")
    tokens = raw.split()
    folded = [_fold(t) for t in tokens]
    verb_at = next((i for i in range(len(folded) - 1, -1, -1) if folded[i] in VERBS), None)
    if verb_at is None:
        return None
    app = None
    app_at = None
    for i, token in enumerate(tokens[:verb_at] or tokens):
        if i + 1 < len(tokens) and folded[i] == "not" and folded[i + 1].startswith("defter"):
            app, app_at = "not defteri", (i, i + 1)
            break
        hit = _target(token)
        if hit:
            app, app_at = hit, (i, i)
            break
        if folded[i] in HERE:
            app, app_at = "here", (i, i)
            break
    if app is None:
        return None
    if folded[verb_at] in {"at", "atsana"} and app == "here":
        return None
    skip = set(range(app_at[0], app_at[1] + 1)) | {verb_at}
    words = [tokens[i] for i in range(len(tokens)) if i not in skip and not (folded[i] in FILLER and (i < app_at[0] + 2 or i > verb_at - 2))]
    body = " ".join(words).strip(" ,:;\"'")
    send = folded[verb_at] in SEND_VERBS or any(f in SEND_VERBS for f in folded[verb_at + 1:])
    if verb_at + 1 < len(tokens) and not body:
        body = " ".join(tokens[verb_at + 1:]).strip(" ,:;\"'")
    if not body and folded[verb_at] in SEND_VERBS:
        return None
    use_last = _fold(body) in LAST or not body
    compose = bool(set(_fold(w) for w in body.split()) & COMPOSE) and len(body.split()) <= 8
    return {"app": app, "text": body, "send": send, "use_last": use_last, "compose": compose}


def _exe(hwnd) -> str:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not process:
        return ""
    try:
        size = wintypes.DWORD(512)
        buf = ctypes.create_unicode_buffer(512)
        if not kernel32.QueryFullProcessImageNameW(process, 0, buf, ctypes.byref(size)):
            return ""
        return os.path.basename(buf.value).lower()
    finally:
        kernel32.CloseHandle(process)


def _find_window(exes: list[str]):
    found = []

    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0 and _exe(hwnd) in exes:
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return found[0] if found else None


def _focus(hwnd) -> bool:
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    fg = user32.GetForegroundWindow()
    if fg == hwnd:
        return True
    me = kernel32.GetCurrentThreadId()
    other = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    if other:
        user32.AttachThreadInput(me, other, True)
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SwitchToThisWindow(hwnd, True)
    finally:
        if other:
            user32.AttachThreadInput(me, other, False)
    for _ in range(10):
        if user32.GetForegroundWindow() == hwnd:
            return True
        time.sleep(0.05)
    return user32.GetForegroundWindow() == hwnd


def _send_keys(events: list[INPUT]) -> None:
    for start in range(0, len(events), 40):
        chunk = events[start : start + 40]
        array = (INPUT * len(chunk))(*chunk)
        user32.SendInput(len(chunk), array, ctypes.sizeof(INPUT))
        time.sleep(0.008)


def _type_text(text: str) -> None:
    events = []
    for char in text:
        code = ord(char)
        units = [code] if code <= 0xFFFF else [0xD800 + ((code - 0x10000) >> 10), 0xDC00 + ((code - 0x10000) & 0x3FF)]
        for unit in units:
            for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
                event = INPUT(type=INPUT_KEYBOARD)
                event.u.ki = KEYBDINPUT(0, unit, flags, 0, 0)
                events.append(event)
    _send_keys(events)


def _press_enter() -> None:
    events = []
    for flags in (0, KEYEVENTF_KEYUP):
        event = INPUT(type=INPUT_KEYBOARD)
        event.u.ki = KEYBDINPUT(VK_RETURN, 0, flags, 0, 0)
        events.append(event)
    _send_keys(events)


def type_into(app: str, text: str, send: bool) -> str:
    text = " ".join(text.split())[:MAX_CHARS]
    if not text:
        return t("type.empty")
    if app == "here":
        hwnd = user32.GetForegroundWindow()
        label = t("type.here")
    else:
        label, exes, uri = TARGETS[app]
        hwnd = _find_window(exes)
        if hwnd is None and uri:
            os.startfile(uri)
            for _ in range(40):
                time.sleep(0.25)
                hwnd = _find_window(exes)
                if hwnd:
                    break
            time.sleep(1.5)
        if hwnd is None:
            return t("type.closed", label=label)
    if not hwnd:
        return t("type.no_window")
    exe = _exe(hwnd)
    if exe in NEVER:
        return t("type.unsafe")
    if not _focus(hwnd):
        return t("type.no_focus", label=label)
    time.sleep(0.35)
    if user32.GetForegroundWindow() != hwnd:
        return t("type.lost_focus", label=label)
    _type_text(text)
    if send:
        time.sleep(0.1)
        _press_enter()
        return t("type.sent", label=label)
    return t("type.typed", label=label)
