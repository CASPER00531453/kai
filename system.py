"""Control the computer itself: volume, brightness, lock, sleep, shutdown.

Everything here acts on this PC only, with the tools Windows already ships —
no extra packages. Replies come back as i18n keys filled by the caller.
"""

from __future__ import annotations

import ctypes
import subprocess

from i18n import t

CREATE_NO_WINDOW = 0x08000000

_user32 = ctypes.windll.user32

# Virtual-key codes for the media keys, pressed the same way the keyboard does.
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
KEYEVENTF_KEYUP = 0x0002


def _tap(vk: int, times: int = 1) -> None:
    for _ in range(times):
        _user32.keybd_event(vk, 0, 0, 0)
        _user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def _powershell(script: str, timeout: float = 8) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception:
        return None


# ── Volume ────────────────────────────────────────────────────────────────────

def volume_up() -> str:
    _tap(VK_VOLUME_UP, 5)   # ~10%
    return t("sys.vol_up")


def volume_down() -> str:
    _tap(VK_VOLUME_DOWN, 5)
    return t("sys.vol_down")


def volume_mute() -> str:
    _tap(VK_VOLUME_MUTE)
    return t("sys.vol_mute")


# ── Brightness (laptops) ───────────────────────────────────────────────────────

def _brightness_now() -> int | None:
    done = _powershell("(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness")
    try:
        return int((done.stdout or "").strip().splitlines()[0])
    except (AttributeError, ValueError, IndexError):
        return None


def brightness_set(level: int) -> str:
    level = max(0, min(100, int(level)))
    done = _powershell(
        f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level})"
    )
    if done is None or done.returncode != 0:
        return t("sys.no_brightness")
    return t("sys.brightness", level=level)


def brightness_step(delta: int) -> str:
    now = _brightness_now()
    if now is None:
        return t("sys.no_brightness")
    return brightness_set(now + delta)


# ── Session and power ───────────────────────────────────────────────────────────

def lock() -> str:
    _user32.LockWorkStation()
    return t("sys.locked")


def sleep() -> str:
    # False = sleep (not hibernate), True = force, False = no wake events disabled.
    ctypes.windll.powrprof.SetSuspendState(False, True, False)
    return t("sys.sleeping")


def _schedule(flag: str, minutes: int) -> None:
    subprocess.run(
        ["shutdown", flag, "/t", str(max(0, int(minutes * 60)))],
        creationflags=CREATE_NO_WINDOW,
        capture_output=True,
    )


def shutdown(minutes: int = 0) -> str:
    _schedule("/s", minutes)
    return t("sys.shutdown_now") if minutes <= 0 else t("sys.shutdown_in", minutes=minutes)


def restart(minutes: int = 0) -> str:
    _schedule("/r", minutes)
    return t("sys.restart_now") if minutes <= 0 else t("sys.restart_in", minutes=minutes)


def cancel_power() -> str:
    done = subprocess.run(["shutdown", "/a"], creationflags=CREATE_NO_WINDOW, capture_output=True)
    # /a returns non-zero when nothing was scheduled.
    return t("sys.power_cancelled") if done.returncode == 0 else t("sys.nothing_scheduled")


# ── Dispatch ────────────────────────────────────────────────────────────────────

def run(act: str, arg: int = 0) -> str:
    actions = {
        "vol_up": volume_up,
        "vol_down": volume_down,
        "vol_mute": volume_mute,
        "bright_up": lambda: brightness_step(20),
        "bright_down": lambda: brightness_step(-20),
        "bright_set": lambda: brightness_set(arg),
        "lock": lock,
        "sleep": sleep,
        "shutdown": lambda: shutdown(arg),
        "restart": lambda: restart(arg),
        "cancel": cancel_power,
    }
    handler = actions.get(act)
    if handler is None:
        return ""
    try:
        return handler()
    except Exception:
        return t("sys.failed")
