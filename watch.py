"""Foreground app, cursor position and game detection."""

from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
]

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SKIP = {
    "kai.exe",
    "python.exe",
    "pythonw.exe",
    "cursor.exe",
    "code.exe",
    "explorer.exe",
    "searchhost.exe",
    "shellexperiencehost.exe",
    "applicationframehost.exe",
    "textinputhost.exe",
    "windowsterminal.exe",
    "cmd.exe",
    "powershell.exe",
    "pwsh.exe",
    "systemsettings.exe",
}


class _RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class _CURSORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hCursor", wintypes.HANDLE),
        ("ptScreenPos", wintypes.POINT),
    ]


class _POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


user32.GetCursorInfo.argtypes = [ctypes.POINTER(_CURSORINFO)]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(_RECT)]
user32.GetCursorPos.argtypes = [ctypes.POINTER(_POINT)]

_GAME_OK = SKIP | {
    "brave.exe",
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "discord.exe",
    "spotify.exe",
    "notepad.exe",
}
_game_cache = {"t": 0.0, "v": False}


def cursor_pos() -> tuple[int, int]:
    point = _POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def game_name() -> str:
    snap = foreground()
    if not snap:
        return ""
    return {
        "league of legends.exe": "League of Legends",
        "leagueclientux.exe": "League of Legends",
        "leagueclient.exe": "League of Legends",
        "cs2.exe": "Counter-Strike 2",
        "valorant-win64-shipping.exe": "Valorant",
        "fortniteclient-win64-shipping.exe": "Fortnite",
    }.get(snap["exe"], "")


def playing_game() -> bool:
    now = time.monotonic()
    if now - _game_cache["t"] < 0.45:
        return _game_cache["v"]
    _game_cache["t"] = now
    _game_cache["v"] = _playing_game()
    return _game_cache["v"]


def _playing_game() -> bool:
    info = _CURSORINFO()
    info.cbSize = ctypes.sizeof(_CURSORINFO)
    if user32.GetCursorInfo(ctypes.byref(info)) and not (info.flags & 0x0001):
        return True
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False
    snap = foreground()
    if not snap or snap["exe"] in _GAME_OK:
        return False
    rect = _RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False
    wide = max(1, rect.right - rect.left)
    tall = max(1, rect.bottom - rect.top)
    screen_w = user32.GetSystemMetrics(0)
    screen_h = user32.GetSystemMetrics(1)
    return wide >= screen_w * 0.9 and tall >= screen_h * 0.9


def foreground() -> dict | None:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return None
    process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not process:
        return None
    try:
        size = wintypes.DWORD(512)
        buf = ctypes.create_unicode_buffer(512)
        if not kernel32.QueryFullProcessImageNameW(process, 0, buf, ctypes.byref(size)):
            return None
        exe = os.path.basename(buf.value).lower()
    finally:
        kernel32.CloseHandle(process)
    if exe in SKIP:
        return None
    label = os.path.splitext(exe)[0].replace("-", " ").title()
    return {"exe": exe, "label": label}
