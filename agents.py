"""Claude Code hooks and the optional service checks. Kai's own names, no borrowed character."""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
import urllib.request

from i18n import t

MARKER = "kai_hook"
EVENTS = (
    ("SessionStart", 10),
    ("SessionEnd", 10),
    ("UserPromptSubmit", 10),
    ("PreToolUse", 10),
    ("PostToolUse", 10),
    ("PostToolUseFailure", 10),
    ("PermissionRequest", 120),
    ("Notification", 10),
    ("Stop", 10),
    ("StopFailure", 10),
    ("SubagentStart", 10),
    ("SubagentStop", 10),
)

_lock = threading.Lock()
# When a question sent ahead went unanswered, per session.
_ask_missed: dict[str, float] = {}
# Requests waiting for the island, oldest first, by request id. Several sessions
# can ask at once: they wait their turn on the card instead of going back to the
# terminal (Coucou #984).
_permits: dict[str, dict] = {}
MAX_PENDING = 5
_request_seq = 0
_stop = False
_paused = False


def set_paused(on: bool) -> None:
    global _paused
    _paused = bool(on)


def pipe_name() -> str:
    return r"\\.\pipe\kai-" + os.environ.get("USERNAME", "user")


def _detail(payload: dict) -> str:
    tool = str(payload.get("tool_name") or t("claude.tool"))
    data = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    piece = data.get("command") or data.get("file_path") or data.get("path") or data.get("pattern") or ""
    piece = " ".join(str(piece).split())[:160]
    if piece:
        return f"{tool}: {piece}"
    return t("claude.wants", tool=tool)


def _tool_lines(payload: dict) -> list[tuple[str, str]]:
    tool = str(payload.get("tool_name") or "")
    data = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    old = str(data.get("old_string") or "")
    new = str(data.get("new_string") or data.get("content") or "")
    rows: list[tuple[str, str]] = []
    if old or tool in {"Edit", "StrReplace", "MultiEdit"}:
        rows.extend(("-", line.strip()[:90]) for line in old.splitlines() if line.strip())
        rows.extend(("+", line.strip()[:90]) for line in new.splitlines() if line.strip())
    elif new and tool in {"Write", "NotebookEdit"}:
        rows.extend(("+", line.strip()[:90]) for line in new.splitlines() if line.strip())
    return rows[:24]


def summarize(payload: dict) -> str:
    event = str(payload.get("hook_event_name") or "")
    tool = str(payload.get("tool_name") or "")
    if event == "PermissionRequest":
        return _detail(payload)
    if event in {"PreToolUse", "PostToolUse"}:
        return f"Claude {tool or event}"
    if event == "PostToolUseFailure":
        return t("claude.failed", tool=tool or t("claude.tool_short"))
    if event == "Stop":
        return t("claude.finished")
    if event == "UserPromptSubmit":
        return t("claude.prompted")
    if event:
        return f"Claude {event}"
    return "Claude"


def answer(word: str, request_id: str = "") -> None:
    """The decision for the request on the card; without an id, the oldest one waiting."""
    with _lock:
        key = request_id if request_id in _permits else next(iter(_permits), None)
        pending = _permits.pop(key, None) if key else None
    if not pending:
        return
    # allow, deny, "ask" (hand it back to the terminal) or the answers to a question.
    word = str(word).strip()
    known = ("allow", "always", "deny", "ask", "plan_auto", "plan_default", "plan_change")
    pending["word"] = word if word in known or (word.startswith("{") and len(word) < 60000) else "deny"
    pending["event"].set()


def _read_line(handle) -> bytes:
    import win32file

    buf = b""
    while b"\n" not in buf and len(buf) < 1_000_000:
        _, chunk = win32file.ReadFile(handle, 65536)
        if not chunk:
            break
        buf += chunk
    return buf.split(b"\n", 1)[0]


def _serve(on_event) -> None:
    import win32file
    import win32pipe

    name = pipe_name()
    while not _stop:
        pipe = win32pipe.CreateNamedPipe(
            name,
            win32pipe.PIPE_ACCESS_DUPLEX,
            win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_WAIT,
            win32pipe.PIPE_UNLIMITED_INSTANCES,
            65536,
            65536,
            0,
            None,
        )
        try:
            win32pipe.ConnectNamedPipe(pipe, None)
        except Exception:
            win32file.CloseHandle(pipe)
            continue
        threading.Thread(target=_client, args=(pipe, on_event), daemon=True).start()


