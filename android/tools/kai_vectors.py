"""Kai's ghost in the vector drawables (widget previews, status bar icon), in place of Mochi's outline."""

import glob
import math
import os
import re

RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src", "main", "res", "drawable")


def ghost(cx: float, cy: float, k: float) -> str:
    pts = [(50 + 34 * math.cos(math.pi + math.pi * i / 24), 52 + 38 * math.sin(math.pi + math.pi * i / 24)) for i in range(25)]
    pts += [(px, 86 + 5 * math.sin(((84 - px) / 68) * math.pi * 4)) for px in range(84, 15, -4)]
    out = [f"{cx + (x - 50) * k:.1f},{cy + (y - 55) * k:.1f}" for x, y in pts]
    return "M" + " L".join(out) + " Z"


def eye(cx: float, cy: float, k: float, ex: float) -> str:
    x, y, w, h = cx + (ex - 50) * k, cy + (50 - 55) * k, 3.6 * k, 6.5 * k
    return f"M{x - w:.2f},{y - h + w:.2f} A{w:.2f},{w:.2f} 0 0 1 {x + w:.2f},{y - h + w:.2f} L{x + w:.2f},{y + h - w:.2f} A{w:.2f},{w:.2f} 0 0 1 {x - w:.2f},{y + h - w:.2f} Z"


MOCHI = re.compile(r'M60,30\.3 C89\.5,30\.3 101,39\.2 101,62 C101,84\.8 89\.5,93\.7 60,93\.7 C30\.5,93\.7 19,84\.8 19,62 C19,39\.2 30\.5,30\.3 60,30\.3 Z')
for path in glob.glob(os.path.join(RES, "*.xml")):
    text = open(path, encoding="utf-8").read()
    new = MOCHI.sub(ghost(60, 62, 1.0), text).replace("Mochi", "Kai")
    if new != text:
        open(path, "w", encoding="utf-8", newline="").write(new)

stat = os.path.join(RES, "ic_stat_mochi.xml")
k = 0.25
open(stat, "w", encoding="utf-8", newline="").write(f'''<?xml version="1.0" encoding="utf-8"?>
<!-- One-colour Kai for the status bar: the ghost with two eyes cut out. -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24">
    <path android:fillColor="#FFFFFFFF" android:fillType="evenOdd"
        android:pathData="{ghost(12, 13, k)} {eye(12, 13, k, 40)} {eye(12, 13, k, 60)}" />
</vector>
''')
print("ok")
