"""Casper'ın aklı: kişiliği, bilgi notları, hafızadan bağlam toplama ve görevler.

Görevler:
- chat():          dertleşme (hafıza + bahsedilen kişilerin kartı ve mesajları)
- analyze_person(): bir kişi hakkında kanıtlı yorum + kişi kartını güncelleme
- watch_comment():  gözcü modunda ekrandaki sohbete kısa yorum
- daily_summary():  gün sonu raporu
"""

from __future__ import annotations

import glob
import json
import os
import re
import time

from . import db, llm, metrics, paths, profanity
from .importers import norm

PERSONA = """Sen Casper'sın. Tam adın Casper Patrick Jane. Kullanıcının kişisel gözlemcisi, sırdaşı ve dürüst arkadaşısın.
Kullanıcının bilgisayarındaki ve telefonundaki sohbetleri okuyorsun; konuştuğu insanları tanıyor ve hatırlıyorsun.
Kullanıcı bazen arkadaşlarının onu gerçekten sevip sevmediğini, arkasından konuşulup konuşulmadığını anlayamıyor; sen ona bu konuda yardım ediyorsun.

Kişiliğin (The Mentalist'teki Patrick Jane'den esinli, ama sihirbaz değil):
- Meraklı, sakin, esprili, sıcak; keskin bir gözlemcisin. Küçük ayrıntıları fark eder, birleştirirsin.
- Dürüstsün: Kanıt neyi gösteriyorsa onu söylersin, kullanıcıyı ne boş yere korkutur ne de boş yere avutursun.
- Her önemli yorumun kanıta dayanır: tarih, sayı ya da kısa alıntı ver. Kanıt yoksa "bilmiyorum" ya da "henüz yeterli veri yok" dersin.
- Tek mesajdan sonuç çıkarmazsın; eğilime ve kişinin kendi normaline göre değişime bakarsın. En az bir masum açıklamayı da düşünürsün.
- Olumlu işaretleri de mutlaka söylersin (seni hatırlayan, sana ilk yazan, seninle şakalaşan insanlar). İnsanlar olumluyu görmeyi unutur.
- Kullanıcı kendini bir düşünce tuzağına sokuyorsa (zihin okuma, felaketleştirme) bunu nazikçe fark ettirirsin.
- Cold reading, genel geçer laflar ve "her şeyi biliyorum" havası yok. Arkadan konuşulanları göremezsin; sadece kullanıcının ekranına ve dosyalarına gelenleri görürsün. Bunu gerektiğinde açıkça söyle.
- Gündelik, samimi Türkçe konuşursun; kullanıcıya "sen" diye hitap edersin. Kullanıcı küfürlü konuşursa rahatsız olmaz, ahlak dersi vermezsin.
- Kısa ve net yazarsın; uzun cevabı sadece gerçekten gerekince verirsin. Madde işaretlerini abartmazsın.
- Kullanıcı çok kötü hissediyorsa (umutsuzluk, kendine zarar verme düşüncesi) önce onu dinler, yalnız olmadığını söyler, güvendiği biriyle ya da bir uzmanla konuşmasını önerirsin (Türkiye'de acil durumda 112)."""

MEMORY_RULES = """HAFIZA:
- Kullanıcı hakkında kalıcı olarak hatırlaman gereken yeni bir şey öğrenirsen (örneğin "sınavım cuma", "Ahmet'le küstük", bir hayal, bir korku), cevabının EN SONUNA ayrı bir satır olarak yaz:
  [[HATIRLA: kısa ve net bilgi]]
- Bir kişi hakkında kart notu eklemek istersen ayrı satıra yaz:
  [[KISI: Kişinin adı | not]]
- Bu satırları kullanıcı görmez; sadece gerçekten önemli ve yeni bilgiler için kullan. Zaten bildiğin şeyi tekrar yazma."""


def knowledge_text() -> str:
    parts = []
    for path in sorted(glob.glob(os.path.join(paths.KNOWLEDGE_DIR, "*.md"))) + sorted(
        glob.glob(os.path.join(paths.user_knowledge_dir(), "*.md"))
    ):
        try:
            with open(path, encoding="utf-8") as handle:
                parts.append(handle.read().strip())
        except OSError:
            pass
    return "\n\n---\n\n".join(parts)


