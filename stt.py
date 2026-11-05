"""Speech to text for dictation, the notetaker and OK Kai.

Three engines. Online: Whisper on Groq with the saved key, then Google (the
audio leaves the computer). Whisper Turbo and Parakeet run on this computer
once downloaded (models.py) and nothing leaves it. A loaded model is kept for
a few minutes, then let go: Whisper Turbo holds about a gigabyte.
"""

from __future__ import annotations

import glob
import os
import threading
import time

import models

RATE = 16000
IDLE = 300.0
ENGINES = ("online", "whisper", "parakeet")

_lock = threading.Lock()
_decode = threading.Lock()
_loaded: dict[str, list] = {}


def ready(engine: str) -> bool:
    return engine == "online" or models.path(engine) is not None


def _find(folder: str, pattern: str) -> str:
    hits = sorted(glob.glob(os.path.join(folder, pattern)))
    # The int8 files are a quarter of the size and as accurate for speech.
    small = [h for h in hits if ".int8." in h]
    return (small or hits or [""])[0]


def _threads() -> int:
    return max(2, min(8, (os.cpu_count() or 4) // 2))


def _build(engine: str, language: str):
    import sherpa_onnx

    folder = models.path(engine)
    if not folder:
        return None
    if engine == "whisper":
        return sherpa_onnx.OfflineRecognizer.from_whisper(
            encoder=_find(folder, "*encoder*.onnx"),
            decoder=_find(folder, "*decoder*.onnx"),
            tokens=_find(folder, "*tokens.txt"),
            language=language,
            task="transcribe",
            num_threads=_threads(),
        )
    return sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=_find(folder, "encoder*.onnx"),
        decoder=_find(folder, "decoder*.onnx"),
        joiner=_find(folder, "joiner*.onnx"),
        tokens=os.path.join(folder, "tokens.txt"),
        model_type="nemo_transducer",
        num_threads=_threads(),
    )


def _recognizer(engine: str, language: str):
    key = f"{engine}:{language if engine == 'whisper' else ''}"
    with _lock:
        held = _loaded.get(key)
        if held:
            held[1] = time.monotonic()
            return held[0]
    rec = _build(engine, language)
    if rec is None:
        return None
    with _lock:
        _loaded[key] = [rec, time.monotonic()]
    _sweep_later()
    return rec


_sweeper: threading.Thread | None = None


def _sweep_later() -> None:
    global _sweeper
    if _sweeper and _sweeper.is_alive():
        return

    def sweep() -> None:
        while True:
            time.sleep(30)
            with _lock:
                for key in [k for k, (_r, used) in _loaded.items() if time.monotonic() - used > IDLE]:
                    del _loaded[key]
                if not _loaded:
                    return

    _sweeper = threading.Thread(target=sweep, daemon=True)
    _sweeper.start()


def _offline(samples, engine: str, language: str) -> str:
    import numpy as np

    rec = _recognizer(engine, language)
    if rec is None:
        return ""
    audio = np.asarray(samples, dtype=np.float32).reshape(-1)
    stream = rec.create_stream()
    # Half a second of silence first, as a call always has: dictation starts with
    # the key, the first word is already under way, and Parakeet, which guesses the
    # language itself, then often began in English and went on mixing (Coucou 0.5.9).
    stream.accept_waveform(RATE, np.zeros(int(RATE * 0.5), dtype=np.float32))
    stream.accept_waveform(RATE, audio)
    # Whisper hears the end of a sentence better with a little silence after it.
    stream.accept_waveform(RATE, np.zeros(int(RATE * 0.3), dtype=np.float32))
    # One decode at a time: dictation, the notetaker and OK Kai share the model.
    with _decode:
        rec.decode_stream(stream)
    return (stream.result.text or "").strip()


def transcribe(samples, engine: str = "online", language: str = "tr", prompt: str = "") -> tuple[str, str]:
    """(text, engine that heard it). An engine that is not downloaded falls back to online."""
    import ears

    if engine in ("whisper", "parakeet") and ready(engine):
        try:
            loud = ears.loudness(samples)
            if loud < ears.SILENCE:
                return "", engine
            text = _offline(samples, engine, language)
            return ears.drop_ghosts(text), engine
        except Exception as exc:
            ears._log(f"{engine} ses {type(exc).__name__}: {exc}")
    return ears.transcribe(samples, prompt=prompt, grammar=False), "online"


def split(samples, rate: int = RATE, longest: float = 24.0, gap: float = 0.6) -> list[tuple[int, int]]:
    """(start, end) sample ranges of speech, cut at pauses, none longer than `longest` seconds.

    Whisper reads at most 30 seconds at a time, so a long recording is cut where
    someone stops for breath rather than in the middle of a word.
    """
    import numpy as np

    audio = np.asarray(samples, dtype=np.float32).reshape(-1)
    hop = int(rate * 0.05)
    if audio.size < hop:
        return []
    frames = audio[: audio.size // hop * hop].reshape(-1, hop)
    energy = np.sqrt(np.mean(np.square(frames), axis=1))
    floor = max(0.006, float(np.percentile(energy, 20)) * 2.2)
    loud = energy > floor
    spans: list[tuple[int, int]] = []
    start = None
    quiet = 0
    need = int(gap / 0.05)
    for i, on in enumerate(loud):
        if on:
            if start is None:
                start = i
            quiet = 0
        elif start is not None:
            quiet += 1
            if quiet >= need:
                spans.append((start, i - quiet + 1))
                start = None
                quiet = 0
        if start is not None and (i - start) * 0.05 >= longest:
            spans.append((start, i + 1))
            start = None
            quiet = 0
    if start is not None:
        spans.append((start, len(loud)))
    pad = 4
    return [(max(0, a - pad) * hop, min(len(loud), b + pad) * hop) for a, b in spans if (b - a) * 0.05 >= 0.3]
