"""Low-level keyboard hook. Watches AltGr without eating the key."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
LLKHF_UP = 0x80
VK_RMENU = 0xA5

MODIFIERS = {
    0x10, 0x11, 0x12,
    0xA0, 0xA1,  # shift
    0xA2, 0xA3,  # ctrl (AltGr also injects left ctrl)
    0xA4, 0xA5,  # alt
    0x5B, 0x5C,  # win
    0x5D,
    0x14,  # caps
}

if ctypes.sizeof(ctypes.c_void_p) == 8:
    LRESULT = ctypes.c_longlong
else:
    LRESULT = ctypes.c_long

HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL


VK_ESCAPE = 0x1B
# The dictation key: held to dictate, tapped twice to dictate hands-free. Each
# choice is the keys held together; "ctrlwin" takes either Ctrl with either Win.
DICTATION_KEYS = {
    "rctrl": (0xA3,), "rshift": (0xA1,), "ctrlwin": (-1,),
    "lctrl": (0xA2,), "lshift": (0xA0,), "lalt": (0xA4,),
}
# AltGr is Kai's own talk key: never part of a dictation shortcut.
NOT_IN_SHORTCUT = {VK_RMENU}
# The left Ctrl Windows sends ahead of every AltGr: not a Ctrl the user pressed.
ALTGR_CTRL_SCAN = 0x21D
VK_MASK = 0xE8  # unassigned: tapped so a held Alt or Win opens no menu when let go


def parse_keys(value: str) -> tuple[int, ...] | None:
    """A preset's keys, or a shortcut of one's own: "keys:12+10+46" (virtual keys, hex), up to four."""
    if value in DICTATION_KEYS:
        return DICTATION_KEYS[value]
    if not str(value).startswith("keys:"):
        return None
    try:
        keys = tuple(int(part, 16) for part in value[5:].split("+") if part)
    except ValueError:
        return None
    if not 1 <= len(keys) <= 4 or len(set(keys)) != len(keys) or any(k in NOT_IN_SHORTCUT or not 0 < k < 0xFF for k in keys):
        return None
    return keys


def _same(vk: int, want: int) -> bool:
    """A shortcut recorded as "Ctrl" or "Shift" takes either side."""
    sides = {0x11: (0xA2, 0xA3), 0x10: (0xA0, 0xA1), 0x12: (0xA4, 0xA5)}
    return vk == want or vk in sides.get(want, ())


class AltGrHook:
    def __init__(self, hwnd: int, on_down: int, on_up: int, on_other: int, dictation: tuple[int, int, int] | None = None) -> None:
        self.hwnd = hwnd
        self.on_down = on_down
        self.on_up = on_up
        self.on_other = on_other
        # (key down, key up, Escape) messages for dictation; the key is set by `dictation_key`.
        self.dictation = dictation
        self.dictation_key = ""
        self._held = False
        self._ctrl = False
        self._win = False
        # The keys down right now, for a shortcut of several keys.
        self._down: set[int] = set()
        self._proc = HOOKPROC(self._callback)
        self.hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, None, 0)
        if not self.hook:
            raise OSError(f"klavye kancası kurulamadı ({ctypes.get_last_error()})")

    def _dictation(self, vk: int, is_up: bool) -> None:
        down_msg, up_msg, esc_msg = self.dictation
        if vk == VK_ESCAPE and not is_up:
            user32.PostMessageW(self.hwnd, esc_msg, 0, 0)
            return
        keys = parse_keys(self.dictation_key)
        if keys is None:
            return
        if keys == (-1,):
            if vk in (0xA2, 0xA3, 0x11):
                self._ctrl = not is_up
            elif vk in (0x5B, 0x5C):
                self._win = not is_up
            else:
                return
            pressed = self._ctrl and self._win
        else:
            if not any(_same(vk, k) for k in keys):
                return
            if is_up:
                self._down.discard(vk)
            else:
                self._down.add(vk)
            pressed = all(any(_same(d, k) for d in self._down) for k in keys)
            if pressed and not self._held and any(k in (0xA4, 0xA5, 0x12, 0x5B, 0x5C) for k in keys):
                # Letting go of a held Alt or Win would open a menu: a key nobody uses masks it.
                user32.keybd_event(VK_MASK, 0, 0, 0)
                user32.keybd_event(VK_MASK, 0, 2, 0)
        # Held keys repeat their key-down; only the change is news.
        if pressed != self._held:
            self._held = pressed
            user32.PostMessageW(self.hwnd, down_msg if pressed else up_msg, 0, 0)

    def _callback(self, n_code, w_param, l_param):
        if n_code >= 0:
            try:
                kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                is_up = bool(kb.flags & LLKHF_UP) or w_param in (WM_KEYUP, WM_SYSKEYUP)
                vk = int(kb.vkCode)
                # Keys Kai types itself (the paste) are not the user's.
                injected = bool(kb.flags & 0x10)
                # The left Ctrl that comes with AltGr is not the user's Ctrl.
                fake_ctrl = vk == 0xA2 and kb.scanCode == ALTGR_CTRL_SCAN
                if self.dictation and not injected and not fake_ctrl:
                    self._dictation(vk, is_up)
                    # A shortcut's own letter (Alt+Shift+F, F9) is kept from the app in front.
                    if self._swallows(vk):
                        return 1
                if vk == VK_RMENU:
                    msg = self.on_up if is_up else self.on_down
                    user32.PostMessageW(self.hwnd, msg, 0, 0)
                elif not is_up and vk not in MODIFIERS and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN) and not self._in_shortcut(vk):
                    user32.PostMessageW(self.hwnd, self.on_other, vk, 0)
            except Exception:
                pass
        return user32.CallNextHookEx(self.hook, n_code, w_param, l_param)

    def _in_shortcut(self, vk: int) -> bool:
        """A key of the dictation shortcut itself is no "other key" that cancels it."""
        keys = parse_keys(self.dictation_key) if self.dictation else None
        return bool(keys) and keys != (-1,) and any(_same(vk, k) for k in keys)

    def _swallows(self, vk: int) -> bool:
        keys = parse_keys(self.dictation_key)
        if not keys or keys == (-1,) or vk in MODIFIERS:
            return False
        if not any(_same(vk, k) for k in keys):
            return False
        # Only while the rest of the shortcut is held, or the key could never be typed.
        rest = [k for k in keys if not _same(vk, k)]
        return all(any(_same(d, k) for d in self._down) for k in rest)

    def close(self) -> None:
        if self.hook:
            user32.UnhookWindowsHookEx(self.hook)
            self.hook = None
