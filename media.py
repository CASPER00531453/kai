"""Now playing via Windows media controls, and Spotify song search + play."""

from __future__ import annotations

import asyncio
import io
import os
import re
import threading
import time
import urllib.parse

from PIL import Image

_state_lock = threading.Lock()
_state: dict | None = None
_cover_key = None
_cover: Image.Image | None = None
_played: list[str] = []
PLAYING = 4


def _run(coro_fn, *args):
    return asyncio.run(coro_fn(*args))


async def _session(prefer_spotify: bool = True):
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Manager

    manager = await Manager.request_async()
    sessions = list(manager.get_sessions())
    for session in sessions:
        if "spotify" in (session.source_app_user_model_id or "").lower():
            return session
    if prefer_spotify and sessions:
        return manager.get_current_session()
    return None


async def _read_cover(info) -> Image.Image | None:
    from winrt.windows.storage.streams import Buffer, InputStreamOptions

    if info.thumbnail is None:
        return None
    stream = await info.thumbnail.open_read_async()
    size = int(stream.size)
    if size <= 0 or size > 8_000_000:
        return None
    buffer = Buffer(size)
    await stream.read_async(buffer, size, InputStreamOptions.READ_AHEAD)
    data = bytes(memoryview(buffer)[: buffer.length])
    image = Image.open(io.BytesIO(data)).convert("RGB")
    width, height = image.size
    if width != height:
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        image = image.crop((left, top, left + side, top + side))
    return image


async def _snapshot() -> dict | None:
    global _cover_key, _cover
    session = await _session()
    if session is None:
        return None
    info = await session.try_get_media_properties_async()
    timeline = session.get_timeline_properties()
    playback = session.get_playback_info()
    title = info.title or ""
    artist = info.artist or ""
    key = (title, artist)
    if key != _cover_key:
        try:
            _cover = await _read_cover(info)
        except Exception:
            _cover = None
        _cover_key = key
        label = " — ".join(part for part in (artist, title) if part)
        if label:
            with _state_lock:
                if not _played or _played[-1] != label:
                    _played.append(label)
                    del _played[:-8]
    return {
        "title": title,
        "artist": artist,
        "position": timeline.position.total_seconds(),
        "duration": max(0.0, (timeline.end_time - timeline.start_time).total_seconds()),
        "playing": int(playback.playback_status) == PLAYING,
        "at": time.monotonic(),
        "cover": _cover,
    }


def refresh() -> dict | None:
    global _state

    async def _timed():
        return await asyncio.wait_for(_snapshot(), 3.0)

    try:
        snap = _run(_timed)
    except Exception:
        snap = None
    with _state_lock:
        _state = snap
    return snap


def current() -> dict | None:
    with _state_lock:
        snap = dict(_state) if _state else None
    if snap and snap["playing"]:
        snap["position"] = min(snap["duration"] or 1e9, snap["position"] + time.monotonic() - snap["at"])
    return snap


def played() -> list[str]:
    with _state_lock:
        return list(_played)


def _control(name: str) -> bool:
    async def act():
        session = await _session()
        if session is None:
            return False
        return bool(await getattr(session, name)())

    try:
        ok = _run(act)
    except Exception:
        ok = False
    time.sleep(0.25)
    refresh()
    return ok


def toggle() -> bool:
    return _control("try_toggle_play_pause_async")


def pause() -> bool:
    return _control("try_pause_async")


def resume() -> bool:
    return _control("try_play_async")


def next_track() -> bool:
    return _control("try_skip_next_async")


def previous_track() -> bool:
    return _control("try_skip_previous_async")


# Folded so "sezen aksu firuze" finds "Sezen Aksu · Firuze" however it was typed.
_FOLD = str.maketrans("çğıöşüâîû", "cgiosuaiu")


def _words(text: str) -> set[str]:
    folded = text.replace("İ", "i").replace("I", "i").lower().translate(_FOLD)
    return set(re.sub(r"[^\w ]", " ", folded).split())


def _spotify_window():
    import subprocess

    import uiautomation as auto

    out = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq Spotify.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        creationflags=0x08000000,
    ).stdout
    pids = set()
    for line in out.splitlines():
        parts = line.strip().strip('"').split('","')
        if len(parts) > 1 and parts[1].isdigit():
            pids.add(int(parts[1]))
    if not pids:
        return None
    for top in auto.GetRootControl().GetChildren():
        if top.ProcessId in pids and (top.ClassName or "").startswith("Chrome_WidgetWin") and top.Name:
            return top
    return None


# UI Automation ids: control types, properties and patterns.
_BUTTON, _COMBO, _LINK, _ROW = 50000, 50003, 50005, 50029
_CONTROL_TYPE, _CAN_INVOKE = 30003, 30031
_INVOKE, _VALUE = 10000, 10002


def _uia():
    from uiautomation import uiautomation as core

    return core._AutomationClient.instance().IUIAutomation, core.comtypes.gen.UIAutomationClient


def _all(element, control_type: int) -> list:
    """Every descendant of one control type, in a single call: Spotify's tree is
    thousands of nodes deep and walking it from Python took minutes."""
    client, _ = _uia()
    found = element.FindAll(4, client.CreatePropertyCondition(_CONTROL_TYPE, control_type))
    return [found.GetElement(index) for index in range(found.Length)]


