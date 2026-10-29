"""What the v2 island's pills show: Spotify, Steam games, the machine, the weather.

GitHub, Vercel and Stripe are still here and still read-only, but only fetched
when a key is saved; their pills are switched off in the island for now.
"""

from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

TICK = 2.0
REFRESH = 90.0
GAMES_EVERY = 60.0
WEATHER_EVERY = 900.0
GPU_EVERY = 6.0
CREATE_NO_WINDOW = 0x08000000

_lock = threading.Lock()
_state: dict = {"cards": {}, "version": 0, "keys": None, "now": False}
_seen: dict[str, str] = {}


def _get(url: str, token: str = "", accept: str = "application/json"):
    headers = {"Accept": accept, "User-Agent": "Kai/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def _card(data: dict, error: str | None = None, configured: bool = True, event: dict | None = None) -> dict:
    return {"configured": configured, "data": data, "error": error, "event": event}


# ── Spotify ───────────────────────────────────────────────────────────────────

def _spotify(settings) -> dict:
    """What is playing, read from Windows' media controls. No key involved."""
    import media

    try:
        snap = media.refresh()
    except Exception:
        snap = None
    snap = snap or {}
    return _card(
        {
            "title": str(snap.get("title") or ""),
            "artist": str(snap.get("artist") or ""),
            "playing": bool(snap.get("playing")),
            "position": int(snap.get("position") or 0),
            "duration": int(snap.get("duration") or 0),
            "favorite": str(getattr(settings, "favorite_song", "") or ""),
        }
    )


def media_do(op: str) -> None:
    """Buttons on the Spotify card."""
    import control
    import media
    from settings import Settings

    if op == "toggle":
        media.toggle()
    elif op == "next":
        media.next_track()
    elif op == "prev":
        media.previous_track()
    elif op == "fav_save":
        snap = media.refresh()
        if snap and (snap.get("title") or "").strip():
            settings = Settings()
            settings.favorite_song = " - ".join(part for part in (snap.get("artist") or "", snap.get("title") or "") if part)[:120]
            settings.save()
    elif op == "fav_play":
        song = Settings().favorite_song
        if song:
            control.perform({"op": "play", "key": "spotify", "raw": song})
    refresh()


# ── Steam games ───────────────────────────────────────────────────────────────

# Things Steam installs next to games that nobody plays.
_NOT_GAMES = ("steamworks", "redistributable", "proton", "steam linux runtime", "steamvr")


def _steam_root() -> str:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            return str(winreg.QueryValueEx(key, "SteamPath")[0])
    except OSError:
        return ""


def _steam_games() -> list[dict]:
    root = _steam_root()
    if not root:
        return []
    folders = [root]
    try:
        with open(os.path.join(root, "steamapps", "libraryfolders.vdf"), encoding="utf-8", errors="ignore") as handle:
            folders += [path.replace("\\\\", "\\") for path in re.findall(r'"path"\s+"([^"]+)"', handle.read())]
    except OSError:
        pass
    games = {}
    for folder in folders:
        apps = os.path.join(folder, "steamapps")
        try:
            names = os.listdir(apps)
        except OSError:
            continue
        for name in names:
            if not (name.startswith("appmanifest_") and name.endswith(".acf")):
                continue
            try:
                with open(os.path.join(apps, name), encoding="utf-8", errors="ignore") as handle:
                    text = handle.read()
            except OSError:
                continue
            field = lambda key: (re.search(rf'"{key}"\s+"([^"]*)"', text) or [None, ""])[1]
            title = field("name")
            if not title or any(word in title.lower() for word in _NOT_GAMES):
                continue
            games[field("appid")] = {
                "id": "steam:" + field("appid"), "name": title, "store": "Steam",
                "lastPlayed": int(field("LastPlayed") or 0) * 1000,
            }
    return list(games.values())


def _epic_games() -> list[dict]:
    """Games the Epic launcher has installed, from its own manifest files."""
    folder = os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), "Epic", "EpicGamesLauncher", "Data", "Manifests")
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    games = []
    for name in names:
        if not name.endswith(".item"):
            continue
        try:
            with open(os.path.join(folder, name), encoding="utf-8", errors="ignore") as handle:
                item = json.load(handle)
        except (OSError, ValueError):
            continue
        title = str(item.get("DisplayName") or "")
        app = str(item.get("AppName") or "")
        if not title or not app or "games" not in (item.get("AppCategories") or ["games"]):
            continue
        parts = [str(item.get("CatalogNamespace") or ""), str(item.get("CatalogItemId") or ""), app]
        target = "%3A".join(parts) if all(parts) else app
        _launchers["epic:" + app] = f"com.epicgames.launcher://apps/{target}?action=launch&silent=true"
        games.append({"id": "epic:" + app, "name": title, "store": "Epic", "lastPlayed": 0})
    return games