# Set by the app to also hand every raw hook payload to the v2 island.
raw_sink = None


def _forward(payload: dict) -> None:
    sink = raw_sink
    if sink is None:
        return
    try:
        sink(payload)
    except Exception:
        pass


def _client(pipe, on_event) -> None:
    import win32file

    global _request_seq
    try:
        raw = _read_line(pipe)
        payload = json.loads(raw.decode("utf-8", errors="replace"))
        if not isinstance(payload, dict):
            return
        event = str(payload.get("hook_event_name") or "")
        if payload.get("coucou_agent"):
            # Another agent (Codex, Gemini…): its own pill on the island, and nothing else.
            # Kai never answers their permission requests.
            if event != "PermissionRequest":
                _forward(payload)
            return
        # A turn ends with a task waiting in the queue: Claude Code is given it and
        # goes on, instead of stopping (kai_hook.py turns it into a "block").
        next_task = None
        if event == "Stop":
            import taskqueue

            next_task = taskqueue.take()
            if next_task:
                payload["queued_next"] = next_task
                _log(f"sıradaki iş verildi: {next_task[:80]}")
        if event != "PermissionRequest":
            _forward(payload)
        if event == "Stop":
            try:
                win32file.WriteFile(pipe, (json.dumps({"next": next_task}, ensure_ascii=True) + "\n").encode("ascii"))
            except Exception:
                pass  # a relay that does not wait for it (other agents, an older Kai)
        if event == "PostToolUse":
            lines = _tool_lines(payload)
            if lines:
                on_event(summarize(payload), False, {"lines": lines})
            else:
                on_event(summarize(payload), False)
            return
        if event == "PreToolUse":
            on_event("thinking", False)
            return
        if event == "Stop":
            on_event("isteğiniz tamamlandı", False, {"done": True})
            return
        if event != "PermissionRequest":
            on_event(summarize(payload), False)
            return
        # The same question left unanswered on the island a moment ago: Claude asks
        # it right away instead of waiting on the island a second time.
        missed = _ask_missed.get(str(payload.get("session_id") or ""), 0)
        if payload.get("tool_name") == "AskUserQuestion" and not payload.get("kai_ask") and time.time() - missed < 15:
            _log("soru zaten adada cevapsız kaldı, Claude'a bırakıldı")
            return
        box = {"event": threading.Event(), "word": ""}
        with _lock:
            busy = len(_permits) >= MAX_PENDING
            if not busy:
                _request_seq += 1
                request_id = f"{time.time():.3f}-{_request_seq}"
                _permits[request_id] = box
                waiting = len(_permits) - 1
        if busy:
            _log(f"istek atlandı, {MAX_PENDING} istek zaten sırada: {payload.get('tool_name')}")
            return
        if waiting:
            _log(f"istek sıraya girdi, önünde {waiting} istek var: {payload.get('tool_name')}")
        # Only a request Kai can actually answer gets a card on the v2 island.
        payload["request_id"] = request_id
        kind = "soru" if payload.get("kai_ask") else "izin"
        _log(f"{kind} geldi: {payload.get('tool_name')}")
        asked_at = time.time()
        _forward(payload)
        on_event(summarize(payload), True)
        # A question sent ahead (--ask) holds Claude's own question back, so it waits
        # less: past that, Claude shows it as usual.
        wait = ASK_WAIT if payload.get("kai_ask") else 108
        if not box["event"].wait(wait):
            _log(f"{kind}: cevap gelmedi, {time.time() - asked_at:.0f} sn sonra Claude'a bırakıldı")
            if payload.get("kai_ask"):
                _ask_missed[str(payload.get("session_id") or "")] = time.time()
            with _lock:
                if _permits.get(request_id) is box:
                    del _permits[request_id]
            return
        word = box["word"] or "deny"
        _log(f"{kind}: {'cevaplandı' if word.startswith('{') else word} ({time.time() - asked_at:.0f} sn)")
        if word == "ask":
            return  # no decision: Claude Code asks in the terminal
        # UTF-8: an answer carries the labels picked, often with Turkish letters,
        # and an ASCII encode lost every one of them without a word.
        win32file.WriteFile(pipe, (word + "\n").encode("utf-8"))
    except Exception as exc:
        _log(f"istek işlenemedi: {type(exc).__name__}: {exc}")
        return
    finally:
        try:
            win32file.CloseHandle(pipe)
        except Exception:
            pass


