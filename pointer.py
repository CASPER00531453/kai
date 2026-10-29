"""Blue cursor with a small bot. Moves, then clicks what is on screen."""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

from PIL import Image, ImageDraw

from i18n import t
from island import (
    AC_SRC_ALPHA,
    BITMAPINFOHEADER,
    BLENDFUNCTION,
    POINT,
    SIZE,
    ULW_ALPHA,
    WNDCLASSW,
    WNDPROC,
    WS_EX_LAYERED,
    WS_EX_NOACTIVATE,
    WS_EX_TOOLWINDOW,
    WS_EX_TOPMOST,
    WS_POPUP,
    gdi32,
    kernel32,
    user32,
)

WS_EX_TRANSPARENT = 0x00000020
SW_SHOWNA = 8
SW_HIDE = 0
HWND_TOPMOST = -1
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
SM_CXSCREEN = 0
SM_CYSCREEN = 1

NEVER = {
    "cmd.exe", "powershell.exe", "pwsh.exe", "windowsterminal.exe", "regedit.exe",
    "mmc.exe", "kai.exe", "python.exe", "pythonw.exe",
}
PLAY_BITS = ("çal", "play", "oyna", "başlat", "baslat", "oynat")
OPEN_BITS = ("aç", "ac", "open", "launch")


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _UNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _UNION)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]


def _send_mouse(flags: int, x: int = 0, y: int = 0) -> None:
    event = _INPUT(type=0)
    event.u.mi = _MOUSEINPUT(x, y, 0, flags, 0, 0)
    user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(_INPUT))


def _click_at(x: int, y: int) -> None:
    width = max(1, user32.GetSystemMetrics(SM_CXSCREEN))
    height = max(1, user32.GetSystemMetrics(SM_CYSCREEN))
    ax = int(x * 65535 / width)
    ay = int(y * 65535 / height)
    _send_mouse(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, ax, ay)
    time.sleep(0.05)
    _send_mouse(MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_ABSOLUTE, ax, ay)
    _send_mouse(MOUSEEVENTF_LEFTUP | MOUSEEVENTF_ABSOLUTE, ax, ay)


class Pointer:
    def __init__(self) -> None:
        self._class = "KaiPointerWindow"
        self._proc_ref = WNDPROC(self._proc)
        self.hwnd = self._create()
        self.visible = False

    def _proc(self, hwnd, msg, w_param, l_param):
        if msg == 0x0002:
            return 0
        return user32.DefWindowProcW(hwnd, msg, w_param, l_param)

    def _create(self) -> int:
        module = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW()
        wc.lpfnWndProc = self._proc_ref
        wc.hInstance = module
        wc.lpszClassName = self._class
        user32.RegisterClassW(ctypes.byref(wc))
        hwnd = user32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT,
            self._class,
            "KaiPointer",
            WS_POPUP,
            0, 0, 96, 96,
            None, None, module, None,
        )
        return hwnd

    def move(self, x: int, y: int) -> None:
        image = self._image()
        self._blit(image, x, y)
        if not self.visible and self.hwnd:
            user32.ShowWindow(self.hwnd, SW_SHOWNA)
            self.visible = True

    def hide(self) -> None:
        if self.hwnd and self.visible:
            user32.ShowWindow(self.hwnd, SW_HIDE)
            self.visible = False

    def _image(self) -> Image.Image:
        img = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.polygon([(4, 4), (4, 46), (16, 34), (28, 58), (36, 54), (22, 30), (40, 30)], fill=(53, 184, 255, 255))
        draw.polygon([(6, 8), (6, 40), (14, 32), (24, 52), (30, 49), (19, 28), (34, 28)], fill=(210, 244, 255, 255))
        cx, cy, radius = 62, 58, 14
        for ox, oy in ((0, -0.55), (0, 0.55), (-0.55, 0), (0.55, 0)):
            draw.ellipse(
                (cx + ox * radius - radius * 0.72, cy + oy * radius - radius * 0.72, cx + ox * radius + radius * 0.72, cy + oy * radius + radius * 0.72),
                fill=(53, 184, 255, 255),
            )
        eye = 3.2
        for side in (-1, 1):
            ex = cx + side * radius * 0.32
            draw.ellipse((ex - eye, cy - eye, ex + eye, cy + eye), fill=(6, 18, 40, 255))
        return img

    def _blit(self, image: Image.Image, x: int, y: int) -> None:
        import numpy as np

        rgba = np.asarray(image.convert("RGBA"), dtype=np.float32)
        alpha = rgba[:, :, 3:4] / 255.0
        rgba[:, :, 0:3] *= alpha
        bgra = rgba[:, :, [2, 1, 0, 3]].astype(np.uint8)
        raw = bgra.tobytes()
        height, width = bgra.shape[0], bgra.shape[1]
        hdc_screen = user32.GetDC(0)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        info = BITMAPINFOHEADER()
        info.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.biWidth = width
        info.biHeight = -height
        info.biPlanes = 1
        info.biBitCount = 32
        bits = ctypes.c_void_p()
        bitmap = gdi32.CreateDIBSection(hdc_screen, ctypes.byref(info), 0, ctypes.byref(bits), None, 0)
        if not bitmap or not bits:
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(0, hdc_screen)
            return
        ctypes.memmove(bits, raw, len(raw))
        old = gdi32.SelectObject(hdc_mem, bitmap)
        origin = POINT(int(x), int(y))
        size = SIZE(width, height)
        src = POINT(0, 0)
        blend = BLENDFUNCTION(0, 0, 255, AC_SRC_ALPHA)
        user32.UpdateLayeredWindow(
            self.hwnd, hdc_screen, ctypes.byref(origin), ctypes.byref(size),
            hdc_mem, ctypes.byref(src), 0, ctypes.byref(blend), ULW_ALPHA,
        )
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0, 0x0001 | 0x0002 | SWP_NOACTIVATE | SWP_SHOWWINDOW)
        gdi32.SelectObject(hdc_mem, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)

    def destroy(self) -> None:
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None


