"""Relay an agent's hook to Kai. Never blocks the session if Kai is closed.

Usage: kai_hook.py [--agent <name>] [<EventName>]
Claude Code runs it without --agent. Every other agent (Codex, Copilot CLI,
Gemini CLI…) is tagged with its name, and its event and field names are mapped
onto Claude Code's so the island reads them all the same way.

Kai only answers Claude Code's permission requests. For the other agents the
reply is silence, or the "no opinion" JSON the agent expects: nothing that
allows anything is ever printed for them.
"""

from __future__ import annotations

import json
import os
import sys

PIPE = r"\\.\pipe\kai-" + os.environ.get("USERNAME", "user")
DROPPED = {"tool_response", "transcript_path"}
# The AskUserQuestion input of this hook, kept to build the answer from.
_ASKED = None
# The ExitPlanMode input: Claude Code ignores an allow for it without updatedInput.
_PLAN = None
# The rules Claude Code offers to remember with a request ("always allow"), whole.
_SUGGESTED = None
# Events where Kai needs to know which window the session lives in.
WINDOW_EVENTS = {"Stop", "StopFailure", "PermissionRequest"}

# Each agent's event names, as Claude Code's.
EVENTS = {
    "BeforeTool": "PreToolUse", "BeforeToolSelection": "PreToolUse", "AfterTool": "PostToolUse",
    "AfterModel": "PostToolUse", "BeforeAgent": "UserPromptSubmit", "AfterAgent": "Stop",
    "startup": "SessionStart", "exit": "SessionEnd",
    "PreInvocation": "UserPromptSubmit", "PostInvocation": "PostToolUse",
    "pre_tool_use": "PreToolUse", "post_tool_use": "PostToolUse", "user_prompt_submit": "UserPromptSubmit",
    "session_start": "SessionStart", "session_end": "SessionEnd", "stop": "Stop",
    "sessionStart": "SessionStart", "userPromptSubmitted": "UserPromptSubmit", "agentStop": "Stop",
    "notification": "Notification", "preToolUse": "PreToolUse", "postToolUse": "PostToolUse",
    "permissionRequest": "PermissionRequest", "sessionEnd": "SessionEnd",
    "beforeSubmitPrompt": "UserPromptSubmit", "postToolUseFailure": "PostToolUseFailure",
    "subagentStart": "SubagentStart", "subagentStop": "SubagentStop",
}
ARG_ALIASES = (("CommandLine", "command"), ("FilePath", "file_path"), ("Path", "path"),
               ("Url", "url"), ("Query", "query"), ("Pattern", "pattern"))
# Agents that read a JSON object on stdout after every hook.
WANTS_JSON = {"gemini", "antigravity", "copilot", "muse"}


def _clip(value, limit: int = 2000):
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + "…"
    if isinstance(value, list):
        return [_clip(item, limit) for item in value]
    if isinstance(value, dict):
        return {key: _clip(item, limit) for key, item in value.items()}
    return value


def _patch(response) -> list | None:
    """The few changed lines of an edit, with their line numbers. The file itself stays behind."""
    hunks = response.get("structuredPatch") if isinstance(response, dict) else None
    if not isinstance(hunks, list):
        return None
    small = []
    for hunk in hunks[:4]:
        if not isinstance(hunk, dict):
            continue
        lines = [str(line)[:240] for line in (hunk.get("lines") or [])[:40]]
        small.append({"oldStart": hunk.get("oldStart"), "newStart": hunk.get("newStart"), "lines": lines})
    return small or None


def _args() -> tuple[str, str]:
    """(agent, event) from the command line."""
    agent = event = ""
    words = iter(sys.argv[1:])
    for word in words:
        if word == "--agent":
            agent = next(words, "")
        elif not event:
            event = word
    return agent.strip().lower(), event


def _text(payload: dict, key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) and value else ""


def _normalize(payload: dict) -> None:
    """Other agents' field names, as Claude Code's: tool_name, tool_input, session_id, cwd."""
    call = payload.get("toolCall") if isinstance(payload.get("toolCall"), dict) else {}
    if "tool_name" not in payload:
        name = _text(payload, "toolName") or _text(call, "name") or _text(payload, "tool")
        if name:
            payload["tool_name"] = name
    if "tool_input" not in payload:
        args = payload.get("toolArgs")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = None
        if not isinstance(args, dict) and isinstance(call.get("args"), dict):
            args = dict(call["args"])
            for source, target in ARG_ALIASES:
                if source in args:
                    args[target] = args[source]
        if isinstance(args, dict):
            payload["tool_input"] = args
    if not _text(payload, "session_id"):
        found = next((_text(payload, key) for key in ("conversationId", "conversation_id", "sessionId") if _text(payload, key)), "")
        found = found or os.environ.get("GEMINI_SESSION_ID", "")
        if found:
            payload["session_id"] = found
    if not _text(payload, "cwd"):
        found = _text(payload, "workdir")
        for key in ("workspacePaths", "workspace_roots"):
            roots = payload.get(key)
            if not found and isinstance(roots, list) and roots and isinstance(roots[0], str):
                found = roots[0]
        if found:
            payload["cwd"] = found


