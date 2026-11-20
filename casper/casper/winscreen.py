"""Windows: öndeki pencere, süreç adı, pencerenin ekran görüntüsü.

Başka işletim sistemlerinde sessizce boş döner (testler Linux'ta da çalışsın).
"""

from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass

IS_WINDOWS = os.name == "nt"


@dataclass
class Window:
    hwnd: int
    title: str
    exe: str
    pid: int
    rect: tuple[int, int, int, int]  # sol, üst, sağ, alt (fiziksel piksel)


def make_dpi_aware() -> None:
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def foreground() -> Window | None:
    if not IS_WINDOWS:
        return None
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.GetForegroundWindow.restype = ctypes.c_void_p
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    length = user32.GetWindowTextLengthW(ctypes.c_void_p(hwnd))
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(ctypes.c_void_p(hwnd), buf, length + 1)
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
    exe = ""
    kernel32.OpenProcess.restype = ctypes.c_void_p
    handle = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if handle:
        try:
            size = wintypes.DWORD(1024)
            path = ctypes.create_unicode_buffer(1024)
            if kernel32.QueryFullProcessImageNameW(ctypes.c_void_p(handle), 0, path, ctypes.byref(size)):
                exe = os.path.basename(path.value)
        finally:
            kernel32.CloseHandle(ctypes.c_void_p(handle))
    rect = wintypes.RECT()
    # Gölgesiz gerçek çerçeve (DWMWA_EXTENDED_FRAME_BOUNDS); olmazsa klasik dikdörtgen.
    try:
        ctypes.windll.dwmapi.DwmGetWindowAttribute(ctypes.c_void_p(hwnd), 9, ctypes.byref(rect), ctypes.sizeof(rect))
    except Exception:
        user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect))
    if rect.right - rect.left <= 0:
        user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect))
    return Window(hwnd, buf.value, exe, pid.value, (rect.left, rect.top, rect.right, rect.bottom))


def is_minimized(hwnd: int) -> bool:
    return IS_WINDOWS and bool(ctypes.windll.user32.IsIconic(ctypes.c_void_p(hwnd)))


def grab(rect: tuple[int, int, int, int]):
    """Pencerenin kapladığı alanın görüntüsü (PIL.Image). Çok ekranlı kurulumda da çalışır."""
    from PIL import ImageGrab

    left, top, right, bottom = rect
    if right - left < 50 or bottom - top < 50:
        return None
    return ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