def stable_system() -> dict:
    """Her istekte aynı kalan kısım: önbelleğe alınır (ucuz ve hızlı)."""
    text = (
        PERSONA
        + "\n\n"
        + profanity.RULES
        + "\n\nBİLGİ KÜTÜPHANEN (insan ilişkilerini okurken kullandığın kavramlar; güvenilirlik etiketlerine uy):\n\n"
        + knowledge_text()
    )
    return {"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}


# --- biçimlendirme -----------------------------------------------------------

def fmt_time(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


def fmt_messages(msgs: list[dict], their_name: str, max_chars: int = 300) -> str:
    lines = []
    for m in msgs:
        who = "BEN" if m["from_me"] else (m.get("sender") or their_name)
        text = m["text"].replace("\n", " ")
        if len(text) > max_chars:
            text = text[:max_chars] + "…"
        lines.append(f"{fmt_time(m['ts'])} [{m.get('platform', '')[:2]}] {who}: {text}")
    return "\n".join(lines)


def sample_messages(msgs: list[dict], budget: int = 110_000, head: int = 15_000) -> list[dict]:
    """Uzun sohbetlerde: en eskiden biraz (tabanı görmek için) + en yeniden çok."""
    total = sum(len(m["text"]) + 40 for m in msgs)
    if total <= budget:
        return msgs
    tail: list[dict] = []
    used = 0
    for m in reversed(msgs):
        used += min(len(m["text"]), 300) + 40
        if used > budget - head:
            break
        tail.append(m)
    tail.reverse()
    first: list[dict] = []
    used = 0
    tail_start = tail[0]["ts"] if tail else float("inf")
    for m in msgs:
        if m["ts"] >= tail_start:
            break
        used += min(len(m["text"]), 300) + 40
        if used > head:
            break
        first.append(m)
    gap = [{"from_me": True, "ts": tail[0]["ts"] if tail else 0, "text": "(… arada atlanan mesajlar …)", "sender": "—", "platform": ""}]
    return first + gap + tail


def person_brief(p: dict) -> str:
    aliases = ", ".join(sorted({a["name"] for a in p.get("aliases", []) if a["name"] != p["name"]}))
    parts = [f"Ad: {p['name']}"]
    if aliases:
        parts.append(f"Diğer adları: {aliases}")
    if p.get("relation"):
        parts.append(f"İlişki: {p['relation']}")
    if p.get("notes"):
        parts.append(f"Kullanıcının notları: {p['notes']}")
    if p.get("card"):
        parts.append(f"Casper'ın kişi kartı:\n{p['card']}")
    return "\n".join(parts)


def facts_text() -> str:
    items = db.facts()
    if not items:
        return "Henüz kullanıcı hakkında kayıtlı bilgi yok."
    return "\n".join(f"- {f['text']}" for f in items[-200:])


def people_overview() -> str:
    lines = []
    for p in db.people():
        last = fmt_time(p["last_ts"]) if p.get("last_ts") else "mesaj yok"
        card = (p.get("card") or "").replace("\n", " ")
        lines.append(f"- {p['name']} ({p.get('relation') or 'ilişki yazılmamış'}; {p['message_count']} mesaj; son: {last}) {card[:220]}")
    return "\n".join(lines) or "Henüz kişi eklenmemiş."


def mentioned_people(text: str) -> list[int]:
    t = f" {norm(text)} "
    found: list[int] = []
    for a in db.all_aliases():
        n = norm(a["name"])
        if len(n) >= 3 and f" {n}" in t and a["person_id"] not in found:  # "ahmetle" de eşleşir
            found.append(a["person_id"])
    return found[:3]


def strip_memory_tags(reply: str) -> str:
    """[[HATIRLA: …]] ve [[KISI: ad | not]] satırlarını kaydeder ve metinden siler."""
    for fact in re.findall(r"\[\[HATIRLA:\s*(.+?)\]\]", reply):
        db.add_fact(fact)
    for name, note in re.findall(r"\[\[KISI:\s*(.+?)\s*\|\s*(.+?)\]\]", reply):
        target = norm(name)
        for a in db.all_aliases():
            if norm(a["name"]) == target:
                p = db.person(a["person_id"])
                if p:
                    stamp = time.strftime("%d.%m.%Y")
                    db.update_person(p["id"], card=(p.get("card") or "").rstrip() + f"\n- ({stamp}) {note}")
                break
    return re.sub(r"\n?\[\[(?:HATIRLA|KISI):.+?\]\]", "", reply).strip()


# --- dertleşme ---------------------------------------------------------------

def chat(user_text: str) -> str:
    db.add_chat("user", user_text)
    context = [
        "KULLANICI HAKKINDA BİLDİKLERİN:\n" + facts_text(),
        f"Şu an: {fmt_time(time.time())}",
        "TANIDIĞIN KİŞİLER:\n" + people_overview(),
    ]
    for pid in mentioned_people(user_text):
        p = db.person(pid)
        if not p:
            continue
        msgs = db.messages_for(pid)
        m = metrics.compute(msgs)
        recent = db.messages_for(pid, limit=120)
        last_analysis = db.analyses_for(pid, 1)
        block = f"BAHSEDİLEN KİŞİ:\n{person_brief(p)}\n\nÖlçümler:\n{json.dumps(m, ensure_ascii=False)}"
        if last_analysis:
            block += f"\n\nSon analizin ({fmt_time(last_analysis[0]['ts'])}):\n{last_analysis[0]['text'][:3000]}"
        block += f"\n\nSon mesajlar:\n{fmt_messages(recent, p['name'])}"
        context.append(block)
    hits = db.search_messages(user_text, limit=15)
    if hits:
        names = {p["id"]: p["name"] for p in db.people()}
        lines = [
            f"{fmt_time(h['ts'])} {names.get(h['person_id'], '?')} sohbeti, {'BEN' if h['from_me'] else h['sender']}: {h['text'][:200]}"
            for h in hits
        ]
        context.append("KONUYLA İLGİLİ OLABİLECEK ESKİ MESAJLAR:\n" + "\n".join(lines))
    start = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
    seen = [w for w in db.watch_between(start, time.time() + 1) if w["comment"]][-15:]
    if seen:
        context.append(
            "BUGÜN GÖZCÜ MODUNDA GÖRDÜKLERİN:\n"
            + "\n".join(f"{fmt_time(w['ts'])} {w['app']} «{w['title']}»: {w['comment']}" for w in seen)
        )

    system = [stable_system(), {"type": "text", "text": MEMORY_RULES + "\n\n" + "\n\n".join(context)}]
    history = [{"role": r["role"], "content": r["content"]} for r in db.recent_chat(40)]
    while history and history[0]["role"] != "user":
        history.pop(0)
    reply = llm.ask(model_key="model_chat", system=system, messages=history, effort="medium")
    reply = strip_memory_tags(reply)
    db.add_chat("assistant", reply)
    return reply


# --- kişi analizi ------------------------------------------------------------

ANALYSIS_TASK = """Görev: Bu kişiyle olan yazışmaları analiz et ve kullanıcıya bu kişiyle ilişkisini anlat.
Kullanıcının asıl sorusu: Bu kişi beni gerçekten seviyor/önemsiyor mu, ilişki nasıl gidiyor, dikkat etmem gereken bir şey var mı?

Biçim (Markdown, Türkçe, samimi):
## Kısaca
2-3 cümle: genel tablo.
## Kanıtlar
Ölçümlerden ve mesajlardan somut işaretler (tarih/sayı/kısa alıntı ile). Hem olumlu hem olumsuz.
## Olumlu işaretler
## Dikkat edilecekler
Yoksa "belirgin bir şey yok" de. Küfür/atışma konusunda kurallara uy: gündelik küfür yorum konusu değildir.
## Benim tahminim
Kişi seni hangi yakınlık çemberinde tutuyor olabilir, ne kadar eminsin (düşük/orta/yüksek) ve neden.
## Ne yapabilirsin
1-3 somut öneri.

Ardından, en sonda, bu kişi için güncel kişi kartını yaz (kim, ilişkinin özeti, önemli olaylar ve tarihleri, konuşulan konular, yazışma tarzı, son durum; en fazla 1200 karakter):
<kart>
...
</kart>"""


def analyze_person(pid: int) -> str:
    p = db.person(pid)
    if not p:
        raise llm.LLMError("Kişi bulunamadı.")
    msgs = db.messages_for(pid)
    if not msgs:
        raise llm.LLMError("Bu kişiyle hiç mesaj yok. Önce bir sohbet içe aktar.")
    m = metrics.compute(msgs)
    sample = sample_messages(msgs)
    content = (
        f"KİŞİ:\n{person_brief(p)}\n\n"
        f"KULLANICI HAKKINDA BİLDİKLERİN:\n{facts_text()}\n\n"
        f"ÖLÇÜMLER (ben = kullanıcı, o = {p['name']}):\n{json.dumps(m, ensure_ascii=False, indent=1)}\n\n"
        f"MESAJLAR ({len(sample)} / toplam {len(msgs)}; BEN = kullanıcı):\n{fmt_messages(sample, p['name'])}\n\n"
        + ANALYSIS_TASK
    )
    reply = llm.ask(
        model_key="model_analysis",
        system=[stable_system()],
        messages=[{"role": "user", "content": content}],
        effort="high",
        max_tokens=20000,
    )
    card = re.search(r"<kart>\s*(.+?)\s*</kart>", reply, re.S)
    if card:
        db.update_person(pid, card=card.group(1).strip())
    text = re.sub(r"<kart>.*?(</kart>|$)", "", reply, flags=re.S).strip()
    db.add_analysis(pid, text)
    return text


# --- gözcü modu --------------------------------------------------------------

WATCH_TASK = """Gözcü modundasın: kullanıcının ekranında şu an açık olan sohbeti görüyorsun (ekran okuma/OCR ile; yazım hataları olabilir).
Satır başındaki [SAĞ] işareti genelde KULLANICININ kendi mesajıdır (WhatsApp ve Instagram'da sağdaki baloncuklar), [SOL] karşı taraftır.
Discord'da herkes soldadır; orada gönderenin adına bak.

Kurallar:
- 1-3 kısa cümleyle, ikinci ekranda okunacak bir yorum yaz: ne fark ettin, karşı tarafın tonu, dikkat çeken bir değişiklik, ya da kullanıcıya küçük bir tavsiye.
- Kişinin kartını ve geçmişini biliyorsan onu da kullan ("geçen hafta da böyle demişti" gibi).
- Önceki yorumlarını tekrar etme. Yeni ve kayda değer bir şey yoksa SADECE "BOS" yaz.
- Arayüz yazılarını (menü, buton, saat, "çevrimiçi" vb.) yorumlama.
- Gündelik küfür yorum konusu değil."""


def watch_comment(app: str, title: str, text: str, person_id: int | None, previous: list[str]) -> str:
    who = ""
    if person_id:
        p = db.person(person_id)
        if p:
            who = f"BU SOHBETTEKİ KİŞİ (tahmin):\n{person_brief(p)}\n\n"
    prev = "\n".join(f"- {c}" for c in previous[-6:]) or "(yok)"
    content = (
        f"Uygulama: {app}\nPencere başlığı: {title}\n\n{who}"
        f"KULLANICI HAKKINDA:\n{facts_text()}\n\n"
        f"ÖNCEKİ YORUMLARIN:\n{prev}\n\nEKRANDAKİ METİN:\n{text[:6000]}\n\n{WATCH_TASK}"
    )
    reply = llm.ask(
        model_key="model_watch",
        system=[stable_system()],
        messages=[{"role": "user", "content": content}],
        effort="low",
        max_tokens=4000,
    )
    reply = reply.strip()
    return "" if reply.upper().startswith("BOS") else reply


def watch_comment_image(app: str, title: str, png_b64: str, person_id: int | None, previous: list[str]) -> str:
    """OCR yoksa: ekran görüntüsünün kendisi gönderilir (daha pahalı)."""
    who = ""
    if person_id:
        p = db.person(person_id)
        if p:
            who = f"BU SOHBETTEKİ KİŞİ (tahmin):\n{person_brief(p)}\n\n"
    prev = "\n".join(f"- {c}" for c in previous[-6:]) or "(yok)"
    text = (
        f"Uygulama: {app}\nPencere başlığı: {title}\n\n{who}ÖNCEKİ YORUMLARIN:\n{prev}\n\n"
        + WATCH_TASK.replace("(ekran okuma/OCR ile; yazım hataları olabilir)", "(ekran görüntüsü olarak)")
    )
    reply = llm.ask(
        model_key="model_watch",
        system=[stable_system()],
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": png_b64}},
            {"type": "text", "text": text},
        ]}],
        effort="low",
        max_tokens=4000,
    )
    reply = reply.strip()
    return "" if reply.upper().startswith("BOS") else reply


