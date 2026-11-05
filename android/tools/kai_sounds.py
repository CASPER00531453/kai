"""Kai's own little sounds for the Android app, synthesised (no recording, nobody else's).

python android/tools/kai_sounds.py  ->  app/src/main/res/raw/<name>.wav
"""

import math
import os
import struct
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "app", "src", "main", "res", "raw")
RATE = 44100

# name -> notes as (frequency Hz, length s); 0 Hz is a rest.
TUNES = {
    "approval": [(880, 0.09), (0, 0.03), (880, 0.09)],
    "question": [(660, 0.08), (990, 0.14)],
    "finish": [(523, 0.08), (659, 0.08), (784, 0.16)],
    "error": [(330, 0.12), (247, 0.2)],
    "greet": [(587, 0.07), (784, 0.07), (988, 0.12)],
    "love": [(784, 0.08), (1047, 0.16)],
    "work": [(440, 0.06)],
    "think": [(523, 0.05), (587, 0.05)],
    "search": [(698, 0.05), (784, 0.05), (880, 0.05)],
    "rate": [(392, 0.14), (330, 0.14)],
    "sleep": [(392, 0.18), (330, 0.24)],
    "dizzy": [(600, 0.05), (500, 0.05), (600, 0.05), (450, 0.08)],
    "annoyed": [(294, 0.1), (277, 0.14)],
    "slap": [(180, 0.05)],
}


def render(notes) -> bytes:
    frames = bytearray()
    for freq, length in notes:
        count = int(RATE * length)
        for i in range(count):
            t = i / RATE
            # A soft attack and a quick fade: a blip, not a beep.
            env = min(1.0, t / 0.008) * math.exp(-4.5 * t / max(length, 0.01))
            value = 0.0 if freq == 0 else env * (0.75 * math.sin(2 * math.pi * freq * t) + 0.25 * math.sin(4 * math.pi * freq * t))
            frames += struct.pack("<h", int(max(-1.0, min(1.0, value * 0.5)) * 32767))
    return bytes(frames)


os.makedirs(RAW, exist_ok=True)
for name, notes in TUNES.items():
    with wave.open(os.path.join(RAW, f"{name}.wav"), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(render(notes))
print("ok")
