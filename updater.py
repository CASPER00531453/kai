"""Find, download and install a newer Kai.

The latest GitHub release of version.UPDATE_REPO is the source of truth. Its
tag is the version ("v2.1.0" or "2.1.0") and its Kai-Setup*.exe asset is the
installer. The download is checked against the SHA-256 GitHub publishes for
the asset, then the installer runs silently: it closes Kai, replaces it in
place (settings stay in %APPDATA%\\Kai) and starts it again.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.request

from version import UPDATE_REPO, VERSION

_lock = threading.Lock()
_state: dict = {"checked": False, "latest": None, "url": None, "digest": None, "notes": "", "page": "", "error": None, "at": 0.0}
# How often Kai looks again while it runs: a few times a day.
EVERY = 6 * 3600


def _cache_path() -> str:
    from settings import v2_file

    return v2_file("update.json")


def _save(state: dict) -> None:
    try:
        path = _cache_path()
        with open(path + ".tmp", "w", encoding="utf-8") as handle:
            json.dump(state, handle)
        os.replace(path + ".tmp", path)
    except Exception:
        pass


def _load() -> None:
    """A newer check made by the other process."""
    try:
        with open(_cache_path(), encoding="utf-8") as handle:
            saved = json.load(handle)
    except Exception:
        return
    if isinstance(saved, dict) and float(saved.get("at") or 0) > float(_state.get("at") or 0):
        _state.update({key: saved.get(key) for key in _state})


def _parse(version: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", version or "")
    return tuple(int(p) for p in parts[:3]) + (0,) * (3 - len(parts[:3]))


def newer(candidate: str, current: str = VERSION) -> bool:
    return _parse(candidate) > _parse(current)


def check(timeout: float = 10) -> dict:
    """Ask GitHub for the latest release. Never raises; errors land in 'error'."""
    result = {"checked": True, "latest": None, "url": None, "digest": None, "notes": "", "page": "", "error": None, "at": time.time()}
    if not UPDATE_REPO:
        result["error"] = "no-repo"
    else:
        try:
            request = urllib.request.Request(
                f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest",
                headers={"Accept": "application/vnd.github+json", "User-Agent": f"Kai/{VERSION}"},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                release = json.loads(response.read().decode("utf-8"))
            asset = next(
                (a for a in release.get("assets") or [] if re.match(r"(?i)kai-setup.*\.exe$", str(a.get("name") or ""))),
                None,
            )
            result["latest"] = str(release.get("tag_name") or "").lstrip("vV")
            result["notes"] = str(release.get("body") or "")[:400]
            page = str(release.get("html_url") or "")
            result["page"] = page if page.startswith("https://github.com/") else ""
            if asset:
                result["url"] = asset.get("browser_download_url")
                digest = str(asset.get("digest") or "")
                result["digest"] = digest.split(":", 1)[1] if digest.startswith("sha256:") else None
            else:
                result["error"] = "no-installer"
        except Exception as exc:
            # No release published yet is not a failure: there is simply nothing newer.
            if getattr(exc, "code", None) != 404:
                result["error"] = type(exc).__name__
    with _lock:
        _state.update(result)
    _save(result)
    return dict(result)


def due() -> bool:
    """True when the last look at GitHub is older than EVERY."""
    with _lock:
        _load()
        return time.time() - float(_state.get("at") or 0) > EVERY


def status() -> dict:
    with _lock:
        _load()
        state = dict(_state)
    state["current"] = VERSION
    state["available"] = bool(state["url"] and state["latest"] and newer(state["latest"]))
    return state


def install(progress=None) -> str | None:
    """Download the newer installer and start it. Returns an error key, or None once it is running."""
    state = status()
    if not state["available"]:
        return "none"
    url = str(state["url"])
    if not url.startswith("https://github.com/") and not url.startswith("https://objects.githubusercontent.com/"):
        return "bad-url"
    target = os.path.join(tempfile.gettempdir(), f"Kai-Setup-{state['latest']}.exe")
    digest = hashlib.sha256()
    try:
        request = urllib.request.Request(url, headers={"User-Agent": f"Kai/{VERSION}"})
        with urllib.request.urlopen(request, timeout=60) as response, open(target, "wb") as handle:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = response.read(1 << 16)
                if not chunk:
                    break
                handle.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress and total:
                    progress(done / total)
    except Exception:
        return "download"
    # GitHub publishes each asset's SHA-256; a mismatch means a broken or swapped file.
    if state["digest"] and digest.hexdigest().lower() != state["digest"].lower():
        try:
            os.remove(target)
        except OSError:
            pass
        return "checksum"
    # The installer closes Kai, updates it and starts it again (see Kai.iss).
    # Without PyInstaller's own variables: the new Kai inherits this environment
    # through the installer, and with them it took itself for a child of this
    # one and ran the old version's unpacked files instead of its own.
    env = {
        key: value for key, value in os.environ.items()
        if not key.upper().startswith(("_PYI", "_MEI"))
    }
    subprocess.Popen([target, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], close_fds=True, env=env)
    return None
