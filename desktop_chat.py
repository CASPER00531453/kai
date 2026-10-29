"""A reply ready in the Claude desktop app, for the island. Experimental, off by default.

A plain Claude Desktop chat (not a Code session) runs no hook, so Kai never
hears that a reply is done. After coucou's ClaudeDesktopChatWatcher: when you
leave the Claude window while it is still writing, Kai looks once a second
until it stops, then the Claude Desktop pill says the reply is ready and the
mascot jumps.

On the Mac the "Stop response" button tells it. On Windows the app keeps its
accessibility tree closed unless a screen reader runs, so when that button
cannot be seen, the app's own processor use stands in for it: busy while it
writes, quiet once done. Nothing of the chat is read, and nothing runs while
Claude is in front or the setting is off.
"""

from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32
user32.GetForegroundWindow.restype = ctypes.c_void_p
user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
kernel32.OpenProcess.restype = ctypes.c_void_p
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
kernel32.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.c_void_p] * 4
kernel32.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong)]
kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
kernel32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
kernel32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

EXE = "claude.exe"
# A reply longer than this many seconds is given up on: no endless polling.
MAX_POLLS = 1800
# Processor use of the whole app, in share of one core: about 0.6 while it writes.
BUSY = 0.25
QUIET = 0.10
QUIET_FOR = 4

STOP_LABELS = {
    "stop response", "stop generating", "yanıtı durdur", "durdur", "oluşturmayı durdur",
    "arrêter la réponse", "detener respuesta", "antwort stoppen", "interrompi risposta",
}


class _Entry(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


def _exe_of(pid: int) -> str:
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


def _front() -> tuple[int, int]:
    """(window, process) in front."""
    hwnd = user32.GetForegroundWindow() or 0
    pid = wintypes.DWORD()
    if hwnd:
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(hwnd), pid.value


def _app_pids() -> list[int]:
    snap = kernel32.CreateToolhelp32Snapshot(2, 0)
    found = []
    entry = _Entry()
    entry.dwSize = ctypes.sizeof(_Entry)
    try:
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() == EXE:
                found.append(entry.th32ProcessID)
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)
    return found


def _cpu_seconds(pids: list[int]) -> float:
    total = 0
    for pid in pids:
        process = kernel32.OpenProcess(0x1000, False, pid)
        if not process:
            continue
        try:
            times = [ctypes.c_ulonglong() for _ in range(4)]
            if kernel32.GetProcessTimes(process, *[ctypes.byref(t) for t in times]):
                total += times[2].value + times[3].value
        finally:
            kernel32.CloseHandle(process)
    return total / 1e7


def _stop_button(hwnd: int) -> bool | None:
    """True or False when the app's buttons can be read; None when its tree is closed."""
    try:
        import uiautomation as auto

        window = auto.ControlFromHandle(hwnd)
        seen = 0
        for control, _depth in auto.WalkControl(window, maxDepth=40):
            seen += 1
            if seen > 3000:
                break
            if control.ControlTypeName != "ButtonControl":
                continue
            label = (control.Name or "").strip().lower()
            if label in STOP_LABELS or ("stop" in label and "respon" in label):
                return True
        # Only the frame's own buttons: the web content is not exposed.
        return None if seen < 40 else False
    except Exception:
        return None


class Watcher:
    def __init__(self, enabled, on_ready) -> None:
        self.enabled = enabled
        self.on_ready = on_ready

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        claude_hwnd = 0
        while True:
            time.sleep(1.0)
            if not self.enabled():
                claude_hwnd = 0
                continue
            try:
                hwnd, pid = _front()
                if hwnd and _exe_of(pid) == EXE:
                    claude_hwnd = hwnd
                    continue
                if claude_hwnd:
                    left, claude_hwnd = claude_hwnd, 0
                    if self._writing_then_done(left):
                        self.on_ready()
            except Exception:
                claude_hwnd = 0

    def _writing_then_done(self, hwnd: int) -> bool:
        """You just left Claude: was it writing, and did it finish before you came back?"""
        button = _stop_button(hwnd)
        if button is False:
            return False
        pids = _app_pids()
        last = _cpu_seconds(pids)
        quiet = 0
        busy = button is True
        for poll in range(MAX_POLLS):
            time.sleep(1.0)
            if not self.enabled():
                return False
            front, pid = _front()
            if front == hwnd or (front and _exe_of(pid) == EXE):
                return False  # back in Claude: you see the reply yourself
            if button is True:
                if _stop_button(hwnd) is False:
                    return True
                continue
            now = _cpu_seconds(pids)
            share, last = now - last, now
            if poll < 2:
                busy = busy or share > BUSY
                if poll == 1 and not busy:
                    return False  # it was not writing
                continue
            quiet = quiet + 1 if share < QUIET else 0
            if quiet >= QUIET_FOR:
                return True
        return False
