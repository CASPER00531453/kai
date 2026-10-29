"""Notetaker: records a call from this computer, no bot joins it.

Two streams: the microphone (you) and what the computer plays (the others),
the latter through WASAPI loopback. While recording, the words show live.
When it stops, each stream is transcribed again in full, the computer's side
is split into speakers when the speaker model is downloaded (Person 2,
Person 3…), and the chosen model writes a title, a summary, the key points
and the to-dos. The audio is deleted once the transcript is written; notes
stay in %APPDATA%\\Kai\\notes as JSON.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid

import numpy as np

import models
import stt

RATE = 16000
LIVE_EVERY = 8.0


def notes_dir() -> str:
    from settings import settings_path

    path = os.path.join(os.path.dirname(settings_path()), "notes")
    os.makedirs(path, exist_ok=True)
    return path


def _tmp_dir() -> str:
    path = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "Kai", "recording")
    os.makedirs(path, exist_ok=True)
    return path


def _to_16k(block: np.ndarray, rate: int, channels: int) -> np.ndarray:
    audio = block.reshape(-1, channels).mean(axis=1) if channels > 1 else block.reshape(-1)
    if rate == RATE or audio.size == 0:
        return audio.astype(np.float32)
    # A short moving average before thinning keeps the hiss of folded-down highs out.
    width = max(1, int(round(rate / RATE)))
    if width > 1:
        audio = np.convolve(audio, np.ones(width) / width, mode="same")
    n = int(audio.size * RATE / rate)
    return np.interp(np.linspace(0, audio.size - 1, n), np.arange(audio.size), audio).astype(np.float32)


class _Track:
    """One stream, written to disk as 16 kHz int16 while it records."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.handle = open(path, "wb")
        self.lock = threading.Lock()
        self.samples = 0
        self.live_from = 0
        self.level = 0.0

    def write(self, audio: np.ndarray) -> None:
        pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
        with self.lock:
            self.handle.write(pcm.tobytes())
            self.samples += pcm.size
        if audio.size:
            self.level = min(1.0, float(np.sqrt(np.mean(np.square(audio)))) * 14)

    def read(self, start: int = 0, end: int | None = None) -> np.ndarray:
        with self.lock:
            if not self.handle.closed:
                self.handle.flush()
            stop = self.samples if end is None else min(end, self.samples)
        if stop <= start:
            return np.zeros(0, dtype=np.float32)
        with open(self.path, "rb") as handle:
            handle.seek(start * 2)
            raw = handle.read((stop - start) * 2)
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768

    def close(self) -> None:
        with self.lock:
            self.handle.close()


