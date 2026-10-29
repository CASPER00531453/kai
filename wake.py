"""« OK Kai »: Kai listens for its name on this computer, and only then for the request.

A small keyword model (sherpa-onnx, 17 MB) hears the microphone all the time
while this is on; nothing leaves the computer until « OK Kai » is heard. Then
Kai records the sentence that follows, up to a pause, and hands it to the same
path as AltGr. Off by default.
"""

from __future__ import annotations

import glob
import os
import threading
import time

import models
import voicelevel

RATE = 16000
# The ways people say it, spelled for the keyword model (English word pieces).
PHRASES = ("OK KAI", "OKAY KAI", "O KAY KAI", "OKEY KAI", "HEY KAI", "OKAY KY", "OK KY", "OKAY KAY", "OKEY KAY", "OK KAY")
# Sensitivity: (threshold, boost). Lower thresholds wake more easily, and more often by mistake.
SENSE = {"low": (0.15, 3.0), "mid": (0.08, 3.5), "high": (0.05, 3.8)}
END_SILENCE = 0.9  # a pause this long ends the request
LONGEST = 12.0
WAIT_FOR_SPEECH = 5.0  # after « OK Kai », how long to wait for the sentence to start


def _file(folder: str, pattern: str) -> str:
    hits = sorted(glob.glob(os.path.join(folder, pattern)))
    small = [h for h in hits if ".int8." in h]
    return (small or hits or [""])[0]


def keywords_file(folder: str, boost: float, threshold: float) -> str:
    """Writes Kai's phrases as word pieces next to the model and returns the file."""
    import sentencepiece as spm

    sp = spm.SentencePieceProcessor(model_file=os.path.join(folder, "bpe.model"))
    target = os.path.join(folder, "kai_keywords.txt")
    with open(target, "w", encoding="utf-8") as handle:
        for phrase in PHRASES:
            pieces = " ".join(sp.encode(phrase, out_type=str))
            handle.write(f"{pieces} :{boost} #{threshold} @OK_KAI\n")
    return target


def spotter(threshold: float = 0.08, boost: float = 3.5):
    import sherpa_onnx

    folder = models.path("wake")
    if not folder:
        return None
    return sherpa_onnx.KeywordSpotter(
        tokens=os.path.join(folder, "tokens.txt"),
        encoder=_file(folder, "encoder-*.onnx"),
        decoder=_file(folder, "decoder-*.onnx"),
        joiner=_file(folder, "joiner-*.onnx"),
        keywords_file=keywords_file(folder, boost, threshold),
        num_threads=1,
        keywords_threshold=threshold,
        keywords_score=boost,
        max_active_paths=4,
    )


class WakeWord:
    """Runs while « OK Kai » is on. `on_request(audio)` gets the sentence after the name."""

    def __init__(self, on_wake, on_request, paused, sense: str = "mid") -> None:
        self.sense = sense if sense in SENSE else "mid"
        self.on_wake = on_wake
        self.on_request = on_request
        self.paused = paused
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.error = ""

    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="kai-wake", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        try:
            self._listen()
        except Exception as exc:
            import traceback

            self.error = f"{type(exc).__name__}: {exc}"
            try:
                from ears import _log

                _log("OK Kai hatası: " + traceback.format_exc().replace("\n", " | ")[-600:])
            except Exception:
                pass

    def _listen(self) -> None:
        import numpy as np
        import sounddevice as sd

        kws = spotter(*SENSE[self.sense])
        if kws is None:
            self.error = "model yok"
            return
        stream = kws.create_stream()
        blocks: list = []
        lock = threading.Lock()
        ready = threading.Event()

        def callback(indata, frames, time_info, status) -> None:
            with lock:
                blocks.append(np.asarray(indata, dtype=np.float32).reshape(-1).copy())
            ready.set()

        try:
            mic = sd.InputStream(channels=1, samplerate=RATE, blocksize=1600, dtype="float32", callback=callback)
            mic.start()
        except Exception as exc:
            self.error = str(exc)
            return
        recording: list | None = None
        heard_at = 0.0
        spoke_at = 0.0
        try:
            while not self._stop.is_set():
                if not ready.wait(0.5):
                    continue
                ready.clear()
                with lock:
                    chunk = np.concatenate(blocks) if blocks else None
                    blocks.clear()
                if chunk is None:
                    continue
                if self.paused():
                    recording = None
                    continue
                now = time.monotonic()
                if recording is None:
                    stream.accept_waveform(RATE, chunk)
                    while kws.is_ready(stream):
                        kws.decode_stream(stream)
                    if kws.get_result(stream):
                        kws.reset_stream(stream)
                        recording = []
                        heard_at = now
                        spoke_at = 0.0
                        self.on_wake()
                    continue
                # « OK Kai » was heard: keep the sentence that follows, until a pause.
                recording.append(chunk)
                level = float(np.sqrt(np.mean(np.square(chunk)))) * 14.0
                voicelevel.put(min(1.0, level))
                if level > 0.12:
                    spoke_at = now
                waited = now - heard_at
                done = (spoke_at and now - spoke_at > END_SILENCE) or waited > LONGEST
                gave_up = not spoke_at and waited > WAIT_FOR_SPEECH
                if done or gave_up:
                    audio = np.concatenate(recording) if recording and spoke_at else None
                    recording = None
                    voicelevel.put(0.0)
                    stream = kws.create_stream()
                    try:
                        self.on_request(audio)
                    except Exception:
                        pass
        finally:
            try:
                mic.stop()
                mic.close()
            except Exception:
                pass