# Games that come with their own launcher and only show up in the Start menu.
_START_MENU_GAMES = (
    "valorant", "league of legends", "minecraft", "roblox", "genshin impact", "overwatch",
    "world of warcraft", "apex legends", "rocket league", "gta", "grand theft auto", "fortnite",
)
_launchers: dict[str, str] = {}


def _other_games(have: set[str]) -> list[dict]:
    import control

    games = []
    for folded, label, app_id in control._installed():
        if app_id.startswith("steam://") or label.lower() in have:
            continue
        if any(word in folded.split() for word in ("tracker", "studio", "support", "uninstall")):
            continue
        if any(folded.startswith(title) for title in _START_MENU_GAMES):
            _launchers["app:" + app_id] = app_id
            games.append({"id": "app:" + app_id, "name": label, "store": "", "lastPlayed": 0})
    return games


def _games() -> dict:
    rows = _steam_games() + _epic_games()
    rows += _other_games({str(game["name"]).lower() for game in rows})
    # Steam is the only one that says when a game was last played, so those lead.
    rows.sort(key=lambda game: (-game["lastPlayed"], str(game["name"]).lower()))
    return _card({"games": rows, "total": len(rows)})


def launch_game(game_id: str) -> None:
    import control

    if game_id.startswith("steam:") and game_id[6:].isdigit():
        control.open_steam_game(game_id[6:])
    elif game_id in _launchers:
        control._launch(_launchers[game_id])


# ── This computer ─────────────────────────────────────────────────────────────

class _FILETIME(ctypes.Structure):
    _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]


class _MEMORY(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_uint32), ("load", ctypes.c_uint32),
        ("total", ctypes.c_uint64), ("free", ctypes.c_uint64),
        ("page_total", ctypes.c_uint64), ("page_free", ctypes.c_uint64),
        ("virtual_total", ctypes.c_uint64), ("virtual_free", ctypes.c_uint64),
        ("extended", ctypes.c_uint64),
    ]


_cpu_last: tuple[int, int] | None = None
_gpu: dict = {"at": 0.0, "data": {}}


def _cpu_percent() -> int:
    """Busy share since the previous call."""
    global _cpu_last
    idle, kernel, user = _FILETIME(), _FILETIME(), _FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
        return 0
    value = lambda ft: (ft.high << 32) | ft.low
    now = (value(idle), value(kernel) + value(user))
    before, _cpu_last = _cpu_last, now
    if before is None or now[1] == before[1]:
        return 0
    busy = 1.0 - (now[0] - before[0]) / (now[1] - before[1])
    return max(0, min(100, round(busy * 100)))


def _gpu_now() -> dict:
    """Temperature and load from nvidia-smi. Empty on a machine without an Nvidia card."""
    if time.monotonic() - _gpu["at"] < GPU_EVERY:
        return _gpu["data"]
    _gpu["at"] = time.monotonic()
    try:
        done = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,name", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=6, creationflags=CREATE_NO_WINDOW,
        )
        temp, load, name = [part.strip() for part in done.stdout.strip().splitlines()[0].split(",", 2)]
        _gpu["data"] = {"gpuTemp": int(temp), "gpuLoad": int(load), "gpuName": name.replace("NVIDIA ", "").replace("GeForce ", "")}
    except Exception:
        _gpu["data"] = {}
    return _gpu["data"]


def _system() -> dict:
    memory = _MEMORY()
    memory.length = ctypes.sizeof(_MEMORY)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory))
    gb = 1024 ** 3
    data = {
        "cpu": _cpu_percent(),
        "ram": int(memory.load),
        "ramUsed": round((memory.total - memory.free) / gb, 1),
        "ramTotal": round(memory.total / gb),
    }
    data.update(_gpu_now())
    return _card(data)


