"""Türkçe küfür ve atışma ölçümü: arkadaşlıkta küfür olur, mesele dozu ve yönü.

Seviyeler (her mesaj için):
- temiz:     küfür yok
- gündelik:  amk, aq, lan, oha, siktir, "amına koyim" gibi ünlemler. Noktalama
             işareti gibidir, KÜFÜR SAYILMAZ, hiçbir puanı etkilemez.
- atışma:    "mal", "salak", "gerizekalı" gibi lakaplar ya da gülme işaretiyle
             gelen ağır kelimeler. Arkadaş arasında şaka, tek başına sorun değil.
- dikkat:    aileye yönelik küfür, ağır hakaret; gülme/şaka işareti yok.
- ağır:      tehdit ya da aşağılama ("iğrençsin", "senden nefret ediyorum").

Sorun tek mesajda değil eğilimdedir: dikkat/ağır oranı artıyor mu, tek taraflı mı.
Bu modül sadece sayar; yorumu Casper bağlamı okuyarak yapar.
"""

from __future__ import annotations

import re

ASCII = str.maketrans("çğıöşüâîûÇĞİIÖŞÜ", "cgiosuaiuCGIIOSU")

# Gündelik ünlemler: sayılmaz.
CASUAL_WORDS = {
    "amk", "amq", "amg", "aq", "awk", "mk", "mq", "lan", "ulan", "la", "oha", "ooha",
    "siktir", "hassiktir", "hasiktir", "siktirgit", "siktiret", "bok", "boktan", "yarrak",
    "aminakoyim", "aminakoyayim", "aminakodum", "aminakoyim", "amnskm", "amk.", "sktr",
    "sikerim", "sikeyim", "yuh", "lanet",
}
CASUAL_PHRASES = [
    r"\bam[iı]?na? ?k[o0]y(?:ay)?[iı]?m\b",
    r"\bam[iı]na? ?k[o0]d[uı]m(?:un)?\b",
    r"\ba\.q\b",
    r"\bsiktir (?:git|et|ol)\b",
    r"\b(?:ben|boyle|bunun|bu isin|isin) (?:ta )?amina\b",
]
# Lakap ve hafif hakaret: arkadaş arasında çoğu zaman şaka.
INSULT_WORDS = {
    "mal", "salak", "aptal", "gerizekali", "gerizekal", "dangalak", "ahmak", "hiyar", "okuz",
    "esek", "beyinsiz", "embesil", "dalyarak", "dallama", "angut", "odun", "keko", "ezik",
}
INSULT_PHRASES = [r"\bgeri zekal[iı]\b", r"\bmal m[iı]s[iı]n\b"]
# Ağır: aileye yönelik, aşağılayıcı lakaplar.
HEAVY_WORDS = {
    "orospu", "orsp", "kahpe", "pezevenk", "yavsak", "serefsiz", "haysiyetsiz",
    "namussuz", "ibne", "pust", "kaltak", "surtuk", "gavat",
}
HEAVY_PHRASES = [
    r"\b(?:anan|anani|ananin|anneni|annenin|bacin|bacini|avradini|sulaleni|ecdadini|ceddini)\b.{0,25}\b(?:sik|sok|s2k|koy|kodu)",
    r"\b(?:sik|s2k)\w* (?:anani|anneni|bacini|avradini|sulaleni)\b",
    r"\borospu ?(?:cocu|evlad)",
]
# Türkçe harf olmadan başka anlama gelenler ("pic at", "öç"): sadece yazıldığı gibi aranır.
HEAVY_RAW = [r"(?<!\w)piç(?:sin|ler|lik|in|e)?(?!\w)", r"(?<!\w)o\.?ç(?!\w)", r"(?<!\w)o\.ç\.?(?!\w)"]
# Tehdit.
THREAT_PHRASES = [
    r"\bseni (?:oldururum|gebertirim|keserim|bitiririm|mahvederim|dovecegim|doverim)\b",
    r"\b(?:kafani|agzini|burnunu|bacaklarini) (?:kirarim|kiracagim|patlatirim)\b",
    r"\bcanina okurum\b",
    r"\b(?:geberesice|gebereceksin|olesice|olsen de kurtulsak)\b",
]
# Aşağılama (Gottman'ın en zararlı bulduğu şey).
CONTEMPT_PHRASES = [
    r"\bsenden nefret ediyorum\b",
    r"\bnefret ediyorum senden\b",
    r"\b(?:igrencsin|rezilsin|zavallisin|degersizsin|beş para etmezsin|bes para etmezsin)\b",
    r"\bkimse seni sevmiyor\b",
    r"\byuzunu gormek istemiyorum\b",
    r"\bsenin gibi arkadas olmaz olsun\b",
]
LAUGH = re.compile(
    r"(?:ha){2,}|(?:he){3,}|(?:hi){3,}|(?:ah){2,}a?|(?:sj){2,}|(?:js){2,}|(?:sk){2,}|xd+\b|\blol\b|\bskdj|\basd"
    r"|[😂🤣💀😭😹😆😅🙃😜😝🤪😛]"
)
MASH = re.compile(r"^[sdjkfhglqwrtypzxcvbnm]{5,}$")
WORD = re.compile(r"[\w.]+", re.UNICODE)

