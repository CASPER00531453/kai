"""Silence while you speak to Kai (Coucou's hush.rs).

From the moment Kai listens (dictation, a question after « OK Kai ») until it
has heard you, every other app's session in the Windows mixer is muted, so a
video, music or a call does not get in the way of your voice. Kai's own sounds
keep playing, sessions the user had muted stay theirs, and only the ones Kai
muted get their sound back. The list is kept on disk, so a Kai that quit while
listening gives the sound back at the next start.
"""

from __future__ import annotations

import json
import os
import queue
import threading

# The user's choice (Kai window › Flow), set by settings.py when it loads.
enabled = True

_depth = 0
_lock = threading.Lock()
_jobs: "queue.Queue[str] | None" = None


def _list_path() -> str:
    from settings import v2_file

    return v2_file("hushed.json")


def _load() -> list[str]:
    try:
        with open(_list_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    return [str(x) for x in data] if isinstance(data, list) else []


def _save(ids: list[str]) -> None:
    path = _list_path()
    try:
        if ids:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(ids, handle)
        elif os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _ours() -> set[int]:
    """Kai's own processes (the island and the window run as children, their webviews below them)."""
    import psutil

    me = psutil.Process()
    top = me
    # Up to the first Kai: started from the main process, the island is its child.
    for parent in me.parents():
        if parent.name().lower() == me.name().lower():
            top = parent
    return {top.pid, *(child.pid for child in top.children(recursive=True))}


def _sessions():
    from pycaw.pycaw import AudioUtilities

    for session in AudioUtilities.GetAllSessions():
        try:
            # Windows' own sounds (notifications, errors) have no process: left alone.
            if not session.ProcessId:
                continue
            yield session.InstanceIdentifier, session.ProcessId, session.SimpleAudioVolume
        except Exception:
            continue


def _mute_others() -> None:
    muted = _load()
    ours = _ours()
    for ident, pid, volume in _sessions():
        if pid in ours or ident in muted:
            continue
        try:
            # Already muted by the user: theirs to unmute, not ours.
            if volume.GetMute():
                continue
            volume.SetMute(1, None)
            muted.append(ident)
        except Exception:
            continue
    _save(muted)


def _restore() -> None:
    muted = _load()
    if not muted:
        return
    for ident, _pid, volume in _sessions():
        if ident in muted:
            try:
                volume.SetMute(0, None)
            except Exception:
                pass
    _save([])


def _send(job: str) -> None:
    """One thread does the work, in order: a mute is never undone by an older restore."""
    global _jobs
    with _lock:
        if _jobs is None:
            _jobs = queue.Queue()

            def work() -> None:
                import comtypes

                comtypes.CoInitialize()
                while True:
                    name = _jobs.get()
                    try:
                        _mute_others() if name == "mute" else _restore()
                    except Exception:
                        pass

            threading.Thread(target=work, name="kai-hush", daemon=True).start()
    _jobs.put(job)


def begin() -> bool:
    """Kai starts listening: the other apps go quiet. True when a silence was taken."""
    global _depth
    if not enabled:
        return False
    with _lock:
        _depth += 1
        first = _depth == 1
    if first:
        _send("mute")
    return True


def end() -> None:
    """Kai has heard you: the sound comes back once nobody listens any more."""
    global _depth
    with _lock:
        if _depth == 0:
            return
        _depth -= 1
        last = _depth == 0
    if last:
        _send("restore")


def setup() -> None:
    """At start: a silence left by a Kai that quit while listening is undone."""
    try:
        if os.path.exists(_list_path()):
            _send("restore")
    except Exception:
        pass
