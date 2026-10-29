"""Speech models that run on this computer: recognition, wake word and Kai's own voice.

Each model comes from the sherpa-onnx releases on GitHub, is checked against
its SHA-256 before anything is unpacked, and lands in
%LOCALAPPDATA%\\Kai\\models\\<id>. Nothing here runs on its own: the app's
Download button calls `download`, and the speech code calls `path`.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tarfile
import threading
import time
import urllib.request

BASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download"

# id: (title, url, bytes, sha256, the file that proves it is unpacked)
CATALOG: dict[str, dict] = {
    "whisper": {
        "title": "Whisper Turbo",
        "about": "Türkçe dahil 99 dil. Dikte, not alıcı ve OK Kai için.",
        "url": f"{BASE}/asr-models/sherpa-onnx-whisper-turbo.tar.bz2",
        "size": 563_816_634,
        "sha256": "b11acbbcd660b44a8e0df33724feb5aaa709cf65668f2823d59f656312544f22",
        "check": "turbo-tokens.txt",
    },
    "parakeet": {
        "title": "Parakeet v3",
        "about": "25 Avrupa dili, Türkçe yok. Daha hızlı ve isabetli.",
        "url": f"{BASE}/asr-models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2",
        "size": 487_190_000,
        "sha256": "5793d0fd397c5778d2cf2126994d58e9d56b1be7c04d13c7a15bb1b4eafb16bf",
        "check": "tokens.txt",
    },
    "wake": {
        "title": "OK Kai",
        "about": "Uyandırma sözünü bilgisayarda duyar; ses dışarı gitmez.",
        "url": f"{BASE}/kws-models/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01.tar.bz2",
        "size": 17_600_000,
        "sha256": "f170013b4716e41b62b9bfd809687c207cef798ef9bc6534d524e17af9b6561a",
        "check": "tokens.txt",
    },
    "speakers": {
        "title": "Konuşmacı ayırma",
        "about": "Not alıcıda kimin konuştuğunu ayırır.",
        "url": f"{BASE}/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2",
        "size": 6_900_000,
        "sha256": "24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488",
        "check": "model.onnx",
        "extra": (f"{BASE}/speaker-recongition-models/wespeaker_en_voxceleb_resnet34_LM.onnx", "voice.onnx", "e9848563da86f263117134dfd7ad63c92355b37de492b55e325400c9d9c39012"),
    },
    "voice_tr": {
        "title": "Kai'nin Türkçe sesi",
        "about": "İnternetsiz Türkçe ses. Bedava, anahtar istemez, hiç kesilmez.",
        "url": f"{BASE}/tts-models/vits-piper-tr_TR-fahrettin-medium.tar.bz2",
        "size": 67_212_827,
        "sha256": "2ee3c18b5dc0a5faf913f995b027163befa6e7a6ad2f5c6b8a2e99fe1aad8b6d",
        "check": "tr_TR-fahrettin-medium.onnx",
    },
}

_lock = threading.Lock()
_jobs: dict[str, dict] = {}


def root() -> str:
    folder = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "Kai", "models")
    os.makedirs(folder, exist_ok=True)
    return folder


def path(model: str) -> str | None:
    """The unpacked model's folder, or None while it is not downloaded."""
    info = CATALOG.get(model)
    if not info:
        return None
    folder = os.path.join(root(), model)
    for here, _dirs, files in os.walk(folder):
        if info["check"] in files:
            return here
    return None


def status() -> list[dict]:
    """What the Download buttons show."""
    out = []
    for model, info in CATALOG.items():
        with _lock:
            job = dict(_jobs.get(model) or {})
        out.append({
            "id": model,
            "title": info["title"],
            "about": info["about"],
            "size": info["size"],
            "ready": path(model) is not None,
            "busy": bool(job.get("busy")),
            "done": job.get("done", 0),
            "error": job.get("error", ""),
        })
    return out


def download(model: str) -> bool:
    """Starts a download in the background. False when one is already running."""
    if model not in CATALOG:
        return False
    with _lock:
        if (_jobs.get(model) or {}).get("busy"):
            return False
        _jobs[model] = {"busy": True, "done": 0, "error": ""}
    threading.Thread(target=_run, args=(model,), daemon=True).start()
    return True


def remove(model: str) -> None:
    shutil.rmtree(os.path.join(root(), model), ignore_errors=True)


def _fetch(url: str, target: str, model: str, expect: str, offset: int = 0) -> str:
    """Downloads `url` to `target`; returns its SHA-256."""
    digest = hashlib.sha256()
    req = urllib.request.Request(url, headers={"User-Agent": "Kai"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(target, "wb") as out:
        while True:
            block = resp.read(1 << 20)
            if not block:
                break
            out.write(block)
            digest.update(block)
            offset += len(block)
            with _lock:
                _jobs[model]["done"] = offset
    got = digest.hexdigest()
    if expect and got != expect:
        raise ValueError("indirilen dosyanın SHA-256'sı tutmuyor")
    return got


def _unpack(archive: str, into: str) -> None:
    with tarfile.open(archive, "r:bz2") as tar:
        for member in tar.getmembers():
            name = os.path.normpath(member.name)
            # Nothing may land outside the model's folder.
            if name.startswith("..") or os.path.isabs(name) or not (member.isfile() or member.isdir()):
                continue
            tar.extract(member, into, filter="data")


def _run(model: str) -> None:
    info = CATALOG[model]
    folder = os.path.join(root(), model)
    part = os.path.join(root(), f"{model}.part")
    try:
        shutil.rmtree(folder, ignore_errors=True)
        os.makedirs(folder, exist_ok=True)
        got = _fetch(info["url"], part, model, info["sha256"])
        with _lock:
            _jobs[model]["sha256"] = got
        _unpack(part, folder)
        extra = info.get("extra")
        if extra:
            url, name, expect = extra
            _fetch(url, os.path.join(path(model) or folder, name), model, expect, offset=info["size"])
        if path(model) is None:
            raise ValueError("model açılamadı")
    except Exception as exc:
        shutil.rmtree(folder, ignore_errors=True)
        with _lock:
            _jobs[model] = {"busy": False, "done": 0, "error": str(exc) or type(exc).__name__}
        return
    finally:
        try:
            os.remove(part)
        except OSError:
            pass
    with _lock:
        _jobs[model] = {"busy": False, "done": info["size"], "error": "", "sha256": (_jobs.get(model) or {}).get("sha256", "")}


def wait(model: str, timeout: float = 3600) -> bool:
    """For scripts and tests: blocks until the download ends."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        with _lock:
            busy = (_jobs.get(model) or {}).get("busy")
        if not busy:
            return path(model) is not None
        time.sleep(1)
    return False