def _add_session_name(payload: dict) -> None:
    """The folder the session started in and its /rename title, from the transcript.

    The pill is named after them, not after a subfolder the agent moved into.
    """
    path = payload.get("transcript_path") or ""
    if not isinstance(path, str) or not path:
        return
    try:
        with open(path, "rb") as handle:
            for line in handle.read(16384).splitlines():
                try:
                    root = json.loads(line).get("cwd")
                except Exception:
                    continue
                if isinstance(root, str) and root:
                    payload["session_root"] = root
                    break
            handle.seek(0, os.SEEK_END)
            start = max(0, handle.tell() - 65536)
            handle.seek(start)
            lines = handle.read().splitlines()
            for line in reversed(lines[1:] if start else lines):
                if b'"custom-title"' in line:
                    title = json.loads(line).get("customTitle")
                    if isinstance(title, str) and title:
                        payload["session_title"] = title[:60]
                    break
    except Exception:
        pass


def _add_host_window(payload: dict) -> None:
    """The terminal or editor this session runs in: the nearest ancestor with a window.

    Kai then stays quiet when that window is in front, and can bring it forward.
    """
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    class ENTRY(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]

    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    snap = kernel32.CreateToolhelp32Snapshot(2, 0)
    parents: dict[int, tuple[int, str]] = {}
    entry = ENTRY()
    entry.dwSize = ctypes.sizeof(ENTRY)
    try:
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            parents[entry.th32ProcessID] = (entry.th32ParentProcessID, entry.szExeFile.lower())
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)

    windows: dict[int, int] = {}
    PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.GetWindow.argtypes = [wintypes.HWND, ctypes.c_uint]
    user32.GetWindow.restype = wintypes.HWND

    def each(hwnd, _):
        if user32.IsWindowVisible(hwnd) and not user32.GetWindow(hwnd, 4) and user32.GetWindowTextLengthW(hwnd) > 0:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            windows.setdefault(pid.value, int(hwnd or 0))
        return True

    user32.EnumWindows(PROC(each), 0)
    pid = os.getpid()
    for _ in range(16):
        if pid not in parents or pid == 0:
            break
        parent, exe = parents[pid]
        if pid in windows and exe != "explorer.exe":
            payload["host_pid"] = pid
            payload["host_exe"] = exe
            payload["host_hwnd"] = windows[pid]
            return
        if parent == pid:
            break
        pid = parent
    # A plain console: its window is the session's.
    kernel32.GetConsoleWindow.restype = wintypes.HWND
    console = kernel32.GetConsoleWindow()
    if console:
        payload["host_hwnd"] = int(console)


def _read_event(agent: str, said: str) -> tuple[dict, str] | None:
    raw = sys.stdin.buffer.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    if not raw.strip():
        return None
    try:
        payload = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    global _ASKED, _PLAN, _SUGGESTED
    if isinstance(payload.get("permission_suggestions"), list):
        _SUGGESTED = payload["permission_suggestions"]
        # The island only needs to know there is something to remember.
        payload["can_always"] = bool(_SUGGESTED)
    if payload.get("tool_name") == "AskUserQuestion":
        _ASKED = payload.get("tool_input")  # whole, before anything is clipped
    if payload.get("tool_name") == "ExitPlanMode":
        _PLAN = payload.get("tool_input")
    payload["patch"] = _patch(payload.get("tool_response"))
    _add_session_name(payload)
    for key in DROPPED:
        payload.pop(key, None)
    event = str(payload.get("hook_event_name") or said)
    if agent:
        _normalize(payload)
        event = EVENTS.get(event, event)
        if event == "Stop" and payload.get("status") == "error":
            event = "StopFailure"
        payload["coucou_agent"] = agent
    payload["hook_event_name"] = event
    if not payload.get("cwd"):
        payload["cwd"] = os.getcwd()
    if event in WINDOW_EVENTS:
        try:
            _add_host_window(payload)
        except Exception:
            pass
    return _clip(payload), event