# ── Weather ───────────────────────────────────────────────────────────────────

_place: dict = {}


def _sky(code: int) -> str:
    """WMO weather code to the name of an i18n string."""
    if code == 0:
        return "sky.clear"
    if code in (1, 2):
        return "sky.partly"
    if code == 3:
        return "sky.cloudy"
    if code in (45, 48):
        return "sky.fog"
    if code in (71, 73, 75, 77, 85, 86):
        return "sky.snow"
    if code >= 95:
        return "sky.storm"
    return "sky.rain"


def _weather(city: str) -> dict:
    from i18n import current, t

    city = " ".join(city.split())
    if not city:
        return _card({}, configured=False)
    try:
        if _place.get("asked") != city:
            found = _get(
                "https://geocoding-api.open-meteo.com/v1/search?count=1&language="
                + current() + "&name=" + urllib.parse.quote(city)
            )
            hit = ((found or {}).get("results") or [None])[0]
            if not hit:
                return _card({}, error=t("sky.no_city", city=city))
            _place.update(asked=city, name=str(hit.get("name") or city), lat=hit["latitude"], lon=hit["longitude"])
        now = _get(
            "https://api.open-meteo.com/v1/forecast?timezone=auto&forecast_days=1"
            "&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m"
            "&daily=temperature_2m_max,temperature_2m_min"
            f"&latitude={_place['lat']}&longitude={_place['lon']}"
        )
    except Exception as exc:
        return _card({}, error=_problem(exc))
    spot = (now or {}).get("current") or {}
    daily = (now or {}).get("daily") or {}
    return _card(
        {
            "city": _place["name"],
            "temp": round(float(spot.get("temperature_2m") or 0)),
            "feels": round(float(spot.get("apparent_temperature") or 0)),
            "wind": round(float(spot.get("wind_speed_10m") or 0)),
            "sky": t(_sky(int(spot.get("weather_code") or 0))),
            "high": round(float((daily.get("temperature_2m_max") or [0])[0])),
            "low": round(float((daily.get("temperature_2m_min") or [0])[0])),
        }
    )


# ── Keyed services, switched off in the island for now ────────────────────────

def _github(token: str) -> tuple[dict, dict | None]:
    accept = "application/vnd.github+json"
    user = _get("https://api.github.com/user", token, accept)
    repos = _get("https://api.github.com/user/repos?per_page=100&affiliation=owner", token, accept)
    owned = repos if isinstance(repos, list) else []
    total = int(user.get("public_repos") or 0) + int(user.get("total_private_repos") or 0)
    data = {
        "login": str(user.get("login") or ""),
        "totalRepos": max(total, len(owned)),
        "totalStars": sum(int(repo.get("stargazers_count") or 0) for repo in owned),
    }
    return data, None


def _vercel(token: str) -> tuple[dict, dict | None]:
    raw = _get("https://api.vercel.com/v6/deployments?limit=3", token)
    rows = []
    for item in (raw or {}).get("deployments") or []:
        meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
        rows.append(
            {
                "id": str(item.get("uid") or ""),
                "projectName": str(item.get("name") or ""),
                "state": str(item.get("readyState") or item.get("state") or "").upper(),
                "createdAt": item.get("created") or item.get("createdAt") or 0,
                "commitMessage": str(meta.get("githubCommitMessage") or "")[:120],
                "branch": str(meta.get("githubCommitRef") or ""),
                "url": str(item.get("url") or ""),
            }
        )
    event = None
    if rows and rows[0]["state"] in {"READY", "ERROR", "CANCELED"}:
        mark = rows[0]["id"] + rows[0]["state"]
        # The first look only records what is there; an event is a change after that.
        if "vercel" in _seen and _seen["vercel"] != mark:
            event = {"success": rows[0]["state"] == "READY", "label": rows[0]["projectName"], "detail": rows[0]["state"].title()}
        _seen["vercel"] = mark
    return {"deployments": rows}, event


