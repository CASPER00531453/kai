"""Windows'ta (CI) gerçek parçaları dener: OCR, öndeki pencere, pywebview içe aktarımı."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from casper import ocr, winscreen  # noqa: E402

import webview  # noqa: E402,F401

winscreen.make_dpi_aware()
print("öndeki pencere:", winscreen.foreground())

print("OCR var mı:", ocr.available(), ocr.last_error())
if ocr.available():
    img = Image.new("RGB", (900, 300), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("arial.ttf", 48)
    draw.text((20, 40), "Hello Casper", fill="black", font=font)
    draw.text((520, 180), "see you", fill="black", font=font)
    lines = ocr.read_lines(img)
    text = ocr.format_lines(lines)
    print(text)
    assert "Casper" in text, text
    assert "[SOL] Hello Casper" in text and "[SAĞ] see you" in text, text
print("TAMAM")