class Recorder:
    def __init__(self, settings_getter) -> None:
        self._settings = settings_getter
        self.lock = threading.Lock()
        self.active = False
        self.processing = False
        self.started = 0.0
        self.live: list[dict] = []
        self.error = ""
        self.last_id = ""
        self._streams: list = []
        self._pa = None
        self._tracks: dict[str, _Track] = {}
        self._stop = threading.Event()

    # ── Status for the app and the island ───────────────────────────────────

    def status(self) -> dict:
        with self.lock:
            return {
                "recording": self.active,
                "processing": self.processing,
                "started": self.started,
                "seconds": round(time.time() - self.started) if self.active else 0,
                "live": self.live[-40:],
                "error": self.error,
                "last_id": self.last_id,
                "mic": self._tracks["me"].level if "me" in self._tracks else 0.0,
                "system": self._tracks["them"].level if "them" in self._tracks else 0.0,
            }

    # ── Recording ───────────────────────────────────────────────────────────

    def start(self) -> bool:
        with self.lock:
            if self.active or self.processing:
                return False
            self.error = ""
            self.live = []
        try:
            import pyaudiowpatch as pyaudio
        except Exception as exc:
            self.error = f"kayıt kitaplığı yok: {exc}"
            return False
        pa = pyaudio.PyAudio()
        token = uuid.uuid4().hex[:10]
        tracks = {
            "me": _Track(os.path.join(_tmp_dir(), f"{token}-me.pcm")),
            "them": _Track(os.path.join(_tmp_dir(), f"{token}-them.pcm")),
        }
        streams = []

        def opener(track: _Track, info: dict):
            rate = int(info["defaultSampleRate"])
            channels = max(1, min(2, int(info["maxInputChannels"]) or 1))

            def callback(data, frames, time_info, status):
                block = np.frombuffer(data, dtype=np.float32)
                track.write(_to_16k(block, rate, channels))
                return (None, pyaudio.paContinue)

            return pa.open(
                format=pyaudio.paFloat32,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=int(info["index"]),
                frames_per_buffer=int(rate * 0.1),
                stream_callback=callback,
            )

        try:
            mic_info = pa.get_default_input_device_info()
            streams.append(opener(tracks["me"], mic_info))
        except Exception as exc:
            self.error = f"mikrofon açılamadı: {exc}"
        try:
            loop_info = pa.get_default_wasapi_loopback()
            streams.append(opener(tracks["them"], loop_info))
        except Exception as exc:
            self.error = (self.error + " · " if self.error else "") + f"bilgisayar sesi alınamadı: {exc}"
        if not streams:
            for t in tracks.values():
                t.close()
            pa.terminate()
            return False
        for s in streams:
            s.start_stream()
        with self.lock:
            self._pa = pa
            self._streams = streams
            self._tracks = tracks
            self.active = True
            self.started = time.time()
            self._stop.clear()
        threading.Thread(target=self._live_loop, daemon=True).start()
        return True

    def stop(self) -> bool:
        with self.lock:
            if not self.active:
                return False
            self.active = False
            self.processing = True
            streams, pa, tracks = self._streams, self._pa, self._tracks
            self._streams = []
            self._stop.set()
        for s in streams:
            try:
                s.stop_stream()
                s.close()
            except Exception:
                pass
        try:
            pa.terminate()
        except Exception:
            pass
        for t in tracks.values():
            t.close()
        threading.Thread(target=self._finish, args=(tracks, time.time() - self.started), daemon=True).start()
        return True

    def _engine(self) -> tuple[str, str]:
        settings = self._settings()
        engine = getattr(settings, "stt_engine", "online")
        # Long recordings go to the computer's own model when it is there, even if
        # dictation is set to online: a whole call is a lot of audio to send.
        if engine == "online" and stt.ready("whisper"):
            engine = "whisper"
        # A call can be in any language: Whisper finds out by itself.
        return engine, "" if engine == "whisper" else getattr(settings, "language", "tr")

    def _hear(self, audio: np.ndarray) -> str:
        engine, language = self._engine()
        text, _used = stt.transcribe(audio, engine=engine, language=language)
        return text

    def _live_loop(self) -> None:
        while not self._stop.wait(LIVE_EVERY):
            them_spans: list[tuple[float, float]] = []
            for who, track in sorted(self._tracks.items(), key=lambda kv: kv[0] != "them"):
                end = track.samples
                # Leave the last half second: it may be the middle of a word.
                end = max(track.live_from, end - RATE // 2)
                chunk = track.read(track.live_from, end)
                if chunk.size < RATE:
                    continue
                spans = stt.split(chunk)
                offset = track.live_from / RATE
                if who == "them":
                    them_spans = [(offset + a / RATE, offset + b / RATE) for a, b in spans]
                for a, b in spans:
                    if who == "me" and _echo(chunk[a:b], offset + a / RATE, offset + b / RATE, them_spans):
                        continue
                    try:
                        text = self._hear(chunk[a:b])
                    except Exception:
                        text = ""
                    if text:
                        with self.lock:
                            self.live.append({"who": who, "t": round((track.live_from + a) / RATE, 1), "text": text})
                track.live_from = end

    # ── After the call ──────────────────────────────────────────────────────

    def _speakers(self, audio: np.ndarray) -> list[tuple[float, float, int]]:
        """(start, end, speaker) for the computer's side, or [] without the model."""
        folder = models.path("speakers")
        if not folder or audio.size < RATE * 3:
            return []
        try:
            import sherpa_onnx

            seg = os.path.join(folder, "model.int8.onnx")
            if not os.path.isfile(seg):
                seg = os.path.join(folder, "model.onnx")
            config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
                segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                    pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=seg),
                ),
                embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=os.path.join(folder, "voice.onnx")),
                clustering=sherpa_onnx.FastClusteringConfig(num_clusters=-1, threshold=0.6),
                min_duration_on=0.3,
                min_duration_off=0.5,
            )
            sd = sherpa_onnx.OfflineSpeakerDiarization(config)
            result = sd.process(audio).sort_by_start_time()
            return [(r.start, r.end, int(r.speaker)) for r in result]
        except Exception:
            return []

    def _finish(self, tracks: dict[str, _Track], seconds: float) -> None:
        note_id = time.strftime("%Y%m%d-%H%M%S")
        lines: list[dict] = []
        try:
            # Where the computer's side talks: the mic hears the speakers there too.
            them = tracks["them"].read()
            them_spans = [(a / RATE, b / RATE) for a, b in stt.split(them)] if them.size else []
            for who, track in tracks.items():
                audio = them if who == "them" else track.read()
                if audio.size < RATE // 2:
                    continue
                turns = self._speakers(audio) if who == "them" else []
                for a, b in stt.split(audio):
                    if who == "me" and _echo(audio[a:b], a / RATE, b / RATE, them_spans):
                        continue
                    text = self._hear(audio[a:b])
                    if not text:
                        continue
                    start, end = a / RATE, b / RATE
                    speaker = 1
                    if who == "them":
                        speaker = 2
                        if turns:
                            # The speaker who talks most inside this piece.
                            share: dict[int, float] = {}
                            for t0, t1, s in turns:
                                overlap = min(end, t1) - max(start, t0)
                                if overlap > 0:
                                    share[s] = share.get(s, 0) + overlap
                            if share:
                                speaker = 2 + max(share, key=share.get)
                    lines.append({"speaker": speaker, "start": round(start, 1), "end": round(end, 1), "text": text})
            lines.sort(key=lambda line: line["start"])
            # Speakers numbered in the order they first talk: Person 2, Person 3…
            order: dict[int, int] = {1: 1}
            for line in lines:
                if line["speaker"] not in order:
                    order[line["speaker"]] = len([k for k in order if k != 1]) + 2
                line["speaker"] = order[line["speaker"]]
            turkish = getattr(self._settings(), "language", "tr") == "tr"
            names = {str(n): ("Sen" if turkish else "You") if n == 1 else (f"Kişi {n}" if turkish else f"Person {n}") for n in sorted(set(order.values()))}
            note = {
                "id": note_id,
                "title": "",
                "started": self.started,
                "seconds": round(seconds),
                "speakers": names,
                "transcript": lines,
                "summary": "",
                "key_points": [],
                "todos": [],
                "engine": self._engine()[0],
            }
            note.update(summarize(note, turkish))
            save(note)
            with self.lock:
                self.last_id = note_id
        except Exception as exc:
            with self.lock:
                self.error = f"döküm yazılamadı: {exc}"
        finally:
            for track in tracks.values():
                try:
                    os.remove(track.path)
                except OSError:
                    pass
            with self.lock:
                self.processing = False


