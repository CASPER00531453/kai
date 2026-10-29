"""How loud the microphone is right now, shared with the island's process.

The main process writes it while Kai listens (AltGr, dictation, OK Kai) and the
island reads it to make the mascot rise and fall with the voice. A named
shared-memory block: no file, no socket, nothing written to disk.
"""

from __future__ import annotations

import mmap
import struct
import time

NAME = "Local\\KaiVoiceLevel"
_map: mmap.mmap | None = None


def _block() -> mmap.mmap:
    global _map
    if _map is None:
        _map = mmap.mmap(-1, 16, tagname=NAME)
    return _map


def put(level: float) -> None:
    try:
        block = _block()
        block.seek(0)
        block.write(struct.pack("<dd", max(0.0, min(1.0, float(level))), time.time()))
    except Exception:
        pass


def get() -> float:
    """0 when nobody has written for half a second: a quiet mic, or none at all."""
    try:
        block = _block()
        block.seek(0)
        level, at = struct.unpack("<dd", block.read(16))
    except Exception:
        return 0.0
    return level if time.time() - at < 0.5 else 0.0
