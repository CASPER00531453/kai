"""Bir kişiyle yazışmanın ölçülebilir tarafı. Yorum değil, sayı.

- Konuşma: 6 saatten uzun sessizlik yeni bir konuşma başlatır.
- Kim başlatıyor, kim bitiriyor; cevapsız kalan mesajlar (24 saat cevap yok).
- Cevap süresi (medyan): sen ona kaç dakikada dönüyorsun, o sana kaç dakikada.
- Mesaj ve kelime dengesi, soru sorma oranı (ilgi işareti).
- Son 30 gün ile ondan önceki 30 gün (yaklaşıyor mu, uzaklaşıyor mu).
- Küfür/atışma özeti (profanity.summarize).
"""

from __future__ import annotations

import statistics
import time

from . import profanity

SESSION_GAP = 6 * 3600
UNANSWERED = 24 * 3600
DAY = 86400


def _median_minutes(values: list[float]) -> float | None:
    return round(statistics.median(values) / 60, 1) if values else None


def compute(messages: list[dict], now: float | None = None) -> dict:
    """messages: zamana göre sıralı {from_me, ts, text}."""
    now = now or time.time()
    msgs = [m for m in messages if m.get("text")]
    if not msgs:
        return {"mesaj": 0}
    two_sided = any(m["from_me"] for m in msgs) and any(not m["from_me"] for m in msgs)

    side = {True: "ben", False: "o"}
    count = {"ben": 0, "o": 0}
    words = {"ben": 0, "o": 0}
    questions = {"ben": 0, "o": 0}
    starts = {"ben": 0, "o": 0}
    ends_unanswered = {"ben": 0, "o": 0}
    reply = {"ben": [], "o": []}  # "ben": benim cevap sürelerim
    sessions = 0

    prev = None
    for i, m in enumerate(msgs):
        who = side[bool(m["from_me"])]
        count[who] += 1
        words[who] += len(m["text"].split())
        if "?" in m["text"]:
            questions[who] += 1
        if prev is None or m["ts"] - prev["ts"] > SESSION_GAP:
            sessions += 1
            starts[who] += 1
        elif prev is not None and bool(prev["from_me"]) != bool(m["from_me"]):
            reply[who].append(m["ts"] - prev["ts"])
        prev = m

    # Cevapsız kalan: biri yazdı, karşı taraf 24 saat içinde hiç yazmadı.
    if two_sided:
        for i, m in enumerate(msgs):
            nxt = msgs[i + 1] if i + 1 < len(msgs) else None
            if nxt is not None and bool(nxt["from_me"]) == bool(m["from_me"]):
                continue  # aynı kişinin arka arkaya mesajları; son mesajda sayılır
            waited = (nxt["ts"] if nxt else now) - m["ts"]
            if waited > UNANSWERED and (nxt is not None or now - m["ts"] < 365 * DAY):
                ends_unanswered[side[bool(m["from_me"])]] += 1

    def window(start: float, end: float) -> dict:
        part = [m for m in msgs if start <= m["ts"] < end]
        return {
            "ben": sum(1 for m in part if m["from_me"]),
            "o": sum(1 for m in part if not m["from_me"]),
            "konusma_gunu": len({time.strftime("%Y-%m-%d", time.localtime(m["ts"])) for m in part}),
        }

    last = msgs[-1]["ts"]
    out = {
        "mesaj": len(msgs),
        "iki_taraf_var": two_sided,
        "ilk_mesaj": time.strftime("%Y-%m-%d", time.localtime(msgs[0]["ts"])),
        "son_mesaj": time.strftime("%Y-%m-%d %H:%M", time.localtime(last)),
        "son_mesajdan_beri_gun": round((now - last) / DAY, 1),
        "konusma_sayisi": sessions,
        "mesaj_sayisi": count,
        "ortalama_kelime": {k: round(words[k] / count[k], 1) if count[k] else 0 for k in count},
        "soru_orani_yuzde": {k: round(100 * questions[k] / count[k], 1) if count[k] else 0 for k in count},
        "konusmayi_baslatan": starts,
        "cevapsiz_kalan_mesaj": ends_unanswered,
        "medyan_cevap_dakika": {"benim_cevabim": _median_minutes(reply["ben"]), "onun_cevabi": _median_minutes(reply["o"])},
        "son_30_gun": window(now - 30 * DAY, now + 1),
        "onceki_30_gun": window(now - 60 * DAY, now - 30 * DAY),
        "kufur": profanity.summarize(msgs),
    }
    total_starts = starts["ben"] + starts["o"]
    if total_starts and two_sided:
        out["baslatma_payim_yuzde"] = round(100 * starts["ben"] / total_starts)
    if two_sided and count["ben"] + count["o"]:
        out["mesaj_payim_yuzde"] = round(100 * count["ben"] / (count["ben"] + count["o"]))
    return out