def _echo(piece: np.ndarray, start: float, end: float, them: list[tuple[float, float]]) -> bool:
    """A quiet stretch of the mic while the computer talks is the speakers heard again, not you.

    Someone talking into their own microphone is several times louder than the
    speakers leaking into it; without headphones Whisper would otherwise write
    the other side's words a second time, as yours.
    """
    overlap = sum(max(0.0, min(end, b) - max(start, a)) for a, b in them)
    if overlap < 0.5 * (end - start):
        return False
    loud = float(np.sqrt(np.mean(np.square(piece)))) if piece.size else 0.0
    return loud < 0.03


def transcript_text(note: dict) -> str:
    names = note.get("speakers") or {}
    out = []
    for line in note.get("transcript") or []:
        who = names.get(str(line.get("speaker")), f"#{line.get('speaker')}")
        out.append(f"{who}: {line.get('text', '')}")
    return "\n".join(out)


SUMMARY_PROMPT = (
    "You write notes of a call from its transcript. Reply with JSON only: "
    '{"title": "a short title", "summary": "3-5 sentences", "key_points": ["..."], "todos": ["who: what"]}. '
    "Write in {lang}. Use only what is in the transcript; leave a list empty when there is nothing for it."
)


def summarize(note: dict, turkish: bool = True) -> dict:
    text = transcript_text(note)
    if not text.strip():
        return {"title": "Boş kayıt" if turkish else "Empty recording"}
    from brain import ask
    from settings import Settings

    try:
        raw = ask(Settings(), text[:60000], system=SUMMARY_PROMPT.replace("{lang}", "Turkish" if turkish else "English"), timeout=90)
    except Exception:
        return {"title": time.strftime("%d.%m.%Y %H:%M", time.localtime(note.get("started") or time.time()))}
    match = re.search(r"\{.*\}", raw or "", re.S)
    try:
        data = json.loads(match.group(0)) if match else {}
    except ValueError:
        data = {}
    return {
        "title": str(data.get("title") or "")[:120] or time.strftime("%d.%m.%Y %H:%M"),
        "summary": str(data.get("summary") or "")[:4000],
        "key_points": [str(x)[:400] for x in (data.get("key_points") or [])][:20],
        "todos": [str(x)[:400] for x in (data.get("todos") or [])][:20],
    }


