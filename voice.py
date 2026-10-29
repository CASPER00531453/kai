"""Kai's voice: its own offline Turkish one, Microsoft's free voices, or ElevenLabs."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import urllib.error
import urllib.request

import miniaudio

import i18n
from i18n import t

_lock = threading.Lock()
_generation = 0
DEFAULT_VOICE = "nPczCjzI2devNBz1zQrb"
DEFAULT_MODEL = "eleven_v3"
PREVIEW = "Merhaba patron, ben Kai. Bu sesim nasıl?"

JARVIS = "jarvis"
JARVIS_VOICE = "onwK4e9ZLuTAKqWW03F9"

EDGE = "edge:"
EDGE_JARVIS = "edge:jarvis"
EDGE_VOICES = {
    EDGE_JARVIS: ("tr-TR-AhmetNeural", "-8%", "-6Hz"),
}

# Kai's own Turkish voice, made on this computer (models.CATALOG["voice_tr"]).
LOCAL = "local:tr"

VOICES = [
    ("Kai, Türkçe, internetsiz (ücretsiz)", LOCAL),
    ("Ahmet, Türkçe, erkek (ücretsiz)", "edge:tr-TR-AhmetNeural"),
    ("Emel, Türkçe, kadın (ücretsiz)", "edge:tr-TR-EmelNeural"),
    ("Jarvis Türkçe, tok ve sakin (ücretsiz)", EDGE_JARVIS),
    ("Andrew, çok dilli, erkek (ücretsiz)", "edge:en-US-AndrewMultilingualNeural"),
    ("Brian, çok dilli, erkek (ücretsiz)", "edge:en-US-BrianMultilingualNeural"),
    ("Florian, çok dilli, erkek (ücretsiz)", "edge:de-DE-FlorianMultilingualNeural"),
    ("Ava, çok dilli, kadın (ücretsiz)", "edge:en-US-AvaMultilingualNeural"),
    ("Emma, çok dilli, kadın (ücretsiz)", "edge:en-US-EmmaMultilingualNeural"),
    ("Jarvis tarzı, İngiliz, sakin", JARVIS),
    ("Brian, erkek, tok", "nPczCjzI2devNBz1zQrb"),
    ("George, erkek, sıcak", "JBFqnCBsd6RMkjVDRZzb"),
    ("Daniel, erkek, ciddi", "onwK4e9ZLuTAKqWW03F9"),
    ("Roger, erkek, rahat", "CwhRBWXzGAHq8TQ4Fs17"),
    ("Charlie, erkek, samimi", "IKne3meq5aSn9XLyUdCD"),
    ("Callum, erkek, sert", "N2lVS1w4EtoT3dr4eOWO"),
    ("Liam, erkek, genç", "TX3LPaxmHKxFdv7VOQHJ"),
    ("Will, erkek, neşeli", "bIHbv24MWmeRgasZH58o"),
    ("Eric, erkek, yumuşak", "cjVigY5qzO86Huf0OWal"),
    ("Chris, erkek, gündelik", "iP95p4xoKVk53GoZ742B"),
    ("Bill, erkek, yaşlı", "pqHfZKP75CvOlQylNhV4"),
    ("Sarah, kadın, yumuşak", "EXAVITQu4vr4xnSDxMaL"),
    ("Laura, kadın, canlı", "FGY2WhTYpPnrIDTdsKH5"),
    ("Alice, kadın, net", "Xb7hH8MSUJpSbSDYk0k2"),
    ("Matilda, kadın, sıcak", "XrExE9yKIg1WjnnlVkGX"),
    ("Jessica, kadın, genç", "cgSgspJ2msm6clMCkdW9"),
    ("Lily, kadın, sakin", "pFZP5JQG7iQjIQuC4Bku"),
    ("River, nötr", "SAz9YHcvj6GT2YYXdXww"),
]

VOICE_NAMES_EN = [
    "Kai, Turkish, offline (free)",
    "Ahmet, Turkish, male (free)",
    "Emel, Turkish, female (free)",
    "Jarvis Turkish, deep and calm (free)",
    "Andrew, multilingual, male (free)",
    "Brian, multilingual, male (free)",
    "Florian, multilingual, male (free)",
    "Ava, multilingual, female (free)",
    "Emma, multilingual, female (free)",
    "Jarvis style, British, calm",
    "Brian, male, deep",
    "George, male, warm",
    "Daniel, male, serious",
    "Roger, male, relaxed",
    "Charlie, male, friendly",
    "Callum, male, tough",
    "Liam, male, young",
    "Will, male, cheerful",
    "Eric, male, soft",
    "Chris, male, casual",
    "Bill, male, old",
    "Sarah, female, soft",
    "Laura, female, lively",
    "Alice, female, clear",
    "Matilda, female, warm",
    "Jessica, female, young",
    "Lily, female, calm",
    "River, neutral",
]

# Free voice that speaks every language; stands in when a Turkish-only one is picked for another language.
MULTILINGUAL = "en-US-AndrewMultilingualNeural"

# (i18n key, model id)
MODELS = [
    ("quality.v3", "eleven_v3"),
    ("quality.v2", "eleven_multilingual_v2"),
    ("quality.flash", "eleven_flash_v2_5"),
]


def voices() -> list[tuple[str, str]]:
    """VOICES with labels in the current language."""
    if i18n.current() == "tr":
        return VOICES
    return [(VOICE_NAMES_EN[index], voice_id) for index, (_label, voice_id) in enumerate(VOICES)]

_errors_shown: set[str] = set()


def speak(text: str, settings, on_error=None, force: bool = False) -> None:
    """Kai answers in writing unless speaking is switched on. `force` is for the voice preview."""
    if not force and not getattr(settings, "speak", False):
        return
    cleaned = " ".join((text or "").split())
    key = (getattr(settings, "elevenlabs_key", "") or "").strip()
    voice = (getattr(settings, "elevenlabs_voice", "") or DEFAULT_VOICE).strip()
    if not cleaned or (not key and not is_free(voice)):
        return
    model = (getattr(settings, "elevenlabs_model", "") or DEFAULT_MODEL).strip()
    threading.Thread(target=_speak, args=(_clip(cleaned), key, voice, model, on_error), daemon=True).start()


def _clip(text: str, limit: int = 1500) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[: end + 1] if end > limit // 2 else cut


def _voice_settings(model: str, jarvis: bool = False) -> dict:
    if model == "eleven_v3":
        return {"stability": 0.5, "similarity_boost": 0.85 if jarvis else 0.75, "use_speaker_boost": True}
    if jarvis:
        return {"stability": 0.75, "similarity_boost": 0.85, "style": 0.0, "use_speaker_boost": True, "speed": 0.95}
    return {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True}


def list_voices(api_key: str) -> list[tuple[str, str]]:
    request = urllib.request.Request(
        "https://api.elevenlabs.io/v1/voices",
        headers={"xi-api-key": api_key.strip()},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    found = []
    for voice in payload.get("voices") or []:
        name = voice.get("name")
        voice_id = voice.get("voice_id")
        if name and voice_id:
            found.append((name, voice_id))
    return found


def _speak(text: str, api_key: str, voice_id: str, model: str, on_error=None) -> None:
    global _generation
    with _lock:
        _generation += 1
        token = _generation
    path = os.path.join(tempfile.gettempdir(), f"kai-voice-{token}.mp3")
    try:
        edge_down = time.monotonic() < _edge_down_until
        if local_ready() and (voice_id == LOCAL or (voice_id.startswith(EDGE) and edge_down)):
            _say_local(text, token)
            return
        if voice_id == LOCAL or voice_id.startswith(EDGE):
            try:
                _download_edge(text, "edge:tr-TR-AhmetNeural" if voice_id == LOCAL else voice_id, path)
            except RuntimeError:
                # Microsoft's free voice comes and goes: Kai's own one stands in,
                # and Microsoft is not asked again for ten minutes (a refusal takes seconds).
                _mark_edge_down()
                if not local_ready():
                    raise
                _log("edge sesi yok, internetsiz sese geçildi")
                _say_local(text, token)
                return
        else:
            _download(text, api_key, voice_id, model, path)
        if token != _generation or os.path.getsize(path) < 1000:
            return
        _play(path, token)
    except Exception as exc:
        _log(f"ses hatası {exc}")
        message = str(exc)
        if on_error and message not in _errors_shown:
            _errors_shown.add(message)
            on_error(message)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


_edge_down_until = 0.0


def _mark_edge_down() -> None:
    global _edge_down_until
    _edge_down_until = time.monotonic() + 600


def is_free(voice_id: str) -> bool:
    """Speaks without an ElevenLabs key."""
    return voice_id == LOCAL or voice_id.startswith(EDGE)


def local_ready() -> bool:
    """Kai's own voice is Turkish only and needs its model downloaded."""
    import models

    return i18n.current() == "tr" and models.path("voice_tr") is not None