def _log(message: str) -> None:
    folder = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    try:
        with open(os.path.join(folder, "kai.log"), "a", encoding="utf-8") as handle:
            handle.write(time.strftime("%H:%M:%S ") + "kanca: " + message[:300] + "\n")
    except OSError:
        pass


def start(on_event) -> None:
    threading.Thread(target=_serve, args=(on_event,), daemon=True).start()
    threading.Thread(target=_watch_services, args=(on_event,), daemon=True).start()
    threading.Thread(target=_watch_editor_permit, args=(on_event,), daemon=True).start()


def stop() -> None:
    global _stop
    _stop = True


def _python() -> str:
    """A real Python for the hook relay, or "" when this computer has none.

    Never Kai.exe itself: a hook that started Kai would pop the "already
    running" box on every Claude Code event. The WindowsApps "python" is only
    a Store shortcut, not an interpreter.
    """
    if not getattr(sys, "frozen", False):
        return sys.executable
    for name in ("python", "py"):
        found = shutil.which(name)
        if found and "windowsapps" not in found.lower():
            return found
    return ""


def _hook_script() -> str:
    here = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "kai_hook.py")


# The relay only needs the standard library. Without site (-S) and isolated (-I)
# Python starts in a third of the time: packages installed on this computer
# (an editable install's finder, .pth files) cost ~80 ms on every hook, and
# Claude Code runs two hooks for every tool call.
FAST = "-I -S"
ASK_FLAG = "--ask"
# Seconds a question waits for the island before Claude asks it itself.
ASK_WAIT = 45


def _status_command() -> str:
    py = _python().replace("\\", "/")
    script = _hook_script().replace("\\", "/")
    return f'"{py}" {FAST} "{script}" --status'


def _command(event: str) -> str:
    py = _python().replace("\\", "/")
    script = _hook_script().replace("\\", "/")
    return f'"{py}" {FAST} "{script}" {event}'


def _settings_path() -> str:
    return os.path.join(os.path.expanduser("~"), ".claude", "settings.json")


def _ours(entry: dict) -> bool:
    hooks = entry.get("hooks") if isinstance(entry, dict) else None
    if not isinstance(hooks, list):
        return False
    return any(MARKER in str(item.get("command") or "") for item in hooks if isinstance(item, dict))


def install_hooks() -> str:
    if not _python():
        return t("claude.no_python")
    path = _settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return t("claude.not_object")
    except FileNotFoundError:
        data = {}
    except json.JSONDecodeError:
        return t("claude.bad_json")
    if os.path.exists(path):
        stamp = time.strftime("%Y%m%d-%H%M%S")
        shutil.copy2(path, path + f".kai-{stamp}.bak")
    hooks = data.get("hooks") if isinstance(data.get("hooks"), dict) else {}
    for event, timeout in EVENTS:
        current = hooks.get(event)
        items = [item for item in current if not _ours(item)] if isinstance(current, list) else []
        items.append({"hooks": [{"type": "command", "command": _command(event), "timeout": timeout}]})
        if event == "PreToolUse":
            # Questions answered from the island: the Claude desktop app shows them
            # itself and sends no PermissionRequest (kai_hook.py --ask).
            items.append({"matcher": "AskUserQuestion",
                          "hooks": [{"type": "command", "command": _command(event) + " " + ASK_FLAG, "timeout": 130}]})
        hooks[event] = items
    data["hooks"] = hooks
    # The status line hands Kai the plan's limits (kai_hook.py --status). Someone
    # else's status line is left alone.
    line = data.get("statusLine")
    if not isinstance(line, dict) or MARKER in str(line.get("command") or ""):
        data["statusLine"] = {"type": "command", "command": _status_command()}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return t("claude.installed")


def hooks_installed() -> bool:
    """True only when Claude's settings call the relay that sits next to this Kai.

    Checking for the name alone kept reporting "installed" after the folder moved,
    while every hook pointed at a script that no longer existed.
    """
    path = _settings_path()
    script = _hook_script()
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            text = handle.read()
    except OSError:
        return False
    # Hooks written by an older Kai start the slow way: written again.
    fast = json.dumps(f'{FAST} "{script.replace(chr(92), "/")}"', ensure_ascii=False)[1:-1]
    if not (os.path.isfile(script) and fast in text and f"PreToolUse {ASK_FLAG}" in text):
        return False
    # Our status line, if it is ours, must call this Kai too.
    try:
        line = json.loads(text).get("statusLine")
    except ValueError:
        return True
    if isinstance(line, dict) and MARKER in str(line.get("command") or ""):
        return line.get("command") == _status_command()
    return isinstance(line, dict)