def save(note: dict) -> None:
    path = os.path.join(notes_dir(), f"{note['id']}.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(note, handle, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def load(note_id: str) -> dict | None:
    if not re.fullmatch(r"[\w-]{1,40}", note_id or ""):
        return None
    try:
        with open(os.path.join(notes_dir(), f"{note_id}.json"), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def listing() -> list[dict]:
    out = []
    for name in sorted(os.listdir(notes_dir()), reverse=True):
        if not name.endswith(".json"):
            continue
        note = load(name[:-5])
        if note:
            out.append({k: note.get(k) for k in ("id", "title", "started", "seconds")})
    return out


def rename_speaker(note_id: str, number: str, name: str) -> dict | None:
    note = load(note_id)
    if not note:
        return None
    clean = " ".join(str(name).split())[:40]
    if clean:
        note.setdefault("speakers", {})[str(number)] = clean
        save(note)
    return note


def delete(note_id: str) -> None:
    if load(note_id) is not None:
        os.remove(os.path.join(notes_dir(), f"{note_id}.json"))


def markdown(note: dict, turkish: bool = True) -> str:
    when = time.strftime("%d.%m.%Y %H:%M", time.localtime(note.get("started") or 0))
    minutes = max(1, round((note.get("seconds") or 0) / 60))
    parts = [f"# {note.get('title') or when}", "", f"*{when} · {minutes} {'dk' if turkish else 'min'}*", ""]
    if note.get("summary"):
        parts += ["## " + ("Özet" if turkish else "Summary"), "", note["summary"], ""]
    if note.get("key_points"):
        parts += ["## " + ("Önemli noktalar" if turkish else "Key points"), ""] + [f"- {p}" for p in note["key_points"]] + [""]
    if note.get("todos"):
        parts += ["## " + ("Yapılacaklar" if turkish else "To-dos"), ""] + [f"- [ ] {p}" for p in note["todos"]] + [""]
    parts += ["## " + ("Döküm" if turkish else "Transcript"), ""]
    names = note.get("speakers") or {}
    for line in note.get("transcript") or []:
        stamp = time.strftime("%M:%S", time.gmtime(line.get("start") or 0))
        parts.append(f"**{names.get(str(line.get('speaker')), '?')}** ({stamp}): {line.get('text', '')}")
    return "\n".join(parts) + "\n"