_compiled: dict[str, list[re.Pattern]] = {}


def _patterns(name: str, items: list[str]) -> list[re.Pattern]:
    if name not in _compiled:
        _compiled[name] = [re.compile(p) for p in items]
    return _compiled[name]


def normalize(text: str) -> str:
    text = (text or "").replace("İ", "i").replace("I", "ı").lower().translate(ASCII)
    text = re.sub(r"(.)\1{2,}", r"\1", text)  # "amkkkk" -> "amk", "lannn" -> "lan"
    return text


def _squash(word: str) -> str:
    return re.sub(r"(.)\1+", r"\1", word)


def is_joking(text: str) -> bool:
    raw = (text or "").lower()
    if LAUGH.search(raw):
        return True
    return any(MASH.match(w) for w in normalize(raw).split())


def analyze(text: str) -> dict:
    norm = normalize(text)
    raw = (text or "").replace("İ", "i").replace("I", "ı").lower()
    words = [w.strip(".") for w in WORD.findall(norm)]
    squashed = [_squash(w) for w in words]

    def hit(word: str, vocab: set[str]) -> bool:
        if word in vocab:
            return True
        # "şerefsizsin", "salaksın": 4+ harfli kelimeler eklerle de tanınır.
        return any(len(v) >= 4 and word.startswith(v) and len(word) - len(v) <= 5 for v in vocab)

    def count_words(vocab: set[str]) -> int:
        return sum(1 for w, s in zip(words, squashed) if hit(w, vocab) or hit(s, vocab))

    def count_phrases(name: str, items: list[str]) -> int:
        return sum(len(p.findall(norm)) for p in _patterns(name, items))

    result = {
        "casual": count_words(CASUAL_WORDS) + count_phrases("casual", CASUAL_PHRASES),
        "insult": count_words(INSULT_WORDS) + count_phrases("insult", INSULT_PHRASES),
        "heavy": count_words(HEAVY_WORDS) + count_phrases("heavy", HEAVY_PHRASES)
        + sum(len(p.findall(raw)) for p in _patterns("heavy_raw", HEAVY_RAW)),
        "threat": count_phrases("threat", THREAT_PHRASES),
        "contempt": count_phrases("contempt", CONTEMPT_PHRASES),
        "joking": is_joking(text),
    }
    result["level"] = level(result)
    return result


def level(r: dict) -> str:
    if (r["threat"] or r["contempt"]) and not r["joking"]:
        return "ağır"
    if r["heavy"] and not r["joking"]:
        return "dikkat"
    if r["heavy"] or r["insult"] or r["threat"] or r["contempt"]:
        return "atışma"
    if r["casual"]:
        return "gündelik"
    return "temiz"


LEVELS = ("temiz", "gündelik", "atışma", "dikkat", "ağır")


def summarize(messages: list[dict]) -> dict:
    """Taraf başına seviye sayıları. messages: {from_me, text, ts}."""
    out = {side: {lv: 0 for lv in LEVELS} for side in ("ben", "o")}
    examples: list[dict] = []
    for m in messages:
        r = analyze(m["text"])
        side = "ben" if m["from_me"] else "o"
        out[side][r["level"]] += 1
        if r["level"] in ("dikkat", "ağır"):
            examples.append({"kim": side, "seviye": r["level"], "ts": m["ts"], "metin": m["text"][:200]})
    for side in ("ben", "o"):
        total = sum(out[side].values()) or 1
        out[side]["sorunlu_yuzde"] = round(100 * (out[side]["dikkat"] + out[side]["ağır"]) / total, 2)
        out[side]["gundelik_yuzde"] = round(100 * out[side]["gündelik"] / total, 1)
    out["ornekler"] = examples[-15:]
    return out


RULES = """KÜFÜR VE ATIŞMA KURALLARI (çok önemli):
- "amk", "aq", "amq", "mk", "lan", "ulan", "oha", "siktir", "hassiktir", "amına koyim" gibi kelimeler Türkçede
  gündelik ünlemdir, noktalama işareti gibidir. Bunları KÜFÜR SAYMA, hiçbir yorumuna olumsuz etki etmesin,
  bunlar yüzünden kimseyi "kaba" ya da "saygısız" diye niteleme.
- "mal", "salak", "gerizekalı", "dangalak" gibi lakaplar arkadaşlar arasında çoğu zaman sevgi/şakadır.
  Karşılıklıysa ve gülme işareti (hahaha, sjsjsj, xd, 😂, 💀, klavye ezmesi) varsa bu YAKINLIK işaretidir.
- Sorun ancak şu durumlarda var: aileye yönelik ciddi küfür, tehdit, aşağılama ("iğrençsin", "senden nefret
  ediyorum", "değersizsin"); şaka işareti yokken; tek taraflı olduğunda (hep biri sövüyor, öbürü susuyor ya
  da kırılıyor); ya da zamanla artıyorsa. O zaman bunu açıkça ve kanıtıyla söyle.
- Tek bir ağır mesajdan sonuç çıkarma; bağlama bak (maç, oyun, şaka, kavga sonrası barışma).
- Kullanıcı da küfürlü konuşabilir; ona ahlak dersi verme, onunla rahat konuş."""
