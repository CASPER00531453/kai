"""How the computer feels, as the mascot shows it. After coucou's MachineVitals.

A busy processor makes Kai sweat and hop, a warm machine flushes him, short
memory puffs him up, a low battery makes him tired, then asleep; plugging in
wakes him. Read by the island's poll at most every few seconds, from Windows'
own counters; nothing leaves the computer.
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

kernel32 = ctypes.windll.kernel32
kernel32.OpenProcess.restype = ctypes.c_void_p
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
kernel32.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.c_void_p] * 4
kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
kernel32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
kernel32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

EVERY = 3.0
HEAT_EVERY = 30.0
_state: dict = {"at": 0.0, "ticks": None, "cpu": 0.0, "busy_samples": 0, "mood": None, "procs": {},
                "top": [], "heat_at": 0.0, "celsius": None, "low": False}


class _Memory(ctypes.Structure):
    _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD), ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


class _Power(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte), ("BatteryLifePercent", ctypes.c_ubyte),
                ("SystemStatusFlag", ctypes.c_ubyte), ("BatteryLifeTime", wintypes.DWORD), ("BatteryFullLifeTime", wintypes.DWORD)]


class _Entry(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


def _cpu_ticks() -> tuple[int, int] | None:
    idle, kern, user = (ctypes.c_ulonglong() for _ in range(3))
    if not kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user)):
        return None
    total = kern.value + user.value  # kernel time includes idle time
    return total - idle.value, total


def _memory_load() -> int:
    status = _Memory()
    status.dwLength = ctypes.sizeof(_Memory)
    return int(status.dwMemoryLoad) if kernel32.GlobalMemoryStatusEx(ctypes.byref(status)) else 0


def _battery() -> tuple[int, bool] | None:
    """(percent, on power), or None for a computer without a battery."""
    power = _Power()
    if not kernel32.GetSystemPowerStatus(ctypes.byref(power)):
        return None
    if power.BatteryFlag & 128 or power.BatteryLifePercent > 100:
        return None
    return int(power.BatteryLifePercent), power.ACLineStatus == 1


def _celsius() -> float | None:
    """The warmest thermal zone Windows reports to anyone (no administrator needed)."""
    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        wmi = win32com.client.GetObject("winmgmts:root\\cimv2")
        rows = wmi.ExecQuery("SELECT Temperature FROM Win32_PerfFormattedData_Counters_ThermalZoneInformation")
        kelvin = max((int(row.Temperature or 0) for row in rows), default=0)
        return kelvin - 273.15 if kelvin > 200 else None
    except Exception:
        return None


def _top_processes() -> list[str]:
    """The two programs eating the most processor since the last look."""
    snap = kernel32.CreateToolhelp32Snapshot(2, 0)
    names: dict[int, str] = {}
    entry = _Entry()
    entry.dwSize = ctypes.sizeof(_Entry)
    try:
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            names[entry.th32ProcessID] = entry.szExeFile
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)
    now: dict[int, int] = {}
    for pid in names:
        process = kernel32.OpenProcess(0x1000, False, pid)
        if not process:
            continue
        try:
            times = [ctypes.c_ulonglong() for _ in range(4)]
            if kernel32.GetProcessTimes(process, *[ctypes.byref(t) for t in times]):
                now[pid] = times[2].value + times[3].value
        finally:
            kernel32.CloseHandle(process)
    last = _state["procs"]
    _state["procs"] = now
    used: dict[str, int] = {}
    for pid, spent in now.items():
        if pid in last and spent > last[pid]:
            name = names[pid].rsplit(".", 1)[0]
            used[name] = used.get(name, 0) + spent - last[pid]
    return [name for name, _ in sorted(used.items(), key=lambda item: -item[1])[:2]]


def _describe(mood: dict, cpu: float, battery, celsius, memory: int, turkish: bool) -> str:
    parts = []
    if mood["busy"] > 0:
        line = f"CPU %{round(cpu * 100)}" if turkish else f"CPU {round(cpu * 100)} %"
        parts.append(line + (" · " + ", ".join(_state["top"]) if _state["top"] else ""))
    if mood["hot"] > 0 and celsius:
        parts.append(f"{round(celsius)}°C")
    if mood["full"] > 0:
        parts.append((f"Bellek %{memory}" if turkish else f"Memory {memory} %"))
    if battery and not battery[1] and battery[0] < 20:
        parts.append((f"Pil %{battery[0]}" if turkish else f"Battery {battery[0]} %"))
    return " · ".join(parts)


def sample(turkish: bool = True) -> dict | None:
    """The mood, at most every EVERY seconds; None between two looks."""
    now = time.monotonic()
    if now - _state["at"] < EVERY:
        return None
    _state["at"] = now
    ticks = _cpu_ticks()
    last = _state["ticks"]
    if ticks and last and ticks[1] > last[1]:
        _state["cpu"] = (ticks[0] - last[0]) / (ticks[1] - last[1])
    _state["ticks"] = ticks
    cpu = _state["cpu"]
    # Two readings in a row above 80 %: a short spike does not make him sweat.
    _state["busy_samples"] = _state["busy_samples"] + 1 if cpu >= 0.8 else 0
    busy = _state["busy_samples"] >= 2
    if busy:
        _state["top"] = _top_processes()
    else:
        _state["procs"], _state["top"] = {}, []
    if now - _state["heat_at"] > HEAT_EVERY:
        _state["heat_at"] = now
        _state["celsius"] = _celsius()
    celsius = _state["celsius"]
    memory = _memory_load()
    battery = _battery()
    hot = 0.0
    if celsius is not None:
        hot = 1.0 if celsius >= 95 else 0.8 if celsius >= 85 else 0.4 if celsius >= 75 else 0.0
    mood = {
        "busy": round(min(1.0, max(0.0, (cpu - 0.6) / 0.3)), 2) if busy else 0.0,
        "hot": hot,
        "full": 1.0 if memory >= 95 else 0.6 if memory >= 88 else 0.0,
        "tired": 1.0 if battery and not battery[1] and battery[0] < 20 else 0.0,
        "asleep": bool(battery and not battery[1] and battery[0] < 10),
    }
    low = mood["tired"] > 0
    # Plugged in while tired: he wakes up.
    mood["woke"] = bool(_state["low"] and not low and battery and battery[1])
    _state["low"] = low
    mood["summary"] = _describe(mood, cpu, battery, celsius, memory, turkish)
    if mood == _state["mood"]:
        return None
    _state["mood"] = dict(mood)
    return mood
