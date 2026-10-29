"""League client: accept a found match, then lock the champion the patron names."""

from __future__ import annotations

import base64
import ctypes
import json
import os
import ssl
import threading
import time
import urllib.request

from i18n import t
from pointer import Pointer

user32 = ctypes.windll.user32
SKIP_PICK = {"yok", "yok.", "hayır", "hayir", "istemiyorum", "yoktur", "bos", "boş", "no", "none", "nope", "skip"}
_SSL = ssl._create_unverified_context()


def _auth() -> tuple[str, str] | None:
    path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Riot Games", "League of Legends", "lockfile")
    try:
        raw = open(path, "r", encoding="utf-8").read().strip()
    except OSError:
        return None
    parts = raw.split(":")
    if len(parts) < 4 or not parts[2].isdigit():
        return None
    return parts[2], parts[3]


def _call(method: str, path: str, body: dict | None = None):
    auth = _auth()
    if not auth:
        return None
    port, password = auth
    token = base64.b64encode(f"riot:{password}".encode()).decode()
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"https://127.0.0.1:{port}{path}",
        data=data,
        method=method,
        headers={"Authorization": f"Basic {token}", "Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, context=_SSL, timeout=4) as response:
            raw = response.read()
    except Exception:
        return None
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return {}


def _phase() -> str:
    value = _call("GET", "/lol-gameflow/v1/gameflow-phase")
    return value if isinstance(value, str) else ""


def _champ_id(name: str) -> int | None:
    wanted = "".join(ch for ch in name.lower() if ch.isalnum())
    roster = _call("GET", "/lol-game-data/assets/v1/champion-summary.json")
    if not isinstance(roster, list):
        return None
    for item in roster:
        if not isinstance(item, dict):
            continue
        for key in ("name", "alias"):
            label = "".join(ch for ch in str(item.get(key) or "").lower() if ch.isalnum())
            if label and (label == wanted or wanted in label or label in wanted):
                try:
                    return int(item.get("id") or 0) or None
                except (TypeError, ValueError):
                    return None
    return None


def _lock(champion_id: int) -> bool:
    session = _call("GET", "/lol-champ-select/v1/session")
    if not isinstance(session, dict):
        return False
    cell = session.get("localPlayerCellId")
    target = None
    for batch in session.get("actions") or []:
        if not isinstance(batch, list):
            continue
        for action in batch:
            if not isinstance(action, dict):
                continue
            if action.get("actorCellId") != cell or action.get("type") != "pick" or action.get("completed"):
                continue
            target = action.get("id")
            if action.get("isInProgress"):
                break
    if target is None:
        return False
    path = f"/lol-champ-select/v1/session/actions/{target}"
    _call("PATCH", path, {"championId": champion_id})
    result = _call("PATCH", path, {"championId": champion_id, "completed": True})
    return isinstance(result, dict)


class QueueAccept:
    def __init__(self, pointer: Pointer, on_ask) -> None:
        self.pointer = pointer
        self.on_ask = on_ask
        self._stop = threading.Event()

    def start(self) -> None:
        self._stop.clear()
        threading.Thread(target=self._run, name="kai-lol", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
        self.pointer.hide()

    def _show_center(self) -> None:
        cx = user32.GetSystemMetrics(0) // 2
        cy = user32.GetSystemMetrics(1) // 2
        user32.SetCursorPos(cx, cy)
        self.pointer.move(cx - 8, cy - 8)

    def _run(self) -> None:
        self._show_center()
        deadline = time.monotonic() + 60 * 25
        while not self._stop.is_set() and time.monotonic() < deadline:
            if _phase() == "ReadyCheck":
                self._show_center()
                _call("POST", "/lol-matchmaking/v1/ready-check/accept")
                self.pointer.hide()
                self._stop.set()
                try:
                    self.on_ask()
                except Exception:
                    pass
                return
            time.sleep(0.4)
        self.pointer.hide()


def pick(pointer: Pointer, text: str) -> str:
    name = " ".join((text or "").split())
    if not name or name.lower().strip(".!") in SKIP_PICK:
        pointer.hide()
        return t("lol_skip")
    champion_id = _champ_id(name)
    if not champion_id:
        return t("lol_unknown", name=name)
    if not _lock(champion_id):
        return t("lol_closed")
    pointer.hide()
    return t("lol_locked", name=name)
