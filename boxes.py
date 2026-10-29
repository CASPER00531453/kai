"""Hollow boxes around the windows Kai can see. Clicks pass through."""

from __future__ import annotations

import ctypes
import os
import threading
from ctypes import wintypes

import numpy as np
from PIL import Image, ImageDraw, ImageFont

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32
dwmapi = ctypes.windll.dwmapi

WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TRANSPARENT = 0x00000020
WS_POPUP = 0x80000000
SW_SHOWNA = 8
SW_HIDE = 0
HWND_TOPMOST = -1
AC_SRC_ALPHA = 1
ULW_ALPHA = 2
GWL_EXSTYLE = -20
DWMWA_CLOAKED = 14

NAMES = {
    "league of legends.exe": "League of Legends",
    "leagueclientux.exe": "League of Legends",
    "leagueclient.exe": "League of Legends",
    "spotify.exe": "Spotify",
    "discord.exe": "Discord",
    "chrome.exe": "Chrome",
    "msedge.exe": "Edge",
    "firefox.exe": "Firefox",
    "steam.exe": "Steam",
    "cursor.exe": "Cursor",
    "code.exe": "VS Code",
    "cs2.exe": "Counter-Strike 2",
    "valorant-win64-shipping.exe": "Valorant",
}
SKIP = {
    "kai.exe", "python.exe", "pythonw.exe", "explorer.exe", "searchhost.exe",
    "shellexperiencehost.exe", "applicationframehost.exe", "textinputhost.exe",
    "startmenuexperiencehost.exe", "lockapp.exe", "systemsettings.exe",
}


class _RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class _POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class _SIZE(ctypes.Structure):
    _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]


class _BLEND(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_byte), ("BlendFlags", ctypes.c_byte), ("SourceConstantAlpha", ctypes.c_byte), ("AlphaFormat", ctypes.c_byte)]


_ENUM = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
if ctypes.sizeof(ctypes.c_void_p) == 8:
    _LRESULT = ctypes.c_longlong
else:
    _LRESULT = ctypes.c_long
_WNDPROC = ctypes.WINFUNCTYPE(_LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class _WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT), ("lpfnWndProc", _WNDPROC), ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
    ]


def _exe(hwnd: int) -> str:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    process = kernel32.OpenProcess(0x1000, False, pid.value)
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


def _label(exe: str, title: str) -> str:
    if exe in NAMES:
        return NAMES[exe]
    clean = " ".join((title or "").split())
    if clean and len(clean) <= 42 and clean.lower() not in {"program manager", "kai"}:
        return clean
    stem = os.path.splitext(exe)[0].replace("-", " ").strip()
    return stem.title() if stem else ""


def scan() -> list[tuple[str, tuple[int, int, int, int]]]:
    found: list[tuple[int, str, tuple[int, int, int, int]]] = []

    def visit(hwnd, _lp):
        if not user32.IsWindowVisible(hwnd):
            return True
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if style & WS_EX_TOOLWINDOW:
            return True
        cloaked = wintypes.DWORD()
        dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), 4)
        if cloaked.value:
            return True
        exe = _exe(hwnd)
        if not exe or exe in SKIP:
            return True
        rect = _RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        width, height = rect.right - rect.left, rect.bottom - rect.top
        if width < 80 or height < 60:
            return True
        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, title, 256)
        name = _label(exe, title.value)
        if not name:
            return True
        found.append((width * height, name, (rect.left, rect.top, rect.right, rect.bottom)))
        return True

    user32.EnumWindows(_ENUM(visit), 0)
    found.sort(key=lambda item: item[0], reverse=True)
    rows = []
    seen = set()
    for _area, name, rect in found:
        key = (name, rect)
        if key in seen:
            continue
        seen.add(key)
        rows.append((name, rect))
        if len(rows) >= 8:
            break
    return rows


def _font(size: int):
    path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "segoeuib.ttf")
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _image(width: int, height: int, name: str) -> Image.Image:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = (90, 210, 255, 230)
    for inset in range(3):
        draw.rectangle((inset, inset, width - 1 - inset, height - 1 - inset), outline=color)
    face = _font(max(14, min(22, width // 18)))
    text = name
    tw = int(draw.textlength(text, font=face)) + 16
    th = 28
    left = max(4, width - tw - 8)
    top = 8
    draw.rounded_rectangle((left, top, left + tw, top + th), radius=8, fill=(8, 16, 28, 210))
    draw.text((left + 8, top + 4), text, font=face, fill=(230, 248, 255, 255))
    return img


class Marks:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._hwnds: list[int] = []
        self._proc = _WNDPROC(lambda hwnd, msg, w, l: user32.DefWindowProcW(hwnd, msg, w, l))
        self._class = "KaiMark"
        self._ready = False
        self.labels: list[str] = []

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="kai-marks", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.labels = []

    def _ensure(self) -> None:
        if self._ready:
            return
        module = kernel32.GetModuleHandleW(None)
        wc = _WNDCLASS()
        wc.lpfnWndProc = self._proc
        wc.hInstance = module
        wc.lpszClassName = self._class
        user32.RegisterClassW(ctypes.byref(wc))
        self._ready = True

    def _window(self) -> int:
        module = kernel32.GetModuleHandleW(None)
        return user32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT,
            self._class, "KaiMark", WS_POPUP, 0, 0, 10, 10, None, None, module, None,
        )

    def _blit(self, hwnd: int, image: Image.Image, x: int, y: int) -> None:
        rgba = np.asarray(image.convert("RGBA"), dtype=np.float32)
        alpha = rgba[:, :, 3:4] / 255.0
        rgba[:, :, 0:3] *= alpha
        bgra = rgba[:, :, [2, 1, 0, 3]].astype(np.uint8)
        height, width = bgra.shape[0], bgra.shape[1]
        hdc = user32.GetDC(0)
        mem = gdi32.CreateCompatibleDC(hdc)

        class BMI(ctypes.Structure):
            _fields_ = [
                ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD),
            ]

        bmi = BMI(40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        bits = ctypes.c_void_p()
        bitmap = gdi32.CreateDIBSection(hdc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        if not bitmap or not bits:
            gdi32.DeleteDC(mem)
            user32.ReleaseDC(0, hdc)
            return
        ctypes.memmove(bits, bgra.tobytes(), width * height * 4)
        old = gdi32.SelectObject(mem, bitmap)
        origin = _POINT(x, y)
        size = _SIZE(width, height)
        src = _POINT(0, 0)
        blend = _BLEND(0, 0, 255, AC_SRC_ALPHA)
        user32.UpdateLayeredWindow(hwnd, hdc, ctypes.byref(origin), ctypes.byref(size), mem, ctypes.byref(src), 0, ctypes.byref(blend), ULW_ALPHA)
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010 | 0x0040)
        gdi32.SelectObject(mem, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(0, hdc)

    def _run(self) -> None:
        self._ensure()
        while not self._stop.wait(0.45):
            try:
                rows = scan()
            except Exception:
                rows = []
            self.labels = [name for name, _rect in rows]
            while len(self._hwnds) < len(rows):
                self._hwnds.append(self._window())
            for hwnd, (name, rect) in zip(self._hwnds, rows):
                left, top, right, bottom = rect
                image = _image(max(20, right - left), max(20, bottom - top), name)
                self._blit(hwnd, image, left, top)
                user32.ShowWindow(hwnd, SW_SHOWNA)
            for hwnd in self._hwnds[len(rows):]:
                user32.ShowWindow(hwnd, SW_HIDE)
        for hwnd in self._hwnds:
            user32.ShowWindow(hwnd, SW_HIDE)
        self.labels = []


marks = Marks()