def _answers_fit(question, answers: dict) -> bool:
    """True when answers covers exactly the questions asked, with labels that were offered."""
    items = question.get("questions") if isinstance(question, dict) else None
    if not isinstance(items, list) or not items or len(items) != len(answers):
        return False
    for item in items:
        text = item.get("question") if isinstance(item, dict) else None
        if not isinstance(text, str):
            return False
        labels = [o.get("label") for o in item.get("options") or [] if isinstance(o, dict) and isinstance(o.get("label"), str)]
        picked = answers.get(text)
        if item.get("multiSelect") is True:
            if not isinstance(picked, list) or not picked or len(set(map(str, picked))) != len(picked):
                return False
            if any(label not in labels for label in picked):
                return False
        elif not isinstance(picked, str) or picked not in labels:
            return False
    return True


def _plan_json(word: str, plan) -> str:
    """A choice on the plan card, as the terminal's own plan dialog would answer it."""
    if word == "plan_change":
        # Like "Tell Claude what to change": the plan is rejected and Claude stops,
        # so the prompt is free for the change.
        decision = {"behavior": "deny", "interrupt": True,
                    "message": "The user wants to change the plan and will type the changes in the terminal."}
    else:
        decision = {"behavior": "allow", "updatedInput": plan if isinstance(plan, dict) else {}}
        mode = {"plan_auto": "auto", "plan_default": "default"}.get(word)
        if mode:
            decision["updatedPermissions"] = [{"type": "setMode", "mode": mode, "destination": "session"}]
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": decision}}, ensure_ascii=True)


def _decision_json(word: str, question=None, plan=None) -> str | None:
    word = word.strip()
    if word in {"plan_auto", "plan_default", "plan_change"}:
        return _plan_json(word, plan) if plan is not None else None
    # A plain allow of a plan still needs its input back, or Claude Code ignores it.
    if word in {"allow", "always"} and plan is not None:
        return _plan_json("plan_default", plan)
    if word.startswith("{"):
        # An answer to AskUserQuestion: the same input back, with the answers added.
        # Nothing else of the input can be changed, and no other tool's input at all.
        try:
            answers = json.loads(word).get("answers")
        except (json.JSONDecodeError, AttributeError):
            return None
        if not isinstance(answers, dict) or not _answers_fit(question, answers):
            return None
        decision = {"behavior": "allow", "updatedInput": {**question, "answers": answers}}
        return json.dumps({"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": decision}}, ensure_ascii=True)
    if word == "always" and _SUGGESTED:
        # "Always allow": the rules Claude Code suggested go back as they came,
        # so it keeps them and does not ask for this again.
        decision = {"behavior": "allow", "updatedPermissions": _SUGGESTED}
        return json.dumps({"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": decision}}, ensure_ascii=True)
    if word in {"allow", "always"}:
        behavior = '{"behavior":"allow"}'
    elif word == "deny":
        behavior = '{"behavior":"deny","message":"Denied from Kai"}'
    else:
        return None
    return (
        '{"hookSpecificOutput":{"hookEventName":"PermissionRequest","decision":'
        + behavior
        + "}}"
    )


def _no_opinion(agent: str, event: str) -> str | None:
    """What another agent must read back when Kai has nothing to say. Never an allow."""
    if event == "PermissionRequest":
        # Copilot is fail-closed: it must always get valid JSON, so silence is an "ask".
        return '{"permissionDecision":"ask"}' if agent == "copilot" else None
    # Antigravity reads "{}" on PreToolUse as a denial; "ask" keeps its own prompt.
    if agent == "antigravity" and event == "PreToolUse":
        return '{"decision":"ask"}'
    return "{}" if agent in WANTS_JSON else None


def _say(line: str | None) -> None:
    if line:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


def _front_is_host(payload: dict) -> bool:
    """The session's own window (the Claude app, the terminal) is the one in front."""
    import ctypes

    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.GetForegroundWindow.restype = ctypes.c_void_p
    front = int(user32.GetForegroundWindow() or 0)
    if not front:
        return False
    if front == int(payload.get("host_hwnd") or 0):
        return True
    # The same program in front (another of its windows or processes) counts too.
    exe = str(payload.get("host_exe") or "")
    if not exe:
        return False
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(ctypes.c_void_p(front), ctypes.byref(pid))
    kernel32.OpenProcess.restype = ctypes.c_void_p
    handle = kernel32.OpenProcess(0x1000, False, pid.value)
    if not handle:
        return False
    try:
        size = wintypes.DWORD(512)
        buf = ctypes.create_unicode_buffer(512)
        kernel32.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_wchar_p, ctypes.POINTER(wintypes.DWORD)]
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return False
        return buf.value.rsplit("\\", 1)[-1].lower() == exe
    finally:
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle(handle)


