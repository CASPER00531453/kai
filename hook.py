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
# The dictation key: held to dictate, tapped twice to dictate hands-free.
DICTATION_KEYS = {"rctrl": 0xA3, "rshift": 0xA1, "ctrlwin": -1}


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
        self._proc = HOOKPROC(self._callback)
        self.hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, None, 0)
        if not self.hook:
            raise OSError(f"klavye kancası kurulamadı ({ctypes.get_last_error()})")

    def _dictation(self, vk: int, is_up: bool) -> None:
        down_msg, up_msg, esc_msg = self.dictation
        if vk == VK_ESCAPE and not is_up:
            user32.PostMessageW(self.hwnd, esc_msg, 0, 0)
            return
        key = DICTATION_KEYS.get(self.dictation_key)
        if key is None:
            return
        if key == -1:
            if vk in (0xA2, 0xA3, 0x11):
                self._ctrl = not is_up
            elif vk in (0x5B, 0x5C):
                self._win = not is_up
            else:
                return
            pressed = self._ctrl and self._win
        elif vk == key:
            pressed = not is_up
        else:
            return
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
                if self.dictation and not injected:
                    self._dictation(vk, is_up)
                if vk == VK_RMENU:
                    msg = self.on_up if is_up else self.on_down
                    user32.PostMessageW(self.hwnd, msg, 0, 0)
                elif not is_up and vk not in MODIFIERS and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    user32.PostMessageW(self.hwnd, self.on_other, vk, 0)
            except Exception:
                pass
        return user32.CallNextHookEx(self.hook, n_code, w_param, l_param)

    def close(self) -> None:
        if self.hook:
            user32.UnhookWindowsHookEx(self.hook)
            self.hook = None
