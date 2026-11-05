"""Draws Kai's launcher icon (the ghost, Kai's own mascot) for the Android app.

python android/tools/kai_icon.py  ->  app/src/main/res/mipmap-*/ic_launcher.png
"""

import math
import os

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "app", "src", "main", "res")
SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}


def ghost(size: int) -> Image.Image:
    s = 4  # drawn large, then scaled down for smooth edges
    n = size * s
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # The background: Kai's dark island, rounded.
    d.rounded_rectangle((0, 0, n - 1, n - 1), radius=int(n * 0.22), fill=(14, 15, 19, 255))
    # The ghost on its sheet (0..100), as in _coucou_ui/src/mochi/mascots.ts.
    u = n / 100 * 0.78
    ox, oy = n / 2 - 50 * u, n / 2 - 55 * u
    pts = []
    for i in range(0, 181):
        a = math.pi + math.pi * i / 180
        pts.append((ox + (50 + 34 * math.cos(a)) * u, oy + (52 + 38 * math.sin(a)) * u))
    for px in range(84, 15, -2):
        y = 86 + 5 * math.sin(((84 - px) / 68) * math.pi * 4)
        pts.append((ox + px * u, oy + y * u))
    glow = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(glow).polygon(pts, fill=(53, 184, 255, 140))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(n * 0.04)))
    d = ImageDraw.Draw(img)
    d.polygon(pts, fill=(77, 181, 255, 255))
    # The eyes: two dark pills.
    for ex in (40, 60):
        cx, cy = ox + ex * u, oy + 50 * u
        d.rounded_rectangle((cx - 3.6 * u, cy - 6.5 * u, cx + 3.6 * u, cy + 6.5 * u), radius=int(3.6 * u), fill=(16, 19, 26, 255))
    return img.resize((size, size), Image.LANCZOS)


for density, px in SIZES.items():
    folder = os.path.join(RES, f"mipmap-{density}")
    os.makedirs(folder, exist_ok=True)
    ghost(px).save(os.path.join(folder, "ic_launcher.png"))
print("ok")
