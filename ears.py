"""Turn a mic recording into text."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import wave

import speech_recognition as sr

import i18n


PHRASES = [
    "open spotify",
    "open steam",
    "open discord",
    "open chrome",
    "close spotify",
    "close steam",
    "spotify",
    "steam",
    "discord",
    "notepad",
]


# Below this the recording is room noise, and Whisper invents a sentence for it.
SILENCE = 0.007
# What Whisper writes when it is handed silence.
GHOSTS = (
    "altyazı m.k", "altyazi m.k", "izlediğiniz için teşekkür", "abone olmayı unutmayın",
    "thanks for watching", "thank you for watching", "subtitles by",
)


def _wav_bytes(samples) -> bytes:
    import numpy as np

    pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype(np.int16)
    return pcm.tobytes()


def _log(message: str) -> None:
    try:
        folder = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(folder, "kai.log"), "a", encoding="utf-8") as handle:
            handle.write(time.strftime("%H:%M:%S ") + message + "\n")
    except Exception:
        pass


def _wav_file(samples) -> bytes:
    import io

    raw = io.BytesIO()
    with wave.open(raw, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(_wav_bytes(samples))
    return raw.getvalue()


def _google(samples) -> str:
    audio = sr.AudioData(_wav_bytes(samples), 16000, 2)
    try:
        return sr.Recognizer().recognize_google(audio, language=i18n.locale()).strip()
    except Exception as exc:
        _log(f"google ses {type(exc).__name__}")
        return ""


def _groq(samples, prompt: str = "") -> str:
    """Whisper on Groq, in the chosen language. Uses the saved Groq key.

    `prompt` carries the dictionary's names, so Whisper spells them as written.
    """
    import json
    import urllib.request
    import uuid

    from settings import Settings

    key = (Settings().groq_key or "").strip()
    if not key or not key.isascii():
        return ""
    boundary = "Kai" + uuid.uuid4().hex
    wav = _wav_file(samples)
    body = b"".join((
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\nwhisper-large-v3-turbo\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\n{i18n.current()}\r\n".encode(),
        (f"--{boundary}\r\nContent-Disposition: form-data; name=\"prompt\"\r\n\r\n{prompt[:800]}\r\n".encode() if prompt else b""),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"kai.wav\"\r\nContent-Type: audio/wav\r\n\r\n".encode(),
        wav,
        f"\r\n--{boundary}--\r\n".encode(),
    ))
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "Kai/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        _log(f"groq ses {type(exc).__name__}")
        return ""
    return str(data.get("text") or "").strip()


def _windows_grammar(samples) -> str:
    pcm = _wav_bytes(samples)
    path = os.path.join(tempfile.gettempdir(), "kai-hear.wav")
    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(pcm)
    quoted = ",".join("'" + item.replace("'", "") + "'" for item in PHRASES)
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine; "
        f"$engine.SetInputToWaveFile('{path}'); "
        "$choices = New-Object System.Speech.Recognition.Choices; "
        f"foreach ($item in @({quoted})) {{ $choices.Add($item) }}; "
        "$builder = New-Object System.Speech.Recognition.GrammarBuilder($choices); "
        "$engine.LoadGrammar((New-Object System.Speech.Recognition.Grammar($builder))); "
        "$result = $engine.Recognize(); "
        "if ($result) { $result.Text }"
    )
    try:
        done = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=12,
            creationflags=0x08000000,
        )
    except Exception:
        return ""
    return (done.stdout or "").strip()


def loudness(samples) -> float:
    import numpy as np

    audio = np.asarray(samples, dtype=np.float32).reshape(-1)
    return float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0


def drop_ghosts(heard: str) -> str:
    """Whisper's sentences for silence ("thanks for watching") are not speech."""
    # "İ".lower() is not a plain "i" in Python, so fold it by hand first.
    if any(ghost in heard.replace("İ", "i").lower() for ghost in GHOSTS):
        _log(f"hayalet cümle atıldı: {heard}")
        return ""
    # Noise read as one word over and over ("do do do do"), or as Japanese.
    import re
    from collections import Counter

    words = re.findall(r"\w+", heard.lower())
    if len(words) >= 4 and Counter(words).most_common(1)[0][1] / len(words) >= 0.6:
        return ""
    if re.search(r"[぀-ヿ一-鿿가-힯]", heard):
        return ""
    return heard


def transcribe(samples, prompt: str = "", grammar: bool = True) -> str:
    import numpy as np

    audio = np.asarray(samples, dtype=np.float32).reshape(-1)
    loud = loudness(audio)
    _log(f"ses {audio.size / 16000:.1f}s seviye {loud:.3f}")
    if loud < SILENCE:
        return ""
    heard = drop_ghosts(_groq(audio, prompt) or _google(audio))
    if heard or not grammar:
        return heard
    return _windows_grammar(audio)
