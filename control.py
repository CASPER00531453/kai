"""Open and close apps from a spoken command. No raw shell."""

from __future__ import annotations

import os
import re
import subprocess
import threading
import time
import urllib.parse

from i18n import t

CREATE_NO_WINDOW = 0x08000000

APPS = {
    "spotify": {"label": "Spotify", "uri": "spotify:", "kill": "Spotify.exe"},
    "steam": {"label": "Steam", "uri": "steam:", "kill": "steam.exe"},
    "discord": {"label": "Discord", "uri": "discord:", "kill": "Discord.exe"},
    "chrome": {"label": "Chrome", "exe": "chrome"},
    "google chrome": {"label": "Chrome", "exe": "chrome"},
    "firefox": {"label": "Firefox", "exe": "firefox"},
    "edge": {"label": "Edge", "exe": "msedge"},
    "microsoft edge": {"label": "Edge", "exe": "msedge"},
    "notepad": {"label": "Not defteri", "exe": "notepad"},
    "not defteri": {"label": "Not defteri", "exe": "notepad"},
    "hesap makinesi": {"label": "Hesap makinesi", "exe": "calc"},
    "hesap": {"label": "Hesap makinesi", "exe": "calc"},
    "calc": {"label": "Hesap makinesi", "exe": "calc"},
    "vscode": {"label": "VS Code", "exe": "code"},
    "visual studio code": {"label": "VS Code", "exe": "code"},
    "kod": {"label": "VS Code", "exe": "code"},
    "whatsapp": {"label": "WhatsApp", "exe": "whatsapp"},
    "telegram": {"label": "Telegram", "exe": "telegram"},
    "epic": {"label": "Epic Games", "uri": "com.epicgames.launcher:"},
    "epic games": {"label": "Epic Games", "uri": "com.epicgames.launcher:"},
    "epic games launcher": {"label": "Epic Games", "uri": "com.epicgames.launcher:"},
    "fortnite": {
        "label": "Fortnite",
        "uri": "com.epicgames.launcher://apps/Fortnite?action=launch&silent=true",
    },
    "valorant": {
        "label": "Valorant",
        "uri": "riotclient://launch-product=valorant&launch-patchline=live",
    },
    "counter strike": {"label": "Counter-Strike", "uri": "steam://rungameid/730"},
    "counter-strike": {"label": "Counter-Strike", "uri": "steam://rungameid/730"},
    "counter strike 2": {"label": "Counter-Strike", "uri": "steam://rungameid/730"},
    "cs2": {"label": "Counter-Strike", "uri": "steam://rungameid/730"},
    "cs": {"label": "Counter-Strike", "uri": "steam://rungameid/730"},
    "league": {"label": "League of Legends", "uri": "leagueoflegends:"},
    "league of legends": {"label": "League of Legends", "uri": "leagueoflegends:"},
    "lol": {"label": "League of Legends", "uri": "leagueoflegends:"},
    "paint": {"label": "Paint", "exe": "mspaint"},
    "ayarlar": {"label": "Ayarlar", "uri": "ms-settings:"},
    "kamera": {"label": "Kamera", "uri": "microsoft.windows.camera:"},
}

# False when the last perform() could not do what was asked.
last_ok = True

BLOCKED = {
    "cmd", "powershell", "pwsh", "reg", "regedit", "mmc", "taskkill",
    "explorer", "kai", "python",
}


