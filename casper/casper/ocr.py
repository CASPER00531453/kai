"""Windows'un kendi yazı tanıması (Windows.Media.Ocr): ücretsiz, yerel, hızlı.

Türkçe için Windows'ta Türkçe dil paketi gerekir (Ayarlar > Saat ve dil > Dil).
Yoksa kullanıcı profilinin dillerinden biriyle tanır. Hiç yoksa available() False
döner ve gözcü modu ekran görüntüsünü doğrudan Claude'a gönderir.

Her satır, pencerenin hangi yarısında başladığına göre [SOL] ya da [SAĞ] ile
işaretlenir: WhatsApp ve Instagram'da sağdaki baloncuklar senin mesajlarındır.
"""

from __future__ import annotations

import asyncio
import io
import threading

_engine = None
_engine_lock = threading.Lock()
_error = ""


def _get_engine():
    global _engine, _error
    with _engine_lock:
        if _engine is not None:
            return _engine
        try:
            from winrt.windows.globalization import Language
            from winrt.windows.media.ocr import OcrEngine

            engine = None
            if OcrEngine.is_language_supported(Language("tr")):
                engine = OcrEngine.try_create_from_language(Language("tr"))
            if engine is None:
                engine = OcrEngine.try_create_from_user_profile_languages()
            if engine is None:
                _error = "Windows'ta OCR dili yok. Türkçe dil paketini kur."
            _engine = engine
        except Exception as exc:  # winrt yok ya da Windows değil
            _error = f"Windows OCR kullanılamıyor: {exc}"
            _engine = None
        return _engine


def available() -> bool:
    return _get_engine() is not None


def last_error() -> str:
    return _error


async def _recognize(png: bytes, engine):
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    writer.write_bytes(png)
    await writer.store_async()
    writer.detach_stream()
    stream.seek(0)
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    return await engine.recognize_async(bitmap)


def read_lines(image) -> list[dict]:
    """PIL görüntüsündeki satırlar; konumlar 0-1 arası (pencereye göre)."""
    engine = _get_engine()
    if engine is None:
        return []
    from winrt.windows.media.ocr import OcrEngine

    limit = OcrEngine.max_image_dimension or 2600
    if max(image.size) > limit:
        scale = limit / max(image.size)
        image = image.resize((int(image.width * scale), int(image.height * scale)))
    width, height = image.size
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="PNG")
    result = asyncio.run(_recognize(buf.getvalue(), engine))
    lines = []
    for line in result.lines:
        words = list(line.words)
        if not words:
            continue
        first, last = words[0].bounding_rect, words[-1].bounding_rect
        lines.append({
            "text": line.text,
            "x": first.x / width,
            "y": first.y / height,
            "right": (last.x + last.width) / width,
        })
    return lines


def side_of(line: dict) -> str:
    """Sağa yaslı baloncuk: ya pencerenin sağ yarısında başlıyor ya da sağ kenara dayanıyor."""
    mine = line["x"] > 0.5 or (line["right"] > 0.88 and line["x"] > 0.42)
    return "[SAĞ]" if mine else "[SOL]"


def format_lines(lines: list[dict]) -> str:
    return "\n".join(f"{side_of(l)} {l['text']}" for l in lines)


def read(image) -> str:
    return format_lines(read_lines(image))
