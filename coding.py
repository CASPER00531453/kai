"""Show code that a local editor just added or removed. Read-only git diff."""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import urllib.parse
from ctypes import wintypes
import ctypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
]

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
CREATE_NO_WINDOW = 0x08000000
THINKING = ("thinking", "generating", "düşünüyor", "dusunuyor")
CODING_EXE = {"cursor.exe", "code.exe", "codex.exe", "claude.exe"}


def _coding_kind(exe: str, title: str) -> str:
    """Real editor apps only. A window that merely mentions Claude does not count."""
    exe = (exe or "").lower()
    if exe in CODING_EXE:
        if exe == "claude.exe":
            return "claude"
        if exe == "codex.exe":
            return "codex"
        if exe == "cursor.exe":
            return "cursor"
        return "code"
    low = (title or "").strip().lower()
    if exe in {"windowsterminal.exe", "node.exe"}:
        if low.startswith("claude code") or low == "claude code":
            return "claude-code"
        if low.startswith("codex"):
            return "codex"
    return ""


def _front() -> tuple[str, str]:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "", ""
    title_buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, title_buf, 512)
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    exe = ""
    if pid.value:
        process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if process:
            try:
                size = wintypes.DWORD(512)
                buf = ctypes.create_unicode_buffer(512)
                if kernel32.QueryFullProcessImageNameW(process, 0, buf, ctypes.byref(size)):
                    exe = os.path.basename(buf.value).lower()
            finally:
                kernel32.CloseHandle(process)
    return exe, title_buf.value or ""


def _uri_path(uri: str) -> str:
    if not uri.startswith("file:"):
        return ""
    path = urllib.parse.unquote(uri[5:])
    path = path.lstrip("/")
    if len(path) >= 3 and path[1] == ":":
        path = path[0] + ":" + path[2:].replace("/", "\\")
    return path if os.path.isdir(path) else ""


def _storage_roots() -> list[str]:
    found = []
    for app in ("Cursor", "Code"):
        path = os.path.expandvars(rf"%APPDATA%\{app}\User\globalStorage\storage.json")
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        folders = (data.get("backupWorkspaces") or {}).get("folders") or []
        for item in folders:
            folder = _uri_path(str(item.get("folderUri") or ""))
            if folder:
                found.append(folder)
    return found


def _git_root(path: str) -> str:
    cur = os.path.abspath(path)
    for _ in range(8):
        if os.path.isdir(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return ""


def _repo(title: str) -> str:
    for match in re.finditer(r"[A-Za-z]:\\[^\"\n\r]+", title or ""):
        raw = match.group(0).strip().rstrip(" .)")
        if os.path.isfile(raw):
            raw = os.path.dirname(raw)
        root = _git_root(raw) if os.path.isdir(raw) else ""
        if root:
            return root
    for folder in _storage_roots():
        root = _git_root(folder)
        if root:
            return root
    return ""


def _diff(root: str) -> list[tuple[str, str]]:
    try:
        done = subprocess.run(
            ["git", "-C", root, "diff", "-U0", "--no-color", "--", ".", ":!*.lock", ":!package-lock.json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=4,
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    rows = []
    for line in (done.stdout or "").splitlines():
        if line.startswith(("+++", "---", "diff ", "index ", "@@")):
            continue
        if line.startswith("+") and line[1:].strip():
            rows.append(("+", line[1:].strip()[:90]))
        elif line.startswith("-") and line[1:].strip():
            rows.append(("-", line[1:].strip()[:90]))
        if len(rows) >= 30:
            break
    return rows


class DiffWatch:
    def __init__(self, on_event) -> None:
        self.on_event = on_event
        self._stop = threading.Event()
        self._prev: list[tuple[str, str]] = []
        self._root = ""
        self._primed = False
        self._dirty = 0.0
        self._thinking = False
        self._worked = False
        self._think_ping = 0.0

    def start(self) -> None:
        threading.Thread(target=self._run, name="kai-diff", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(1.0):
            try:
                self._tick()
            except Exception:
                pass

    def _tick(self) -> None:
        exe, title = _front()
        kind = _coding_kind(exe, title)
        if not kind:
            self._finish_if_idle()
            return
        root = _repo(title) if kind in {"cursor", "code"} else ""
        if not root and kind in {"cursor", "code"}:
            for folder in _storage_roots():
                root = _git_root(folder)
                if root:
                    break
        if root != self._root:
            self._root = root
            self._prev = []
            self._primed = bool(root)
        if not root:
            self._finish_if_idle()
            return
        if not self._primed:
            self._prev = []
            self._primed = True
        lines = _diff(root)
        fresh = [row for row in lines if row not in self._prev]
        self._prev = lines
        title_think = any(word in title.lower() for word in THINKING)
        if fresh:
            self._dirty = time.time()
            self._worked = True
            self.on_event("lines", fresh[:20])
        thinking = title_think or (self._worked and time.time() - self._dirty < 3.0)
        if thinking and (not self._thinking or time.time() - self._think_ping > 5):
            self.on_event("thinking", None)
            self._think_ping = time.time()
        self._thinking = thinking
        self._finish_if_idle()

    def _finish_if_idle(self) -> None:
        if self._worked and not self._thinking and self._dirty and time.time() - self._dirty > 3.2:
            self._worked = False
            self._thinking = False
            self.on_event("done", None)