def _editor_prompt():
    import uiautomation as auto

    hwnd = user32_hwnd()
    if not hwnd:
        return None
    allow = deny = None
    text = ""
    window = auto.ControlFromHandle(hwnd)
    count = 0
    for control, _depth in auto.WalkControl(window, maxDepth=10):
        count += 1
        if count > 220:
            break
        if control.ControlTypeName != "ButtonControl":
            continue
        name = (control.Name or "").strip().lower()
        box = control.BoundingRectangle
        if box.width() < 40 or box.height() < 18:
            continue
        point = (int(box.xcenter()), int(box.ycenter()))
        if name in {"allow", "accept", "approve", "izin ver", "kabul et"}:
            allow = point
        elif name in {"not allow", "don't allow", "dont allow", "deny", "reject", "reddet", "izin verme"}:
            deny = point
        if allow and deny:
            break
    if not allow or not deny:
        return None
    try:
        text = (window.Name or "").strip()
    except Exception:
        text = ""
    return (text or t("claude.asks"), allow, deny)


def user32_hwnd() -> int:
    import ctypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return 0
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    process = kernel32.OpenProcess(0x1000, False, pid.value)
    if not process:
        return 0
    try:
        size = ctypes.c_ulong(512)
        buf = ctypes.create_unicode_buffer(512)
        if not kernel32.QueryFullProcessImageNameW(process, 0, buf, ctypes.byref(size)):
            return 0
        exe = buf.value.rsplit("\\", 1)[-1].lower()
    finally:
        kernel32.CloseHandle(process)
    if exe not in {"cursor.exe", "claude.exe", "codex.exe"}:
        return 0
    return hwnd


def _watch_editor_permit(on_event) -> None:
    last = ""
    while not _stop:
        time.sleep(1.2)
        try:
            hit = _editor_prompt()
        except Exception:
            hit = None
        if not hit:
            last = ""
            continue
        text, allow, deny = hit
        key = f"{text}:{allow}:{deny}"
        if key == last:
            continue
        last = key
        on_event(text[:180], True, {"allow": allow, "deny": deny})


def _get(url: str, headers: dict) -> dict | list | None:
    request = urllib.request.Request(url, headers={"User-Agent": "Kai/1.0", **headers})
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def _watch_services(on_event) -> None:
    seen: dict[str, str] = {}
    while not _stop:
        if _paused:
            time.sleep(2)
            continue
        try:
            from settings import Settings

            settings = Settings()
            pills: list[tuple[str, tuple[int, int, int]]] = []
            token = (getattr(settings, "github_token", "") or "").strip()
            if token:
                user = _get(
                    "https://api.github.com/user",
                    {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                )
                if isinstance(user, dict) and user.get("login"):
                    label = f"GitHub {user.get('login')}"
                    pills.append((label, (180, 180, 190)))
                    if seen.get("github") != label:
                        seen["github"] = label
            vercel = (getattr(settings, "vercel_token", "") or "").strip()
            if vercel:
                data = _get("https://api.vercel.com/v6/deployments?limit=1", {"Authorization": f"Bearer {vercel}"})
                dep = (data or {}).get("deployments") or []
                if dep:
                    state = str(dep[0].get("readyState") or dep[0].get("state") or "")
                    name = str(dep[0].get("name") or "vercel")[:16]
                    label = f"Vercel {name} {state}".strip()
                    color = (80, 200, 140) if state.upper() in {"READY", "SUCCEEDED"} else (255, 170, 70)
                    pills.append((label, color))
                    if seen.get("vercel") != label:
                        seen["vercel"] = label
                        if state.upper() in {"ERROR", "FAILED"}:
                            on_event(label, False)
            stripe = (getattr(settings, "stripe_key", "") or "").strip()
            if stripe:
                balance = _get("https://api.stripe.com/v1/balance", {"Authorization": f"Bearer {stripe}"})
                available = (balance or {}).get("available") or []
                if available:
                    cents = int(available[0].get("amount") or 0)
                    money = f"{available[0].get('currency', 'usd').upper()} {cents / 100:.2f}"
                    label = f"Stripe {money}"
                else:
                    label = t("stripe.linked")
                pills.append((label, (120, 90, 230)))
                if seen.get("stripe") != label:
                    seen["stripe"] = label
            on_event("", False, {"pills": pills})
        except Exception:
            pass
        for _ in range(90):
            if _stop:
                return
            time.sleep(1)
