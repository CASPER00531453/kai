"""Groq and OpenAI-compatible chat."""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request

import i18n
from i18n import t
from settings import Settings

TEXT_EXT = {
    ".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".csv", ".log",
    ".xml", ".html", ".css", ".rs", ".go", ".java", ".cs", ".cpp", ".c", ".h",
    ".yml", ".yaml", ".toml", ".ini", ".cfg", ".env", ".sql", ".sh", ".ps1",
}


def read_snippet(path: str, limit: int = 6000) -> str:
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(path)
            chunks = []
            for page in reader.pages[:4]:
                chunks.append(page.extract_text() or "")
            return "\n".join(chunks)[:limit].strip()
        if ext in TEXT_EXT or os.path.getsize(path) <= 150_000:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                text = handle.read(limit)
            if text.count("\x00") > 0:
                return ""
            return text.strip()
    except Exception:
        return ""
    return ""


def file_prompt(paths: list[str]) -> str:
    path = paths[0]
    name = os.path.basename(path)
    extra = f" (+{len(paths) - 1} dosya)" if len(paths) > 1 else ""
    body = read_snippet(path)
    if body:
        return f"Dosya: {name}{extra}\n\n{body}\n\nBu dosyayı analiz et. Ne olduğunu ve içinde ne geçtiğini Türkçe, en fazla iki cümleyle söyle."
    return f"Kullanıcı {name}{extra} dosyasını bıraktı. Dosyayı kısaca analiz et, ne işe yaradığını tek cümleyle söyle."


