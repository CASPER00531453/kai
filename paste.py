"""Puts dictated text where the user is typing.

The text goes through the clipboard and a Ctrl+V, then the clipboard gets back
what it held. While it is there it is marked so Windows' clipboard history,
cloud clipboard and clipboard managers leave it out. When nothing that takes
text has the focus (the desktop, the taskbar), the words stay on the clipboard
instead and the caller says so.
"""

from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

CF_UNICODETEXT = 13
CF_HDROP = 15
CF_DIB = 8
GMEM_MOVEABLE = 0x0002
KEYEVENTF_KEYUP = 0x0002
VK_CONTROL = 0x11
VK_V = 0x56
NOT_TEXT = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "NotifyIconOverflowWindow"}

kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalSize.restype = ctypes.c_size_t
user32.GetClipboardData.restype = wintypes.HANDLE
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.RegisterClipboardFormatW.restype = wintypes.UINT
user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
user32.EnumClipboardFormats.argtypes = [wintypes.UINT]
user32.EnumClipboardFormats.restype = wintypes.UINT
user32.OpenClipboard.argtypes = [wintypes.HWND]


def foreground_app() -> str:
    """The executable in front, e.g. "chrome.exe", for styles and statistics."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(520)
        buf = ctypes.create_unicode_buffer(520)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
    finally:
        kernel32.CloseHandle(handle)
    return ""


def can_type() -> bool:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False
    name = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, name, 256)
    return name.value not in NOT_TEXT


def _open(retries: int = 10) -> bool:
    for _ in range(retries):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.03)
    return False


def _copy_handle(handle) -> bytes | None:
    size = kernel32.GlobalSize(handle)
    ptr = kernel32.GlobalLock(handle)
    if not ptr:
        return None
    try:
        return ctypes.string_at(ptr, size)
    finally:
        kernel32.GlobalUnlock(handle)


def _alloc(data: bytes):
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    ptr = kernel32.GlobalLock(handle)
    ctypes.memmove(ptr, data, len(data))
    kernel32.GlobalUnlock(handle)
    return handle


def _saveable(fmt: int) -> bool:
    # Formats held as global memory. Bitmaps, palettes and metafiles are GDI
    # handles and cannot be copied this way; CF_DIB carries the picture anyway.
    return fmt not in (2, 3, 9, 14, 17) and fmt != 0


def save() -> list[tuple[int, bytes]]:
    held: list[tuple[int, bytes]] = []
    if not _open():
        return held
    try:
        fmt = user32.EnumClipboardFormats(0)
        while fmt:
            if _saveable(fmt):
                handle = user32.GetClipboardData(fmt)
                if handle:
                    data = _copy_handle(handle)
                    if data is not None and len(data) < 64 * 1024 * 1024:
                        held.append((fmt, data))
            fmt = user32.EnumClipboardFormats(fmt)
    finally:
        user32.CloseClipboard()
    return held


def restore(held: list[tuple[int, bytes]]) -> None:
    if not _open():
        return
    try:
        user32.EmptyClipboard()
        for fmt, data in held:
            user32.SetClipboardData(fmt, _alloc(data))
    finally:
        user32.CloseClipboard()


def put_text(text: str, private: bool = True) -> bool:
    if not _open():
        return False
    try:
        user32.EmptyClipboard()
        user32.SetClipboardData(CF_UNICODETEXT, _alloc((text + "\0").encode("utf-16-le")))
        if private:
            # What Windows and clipboard managers look for to leave an entry out.
            user32.SetClipboardData(user32.RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing"), _alloc(b"\0"))
            zero = (0).to_bytes(4, "little")
            user32.SetClipboardData(user32.RegisterClipboardFormatW("CanIncludeInClipboardHistory"), _alloc(zero))
            user32.SetClipboardData(user32.RegisterClipboardFormatW("CanUploadToCloudClipboard"), _alloc(zero))
    finally:
        user32.CloseClipboard()
    return True


def _ctrl_v() -> None:
    # Keys still held from the dictation shortcut would turn Ctrl+V into something else.
    for vk in (0xA3, 0xA2, 0xA1, 0xA0, 0x5B, 0x5C, 0xA4, 0xA5):
        if user32.GetAsyncKeyState(vk) & 0x8000:
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_V, 0, 0, 0)
    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


def paste(text: str) -> str:
    """"pasted", or "clipboard" when it was left there because nothing takes text."""
    if not text:
        return "pasted"
    if not can_type():
        put_text(text, private=False)
        return "clipboard"
    held = save()
    if not put_text(text):
        return "clipboard"
    _ctrl_v()
    # The app reads the clipboard after the key arrives; give it time before
    # putting back what was there.
    time.sleep(0.35)
    restore(held)
    return "pasted"
