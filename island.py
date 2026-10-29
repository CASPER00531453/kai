"""Top-center layered island window. No taskbar button, no focus steal."""

from __future__ import annotations

import ctypes
import math
import os
import time
from ctypes import wintypes

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from coucou_motion import BotMotion, Tracked
from i18n import t

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

if ctypes.sizeof(ctypes.c_void_p) == 8:
    LRESULT = ctypes.c_longlong
else:
    LRESULT = ctypes.c_long

WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

WS_POPUP = 0x80000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
SW_HIDE = 0
SW_SHOWNA = 8
WM_TIMER = 0x0113
WM_DESTROY = 0x0002
ULW_ALPHA = 0x02
AC_SRC_ALPHA = 1
LOGPIXELSX = 88
MONITOR_DEFAULTTOPRIMARY = 1


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
    ]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_byte),
        ("BlendFlags", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wintypes.ATOM
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
user32.LoadCursorW.restype = wintypes.HANDLE
user32.SetCursor.argtypes = [wintypes.HANDLE]
user32.SetCursor.restype = wintypes.HANDLE
IDC_ARROW = 32512
IDC_HAND = 32649
WM_SETCURSOR = 0x0020
WM_MOUSEACTIVATE = 0x0021
WM_LBUTTONDOWN = 0x0201
MA_NOACTIVATE = 3
user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p]
user32.SetTimer.restype = ctypes.c_size_t
user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_size_t]
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
gdi32.GetDeviceCaps.argtypes = [wintypes.HDC, ctypes.c_int]
gdi32.GetDeviceCaps.restype = ctypes.c_int
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.CreateDIBSection.argtypes = [
    wintypes.HDC, ctypes.c_void_p, wintypes.UINT,
    ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD,
]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
user32.UpdateLayeredWindow.argtypes = [
    wintypes.HWND, wintypes.HDC, ctypes.POINTER(POINT), ctypes.POINTER(SIZE),
    wintypes.HDC, ctypes.POINTER(POINT), wintypes.DWORD,
    ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD,
]
user32.UpdateLayeredWindow.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
user32.MonitorFromPoint.argtypes = [POINT, wintypes.DWORD]
user32.MonitorFromPoint.restype = wintypes.HANDLE
user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
user32.GetMonitorInfoW.restype = wintypes.BOOL
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE


def enable_dpi() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def dpi_scale() -> float:
    hdc = user32.GetDC(0)
    dpi = gdi32.GetDeviceCaps(hdc, LOGPIXELSX) or 96
    user32.ReleaseDC(0, hdc)
    return max(1.0, dpi / 96.0)


def monitor_top_center() -> tuple[int, int, int]:
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    monitor = user32.MonitorFromPoint(POINT(0, 0), MONITOR_DEFAULTTOPRIMARY)
    if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        left, top, right = info.rcMonitor.left, info.rcMonitor.top, info.rcMonitor.right
        return (left + right) // 2, top, right - left
    width = user32.GetSystemMetrics(0)
    return width // 2, 0, width


_fonts: dict[tuple[str, int], ImageFont.ImageFont] = {}


def _font(name: str, size: int) -> ImageFont.ImageFont:
    key = (name, max(8, int(size)))
    cached = _fonts.get(key)
    if cached is not None:
        return cached
    path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name)
    try:
        face = ImageFont.truetype(path, key[1])
    except Exception:
        face = ImageFont.load_default()
    _fonts[key] = face
    return face


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _fit(draw: ImageDraw.ImageDraw, text: str, font, max_px: float) -> str:
    if max_px <= 8 or draw.textlength(text, font=font) <= max_px:
        return text
    trimmed = text
    while trimmed and draw.textlength(trimmed + "…", font=font) > max_px:
        trimmed = trimmed[:-1]
    return (trimmed or text[:1]) + "…"


def _clock(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_px: float) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_px:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