def _foreground_exe() -> tuple[int, str]:
    import os

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return 0, ""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    process = kernel32.OpenProcess(0x1000, False, pid.value)
    if not process:
        return hwnd, ""
    try:
        size = wintypes.DWORD(512)
        buf = ctypes.create_unicode_buffer(512)
        if not kernel32.QueryFullProcessImageNameW(process, 0, buf, ctypes.byref(size)):
            return hwnd, ""
        return hwnd, os.path.basename(buf.value).lower()
    finally:
        kernel32.CloseHandle(process)


def _target(kind: str) -> tuple[int, int] | None:
    import uiautomation as auto

    hwnd, exe = _foreground_exe()
    if not hwnd or exe in NEVER:
        return None
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    bits = PLAY_BITS if kind == "play" else OPEN_BITS + PLAY_BITS
    best = None
    try:
        window = auto.ControlFromHandle(hwnd)
        count = 0
        for control, _depth in auto.WalkControl(window, maxDepth=18):
            count += 1
            if count > 400:
                break
            if control.ControlTypeName not in {"ButtonControl", "HyperlinkControl", "ListItemControl"}:
                continue
            name = (control.Name or "").lower()
            if not any(bit in name for bit in bits):
                continue
            box = control.BoundingRectangle
            if box.width() < 8 or box.height() < 8:
                continue
            score = 2 if any(bit in name for bit in bits[:3]) else 1
            best = (score, int(box.xcenter()), int(box.ycenter()))
            if score == 2:
                break
    except Exception:
        best = None
    if best:
        return best[1], best[2]
    if kind == "play":
        return None
    cx = (rect.left + rect.right) // 2
    cy = (rect.top + rect.bottom) // 2
    if cx <= 0 and cy <= 0:
        return None
    return cx, cy


def glide(pointer: Pointer, x: int, y: int) -> None:
    from watch import cursor_pos

    sx, sy = cursor_pos()
    steps = 16
    for i in range(1, steps + 1):
        t = i / steps
        px = int(sx + (x - sx) * t)
        py = int(sy + (y - sy) * t)
        user32.SetCursorPos(px, py)
        pointer.move(px, py)
        time.sleep(0.018)
    time.sleep(0.12)
    _click_at(x, y)
    time.sleep(0.35)
    pointer.hide()


def act(pointer: Pointer, kind: str) -> str:
    point = _target(kind)
    if not point:
        return t("click.none")
    glide(pointer, point[0], point[1])
    return t("click.played") if kind == "play" else t("click.opened")