_tts = None
_tts_lock = threading.Lock()


def _local_engine():
    global _tts
    with _tts_lock:
        if _tts is None:
            import models
            import sherpa_onnx

            folder = models.path("voice_tr")
            onnx = models.CATALOG["voice_tr"]["check"]
            config = sherpa_onnx.OfflineTtsConfig(
                model=sherpa_onnx.OfflineTtsModelConfig(
                    vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                        model=os.path.join(folder, onnx),
                        tokens=os.path.join(folder, "tokens.txt"),
                        data_dir=os.path.join(folder, "espeak-ng-data"),
                    ),
                    num_threads=2,
                ),
                # One sentence at a time, so the first one plays while the next is made.
                max_num_sentences=1,
            )
            _tts = sherpa_onnx.OfflineTts(config)
        return _tts


def _say_local(text: str, token: int) -> None:
    import queue

    import numpy as np
    import sounddevice as sd

    engine = _local_engine()
    chunks: queue.Queue = queue.Queue()

    def made(samples, _progress) -> int:
        chunks.put(np.asarray(samples, dtype=np.float32).copy())
        return 1 if token == _generation else 0

    def play() -> None:
        with sd.OutputStream(samplerate=engine.sample_rate, channels=1, dtype="float32", latency="high") as stream:
            stream.write(np.zeros(engine.sample_rate // 10, np.float32))
            while True:
                block = chunks.get()
                if block is None or token != _generation:
                    break
                stream.write(block)
            if token == _generation:
                stream.write(np.zeros(engine.sample_rate // 4, np.float32))

    player = threading.Thread(target=play, daemon=True)
    player.start()
    try:
        with _tts_lock:
            engine.generate(text, sid=0, speed=1.0, callback=made)
    finally:
        chunks.put(None)
    player.join()


def _download_edge(text: str, voice_id: str, path: str) -> None:
    import asyncio

    import edge_tts

    name, rate, pitch = EDGE_VOICES.get(voice_id, (voice_id[len(EDGE):], "+0%", "+0Hz"))
    if "Multilingual" not in name and not name.lower().startswith(i18n.current() + "-"):
        name, rate, pitch = MULTILINGUAL, "+0%", "+0Hz"
    try:
        asyncio.run(edge_tts.Communicate(text, name, rate=rate, pitch=pitch).save(path))
    except Exception as exc:
        raise RuntimeError(t("err.edge")) from exc


def _download(text: str, api_key: str, voice_id: str, model: str, path: str) -> None:
    jarvis = voice_id == JARVIS
    if jarvis:
        voice_id = JARVIS_VOICE
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128"
    payload = {"text": text, "model_id": model, "voice_settings": _voice_settings(model, jarvis)}
    if model != "eleven_v3":
        payload["language_code"] = i18n.current()
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
            "User-Agent": "Kai/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        if "paid_plan_required" in detail:
            raise RuntimeError(t("err.eleven_paid")) from exc
        if "missing_permissions" in detail:
            raise RuntimeError(t("err.eleven_perm")) from exc
        if "quota" in detail.lower():
            raise RuntimeError(t("err.eleven_quota")) from exc
        if exc.code in (401, 403):
            raise RuntimeError(t("err.eleven_key")) from exc
        if exc.code == 429:
            raise RuntimeError(t("err.eleven_quota")) from exc
        raise RuntimeError(f"ElevenLabs {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(t("err.eleven_link")) from exc
    with open(path, "wb") as handle:
        handle.write(data)


def _play(path: str, token: int) -> None:
    import numpy as np
    import sounddevice as sd

    decoded = miniaudio.decode_file(path, output_format=miniaudio.SampleFormat.FLOAT32)
    samples = np.asarray(decoded.samples, dtype=np.float32)
    channels = max(1, int(decoded.nchannels))
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    rate = int(decoded.sample_rate)
    samples = np.concatenate([np.zeros(rate // 10, np.float32), samples, np.zeros(rate // 2, np.float32)])
    if token != _generation:
        return
    sd.play(samples, rate, latency="high")
    sd.wait()


def _log(message: str) -> None:
    try:
        with open(os.path.join(tempfile.gettempdir(), "kai-voice.log"), "a", encoding="utf-8") as handle:
            handle.write(message + "\n")
    except OSError:
        pass
