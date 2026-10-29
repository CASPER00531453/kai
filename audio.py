"""Microphone level plus a short recording for speech."""

from __future__ import annotations

import threading


# One block is 50 ms. A phrase needs this many loud ones, or a click or a chair
# creak gets sent off as speech.
SPEECH_LEVEL = 0.12
SPEECH_BLOCKS = 8


class Microphone:
    def __init__(self) -> None:
        self._loud = 0
        self.level = 0.0
        self.error: str | None = None
        self._stream = None
        self._chunks: list = []
        self._lock = threading.Lock()
        self._gen = 0
        self._opening = False
        self._speech_at = 0.0
        self._spoke = 0.0

    def start(self) -> None:
        """Open the mic if it is not already open. A second call must not wipe the buffer."""
        with self._lock:
            if self._stream is not None or self._opening:
                return
            self._opening = True
            self._gen += 1
            gen = self._gen
            self._chunks = []
            self._speech_at = 0.0
            self._spoke = 0.0
            self._loud = 0
            self.error = None
        threading.Thread(target=self._open, args=(gen,), daemon=True).start()

    def _open(self, gen: int) -> None:
        try:
            import numpy as np
            import sounddevice as sd

            def callback(indata, frames, time_info, status) -> None:
                samples = np.asarray(indata, dtype=np.float32).copy()
                if samples.size == 0:
                    return
                rms = float(np.sqrt(np.mean(np.square(samples))))
                with self._lock:
                    if self._gen != gen:
                        return
                    self._chunks.append(samples)
                    self.level = max(0.0, min(1.0, rms * 14.0))
                    if self.level > SPEECH_LEVEL:
                        self._loud += 1

            stream = sd.InputStream(
                channels=1,
                samplerate=16000,
                blocksize=800,
                dtype="float32",
                callback=callback,
            )
            stream.start()
        except Exception as exc:
            with self._lock:
                if gen == self._gen:
                    self.error = str(exc)
                    self.level = 0.0
                    self._opening = False
            return
        with self._lock:
            if gen != self._gen:
                self._opening = False
                abandon = stream
            else:
                self._stream = stream
                self._opening = False
                self.error = None
                abandon = None
        if abandon is not None:
            try:
                abandon.stop()
                abandon.close()
            except Exception:
                pass

    def stop(self) -> None:
        self.stop_and_take()

    def stop_and_take(self):
        with self._lock:
            self._gen += 1
            self._opening = False
            stream = self._stream
            self._stream = None
            chunks = self._chunks
            self._chunks = []
            self._speech_at = 0.0
            self._spoke = 0.0
        self.level = 0.0
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        if not chunks:
            return None
        import numpy as np

        audio = np.concatenate(chunks, axis=0).reshape(-1)
        if audio.size < 16000 * 0.18:
            return None
        return audio

    def poll_phrase(self):
        """A finished sentence while the mic stays open. None if they're still talking."""
        import time

        now = time.monotonic()
        with self._lock:
            if self._stream is None:
                return None
            if self.level > SPEECH_LEVEL:
                self._spoke = now
                if self._speech_at <= 0:
                    self._speech_at = now
            started = self._speech_at
            spoke = self._spoke
        if started <= 0:
            # Nobody is talking: keep the last second only, or the buffer grows for hours.
            with self._lock:
                del self._chunks[:-20]
                self._loud = 0
            return None
        if now - spoke < 0.7 and now - started < 8:
            return None
        with self._lock:
            chunks = self._chunks
            loud = self._loud
            self._chunks = []
            self._speech_at = 0.0
            self._spoke = 0.0
            self._loud = 0
        if not chunks or loud < SPEECH_BLOCKS:
            return None
        import numpy as np

        audio = np.concatenate(chunks, axis=0).reshape(-1)
        if audio.size < 16000 * 0.35:
            return None
        return audio