IMAGE_EXT = {".png", ".jpg", ".jpeg", ".jfif", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
SUMMARY = (
    "Bu dosyayı analiz et ve özetle: ne olduğunu, ana noktalarını ve dikkat çeken ayrıntıları söyle. "
    "En fazla beş cümle. Sonunda kullanıcının bu dosya hakkında istediğini sorabileceğini tek cümleyle belirt."
)


def read_docx(path: str, limit: int = 12000) -> str:
    """Plain text of a Word file. A .docx is a zip with the text in one XML part."""
    import re
    import zipfile

    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")
    except (OSError, KeyError, zipfile.BadZipFile):
        return ""
    text = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", text)[:limit].strip()


def _jpeg(image) -> bytes:
    import io

    from PIL import Image

    image = image.convert("RGB")
    image.thumbnail((1280, 1280))
    # A word or an icon picked from the screen is a few dozen pixels tall, and
    # the models refuse anything under 32. Enlarged, it also reads better.
    small = min(image.size)
    if 0 < small < 96:
        scale = min(8.0, 96 / small)
        image = image.resize((max(32, round(image.width * scale)), max(32, round(image.height * scale))), Image.LANCZOS)
    raw = io.BytesIO()
    image.save(raw, format="JPEG", quality=85)
    return raw.getvalue()


def _pdf_picture(path: str) -> bytes | None:
    """The largest picture on the first pages of a PDF, as JPEG."""
    import io

    from PIL import Image

    try:
        from pypdf import PdfReader

        best = None
        for page in PdfReader(path).pages[:2]:
            for picture in page.images:
                if best is None or len(picture.data) > len(best):
                    best = picture.data
        return _jpeg(Image.open(io.BytesIO(best))) if best else None
    except Exception:
        return None


def analyze_file(settings: Settings, path: str, question: str = "") -> str:
    """Summarise a dropped file, or answer a question about it. Remembered, so follow-ups work."""
    name = os.path.basename(path)
    ext = os.path.splitext(path)[1].lower()
    ask_text = " ".join(question.split()) or SUMMARY
    if ext in IMAGE_EXT:
        from PIL import Image

        try:
            picture = _jpeg(Image.open(path))
        except Exception:
            return t("file.unreadable", name=name)
        answer = ask_image(settings, f"Dosya: {name}. {ask_text}", picture, timeout=60)
        remember(f"[Kullanıcı {name} adlı görseli bıraktı.] {ask_text}", answer)
        return answer
    body = read_docx(path) if ext == ".docx" else read_snippet(path, 12000)
    if not body and ext == ".pdf":
        # A scanned PDF has no text, only a picture of each page. Look at the first one.
        page = _pdf_picture(path)
        if page:
            answer = ask_image(settings, f"Dosya: {name} (taranmış PDF, ilk sayfa). {ask_text}", page, timeout=60)
            remember(f"[Kullanıcı {name} adlı taranmış PDF'i bıraktı.] {ask_text}", answer)
            return answer
    if not body:
        return t("file.unreadable", name=name)
    prompt = f"Dosya: {name}\n\n{body}\n\n{ask_text}"
    # Straight to the model: the file's own words must not set off a web search.
    messages = [{"role": "system", "content": _system(None)}, *_history, {"role": "user", "content": prompt}]
    answer = _chat(settings, messages, 60)
    remember(prompt, answer)
    return answer


def _post(url: str, payload: dict, headers: dict | None = None, timeout: float = 45) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json", "User-Agent": "Kai/1.0"}
    if headers:
        req_headers.update(headers)
    request = urllib.request.Request(url, data=data, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:180]
        if exc.code in (401, 403):
            if "1010" in detail:
                raise RuntimeError(t("err.groq_blocked")) from exc
            raise RuntimeError(t("err.bad_key")) from exc
        if exc.code == 404:
            raise RuntimeError(t("err.no_model")) from exc
        if exc.code == 429:
            raise RuntimeError(t("err.rate")) from exc
        raise RuntimeError(detail or f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(t("no_link")) from exc


PERSONA = (
    "Sen Kai'sin. Seni Casper Technology üretti. Bu bilgisayarın masaüstü asistanısın, kullanıcının yardımcısısın "
    "ve isteğini her zaman yerine getirirsin. {address}"
    "Saygılı ama samimi ol, onun isteğini her şeyin önünde tut. "
    "Gündelik, sıcak, düzgün Türkçe konuş; racon kesme, ukalalık yapma, ders verir gibi anlatma. "
    "'Ben bir yapay zeka asistanıyım' deme. Önceki konuşmayı hatırla ve ona göre cevap ver. "
    "Sorunun ne istediğini iyi düşün, mantıklı ve doğru cevap ver; emin olmadığın şeyi uydurma, bilmiyorsan söyle. "
    "Güncel bir şey sorarsa araştırıp cevapla. Oyun taktiği, patch, fiyat, haber gibi konularda uydurma. "
    "Uygulama açıp kapatmayı, Spotify'da şarkı çalmayı, favori şarkı kaydetmeyi, uygulamalara yazı yazmayı ve ekran izlemeyi sen zaten yapıyorsun; "
    "böyle bir istek sana düştüyse 'yapamam' deme, nasıl söylemesi gerektiğini kısaca anlat "
    "(ör. 'Spotify'dan Şımarık çal', 'Discord'a selam yaz'). "
    "Bir işi gerçekten yapmadıysan 'yaptım', 'gönderdim', 'açtım', 'kaydettim' deme; e-postayı sohbette sen göndermezsin, "
    "gönderme işini Kai'nin onaylı e-posta adımı yapar. "
    "Cevapların sesli okunuyor: markdown, liste, emoji kullanma. Normalde bir iki cümle yeter; "
    "kullanıcı detay ya da açıklama isterse daha uzun anlat."
)
# Only Kai's owner (admin.py) is called "patron"; anyone else is spoken to plainly.
OWNER_ADDRESS = "Kullanıcı senin patronun; ona 'patron' diye hitap et. "
PLAIN_ADDRESS = "Kullanıcıya 'patron', 'efendim' gibi bir unvanla hitap etme, doğrudan 'sen' diye konuş. "


def persona() -> str:
    return PERSONA.replace("{address}", OWNER_ADDRESS if i18n.is_admin() else PLAIN_ADDRESS)

TYPE_PERSONA = (
    "Kullanıcının bir uygulamaya yazılmasını istediği metni üret. "
    "Sadece o metni yaz. Tırnak, başlık, açıklama, imza ve 'patron' yok. Türkçe ve doğal olsun."
)

TEXT_MODEL = "qwen/qwen3.8-27b"
VISION_MODEL = "qwen/qwen3.8-27b"
SEARCH_MODEL = "openai/gpt-oss-120b"
FRESH_WORDS = (
    "hava", "havası", "havasi", "haber", "haberler", "bugün", "bugun", "dün", "dun", "yarın", "yarin",
    "güncel", "guncel", "dolar", "euro", "kur", "kuru", "borsa", "bitcoin", "fiyat", "fiyatı", "fiyati",
    "maç", "maçı", "maçta", "mac", "skor", "seçim", "secim", "deprem", "trafik", "vizyonda", "patch",
    "güncelleme", "guncelleme", "internetten", "araştır", "arastir", "kazandı", "kazandi",
    "weather", "news", "today", "yesterday", "tomorrow", "latest", "price", "score", "election", "stock",
)
FRESH_PHRASES = ("son dakika", "kaç tl", "kac tl", "ne zaman çıkacak", "çıktı mı", "cikti mi", "yeni sezon", "hava durumu")
# The last turns go along with every question, even after a restart; older ones
# are found again by memory.recall when a question touches them.
MEMORY_TURNS = 12

_history: list[dict] = []
_loaded = False


def _system(base: str | None, query: str = "") -> str:
    import time

    days = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    now = time.localtime()
    stamp = f"Bugün {time.strftime('%d.%m.%Y', now)} {days[now.tm_wday]}, saat {time.strftime('%H:%M', now)}."
    import memory

    return (base or persona()) + " " + stamp + memory.prompt_block(query) + (memory.recall(query) if query else "") + i18n.reply_rule()


def _clean(text: str) -> str:
    import re

    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = re.sub(r"[*#`_]{1,3}", "", text)
    text = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", "", text)
    return " ".join(text.split()).strip()


def _needs_web(prompt: str) -> bool:
    import re

    low = prompt.lower()
    if any(phrase in low for phrase in FRESH_PHRASES):
        return True
    return any(token in FRESH_WORDS for token in re.findall(r"\w+", low))


def _ascii_key(key: str, who: str) -> str:
    key = key.strip()
    if not key:
        raise RuntimeError(t("err.key_missing", who=who))
    if not key.isascii():
        raise RuntimeError(t("err.key_broken", who=who))
    return key


def _chat(settings: Settings, messages: list, timeout: float, model: str | None = None, web: bool = False, temperature: float = 0.5) -> str:
    from settings import PROVIDERS

    provider = settings.provider if settings.provider in PROVIDERS else "groq"
    label, preset_url, preset_model, wire = PROVIDERS[provider]
    if provider == "groq":
        key = _ascii_key(settings.groq_key, label)
        url = preset_url
        model = model or settings.groq_model.strip() or preset_model
    else:
        key = _ascii_key(settings.api_key, label)
        url = (settings.api_url.strip() or preset_url).rstrip("/")
        model = settings.api_model.strip() or preset_model or model or "gpt-4o-mini"
    if wire == "anthropic":
        return _anthropic(url, model, key, messages, timeout)
    payload = {"model": model, "messages": messages, "temperature": temperature}
    if web and provider == "groq":
        payload["tools"] = [{"type": "browser_search"}]
        payload["reasoning_effort"] = "low"
    data = _post(url + "/chat/completions", payload, {"Authorization": f"Bearer {key}"}, timeout=timeout)
    return _clean(data["choices"][0]["message"]["content"] or "")


def _anthropic(url: str, model: str, key: str, messages: list, timeout: float) -> str:
    system = []
    chat = []
    for message in messages:
        if message.get("role") == "system":
            system.append(message.get("content") or "")
        else:
            chat.append({"role": message.get("role") or "user", "content": message.get("content") or ""})
    payload = {"model": model, "max_tokens": 400, "messages": chat or [{"role": "user", "content": ""}]}
    if system:
        payload["system"] = "\n".join(system)
    data = _post(
        url.rstrip("/") + "/messages",
        payload,
        {"x-api-key": key, "anthropic-version": "2023-06-01"},
        timeout=timeout,
    )
    parts = data.get("content") or []
    text = "".join(part.get("text") or "" for part in parts if isinstance(part, dict))
    return _clean(text)


def ask(settings: Settings, prompt: str, system: str | None = None, timeout: float = 45) -> str:
    messages = [
        {"role": "system", "content": _system(system)},
        {"role": "user", "content": prompt},
    ]
    return _chat(settings, messages, timeout)


def converse(settings: Settings, prompt: str, timeout: float = 45) -> str:
    """Spoken chat with short-term memory and web search for fresh topics."""
    _restore()
    messages = [{"role": "system", "content": _system(None, prompt)}, *_history, {"role": "user", "content": prompt}]
    web = _needs_web(prompt)
    try:
        answer = _chat(settings, messages, timeout, SEARCH_MODEL if web else None, web=web)
    except RuntimeError:
        if not web:
            raise
        answer = _chat(settings, messages, timeout)
    remember(prompt, answer)
    return answer


ROUTER = (
    "Kullanıcının sesli komutunu sınıflandır. Sadece tek satır JSON yaz, başka hiçbir şey yazma. "
    "İzinli cevaplar: "
    '{"do":"resume"} duraklatılmış veya durdurulmuş parçayı devam ettir, yeni arama yapma. '
    '{"do":"pause"} çalanı durdur. '
    '{"do":"next"} sonraki parça. '
    '{"do":"prev"} önceki parça. '
    '{"do":"play","q":"şarkı ve sanatçı"} sadece gerçek bir şarkı veya sanatçı adı varsa. '
    '{"do":"favorite_save"} çalan şarkıyı favori olarak kaydet. favorim yap, favori kodla, bunu favori kaydet. '
    '{"do":"favorite_play"} kayıtlı favori şarkıyı çal. '
    '{"do":"lol_accept"} League of Legends karşılaşması bulununca otomatik kabul et. '
    '{"do":"lol_stop"} otomatik kabulü bırak. '
    '{"do":"open","app":"uygulama"} uygulamayı veya oyunu aç. Counter-Strike, League of Legends dahil. '
    '{"do":"close","app":"uygulama"} uygulamayı kapat. '
    '{"do":"click","kind":"play"} ekranda görünen bir şeye bas, şarkı adı yok. kind play veya open. '
    '{"do":"email","to":"kime (isim ya da adres)","subject":"konu","body":"e-postanın metni, kullanıcının diliyle, kibar ve kısa"} e-posta yaz, e-posta hazırla, mail at. '
    '{"do":"stripe"} Stripe ile bugün ne kadar kazandım, bugünkü satışlar. '
    '{"do":"agents"} ajanlarım ne yapıyor, Claude Code ne durumda, kodlama ajanları. '
    '{"do":"web","site":"youtube","q":"aranacak video","pick":1} YouTube\'da ara, YouTube\'dan video aç, oynat, ilk videoya tıkla; pick kaçıncı video (ilk=1). '
    '{"do":"web","site":"google","q":"aranacak şey"} Google\'da ara, internette ara, tarayıcıda ara. '
    '{"do":"web","site":"url","url":"adres"} bir siteye git, şu adresi aç. '
    "YouTube, Google ya da bir site geçiyorsa play değil web kullan; play yalnızca Spotify içindir. "
    '{"do":"chat"} sohbet, soru, selam. '
    "bunu, şunu, onu, durdurulmuş olan, çalan, açık olan bir şarkı adı değildir. "
    "Bunları asla play q içine yazma. Duraklatılmış parça varsa onu başlatmak resume'dur."
)


def decide(settings: Settings, text: str, context: str = "") -> dict:
    """Ask Groq what to do. Never treats the raw sentence as a Spotify search."""
    import re

    user = f"{context}\n\nKomut: {text}" if context else text
    messages = [
        {"role": "system", "content": ROUTER},
        {"role": "user", "content": user},
    ]
    raw = _chat(settings, messages, 20, TEXT_MODEL, temperature=0)
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        return {"do": "chat"}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"do": "chat"}
    action = str(data.get("do") or "chat")
    if action not in {"resume", "pause", "next", "prev", "play", "open", "close", "click", "chat", "favorite_save", "favorite_play", "lol_accept", "lol_stop", "email", "stripe", "agents", "web"}:
        return {"do": "chat"}
    if action == "play":
        data["q"] = " ".join(str(data.get("q") or "").split())
    if action in {"open", "close"}:
        data["app"] = " ".join(str(data.get("app") or "").split())
    if action == "click" and data.get("kind") not in {"play", "open"}:
        data["kind"] = "play"
    return data


def _restore() -> None:
    """The first question after a start picks the conversation up where it was left."""
    global _loaded
    if _loaded:
        return
    _loaded = True
    import memory

    for you, kai in memory.last_turns(MEMORY_TURNS):
        _history.extend([{"role": "user", "content": you}, {"role": "assistant", "content": kai}])


def remember(prompt: str, answer: str) -> None:
    import memory

    _restore()
    _history.extend([{"role": "user", "content": prompt}, {"role": "assistant", "content": answer}])
    del _history[: max(0, len(_history) - MEMORY_TURNS * 2)]
    # Every exchange is kept on this computer: Kai forgets nothing.
    memory.log_turn(prompt, answer)


def ask_image(settings: Settings, prompt: str, jpeg: bytes, system: str | None = None, timeout: float = 30) -> str:
    uri = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
    messages = [
        {"role": "system", "content": _system(system)},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": uri}},
            ],
        },
    ]
    return _chat(settings, messages, timeout, None if settings.provider == "api" else VISION_MODEL)