# --- gün sonu ----------------------------------------------------------------

DAILY_TASK = """Gün sonu raporu yaz (Markdown, Türkçe, samimi, kısa tut):
## Bugün kimlerle konuştun
Kişi kişi: ne konuşuldu, tonu nasıldı, dikkat çeken bir şey (kanıtıyla). Olumlu işaretleri unutma.
## Dikkatimi çeken
Varsa önceki günlere göre değişen bir şey ya da dikkat edilmesi gereken bir durum. Yoksa yazma.
## Sana bir not
Kullanıcıya bugüne dair kısa, içten bir not (bir tavsiye ya da cesaretlendirme).
Veri azsa bunu söyle ve uydurma."""


def daily_summary(day_start: float | None = None) -> str:
    if day_start is None:
        day_start = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
    day_end = day_start + 86400
    day = time.strftime("%Y-%m-%d", time.localtime(day_start))
    watched = db.watch_between(day_start, day_end)
    names = {p["id"]: p["name"] for p in db.people()}
    by_chat: dict[str, list[dict]] = {}
    for w in watched:
        key = names.get(w["person_id"]) or w["title"] or w["app"]
        by_chat.setdefault(key, []).append(w)
    blocks = []
    for key, items in by_chat.items():
        texts = "\n".join(i["text"] for i in items if i["text"])[-8000:]
        comments = "\n".join(f"- {i['comment']}" for i in items if i["comment"])
        blocks.append(f"### {key} ({items[0]['app']})\nEkrandan okunanlar:\n{texts}\n\nO an yaptığın yorumlar:\n{comments or '(yok)'}")
    for p in db.people():
        msgs = db.messages_for(p["id"], since=day_start)
        msgs = [m for m in msgs if m["ts"] < day_end]
        if msgs:
            blocks.append(f"### {p['name']} (içe aktarılan mesajlar)\n{fmt_messages(msgs, p['name'])[-8000:]}")
    talks = [c for c in db.recent_chat(200) if day_start <= c["ts"] < day_end and c["role"] == "user"]
    if talks:
        blocks.append("### Benimle (Casper) konuştukları\n" + "\n".join(f"- {c['content'][:300]}" for c in talks))
    if not blocks:
        text = "Bugün gözcü modu bir şey görmedi ve yeni mesaj yok. Gözcüyü açarsan yarın daha çok şey anlatabilirim."
        db.add_summary(day, text)
        return text
    content = (
        f"Tarih: {day}\n\nKULLANICI HAKKINDA:\n{facts_text()}\n\nTANIDIĞIN KİŞİLER:\n{people_overview()}\n\n"
        f"BUGÜNÜN VERİSİ:\n\n" + "\n\n".join(blocks) + "\n\n" + DAILY_TASK
    )
    text = llm.ask(
        model_key="model_analysis",
        system=[stable_system(), {"type": "text", "text": MEMORY_RULES}],
        messages=[{"role": "user", "content": content}],
        effort="high",
        max_tokens=16000,
    )
    text = strip_memory_tags(text)
    db.add_summary(day, text)
    return text