def _ask(payload: dict) -> None:
    """--ask: Claude is about to ask the user a question (AskUserQuestion, PreToolUse).

    Some hosts, such as the Claude desktop app, show the question themselves and
    never send a PermissionRequest for it, so Kai could not answer. Here the
    question goes to Kai as a request; answered there, the tool runs with the
    answers already filled in. While the session's own window is in front the
    user is looking at the question already: nothing is held back.
    """
    if payload.get("tool_name") != "AskUserQuestion":
        return
    try:
        _add_host_window(payload)
        if _front_is_host(payload):
            return
    except Exception:
        pass
    payload["hook_event_name"] = "PermissionRequest"
    payload["kai_ask"] = True
    try:
        pipe = open(PIPE, "r+b", buffering=0)
    except OSError:
        return
    try:
        pipe.write((json.dumps(_clip(payload), ensure_ascii=False) + "\n").encode("utf-8"))
        buf = b""
        while b"\n" not in buf and len(buf) < 65536:
            chunk = pipe.read(4096)
            if not chunk:
                break
            buf += chunk
    except OSError:
        return
    finally:
        pipe.close()
    word = buf.decode("utf-8", errors="replace").strip()
    if not word.startswith("{"):
        return  # "ask", a timeout or no Kai: Claude asks as usual
    try:
        answers = json.loads(word).get("answers")
    except (json.JSONDecodeError, AttributeError):
        return
    question = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else None
    if not isinstance(answers, dict) or not _answers_fit(question, answers):
        return
    _say(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "updatedInput": {**question, "answers": answers},
    }}, ensure_ascii=True))


def _status() -> None:
    """--status: Claude Code's status line. Keeps the plan's limits for the island.

    Claude Code hands the status line its rate limits (five_hour and seven_day,
    each a used percentage and a reset time); they are written to usage.json
    next to Kai's settings, and a short line goes back for the terminal.
    """
    raw = sys.stdin.buffer.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        payload = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return
    if not isinstance(payload, dict):
        return
    limits = payload.get("rate_limits") if isinstance(payload.get("rate_limits"), dict) else {}
    usage = {}
    for name in ("five_hour", "seven_day"):
        window = limits.get(name)
        if isinstance(window, dict) and isinstance(window.get("used_percentage"), (int, float)):
            usage[name] = {"used": max(0.0, min(100.0, float(window["used_percentage"]))),
                           "resets": float(window.get("resets_at") or 0)}
    import time

    folder = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Kai")
    if usage:
        try:
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, "usage.json")
            with open(path + ".tmp", "w", encoding="utf-8") as handle:
                json.dump({**usage, "at": time.time()}, handle)
            os.replace(path + ".tmp", path)
        except OSError:
            pass
    model = payload.get("model") if isinstance(payload.get("model"), dict) else {}
    parts = [str(model.get("display_name") or "Claude")]
    if "five_hour" in usage:
        parts.append(f"5s %{round(usage['five_hour']['used'])}")
    if "seven_day" in usage:
        parts.append(f"7g %{round(usage['seven_day']['used'])}")
    _say(" · ".join(parts))


def _next_task(pipe) -> None:
    """End of a turn: Kai answers with the next task from its queue, or nothing.

    With one, Claude Code is told not to stop (the Stop hook's "block") and is
    handed the task as the reason, so it goes on with it in the same session.
    """
    buf = b""
    while b"\n" not in buf and len(buf) < 65536:
        chunk = pipe.read(4096)
        if not chunk:
            break
        buf += chunk
    try:
        task = json.loads(buf.decode("utf-8", errors="replace") or "{}").get("next")
    except (json.JSONDecodeError, AttributeError):
        return
    if isinstance(task, str) and task.strip():
        _say(json.dumps({
            "decision": "block",
            "reason": "The user queued the next task in Kai while you were working. Do it now: " + task.strip(),
        }, ensure_ascii=True))


def main() -> None:
    if "--status" in sys.argv[1:]:
        _status()
        return
    if "--ask" in sys.argv[1:]:
        raw = sys.stdin.buffer.read()
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        try:
            payload = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return
        if isinstance(payload, dict):
            for key in DROPPED:
                payload.pop(key, None)
            _ask(payload)
        return
    agent, said = _args()
    parsed = _read_event(agent, said)
    if not parsed:
        _say(_no_opinion(agent, EVENTS.get(said, said)) if agent else None)
        return
    payload, event = parsed
    try:
        pipe = open(PIPE, "r+b", buffering=0)
    except OSError:
        _say(_no_opinion(agent, event) if agent else None)
        return
    try:
        pipe.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        if agent:
            _say(_no_opinion(agent, event))
            return
        if event == "Stop":
            _next_task(pipe)
            return
        if event != "PermissionRequest":
            return
        buf = b""
        while b"\n" not in buf and len(buf) < 65536:
            chunk = pipe.read(4096)
            if not chunk:
                break
            buf += chunk
        _say(_decision_json(buf.decode("utf-8", errors="replace"), _ASKED, _PLAN))
    except OSError:
        if agent:
            _say(_no_opinion(agent, event))
        return
    finally:
        pipe.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