def _name(element) -> str:
    try:
        return element.CurrentName or ""
    except Exception:
        return ""


def _value(element) -> str:
    _, gen = _uia()
    try:
        pattern = element.GetCurrentPattern(_VALUE)
        return pattern.QueryInterface(gen.IUIAutomationValuePattern).CurrentValue or "" if pattern else ""
    except Exception:
        return ""


def _invoke(element) -> bool:
    _, gen = _uia()
    try:
        element.GetCurrentPattern(_INVOKE).QueryInterface(gen.IUIAutomationInvokePattern).Invoke()
        return True
    except Exception:
        return False


def _row_of(link):
    """The list row a link sits in."""
    client, _ = _uia()
    walker = client.RawViewWalker
    element = link
    for _step in range(8):
        try:
            element = walker.GetParentElement(element)
            if not element:
                return None
            if element.CurrentControlType == _ROW and element.GetCurrentPropertyValue(_CAN_INVOKE):
                return element
        except Exception:
            return None
    return None


def _tracks(window) -> list[dict]:
    """The songs on the page, in Spotify's order: id, title, artists and row."""
    tracks, seen = [], set()
    for link in _all(window.Element, _LINK):
        match = re.search(r"/track/(\w+)", _value(link))
        title = _name(link).strip()
        if not match or not title or match.group(1) in seen:
            continue
        row = _row_of(link)
        if row is None:
            continue
        seen.add(match.group(1))
        others = [_name(other) for other in _all(row, _LINK)]
        artists = " ".join(text for text in others if text and text != title)
        tracks.append({"id": match.group(1), "title": title, "artists": artists, "row": row})
    return tracks


def _searched(window, query: str) -> bool:
    """Spotify's search box holds this query, so the page is not a previous search."""
    want = query.strip().lower()
    return any(_value(box).strip().lower() == want for box in _all(window.Element, _COMBO))


def _best(tracks: list[dict], want: set[str]) -> dict | None:
    """The song that was asked for, not a cover, remix or feat. of it.

    Words in a title that nobody asked for ("cover", "remix", "feat", "live")
    count against it; between equals Spotify's own order decides. When nothing
    matches by words, Spotify's first song stands: its search forgives typos
    that a word comparison does not.
    """
    if not tracks:
        return None
    need = max(1, -(-len(want) * 3 // 5))
    scored = []
    for index, track in enumerate(tracks):
        title = _words(track["title"])
        overlap = len(want & (title | _words(track["artists"])))
        if overlap >= need and want & title:
            scored.append((overlap, -len(title - want), -index))
    if not scored:
        return tracks[0]
    return tracks[-max(scored)[2]]


def _press_play(row) -> bool:
    """Start the song of one row. A row shows its play button once it is selected."""
    for attempt in range(2):
        for button in _all(row, _BUTTON):
            # "Çal", "…parçasını çal", "Play …": never "Çalma listesine ekle".
            if _words(_name(button)) & {"cal", "play"} and _invoke(button):
                return True
        if attempt == 0:
            _invoke(row)
            time.sleep(0.5)
    return False


def _find_and_press(query: str) -> str | None:
    want = _words(query)
    if not want:
        return None
    os.startfile("spotify:search:" + urllib.parse.quote(query))
    started = time.monotonic()
    window = None
    before: list[str] = []
    track = None
    while time.monotonic() - started < 12.0:
        time.sleep(0.6)
        try:
            window = window or _spotify_window()
            if window is None:
                continue
            # Results of the search before this one are still on the page for a
            # moment; picking from them played something else entirely.
            if not _searched(window, query) and time.monotonic() - started < 6.0:
                continue
            tracks = _tracks(window)
        except Exception:
            window = None
            continue
        ids = [item["id"] for item in tracks[:5]]
        if ids and ids == before:
            track = _best(tracks, want)
            break
        before = ids
    if track is None:
        return None
    label = f"{track['artists']} - {track['title']}" if track["artists"] else track["title"]
    if _press_play(track["row"]):
        return label

    # The row would not play where it stood: open the song on its album and
    # start it there.
    os.startfile("spotify:track:" + track["id"])
    title = _words(track["title"])
    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        time.sleep(0.7)
        try:
            rows = [item for item in _tracks(window) if _words(item["title"]) == title]
            same = [item for item in rows if item["id"] == track["id"]] or rows
            if same and _press_play(same[0]["row"]):
                return label
        except Exception:
            continue
    return None


def play_song(query: str) -> str | None:
    """Search Spotify for query and press play on the row that matches it. Returns its name or None."""
    found: list[str | None] = []

    def work() -> None:
        import gc

        import uiautomation as auto

        with auto.UIAutomationInitializerInThread():
            try:
                found.append(_find_and_press(query))
            finally:
                # Every handle into Spotify has to be let go before COM shuts down
                # on this thread; one left over makes the shutdown wait forever.
                gc.collect()

    # On a thread of its own, so the caller's thread keeps its COM state and a
    # stuck Spotify window can only cost half a minute.
    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(28)
    return found[0] if found else None