def stripe_today(key: str) -> tuple[int, str, int] | None:
    """(amount in cents, currency, number of payments) succeeded since midnight, or None."""
    import time as _time

    if not key:
        return None
    midnight = int(_time.mktime(_time.localtime()[:3] + (0, 0, 0, 0, 0, -1)))
    data = _get(f"https://api.stripe.com/v1/charges?limit=100&created[gte]={midnight}", key)
    if not isinstance(data, dict):
        return None
    paid = [c for c in data.get("data") or [] if c.get("status") == "succeeded" and not c.get("refunded")]
    total = sum(int(c.get("amount") or 0) - int(c.get("amount_refunded") or 0) for c in paid)
    currency = str((paid[0] if paid else {}).get("currency") or "usd")
    return total, currency, len(paid)


def _stripe(key: str) -> tuple[dict, dict | None]:
    balance = _get("https://api.stripe.com/v1/balance", key)
    available = (balance or {}).get("available") or [{}]
    charges = _get("https://api.stripe.com/v1/charges?limit=3", key)
    payments = [
        {
            "id": str(charge.get("id") or ""),
            "description": str(charge.get("description") or charge.get("billing_details", {}).get("name") or "Payment")[:40],
            "amount": int(charge.get("amount") or 0),
            "status": str(charge.get("status") or ""),
            "createdAt": int(charge.get("created") or 0) * 1000,
        }
        for charge in (charges or {}).get("data") or []
    ]
    event = None
    if payments:
        if "stripe" in _seen and _seen["stripe"] != payments[0]["id"]:
            paid = payments[0]["status"] == "succeeded"
            event = {"success": paid, "label": payments[0]["description"], "detail": f"{payments[0]['amount'] / 100:.2f}"}
        _seen["stripe"] = payments[0]["id"]
    data = {
        "balance": int(available[0].get("amount") or 0),
        "currency": str(available[0].get("currency") or "usd"),
        "payments": payments,
    }
    return data, event


SOURCES = (
    ("integration_github", "github_token", _github),
    ("integration_vercel", "vercel_token", _vercel),
    ("integration_stripe", "stripe_key", _stripe),
)


def _problem(exc: Exception) -> str:
    from i18n import t

    if isinstance(exc, urllib.error.HTTPError):
        if exc.code in (401, 403):
            return t("err.bad_key")
        return f"HTTP {exc.code}"
    return t("no_link")


def _fetch(settings) -> dict:
    cards = {}
    for card_id, field, source in SOURCES:
        key = (getattr(settings, field, "") or "").strip()
        if not key or not key.isascii():
            cards[card_id] = _card({}, configured=False)
            continue
        try:
            data, event = source(key)
            cards[card_id] = _card(data, event=event)
        except Exception as exc:
            cards[card_id] = _card({}, error=_problem(exc))
    return cards


def _loop() -> None:
    from settings import Settings

    last = games_at = weather_at = 0.0
    weather_for = None
    while True:
        settings = Settings()
        now = time.monotonic()
        keys = tuple((getattr(settings, field, "") or "").strip() for _id, field, _source in SOURCES)
        with _lock:
            forced, _state["now"] = _state["now"], False
            fresh = {card_id: {**card, "event": None} for card_id, card in _state["cards"].items()}
        if forced or keys != _state["keys"] or now - last >= REFRESH:
            fresh.update(_fetch(settings))
            last = now
        if forced or now - games_at >= GAMES_EVERY or "integration_games" not in fresh:
            fresh["integration_games"] = _games()
            games_at = now
        place = (settings.weather_city, settings.language)
        if forced or place != weather_for or now - weather_at >= WEATHER_EVERY:
            fresh["integration_weather"] = _weather(settings.weather_city)
            weather_at, weather_for = now, place
        fresh["integration_spotify"] = _spotify(settings)
        fresh["integration_system"] = _system()
        with _lock:
            _state["keys"] = keys
            if fresh != _state["cards"]:
                _state["cards"] = fresh
                _state["version"] += 1
        time.sleep(TICK)


def start() -> None:
    threading.Thread(target=_loop, daemon=True).start()


def refresh() -> None:
    with _lock:
        _state["now"] = True


def take(seen_version: int) -> tuple[int, dict | None]:
    """The cards, if they changed since `seen_version`."""
    with _lock:
        if _state["version"] == seen_version:
            return seen_version, None
        return _state["version"], dict(_state["cards"])