class Island:
    def __init__(self, on_message) -> None:
        self.on_message = on_message
        self.scale = dpi_scale()
        self.mode = "idle"
        self.rest = False
        self.shown = 0.0
        self.target = 0.0
        self.level = 0.0
        self.smooth = 0.0
        self.show_dot = True
        self.size_percent = 50
        self.looking = False
        self.watching = False
        self.look_shown = 0.0
        self.greet_ticks = 0
        self.pills: list[tuple[str, tuple[int, int, int]]] = []
        self.motion = BotMotion()
        self.open_track = Tracked(0.0)
        self.look_track = Tracked(0.0)
        self._greeted = False
        self.poke_until = 0
        self.dizzy_until = 0
        self.permit = False
        self.cheer_until = 0
        self.diff_rows: list[tuple[str, str, int]] = []
        self.played = None
        self._blink_until = 0
        self._pokes: list[int] = []
        self.chat = False
        self.you = ""
        self.kai_line = ""
        self.hit = (0, 0, 0, 0)
        self.origin = (0, 0)
        self._ss = 2
        self.buttons: dict[str, tuple[int, int, int, int]] = {}
        self.media = None
        self.typing = False
        self._cover_cache = (None, None)
        self._chat_shadow = (None, None)
        self.busy = False
        self.subtitle = "dinliyor"
        self.tick = 0
        self.visible = False
        self.suppressed = False
        self.last_image: Image.Image | None = None
        self._shadow_key = None
        self._shadow: Image.Image | None = None
        self._class = "KaiIslandWindow"
        self._wndproc = WNDPROC(self._proc)
        self.hwnd = self._create()

    def _create(self) -> int:
        module = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW()
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = module
        wc.hCursor = user32.LoadCursorW(None, IDC_ARROW)
        wc.lpszClassName = self._class
        atom = user32.RegisterClassW(ctypes.byref(wc))
        if not atom:
            err = ctypes.get_last_error()
            if err not in (1410,):  # class already exists
                raise OSError(f"pencere sınıfı kurulamadı ({err})")
        hwnd = user32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            self._class,
            "Kai",
            WS_POPUP,
            0, 0, 10, 10,
            None, None, module, None,
        )
        if not hwnd:
            raise OSError(f"ada penceresi açılmadı ({ctypes.get_last_error()})")
        user32.SetTimer(hwnd, 2, 90, None)
        return hwnd

    def _button_at(self, x: int, y: int) -> str | None:
        for name, (x0, y0, x1, y1) in self.buttons.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return name
        return None

    def _client_cursor(self) -> tuple[int, int]:
        from watch import cursor_pos

        px, py = cursor_pos()
        return px - self.origin[0], py - self.origin[1]

    def _proc(self, hwnd, msg, w_param, l_param):
        if msg == WM_SETCURSOR:
            over = self._button_at(*self._client_cursor()) if self.buttons else None
            user32.SetCursor(user32.LoadCursorW(None, IDC_HAND if over else IDC_ARROW))
            return 1
        if msg == WM_MOUSEACTIVATE:
            return MA_NOACTIVATE
        if msg == WM_LBUTTONDOWN:
            x = ctypes.c_short(l_param & 0xFFFF).value
            y = ctypes.c_short((l_param >> 16) & 0xFFFF).value
            name = self._button_at(x, y)
            if name:
                self.on_message("click", name)
            else:
                self.on_message("poke")
            return 0
        if msg == WM_TIMER:
            self.on_message("watch" if int(w_param) == 2 else "timer")
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        if msg >= 0x8000:
            self.on_message(int(msg), int(w_param))
            return 0
        return user32.DefWindowProcW(hwnd, msg, w_param, l_param)

    def raise_top(self) -> None:
        if self.suppressed or not self.hwnd or not self.visible:
            return
        now = time.monotonic()
        if now < getattr(self, "_raised", 0.0):
            return
        self._raised = now + 1.2
        user32.SetWindowPos(
            self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )

    def start_timer(self) -> None:
        user32.SetTimer(self.hwnd, 1, 33, None)

    def show(self, mode: str, subtitle: str) -> None:
        if self.suppressed:
            return
        self.mode = mode
        self.subtitle = subtitle
        self.target = 1.0
        self.start_timer()

    def hide(self) -> None:
        self.target = 0.0
        self.start_timer()

    def conceal(self) -> None:
        """v2 owns the screen. The first island stays fully hidden."""
        self.suppressed = True
        self.rest = False
        self.looking = False
        self.target = 0.0
        self.shown = 0.0
        if self.hwnd and self.visible:
            user32.ShowWindow(self.hwnd, SW_HIDE)
            self.visible = False

    def release(self) -> None:
        self.suppressed = False

    def wake_idle(self) -> None:
        if self.suppressed:
            return
        self.rest = True
        self.mode = "idle"
        self.target = 0.0
        self.start_timer()

    def poke(self) -> None:
        now = self.tick
        self.motion.squash()
        self._pokes = [stamp for stamp in self._pokes if now - stamp < 18]
        self._pokes.append(now)
        if len(self._pokes) >= 3:
            self.dizzy_until = now + 90
            self.motion.dizzy()
            self._pokes.clear()
        self.start_timer()

    def push_diff(self, rows: list[tuple[str, str]]) -> None:
        for kind, text in rows:
            self.diff_rows.append((kind, str(text)[:90], self.tick))
        self.diff_rows = self.diff_rows[-36:]
        self.start_timer()

    def step(self, level: float) -> None:
        if self.suppressed:
            if self.hwnd and self.visible:
                user32.ShowWindow(self.hwnd, SW_HIDE)
                self.visible = False
            return
        self.tick += 1
        if self.greet_ticks > 0:
            self.greet_ticks -= 1
            if not self._greeted:
                self.motion.greet()
                self._greeted = True
        else:
            self._greeted = False
        if self.tick >= self._blink_until and self.tick % 110 == 0:
            self._blink_until = self.tick + 4
        self.level = level
        self.smooth += (level - self.smooth) * 0.42
        if self.target >= self.open_track.spring.target:
            self.open_track.spring_to(self.target, 0.5, 0.72)
        else:
            self.open_track.curve_towards(self.target, 340)
        self.open_track.step(0.033)
        self.shown = max(0.0, min(1.08, self.open_track.value))
        look_goal = 1.0 if self.looking else 0.0
        if look_goal >= self.look_track.spring.target:
            self.look_track.spring_to(look_goal, 0.42, 0.8)
        else:
            self.look_track.curve_towards(look_goal, 220)
        self.look_track.step(0.033)
        self.look_shown = max(0.0, min(1.0, self.look_track.value))
        self.motion.update(0.033)
        moving = (
            self.open_track.animating
            or self.look_track.animating
            or self.motion.busy
            or abs(self.target - self.shown) > 0.012
        )
        blinking = self.tick < self._blink_until or self.tick < self.cheer_until
        if not moving and self.looking and self.mode == "idle" and self.target < 0.2 and not blinking:
            gap = 2.0
        elif self.watching and not moving and self.mode == "idle" and self.target < 0.2 and not blinking:
            gap = 0.45
        else:
            gap = 0.045 if self.mode != "idle" or self.target > 0.2 or blinking else 0.11
        now = time.monotonic()
        if not moving and now < getattr(self, "_drew", 0.0):
            return
        self._drew = now + gap
        if self.shown <= 0.02 and self.target == 0.0 and not self.rest:
            if self.visible:
                user32.ShowWindow(self.hwnd, SW_HIDE)
                self.visible = False
            return
        image = self._draw()
        self.last_image = image
        self._blit(image)
        if not self.visible:
            user32.ShowWindow(self.hwnd, SW_SHOWNA)
            self.visible = True
            self.raise_top()

    def _draw(self) -> Image.Image:
        ss = 2
        self._ss = ss
        s = self.scale * ss
        user = max(40, min(160, int(self.size_percent))) / 100.0
        content_s = s * user
        ease = _ease(self.shown)
        look = _ease(self.look_shown) * (1.0 - ease)
        side = 92
        idle_w = _lerp(78, side, look)
        idle_h = _lerp(18, side, look)
        media_mode = self.mode == "media"
        diff_mode = self.mode == "diff"
        history = self.played() if media_mode and callable(self.played) else []
        if media_mode:
            mu = max(0.8, user)
            content_s = s * mu
            full_w, full_h = 700 * mu, (214 if len(history) > 1 else 156) * mu
        elif diff_mode:
            mu = max(0.85, user)
            content_s = s * mu
            full_w, full_h = 720 * mu, 240 * mu
        elif self.permit:
            mu = max(0.9, user)
            content_s = s * mu
            full_w, full_h = 760 * mu, 150 * mu
        else:
            full_w, full_h = 560 * user, 112 * user
        cw = int(_lerp(idle_w, full_w, ease) * s)
        ch = int(_lerp(idle_h, full_h, ease) * s)
        self.buttons = {}
        margin = int(18 * s)
        top = int(2 * s)
        chat_w, chat_h, chat_rows = self._chat_layout(s)
        pill_bottom = top + ch
        extra = 0
        if chat_h:
            extra = int(8 * s) + chat_h + int(16 * s)
        w = max(cw, chat_w) + margin * 2
        h = pill_bottom + margin + int(10 * s) + extra
        pill_x = (w - cw) // 2
        pill = (pill_x, top, pill_x + cw, top + ch)
        cx, screen_top, _ = monitor_top_center()
        self.origin = (int(cx - (w // ss) / 2), int(screen_top + self.scale))
        pad = int(10 * s)
        logical_pad = max(1, pad // ss)
        self.hit = (
            self.origin[0] + pill[0] // ss - logical_pad,
            self.origin[1] + pill[1] // ss - logical_pad,
            self.origin[0] + pill[2] // ss + logical_pad,
            self.origin[1] + pill[3] // ss + logical_pad,
        )
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        radius = max(1, ch // 2)
        if media_mode:
            radius = max(1, min(ch // 2, int(_lerp(ch / 2, 44 * content_s, ease))))
        shadow = self._shadow_layer(w, h, pill, radius, s, max(ease, look))
        if shadow.size != img.size:
            shadow = shadow.resize(img.size)
        img = Image.alpha_composite(img, shadow)
        draw = ImageDraw.Draw(img)
        outline = (255, 255, 255, int(28 * max(ease, look))) if max(ease, look) > 0.25 else None
        draw.rounded_rectangle(
            pill,
            radius=radius,
            fill=(8, 8, 10, 250),
            outline=outline,
            width=max(1, int(s)) if outline else 1,
        )

        content_alpha = max(0.0, min(1.0, (ease - 0.42) / 0.58))
        dot_alpha = int(255 * (1.0 - max(content_alpha, look)))
        if dot_alpha > 12 and self.show_dot:
            self._idle_dot(draw, pill, s, dot_alpha)
        if look > 0.08 and content_alpha < 0.5:
            bot = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            bd = ImageDraw.Draw(bot)
            self._draw_bot(bd, (pill[0] + pill[2]) / 2, (pill[1] + pill[3]) / 2, s * (0.72 + 0.28 * look), gaze=True)
            if look < 0.99:
                alpha = bot.getchannel("A").point(lambda p: int(p * look))
                bot.putalpha(alpha)
            img = Image.alpha_composite(img, bot)
        if content_alpha > 0.05:
            overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            if media_mode:
                slot = int(108 * content_s)
                song = (pill[0] + slot, pill[1], pill[2], pill[3])
                self._draw_media(overlay, od, song, content_s, content_alpha > 0.6)
                bot_cx = pill[0] + slot * 0.46
                bot_cy = (pill[1] + pill[3]) / 2
                self._draw_bot(od, bot_cx, bot_cy, content_s * 1.35, gaze=True)
            elif self.mode == "diff":
                self._draw_diff(od, pill, content_s)
            elif self.mode == "music":
                self._draw_music(od, pill, content_s)
            else:
                self._draw_listen(od, pill, content_s)
            if content_alpha < 0.99:
                alpha = overlay.getchannel("A").point(lambda p: int(p * content_alpha))
                overlay.putalpha(alpha)
            img = Image.alpha_composite(img, overlay)
        if chat_h:
            img = self._paint_chat(img, w, pill_bottom + int(10 * s), chat_w, chat_rows, s)
        img = img.resize((max(1, w // ss), max(1, h // ss)), Image.Resampling.LANCZOS)
        self.buttons = {name: tuple(int(value // ss) for value in box) for name, box in self.buttons.items()}
        return img

    def _shadow_layer(self, w: int, h: int, pill, radius: int, s: float, ease: float) -> Image.Image:
        pill_q = tuple(int(value) // 12 * 12 for value in pill)
        key = (w // 24, h // 24, pill_q, radius // 8, int(ease * 4))
        if key == self._shadow_key and self._shadow is not None:
            return self._shadow
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle(
            (pill[0], pill[1] + int(4 * s), pill[2], pill[3] + int(6 * s)),
            radius=radius,
            fill=(0, 0, 0, int(70 + 80 * ease)),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=max(1, min(8, int(2 + 3 * ease)))))
        self._shadow_key = key
        self._shadow = shadow
        return shadow

    def _draw_listen(self, draw: ImageDraw.ImageDraw, pill, s: float) -> None:
        x0, y0, x1, y1 = pill
        cy = (y0 + y1) / 2
        self._draw_bot(draw, x0 + int(52 * s), cy, s)
        title = _font("segoeuib.ttf", 26 * s)
        sub = _font("segoeui.ttf", 18 * s)
        draw.text((x0 + int(108 * s), cy - int(16 * s)), "Kai", font=title, fill=(255, 255, 255, 245))
        bars_x = x1 - int(150 * s)
        text_x = x0 + int(178 * s)
        subtitle = _fit(draw, self.subtitle, sub, max(20, bars_x - text_x - int(10 * s)))
        draw.text((text_x, cy - int(13 * s)), subtitle, font=sub, fill=(174, 174, 184, 255))
        if self.permit:
            self._permit_buttons(draw, bars_x, cy, s)
        else:
            self._bars(draw, bars_x, cy, s)

    def _permit_buttons(self, draw: ImageDraw.ImageDraw, x: float, cy: float, s: float) -> None:
        font = _font("segoeuib.ttf", 14 * s)
        gap = int(8 * s)
        width = int(118 * s)
        height = int(40 * s)
        for index, (name, label, fill) in enumerate((
        ("allow", "Allow", (30, 160, 90, 255)),
        ("deny", "Not allow", (160, 48, 48, 255)),
        )):
            left = x + index * (width + gap)
            top = cy - height / 2
            box = (left, top, left + width, top + height)
            draw.rounded_rectangle(box, radius=int(12 * s), fill=fill)
            draw.text((left + width / 2, cy), label, font=font, fill=(255, 255, 255, 255), anchor="mm")
            self.buttons[name] = (int(box[0]), int(box[1]), int(box[2]), int(box[3]))

    def _idle_dot(self, draw: ImageDraw.ImageDraw, pill, s: float, alpha: int) -> None:
        cx = (pill[0] + pill[2]) / 2
        cy = (pill[1] + pill[3]) / 2
        radius = max(2.0, 3.4 * s)
        glow = int(alpha * 0.35)
        draw.ellipse((cx - radius * 2.1, cy - radius * 2.1, cx + radius * 2.1, cy + radius * 2.1), fill=(53, 184, 255, glow))
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(53, 184, 255, alpha))

    def _gaze(self, cx: float, cy: float, reach: float) -> tuple[float, float]:
        from watch import cursor_pos

        px, py = cursor_pos()
        ox, oy = self.origin
        dx = (px - ox) * self._ss - cx
        dy = (py - oy) * self._ss - cy
        dist = math.hypot(dx, dy) or 1.0
        return dx / dist * reach, dy / dist * reach

    def _chat_scale(self, s: float) -> float:
        return s * max(1.0, min(1.5, self.size_percent / 100.0 + 0.5))

    def _chat_layout(self, s: float) -> tuple[int, int, list]:
        if self.mode == "media" or not self.chat or not (self.you.strip() or self.kai_line.strip() or self.typing):
            return 0, 0, []
        cs = self._chat_scale(s)
        width = int(440 * cs)
        pad = int(12 * cs)
        avatar = int(34 * cs)
        bubble_max = int(width * 0.8)
        bx, by = int(14 * cs), int(9 * cs)
        line_h = int(21 * cs)
        probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
        body = _font("segoeui.ttf", 15 * cs)
        rows = []
        height = pad
        you = self.you.strip()
        if you:
            lines = _wrap(probe, you, body, bubble_max - 2 * bx)[:3]
            text_w = max(probe.textlength(line, font=body) for line in lines)
            bw = int(text_w + 2 * bx)
            bh = len(lines) * line_h + 2 * by
            rows.append(("you", lines, bw, bh))
            height += bh + int(8 * cs)
        kai = self.kai_line.strip()
        if kai or self.typing:
            if kai:
                lines = _wrap(probe, kai, body, bubble_max - avatar - 2 * bx)
                if len(lines) > 9:
                    lines = lines[:9]
                    lines[-1] = _fit(probe, lines[-1] + " …", body, bubble_max - avatar - 2 * bx)
                text_w = max(probe.textlength(line, font=body) for line in lines)
                bw = int(text_w + 2 * bx)
                bh = len(lines) * line_h + 2 * by
            else:
                lines = []
                bw, bh = int(62 * cs), line_h + 2 * by
            rows.append(("kai", lines, bw, bh))
            height += bh + int(8 * cs)
        height += pad - int(8 * cs)
        return width, height, rows

    def _paint_chat(self, img: Image.Image, canvas_w: int, y: int, chat_w: int, rows: list, s: float) -> Image.Image:
        cs = self._chat_scale(s)
        x0 = (canvas_w - chat_w) // 2
        pad = int(12 * cs)
        bx, by = int(14 * cs), int(9 * cs)
        line_h = int(21 * cs)
        avatar = int(34 * cs)
        body = _font("segoeui.ttf", 15 * cs)
        y1 = y + pad + sum(bh + int(8 * cs) for *_, bh in rows) - int(8 * cs) + pad
        key = (img.size, x0, y, y1)
        if self._chat_shadow[0] != key:
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(layer)
            shadow_draw.rounded_rectangle((x0, y + int(4 * s), x0 + chat_w, y1 + int(6 * s)), radius=int(24 * cs), fill=(0, 0, 0, 120))
            self._chat_shadow = (key, layer.filter(ImageFilter.GaussianBlur(radius=max(1, int(7 * s)))))
        img = Image.alpha_composite(img, self._chat_shadow[1])
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle(
            (x0, y, x0 + chat_w, y1),
            radius=int(24 * cs),
            fill=(13, 13, 17, 240),
            outline=(255, 255, 255, 24),
            width=max(1, int(s)),
        )
        cursor = y + pad
        for who, lines, bw, bh in rows:
            if who == "you":
                right = x0 + chat_w - pad
                box = (right - bw, cursor, right, cursor + bh)
                draw.rounded_rectangle(box, radius=int(17 * cs), fill=(28, 132, 230, 255))
                ty = cursor + by
                for line in lines:
                    draw.text((box[0] + bx, ty), line, font=body, fill=(255, 255, 255, 255))
                    ty += line_h
            else:
                left = x0 + pad
                self._mini_bot(draw, left + avatar / 2 - int(2 * cs), cursor + int(17 * cs), cs)
                box = (left + avatar, cursor, left + avatar + bw, cursor + bh)
                draw.rounded_rectangle(box, radius=int(17 * cs), fill=(38, 38, 46, 255))
                if lines:
                    ty = cursor + by
                    for line in lines:
                        draw.text((box[0] + bx, ty), line, font=body, fill=(242, 242, 246, 255))
                        ty += line_h
                else:
                    mid = (box[1] + box[3]) / 2
                    for i in range(3):
                        lift = max(0.0, math.sin(self.tick * 0.35 - i * 0.9)) * 4 * cs
                        dot = 3.6 * cs
                        dx = box[0] + bx + int(4 * cs) + i * int(12 * cs)
                        shade = int(140 + 100 * (lift / (4 * cs)))
                        draw.ellipse((dx - dot, mid - lift - dot, dx + dot, mid - lift + dot), fill=(shade, shade, shade + 8, 255))
            cursor += bh + int(8 * cs)
        return img

    def _mini_bot(self, draw: ImageDraw.ImageDraw, cx: float, cy: float, s: float) -> None:
        radius = 10 * s
        for ox, oy in ((0, -0.55), (0, 0.55), (-0.55, 0), (0.55, 0)):
            draw.ellipse(
                (cx + ox * radius - radius * 0.72, cy + oy * radius - radius * 0.72, cx + ox * radius + radius * 0.72, cy + oy * radius + radius * 0.72),
                fill=(53, 184, 255, 255),
            )
        eye = max(1.5, radius * 0.26)
        for side in (-1, 1):
            ex = cx + side * radius * 0.32
            draw.ellipse((ex - eye, cy - eye, ex + eye, cy + eye), fill=(6, 18, 40, 255))

    def _cover_image(self, cover, side: int, radius: int) -> Image.Image:
        key, cached = self._cover_cache
        want = (id(cover), side, radius)
        if key == want and cached is not None:
            return cached
        if cover is not None:
            tile = cover.convert("RGB").resize((side, side), Image.LANCZOS).convert("RGBA")
        else:
            tile = Image.new("RGBA", (side, side), (40, 40, 52, 255))
            td = ImageDraw.Draw(tile)
            for i in range(side):
                shade = int(60 + 60 * i / max(1, side))
                td.line((0, i, side, i), fill=(shade // 2, shade // 2, shade, 255))
            note = _font("segoeuib.ttf", side * 0.45)
            td.text((side / 2, side / 2), "♪", font=note, fill=(255, 255, 255, 220), anchor="mm")
        mask = Image.new("L", (side, side), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, side - 1, side - 1), radius=radius, fill=255)
        tile.putalpha(mask)
        self._cover_cache = (want, tile)
        return tile

    def _draw_media(self, overlay: Image.Image, draw: ImageDraw.ImageDraw, pill, s: float, live: bool) -> None:
        snap = self.media() if callable(self.media) else None
        x0, y0, x1, y1 = pill
        pad = int(20 * s)
        side = max(8, (y1 - y0) - 2 * pad)
        tile = self._cover_image(snap.get("cover") if snap else None, side, int(22 * s))
        overlay.alpha_composite(tile, (int(x0 + pad), int(y0 + pad)))
        tx = int(x0 + pad + side + 22 * s)
        rx = int(x1 - 28 * s)
        top = y0 + pad

        green = (30, 215, 96, 255)
        label = _font("segoeuib.ttf", 13 * s)
        draw.ellipse((tx, top + 5 * s, tx + 9 * s, top + 14 * s), fill=green)
        playing = bool(snap and snap.get("playing"))
        draw.text((tx + 15 * s, top), t("now_playing") if playing else "Spotify", font=label, fill=green)

        title_font = _font("segoeuib.ttf", 25 * s)
        artist_font = _font("segoeui.ttf", 17 * s)
        controls_w = int(150 * s)
        text_room = max(20, rx - controls_w - tx)
        title = (snap.get("title") if snap else "") or t("nothing_playing")
        artist = (snap.get("artist") if snap else "") or "Spotify"
        draw.text((tx, top + 22 * s), _fit(draw, title, title_font, text_room), font=title_font, fill=(255, 255, 255, 255))
        draw.text((tx, top + 58 * s), _fit(draw, artist, artist_font, text_room), font=artist_font, fill=(168, 168, 180, 255))

        cy = top + 46 * s
        play_r = 24 * s
        play_cx = rx - controls_w / 2
        prev_cx = play_cx - 56 * s
        next_cx = play_cx + 56 * s
        draw.ellipse((play_cx - play_r, cy - play_r, play_cx + play_r, cy + play_r), fill=(255, 255, 255, 255))
        dark = (10, 10, 14, 255)
        if playing:
            bar_w, bar_h = 5 * s, 16 * s
            for dx in (-6 * s, 6 * s):
                draw.rounded_rectangle(
                    (play_cx + dx - bar_w / 2, cy - bar_h / 2, play_cx + dx + bar_w / 2, cy + bar_h / 2),
                    radius=int(2 * s),
                    fill=dark,
                )
        else:
            tri = 10 * s
            draw.polygon([(play_cx - tri * 0.7, cy - tri), (play_cx - tri * 0.7, cy + tri), (play_cx + tri, cy)], fill=dark)
        icon = (235, 235, 240, 255)
        for cx_, sign in ((prev_cx, -1), (next_cx, 1)):
            size = 8 * s
            for k in (0, 1):
                base = cx_ + sign * (k * size - size * 0.5)
                draw.polygon(
                    [(base - sign * size * 0.5, cy - size), (base - sign * size * 0.5, cy + size), (base + sign * size * 0.5, cy)],
                    fill=icon,
                )
            edge = cx_ + sign * size * 1.0
            draw.rounded_rectangle((edge - 1.5 * s, cy - size, edge + 1.5 * s, cy + size), radius=int(1 * s), fill=icon)
        if live:
            hit = 26 * s
            for name, bx in (("prev", prev_cx), ("toggle", play_cx), ("next", next_cx)):
                self.buttons[name] = (int(bx - hit), int(cy - hit), int(bx + hit), int(cy + hit))

        time_font = _font("segoeui.ttf", 13 * s)
        position = snap.get("position", 0.0) if snap else 0.0
        duration = snap.get("duration", 0.0) if snap else 0.0
        bar_y = y1 - pad - 8 * s
        left_txt = _clock(position)
        right_txt = "-" + _clock(max(0.0, duration - position)) if duration else "0:00"
        lw = draw.textlength("00:00", font=time_font)
        bar_l = tx + lw + 10 * s
        bar_r = rx - lw - 10 * s
        draw.text((tx, bar_y - 9 * s), left_txt, font=time_font, fill=(150, 150, 162, 255))
        draw.text((rx, bar_y - 9 * s), right_txt, font=time_font, fill=(150, 150, 162, 255), anchor="ra")
        thick = max(3, int(5 * s))
        draw.rounded_rectangle((bar_l, bar_y - thick / 2, bar_r, bar_y + thick / 2), radius=thick // 2, fill=(255, 255, 255, 48))
        frac = max(0.0, min(1.0, position / duration)) if duration else 0.0
        if frac > 0:
            draw.rounded_rectangle(
                (bar_l, bar_y - thick / 2, bar_l + max(thick, (bar_r - bar_l) * frac), bar_y + thick / 2),
                radius=thick // 2,
                fill=(255, 255, 255, 235),
            )
        history = self.played() if callable(self.played) else []
        if len(history) > 1:
            small = _font("segoeui.ttf", 13 * s)
            y = top + 84 * s
            room = max(20, rx - controls_w - tx)
            for line in history[-4:]:
                if y > bar_y - 18 * s:
                    break
                draw.text((tx, y), _fit(draw, line, small, room), font=small, fill=(150, 150, 162, 255))
                y += 16 * s

    def _draw_diff(self, draw: ImageDraw.ImageDraw, pill, s: float) -> None:
        x0, y0, x1, y1 = pill
        self._draw_bot(draw, x0 + 52 * s, (y0 + y1) / 2, s * 1.05)
        head = _font("segoeuib.ttf", 20 * s)
        mono = _font("consola.ttf", 14 * s)
        label = self.subtitle or t("code")
        draw.text((x0 + 108 * s, y0 + 14 * s), label, font=head, fill=(255, 255, 255, 245))
        top = y0 + 48 * s
        bottom = y1 - 14 * s
        left = x0 + 108 * s
        width = max(40, x1 - left - 16 * s)
        for kind, text, born in self.diff_rows:
            y = top + (self.tick - born) * 1.35 * s
            if y < top or y > bottom:
                continue
            color = (88, 214, 136, 255) if kind == "+" else (255, 96, 104, 255)
            mark = "+ " if kind == "+" else "- "
            draw.text((left, y), _fit(draw, mark + text, mono, width), font=mono, fill=color)

    def _draw_bot(self, draw: ImageDraw.ImageDraw, cx: float, cy: float, s: float, gaze: bool = False) -> None:
        dizzy = self.tick < self.dizzy_until
        cheer = self.tick < self.cheer_until
        bob = abs(math.sin(self.tick * 0.5)) * (7 * s) if cheer else math.sin(self.tick * (0.9 if dizzy else 0.55 if self.busy else 0.18)) * ((3.2 if dizzy else 2.4 if self.busy else 0.8) * s)
        cy -= bob
        radius = 16.5 * s * (1.16 if cheer else 1.08 if self.greet_ticks > 0 else 1.0)
        cy += self.motion.oy * radius
        sx = self.motion.sx
        sy = max(0.2, self.motion.sy)
        body = (53, 184, 255, 255)
        for ox, oy in ((0, -0.55), (0, 0.55), (-0.55, 0), (0.55, 0)):
            rx = radius * 0.72 * sx
            ry = radius * 0.72 * sy
            draw.ellipse(
                (cx + ox * radius * sx - rx, cy + oy * radius * sy - ry, cx + ox * radius * sx + rx, cy + oy * radius * sy + ry),
                fill=body,
            )
        blink = self.tick < self._blink_until and not dizzy
        if abs(self.motion.roll) > 0.08:
            look = math.cos(self.motion.roll) * radius * 0.22
            look_y = math.sin(self.motion.roll) * radius * 0.22
        elif dizzy:
            spin = self.tick * 0.45
            look = math.cos(spin) * radius * 0.22
            look_y = math.sin(spin) * radius * 0.22
        elif gaze:
            look, look_y = self._gaze(cx, cy, radius * 0.18)
        else:
            look = math.sin(self.tick * (0.42 if self.busy else 0.1)) * (radius * (0.12 if self.busy else 0.05))
            look_y = -radius * 0.16 if cheer or self.greet_ticks > 0 else 0.0
        eye = max(2.0, radius * (0.34 if gaze or self.greet_ticks else 0.28))
        eye_h = max(1.0, eye * (0.18 if blink else 1.0))
        for side in (-1, 1):
            ex = cx + side * radius * 0.32 + look
            ey = cy + look_y * sy
            draw.ellipse((ex - eye, ey - eye_h, ex + eye, ey + eye_h), fill=(6, 18, 40, 255))

    def wake_zone(self) -> tuple[int, int, int, int]:
        cx, top, _width = monitor_top_center()
        if self.looking or self.look_shown > 0.15:
            return (cx - 210, top, cx + 210, top + 110)
        return (cx - 120, top, cx + 120, top + 22)

    def _draw_pills(self, img: Image.Image, pill, s: float, look: float) -> None:
        draw = ImageDraw.Draw(img)
        font = _font("segoeuib.ttf", max(10, 11 * s))
        x = pill[0] + (pill[2] - pill[0]) * 0.46
        cy = (pill[1] + pill[3]) / 2
        alpha = int(255 * min(1.0, look))
        for name, color in self.pills[:3]:
            text = name[:18]
            tw = int(draw.textlength(text, font=font)) + int(22 * s)
            th = int(26 * s)
            y = cy - th / 2
            draw.rounded_rectangle((x, y, x + tw, y + th), radius=th / 2, fill=color + (alpha,))
            draw.text((x + int(10 * s), y + int(4 * s)), text, font=font, fill=(8, 10, 16, alpha))
            x += tw + int(8 * s)

    def _bars(self, draw: ImageDraw.ImageDraw, x: float, cy: float, s: float) -> None:
        amp = 0.18 + self.smooth * 0.82
        for i in range(7):
            wave = abs(math.sin(self.tick * 0.34 + i * 0.72))
            bh = (8 + wave * 36 * amp) * s
            bw = max(2, int(3 * s))
            gap = int(6 * s)
            left = x + i * (bw + gap)
            draw.rounded_rectangle(
                (left, cy - bh / 2, left + bw, cy + bh / 2),
                radius=bw // 2,
                fill=(255, 255, 255, 230),
            )

    def _draw_music(self, draw: ImageDraw.ImageDraw, pill, s: float) -> None:
        x0, y0, x1, y1 = pill
        pad = int(12 * s)
        cover = int(52 * s)
        cy0 = y0 + ( (y1 - y0) - cover) / 2
        box = (x0 + pad, cy0, x0 + pad + cover, cy0 + cover)
        draw.rounded_rectangle(box, radius=int(12 * s), fill=(94, 92, 214, 255))
        draw.ellipse(
            (box[0] + int(14 * s), box[1] + int(14 * s), box[2] - int(14 * s), box[3] - int(14 * s)),
            outline=(255, 255, 255, 230),
            width=max(2, int(2 * s)),
        )
        title = _font("segoeuib.ttf", 16 * s)
        sub = _font("segoeui.ttf", 12 * s)
        tx = box[2] + int(12 * s)
        draw.text((tx, y0 + int(14 * s)), "Gece", font=title, fill=(255, 255, 255, 245))
        draw.text((tx, y0 + int(36 * s)), "Kai", font=sub, fill=(174, 174, 184, 255))
        bar_y = y1 - int(18 * s)
        bar_r = x1 - int(16 * s)
        draw.rounded_rectangle((tx, bar_y, bar_r, bar_y + int(4 * s)), radius=int(2 * s), fill=(255, 255, 255, 40))
        progress = (self.tick % 220) / 220
        draw.rounded_rectangle(
            (tx, bar_y, tx + max(6, (bar_r - tx) * progress), bar_y + int(4 * s)),
            radius=int(2 * s),
            fill=(255, 255, 255, 230),
        )

    def _blit(self, image: Image.Image) -> None:
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
        info.biCompression = 0
        info.biSizeImage = width * height * 4
        bits = ctypes.c_void_p()
        bitmap = gdi32.CreateDIBSection(hdc_screen, ctypes.byref(info), 0, ctypes.byref(bits), None, 0)
        if not bitmap or not bits:
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(0, hdc_screen)
            return
        ctypes.memmove(bits, raw, len(raw))
        old = gdi32.SelectObject(hdc_mem, bitmap)

        cx, top, _ = monitor_top_center()
        origin = POINT(int(cx - width / 2), int(top + 1 * self.scale))
        size = SIZE(width, height)
        src = POINT(0, 0)
        blend = BLENDFUNCTION(0, 0, 255, AC_SRC_ALPHA)
        user32.UpdateLayeredWindow(
            self.hwnd, hdc_screen, ctypes.byref(origin), ctypes.byref(size),
            hdc_mem, ctypes.byref(src), 0, ctypes.byref(blend), ULW_ALPHA,
        )
        self.raise_top()
        gdi32.SelectObject(hdc_mem, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)

    def destroy(self) -> None:
        if self.hwnd:
            user32.KillTimer(self.hwnd, 1)
            user32.KillTimer(self.hwnd, 2)
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