def _fold(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("’", "").replace("'", "").replace("`", "")
    text = re.sub(r"[^\w\sçğıöşü]", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _stem(token: str) -> str:
    for key in sorted(APPS, key=len, reverse=True):
        if token == key:
            return key
        if token.startswith(key):
            rest = token[len(key):].strip()
            if rest in {"", "i", "ı", "u", "ü", "e", "a", "yi", "yı", "yu", "yü", "ni", "nı", "nu", "nü"}:
                return key
    return token


CLOSE_VERBS = {"kapat", "kapa", "kapatır", "kapatir", "kapatsana", "kapatırmısın", "close"}
OPEN_VERBS = {"aç", "ac", "açsana", "acsana", "açar", "açarmısın", "başlat", "baslat", "başlatsana", "open", "çalıştır", "calistir"}
FILLER = {
    "o", "zaman", "lütfen", "lutfen", "bi", "bir", "şunu", "sunu", "şu", "su", "hadi", "abi", "kanka",
    "reis", "kai", "kay", "mısın", "misin", "musun", "bana", "benim", "için", "icin", "hemen", "ya", "la",
    "lan", "uygulamasını", "uygulamasini", "uygulaması", "programını", "programi", "oyununu", "oyunu",
}
SONG_WORDS = {
    "şarkısını", "sarkisini", "şarkısı", "şarkı", "sarki", "sarkisini",
    "parçasını", "parcasini", "türküsünü", "turkusunu", "müzik", "muzik", "music",
}
PLAY_VERBS = {"çal", "cal", "çalsana", "calsana", "oynat", "dinlet", "dinle", "play", "çalalım", "calalim"}
PAUSE_VERBS = {"durdur", "duraklat", "pause", "durdursana", "duraklatsana"}
RESUME_VERBS = {"devam", "devamını", "devamini", "devamettir", "resume", "oynatmaya"}
NEXT_VERBS = {"sonraki", "sonrakine", "skip", "atla", "atlat"}
PREV_VERBS = {"önceki", "onceki", "öncekine", "oncekine", "geri"}
MUSIC_DROP = FILLER | SONG_WORDS | PLAY_VERBS | OPEN_VERBS | PAUSE_VERBS | RESUME_VERBS | NEXT_VERBS | PREV_VERBS


def _has_spotify(tokens: list[str]) -> bool:
    return any(t.startswith("spotify") for t in tokens)


def _transport(tokens: list[str]) -> dict | None:
    op = None
    if any(t in PAUSE_VERBS for t in tokens):
        op = "pause"
    elif any(t in NEXT_VERBS for t in tokens):
        op = "next"
    elif any(t in PREV_VERBS for t in tokens):
        op = "prev"
    elif any(t in RESUME_VERBS for t in tokens):
        op = "resume"
    if not op:
        return None
    leftover = [t for t in tokens if t not in MUSIC_DROP and not t.startswith("spotify")]
    leftover = [t for t in leftover if not t.startswith(("şark", "sark", "müz", "muz"))]
    about_music = _has_spotify(tokens) or any(t in SONG_WORDS or t.startswith(("şark", "sark", "müz", "muz")) for t in tokens) or len(tokens) <= 3
    if leftover or not about_music:
        return None
    return {"op": op, "key": "spotify", "raw": ""}


def _music(folded: str) -> dict | None:
    tokens = folded.split()
    if not tokens:
        return None
    moved = _transport(tokens)
    if moved:
        return moved
    has_song = any(t in SONG_WORDS or t.startswith("şark") or t.startswith("sark") for t in tokens)
    has_spotify = _has_spotify(tokens)
    has_play = any(t in PLAY_VERBS for t in tokens)
    has_open = any(t in OPEN_VERBS for t in tokens)
    if not (has_play or has_song or (has_spotify and has_open) or (has_spotify and len(tokens) > 1 and not has_open and not any(t in CLOSE_VERBS for t in tokens))):
        return None
    words = [t for t in tokens if not t.startswith("spotify") and t not in MUSIC_DROP]
    query = " ".join(words).strip()
    if not query:
        return None
    if has_open and not has_spotify and not has_song and not has_play:
        return None
    return {"op": "play", "key": "spotify", "raw": query}


def intent(text: str) -> dict | None:
    folded = _fold(text)
    if not folded:
        return None
    tokens = folded.split()
    op = None
    at = -1
    for index, token in enumerate(tokens):
        if token in CLOSE_VERBS:
            op, at = "close", index
            break
        if token in OPEN_VERBS:
            op, at = "open", index
            break
    if op is None:
        if folded in APPS:
            return {"op": "open", "key": folded, "raw": folded}
        return None
    before = [t for t in tokens[:at] if t not in FILLER]
    after = [t for t in tokens[at + 1 :] if t not in FILLER]
    target = " ".join(before or after).strip()
    if not target:
        return None
    key = _stem(target)
    if key not in APPS:
        for size in (2, 1):
            for start in range(len(before or after)):
                piece = " ".join((before or after)[start : start + size])
                stem = _stem(piece)
                if stem in APPS:
                    key = stem
                    break
            if key in APPS:
                break
    if key in APPS:
        return {"op": op, "key": key, "raw": target}
    if op == "open":
        return {"op": "open", "key": None, "raw": target}
    return None


def _shortcut(name: str) -> str | None:
    want = _fold(name)
    if len(want) < 3:
        return None
    roots = [
        os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
        os.path.join(os.environ.get("PROGRAMDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
        os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
        os.path.join(os.environ.get("PUBLIC", ""), "Desktop"),
    ]
    loose = None
    loose_score = 0
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            for file in files:
                if not file.lower().endswith(".lnk"):
                    continue
                stem = _fold(os.path.splitext(file)[0])
                if stem in BLOCKED or any(part in BLOCKED for part in stem.split()):
                    continue
                path = os.path.join(dirpath, file)
                if stem == want:
                    return path
                score = 2 if stem.startswith(want) or want.startswith(stem) else 1 if want in stem else 0
                if score > loose_score:
                    loose = path
                    loose_score = score
    return loose


_start_apps: dict = {"at": 0.0, "rows": []}


def _installed() -> list[tuple[str, str, str]]:
    """Every app in the Start menu as (folded name, name, AppID). Store apps included."""
    import json

    if _start_apps["rows"] and time.monotonic() - _start_apps["at"] < 600:
        return _start_apps["rows"]
    script = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json -Compress"
    try:
        done = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            timeout=20,
            creationflags=CREATE_NO_WINDOW,
        )
        found = json.loads(done.stdout.decode("utf-8", errors="replace") or "[]")
    except Exception:
        return _start_apps["rows"]
    if isinstance(found, dict):
        found = [found]
    rows = []
    for item in found:
        name = str(item.get("Name") or "").strip()
        app_id = str(item.get("AppID") or "").strip()
        # Start menu links to web pages and uninstallers are not apps.
        if not name or not app_id or app_id.lower().startswith(("http://", "https://")):
            continue
        folded = _fold(name)
        if _blocked_name(name) or any(word in folded.split() for word in ("uninstall", "kaldır", "kaldir")):
            continue
        rows.append((folded, name, app_id))
    _start_apps["rows"] = rows
    _start_apps["at"] = time.monotonic()
    return rows


def _find_app(name: str) -> tuple[str, str] | None:
    """Best Start menu match for a spoken name, as (name, AppID)."""
    want = _fold(name)
    if len(want) < 3:
        return None
    words = set(want.split())
    best = None
    for folded, label, app_id in _installed():
        if folded == want:
            rank = 0
        elif folded.startswith(want + " ") or want.startswith(folded + " "):
            rank = 1
        elif words <= set(folded.split()):
            rank = 2
        else:
            continue
        score = (rank, len(folded))
        if best is None or score < best[0]:
            best = (score, label, app_id)
    return (best[1], best[2]) if best else None


def _running(exe: str) -> bool:
    try:
        done = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {exe}", "/NH", "/FO", "CSV"],
            capture_output=True,
            timeout=10,
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception:
        return False
    return exe.lower().encode() in done.stdout.lower()


def _launch(app_id: str) -> None:
    if "://" in app_id or app_id.endswith(":"):
        os.startfile(app_id)
    else:
        # The same thing the Start menu does, so a launcher hiding in the tray comes to the front.
        subprocess.Popen(["explorer.exe", "shell:AppsFolder\\" + app_id])


def _steam_then(game: str) -> None:
    """Steam first, the game once Steam is up."""
    steam = _find_app("steam")
    try:
        _launch(steam[1] if steam else "steam:")
    except OSError:
        return
    for _ in range(60):
        if _running("steam.exe"):
            break
        time.sleep(1)
    time.sleep(8)
    try:
        os.startfile(game)
    except OSError:
        pass


def open_steam_game(app_id: str) -> None:
    """A game from the island's games card. Steam first when it is not running."""
    target = f"steam://rungameid/{app_id}"
    if _running("steam.exe"):
        os.startfile(target)
    else:
        threading.Thread(target=_steam_then, args=(target,), daemon=True).start()


def _system_intent(folded: str) -> dict | None:
    """Volume, brightness, lock, sleep, shutdown — this computer only."""
    tokens = folded.split()
    has = lambda *words: any(w in folded for w in words)
    number = next((int(tok) for tok in tokens if tok.isdigit()), None)
    minutes = number if has("dakika", "dk", "minute") else 0

    if has("kilitle", "lock") and not has("ekrani izle", "ekranı izle"):
        return {"do": "sys", "act": "lock"}
    if has("uyut", "uyku moduna", "uyku moduna", "sleep", "uykuya"):
        return {"do": "sys", "act": "sleep"}
    if has("yeniden baslat", "yeniden başlat", "restart", "resetle", "tekrar baslat", "tekrar başlat"):
        return {"do": "sys", "act": "restart", "arg": minutes}
    # Power-off only when the target is the computer, never an app.
    pc = has("bilgisayar", "sistem", "pc", "windows", "makine")
    if has("kapatmayi iptal", "kapatmayı iptal", "iptal et") and has("kapat", "kapan"):
        return {"do": "sys", "act": "cancel"}
    if pc and has("kapat", "kapan"):
        return {"do": "sys", "act": "shutdown", "arg": minutes}
    if has("parlakl", "brightness", "ekrani karart", "ekranı karart", "ekran karart"):
        if number is not None and not minutes:
            return {"do": "sys", "act": "bright_set", "arg": number}
        if has("artir", "artır", "yukselt", "yükselt", "ac", "aç", "arttir", "arttır"):
            return {"do": "sys", "act": "bright_up"}
        if has("azalt", "dusur", "düşür", "kis", "kıs", "karart", "indir"):
            return {"do": "sys", "act": "bright_down"}
    if has("ses", "sesi", "volume"):
        if has("kapat", "sustur", "kes", "mute"):
            return {"do": "sys", "act": "vol_mute"}
        if has("ac", "aç", "yukselt", "yükselt", "artir", "artır", "arttir", "arttır"):
            return {"do": "sys", "act": "vol_up"}
        if has("kis", "kıs", "azalt", "dusur", "düşür", "indir"):
            return {"do": "sys", "act": "vol_down"}
    return None


_MEM_SAVE = re.compile(
    r"\b(şunu|sunu|bunu|şu|su)?\s*(hatırla|hatirla|unutma|aklında tut|aklinda tut|aklına yaz|aklina yaz|not et)\b[:,]?",
    re.IGNORECASE,
)
_MEM_TAIL = re.compile(r"\b(olduğunu|oldugunu|diye)?\s*(hatırla|hatirla|unutma|aklında tut|aklinda tut)\s*$", re.IGNORECASE)


def _memory_intent(text: str, folded: str) -> dict | None:
    """'Şunu hatırla: ...', '... olduğunu unutma', 'neyi hatırlıyorsun', '... unut'."""
    # "hatırlat" is a reminder, not memory.
    if "hatırlat" in folded or "hatirlat" in folded:
        return None
    if any(p in folded for p in ("hafızanı sil", "hafizani sil", "her şeyi unut", "her seyi unut", "hafızanı temizle")):
        return {"do": "mem", "act": "clear"}
    if any(p in folded for p in (
        "neyi hatırlıyorsun", "neyi hatirliyorsun", "ne hatırlıyorsun", "neler hatırlıyorsun",
        "hatırladıklarını", "hatirladiklarini", "hafızanda ne", "hafizanda ne",
        "benim hakkımda ne biliyorsun", "benim hakkimda ne biliyorsun", "beni ne kadar tanıyorsun",
    )):
        return {"do": "mem", "act": "list"}
    if "unutma" not in folded and re.search(r"\bunut\b", folded):
        fact = re.sub(r"\b(unut|bunu|şunu|sunu|lütfen|lutfen)\b", " ", text, flags=re.IGNORECASE)
        return {"do": "mem", "act": "forget", "text": " ".join(fact.split()).strip(" .,'")}
    if _MEM_SAVE.search(text) or _MEM_TAIL.search(text):
        fact = _MEM_TAIL.sub("", text)
        fact = _MEM_SAVE.sub(" ", fact)
        fact = re.sub(r"^\s*(kai|kay)\b[,]?", " ", fact, flags=re.IGNORECASE)
        return {"do": "mem", "act": "save", "text": " ".join(fact.split()).strip(" .,:;-'")}
    return None


def do_memory(decision: dict) -> str:
    import memory

    act = decision.get("act")
    text = str(decision.get("text") or "")
    if act == "save":
        if not memory.add(text):
            return t("mem.what")
        return t("mem.saved", fact=text)
    if act == "list":
        known = memory.facts()
        return t("mem.list", facts="; ".join(known[-15:])) if known else t("mem.empty")
    if act == "forget":
        count = memory.forget(text)
        return t("mem.forgot", count=count) if count else t("mem.forgot_none")
    if act == "clear":
        memory.clear()
        import brain

        brain._history.clear()
        return t("mem.cleared")
    return ""


def _reminder_intent(text: str, folded: str) -> dict | None:
    """'20 dakika sonra fırını hatırlat', 'yarın 9'da uyandır', 'alarmları sil'."""
    words = ("hatırlat", "hatirlat", "uyandır", "uyandir", "alarm", "zamanlayıcı", "zamanlayici", "geri sayım", "geri sayim")
    if not any(word in folded for word in words):
        return None
    if any(w in folded for w in ("sil", "iptal", "temizle", "kaldır", "kaldir")):
        return {"do": "rem", "act": "clear"}
    if any(w in folded for w in ("neler", "listele", "ne var", "göster", "goster", "hangi")) and not any(
        ch.isdigit() for ch in folded
    ):
        return {"do": "rem", "act": "list"}
    return {"do": "rem", "act": "add", "text": text}


def do_reminder(decision: dict) -> str:
    import reminders

    act = decision.get("act")
    if act == "clear":
        return t("rem.cleared", count=reminders.clear())
    if act == "list":
        items = reminders.upcoming()
        if not items:
            return t("rem.none")
        shown = [f"{reminders.when(item['due'])} {item['text']}".strip() for item in items[:8]]
        return t("rem.list", items="; ".join(shown))
    parsed = reminders.parse(str(decision.get("text") or ""))
    if not parsed:
        return t("rem.when")
    due, what = parsed
    reminders.add(due, what)
    if what:
        return t("rem.set", when=reminders.when(due), text=what)
    return t("rem.set_plain", when=reminders.when(due))


def do_system(decision: dict) -> str:
    import system

    return system.run(str(decision.get("act") or ""), int(decision.get("arg") or 0))


def direct_command(text: str) -> dict | None:
    """Commands Groq keeps turning into chat. Only exact, unambiguous phrases."""
    folded = _fold(text)
    if not folded:
        return None
    sysish = _system_intent(folded)
    if sysish:
        return sysish
    remind = _reminder_intent(text, folded)
    if remind:
        return remind
    remembered = _memory_intent(text, folded)
    if remembered:
        return remembered
    if "favori" in folded and any(word in folded for word in ("cal", "çal", "oynat", "baslat", "aç", "ac")):
        return {"do": "favorite_play"}
    if "favori" in folded and any(word in folded for word in ("kodla", "kaydet", "yap", "olarak", "isaretle", "işaretle")):
        return {"do": "favorite_save"}
    if any(phrase in folded for phrase in (
        "karsilasmayi otomatik kabul",
        "karşılaşmayı otomatik kabul",
        "otomatik kabul",
        "maci kabul",
        "maçı kabul",
        "mac kabul",
        "karsilasmayi kabul",
    )):
        return {"do": "lol_accept"}
    if "kabul" in folded and any(word in folded for word in ("birak", "bırak", "iptal", "kapat", "durdur")):
        return {"do": "lol_stop"}
    # "X çal" names its own song; asking the model here only invites it to say "playing" and do nothing.
    music = _music(folded)
    if music:
        return {"do": "play", "q": music["raw"]} if music["op"] == "play" else {"do": music["op"]}
    return None


def _blocked_name(name: str) -> bool:
    folded = _fold(name)
    if not folded:
        return False
    parts = folded.split()
    return folded in BLOCKED or any(part in BLOCKED for part in parts)


def perform(action: dict) -> str:
    global last_ok
    last_ok = False
    spec = APPS.get(action["key"]) if action.get("key") else None
    label = spec["label"] if spec else action["raw"]
    try:
        if action["op"] == "play":
            import media

            query = action["raw"]
            name = media.play_song(query)
            if not name:
                os.startfile("spotify:search:" + urllib.parse.quote(query))
                return t("app.searched", query=query)
            last_ok = True
            return t("app.playing", name=name)
        if action["op"] in {"pause", "resume", "next", "prev", "toggle"}:
            import media

            fn = {"pause": media.pause, "resume": media.resume, "next": media.next_track, "prev": media.previous_track, "toggle": media.toggle}[action["op"]]
            ok = fn()
            if not ok:
                return t("app.no_media")
            last_ok = True
            return t("app." + action["op"])
        if action["op"] == "open":
            if _blocked_name(action.get("raw") or "") or _blocked_name(label):
                return t("app.refuse")
            found = _find_app(label) or _find_app(action.get("raw") or "")
            target = found[1] if found else (spec.get("uri") if spec else None)
            if found:
                label = found[0]
            if target and target.startswith("steam://") and not _running("steam.exe"):
                threading.Thread(target=_steam_then, args=(target,), daemon=True).start()
                last_ok = True
                return t("app.steam_first", label=label)
            if target:
                _launch(target)
            elif spec and spec.get("exe"):
                path = _shortcut(spec["label"])
                if path:
                    os.startfile(path)
                else:
                    subprocess.Popen(["cmd", "/c", "start", "", spec["exe"]], creationflags=CREATE_NO_WINDOW)
            else:
                path = _shortcut(action["raw"])
                if not path:
                    return t("app.not_found", label=label)
                os.startfile(path)
            last_ok = True
            return t("app.opening", label=label)
        if not spec or not spec.get("kill"):
            return t("app.cant_close", label=label)
        subprocess.run(
            ["taskkill", "/IM", spec["kill"], "/T"],
            creationflags=CREATE_NO_WINDOW,
            capture_output=True,
        )
        last_ok = True
        return t("app.closed", label=label)
    except Exception:
        return t("app.open_failed", label=label) if action["op"] == "open" else t("app.close_failed", label=label)


def click_intent(text: str) -> str | None:
    folded = _fold(text)
    tokens = folded.split()
    pointed = any(
        t in {"bunu", "şunu", "sunu", "buna", "şuna", "ekrandakini", "ekrandaki"}
        or t.startswith(("ekrandan", "ekranımdan", "ekranimdan"))
        for t in tokens
    )
    if not pointed:
        return None
    if any(t.startswith(v) for t in tokens for v in ("oyna", "çal", "cal", "başlat", "baslat", "tıkla", "tikla")):
        return "play"
    if any(t.startswith(("aç", "ac")) for t in tokens):
        return "open"
    return None


def watch_intent(text: str) -> str | None:
    folded = _fold(text)
    tokens = folded.split()
    stops = ("bırak", "birak", "kes", "durdur", "dur", "kapat", "yeter", "stop")
    if any(t.startswith("izleme") for t in tokens) and any(t.startswith(s) for t in tokens for s in stops):
        return "stop"
    if "izleme" in tokens and len(tokens) <= 3:
        return "stop"
    screen = any(t.startswith("ekran") for t in tokens)
    asks = {"ne", "neler", "nedir", "neyi", "kim", "hangi", "nasıl", "nasil", "oku", "anlat", "söyle", "soyle", "açıkla", "acikla"}
    if screen and (any(t in asks for t in tokens) or any(t.startswith(v) for t in tokens for v in ("görüyor", "goruyor", "yazıyor", "yaziyor"))):
        return "look"
    looks = any(t.startswith(v) for t in tokens for v in ("izle", "bak", "takip"))
    if screen and looks:
        return "start"
    if any(t.startswith(("tuyo", "ipucu", "taktik")) for t in tokens):
        return "start"
    if folded in {"izle", "ekrani izle", "ekranı izle", "beni izle", "izle beni", "oyunumu izle", "oyunu izle"}:
        return "start"
    if any(t.startswith("kamera") for t in tokens) and any(t.startswith(("izle", "bak", "ac", "aç")) for t in tokens):
        return "camera"
    return None


def handle(text: str) -> str | None:
    action = intent(text)
    if not action:
        return None
    return perform(action)


def carry_out(settings, text: str) -> str | None:
    """Open, close, Spotify and the saved favorite. None means it is just chat."""
    import media

    from brain import decide

    heard = " ".join(str(text or "").split())
    if not heard:
        return None
    forced = direct_command(heard)
    action = intent(heard)
    if action and (action.get("key") or action.get("op") == "open"):
        return perform(action)
    try:
        decision = forced or decide(settings, heard, "")
    except Exception:
        decision = {"do": "chat"}
    op = (decision or {}).get("do") or "chat"
    if op == "chat":
        return None
    if op == "sys":
        return do_system(decision)
    if op == "mem":
        return do_memory(decision)
    if op == "rem":
        return do_reminder(decision)
    if op in {"resume", "pause", "next", "prev"}:
        return perform({"op": op, "key": "spotify", "raw": ""})
    if op == "play":
        query = decision.get("q") or ""
        if query:
            return perform({"op": "play", "key": "spotify", "raw": query})
        return perform({"op": "resume", "key": "spotify", "raw": ""})
    if op == "favorite_save":
        snap = media.current()
        if not snap or not (snap.get("title") or "").strip():
            return t("fav_none_playing")
        saved = " - ".join(part for part in (snap.get("artist") or "", snap.get("title") or "") if part)
        settings.favorite_song = saved[:120]
        settings.save()
        return t("fav_saved", song=settings.favorite_song)
    if op == "favorite_play":
        query = settings.favorite_song
        if not query:
            return t("fav_missing")
        return perform({"op": "play", "key": "spotify", "raw": query})
    if op in {"open", "close"}:
        app = decision.get("app") or ""
        if not app:
            return None
        opened = intent(f"{app} {'kapat' if op == 'close' else 'aç'}")
        if not opened or (op == "close" and not opened.get("key")):
            if op != "open":
                return None
            opened = {"op": "open", "key": None, "raw": app}
        elif op == "open" and not opened.get("key"):
            opened = {"op": "open", "key": None, "raw": app}
        return perform(opened)
    return None
