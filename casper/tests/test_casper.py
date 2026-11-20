"""Casper testleri: python -m pytest tests  (Windows gerekmez)."""

from __future__ import annotations

import json
import os
import sys
import time
import zipfile
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("CASPER_DATA_DIR", str(tmp_path / "data"))
    from casper import db

    db.reset_connection()
    yield
    db.reset_connection()


# --- WhatsApp -------------------------------------------------------------------

def test_whatsapp_android_turkish(tmp_path):
    from casper import importers

    text = (
        "19.11.2026 14:30 - Mesajlar ve aramalar uçtan uca şifrelidir.\n"
        "19.11.2026 14:32 - Ahmet: naber amk\n"
        "19.11.2026 14:33 - Burak: iyi sen\n"
        "nasılsın\n"
        "19.11.2026 14:35 - Ahmet: <Medya dahil edilmedi>\n"
        "20.11.2026 09:01 - Burak: Bu mesaj silindi\n"
    )
    path = tmp_path / "WhatsApp Sohbeti - Ahmet.txt"
    path.write_text(text, encoding="utf-8")
    [t] = importers.parse("whatsapp", [str(path)])
    assert t.title == "Ahmet"
    assert [m["sender"] for m in t.messages] == ["Ahmet", "Burak", "Ahmet", "Burak"]
    assert t.messages[1]["text"] == "iyi sen\nnasılsın"
    assert t.messages[2]["text"] == "[medya]"
    assert t.messages[3]["text"] == "[silinen mesaj]"
    assert datetime.fromtimestamp(t.messages[0]["ts"]) == datetime(2026, 11, 19, 14, 32)


def test_whatsapp_us_ampm_and_zip(tmp_path):
    from casper import importers

    text = "11/19/26, 2:32 PM - Ahmet: hey\n11/19/26, 12:05 AM - Burak: yo\n"
    z = tmp_path / "WhatsApp Chat with Ahmet.zip"
    with zipfile.ZipFile(z, "w") as handle:
        handle.writestr("WhatsApp Chat with Ahmet.txt", text)
    [t] = importers.parse("whatsapp", [str(z)])
    assert t.title == "Ahmet"
    times = sorted(datetime.fromtimestamp(m["ts"]) for m in t.messages)
    assert times == [datetime(2026, 11, 19, 0, 5), datetime(2026, 11, 19, 14, 32)]


def test_whatsapp_iphone(tmp_path):
    from casper import importers

    text = "‎[19.11.2026 14:32:05] Ahmet: selam\n[19.11.2026 14:33:00] Burak: aq selam\n"
    path = tmp_path / "_chat.txt"
    path.write_text(text, encoding="utf-8")
    [t] = importers.parse("whatsapp", [str(path)])
    assert [m["text"] for m in t.messages] == ["selam", "aq selam"]


# --- Instagram ------------------------------------------------------------------

def _mojibake(s: str) -> str:
    return s.encode("utf-8").decode("latin-1")


def test_instagram_zip_fixes_turkish(tmp_path):
    from casper import importers

    doc = {
        "participants": [{"name": _mojibake("Ayşe")}, {"name": "burak038_"}],
        "title": _mojibake("Ayşe"),
        "messages": [
            {"sender_name": "burak038_", "timestamp_ms": 1_700_000_100_000, "content": _mojibake("görüşürüz")},
            {"sender_name": _mojibake("Ayşe"), "timestamp_ms": 1_700_000_000_000, "content": _mojibake("çok güzel")},
            {"sender_name": _mojibake("Ayşe"), "timestamp_ms": 1_700_000_050_000, "content": "Liked a message"},
            {"sender_name": _mojibake("Ayşe"), "timestamp_ms": 1_700_000_060_000, "photos": [{"uri": "x"}]},
        ],
    }
    other = {"participants": [{"name": "Mehmet"}], "title": "Mehmet", "messages": [
        {"sender_name": "Mehmet", "timestamp_ms": 1_700_000_000_000, "content": "slm"}]}
    z = tmp_path / "instagram.zip"
    with zipfile.ZipFile(z, "w") as handle:
        handle.writestr("your_instagram_activity/messages/inbox/ayse_123/message_1.json", json.dumps(doc))
        handle.writestr("your_instagram_activity/messages/inbox/mehmet_9/message_1.json", json.dumps(other))
    threads = importers.parse("instagram", [str(z)])
    ayse = next(t for t in threads if t.id == "ayse_123")
    assert ayse.title == "Ayşe"
    assert [m["text"] for m in ayse.messages] == ["çok güzel", "[medya]", "görüşürüz"]
    assert importers.best_thread(threads, ["Ayşe"]) == "ayse_123"
    assert importers.guess_me(ayse, [], ["Ayşe"]) == "burak038_"


# --- Discord --------------------------------------------------------------------

def test_discord_package(tmp_path):
    from casper import importers

    z = tmp_path / "package.zip"
    with zipfile.ZipFile(z, "w") as handle:
        handle.writestr("Messages/index.json", json.dumps({"111": "Direct Message with ahmet#0", "222": "Sunucu #genel"}))
        handle.writestr("Messages/c111/messages.json", json.dumps([
            {"ID": 1, "Timestamp": "2026-11-19 14:32:00", "Contents": "naber", "Attachments": ""},
            {"ID": 2, "Timestamp": "2026-11-19 14:40:00", "Contents": "", "Attachments": "https://cdn/x.png"},
        ]))
        handle.writestr("Messages/c222/messages.csv", "ID,Timestamp,Contents,Attachments\n5,2026-11-18 10:00:00,gg,\n")
    threads = importers.parse("discord", [str(z)])
    dm = next(t for t in threads if t.id == "111")
    assert dm.title == "Direct Message with ahmet#0"
    assert dm.only_mine and all(m["from_me"] for m in dm.messages)
    assert [m["text"] for m in dm.messages] == ["naber", "[medya]"]
    assert next(t for t in threads if t.id == "222").messages[0]["text"] == "gg"


# --- Küfür ----------------------------------------------------------------------

@pytest.mark.parametrize("text,level", [
    ("amk ne yapıyosun", "gündelik"),
    ("aq geldim", "gündelik"),
    ("AMINA KOYİM ya", "gündelik"),
    ("lannnn", "gündelik"),
    ("oha", "gündelik"),
    ("mal mısın sjsjsjs", "atışma"),
    ("salaksın 😂", "atışma"),
    ("ananı sikim ahahahah", "atışma"),
    ("ananı sikerim senin", "dikkat"),
    ("şerefsizsin", "dikkat"),
    ("seni öldürürüm", "ağır"),
    ("iğrençsin", "ağır"),
    ("pic at bana", "temiz"),
    ("merhaba nasılsın", "temiz"),
])
def test_profanity_levels(text, level):
    from casper import profanity

    assert profanity.analyze(text)["level"] == level


# --- Metrikler ------------------------------------------------------------------

def test_metrics_initiation_and_replies():
    from casper import metrics

    base = 1_800_000_000
    hour = 3600
    msgs = [
        {"from_me": True, "ts": base, "text": "naber?"},
        {"from_me": False, "ts": base + 600, "text": "iyi amk sen"},
        {"from_me": True, "ts": base + 900, "text": "iyi"},
        # yeni konuşma (gün sonra), ben başlattım, cevap yok
        {"from_me": True, "ts": base + 30 * hour, "text": "müsait misin?"},
        # yeni konuşma, o başlattı
        {"from_me": False, "ts": base + 80 * hour, "text": "kanka"},
        {"from_me": True, "ts": base + 80 * hour + 120, "text": "söyle"},
    ]
    m = metrics.compute(msgs, now=base + 81 * hour)
    assert m["konusmayi_baslatan"] == {"ben": 2, "o": 1}
    assert m["cevapsiz_kalan_mesaj"]["ben"] == 1
    assert m["medyan_cevap_dakika"]["onun_cevabi"] == 10.0
    assert m["medyan_cevap_dakika"]["benim_cevabim"] == 3.5
    assert m["kufur"]["o"]["gündelik"] == 1
    assert m["kufur"]["o"]["sorunlu_yuzde"] == 0


# --- İçe aktarma akışı (arayüzün çağırdığı API) ---------------------------------

def test_api_import_flow(tmp_path):
    from casper import db
    from casper.api import Api

    path = tmp_path / "WhatsApp Sohbeti - Ahmet.txt"
    path.write_text("19.11.2026 14:32 - Ahmet K: naber\n19.11.2026 14:33 - Burak: iyi\n", encoding="utf-8")
    api = Api()
    pid = api.create_person("Ahmet", "kanka")["id"]
    db.set_setting("my_names", ["Burak"])
    prev = api.import_preview(pid, "whatsapp", [str(path)])
    assert prev["threads"][0]["guess_me"] == "Burak"
    res = api.import_commit(prev["token"], pid, [prev["best"]], "Burak")
    assert res == {"added": 2, "total": 2, "skipped": 0}
    # aynı dosya ikinci kez: hiçbir şey eklenmez
    prev = api.import_preview(pid, "whatsapp", [str(path)])
    assert api.import_commit(prev["token"], pid, [prev["best"]], "Burak")["added"] == 0
    person = api.get_person(pid)
    assert person["metrics"]["mesaj"] == 2
    assert {"platform": "whatsapp", "name": "Ahmet K"} in person["aliases"]
    assert db.search_messages("naber")[0]["sender"] == "Ahmet K"


def test_chat_uses_memory_and_saves_facts(monkeypatch):
    from casper import brain, db, llm

    pid = db.create_person("Ahmet")
    db.add_messages(pid, "whatsapp", "Ahmet", [{"sender": "Ahmet", "from_me": False, "ts": time.time() - 60, "text": "yarın maça geliyon mu"}])
    seen = {}

    def fake_ask(**kwargs):
        seen.update(kwargs)
        return "Ahmet seni maça çağırmış, güzel işaret.\n[[HATIRLA: Cuma günü sınavı var]]\n[[KISI: Ahmet | maç seviyor]]"

    monkeypatch.setattr(llm, "ask", fake_ask)
    reply = brain.chat("Ahmet beni seviyor mu sence")
    assert reply == "Ahmet seni maça çağırmış, güzel işaret."
    context = seen["system"][1]["text"]
    assert "yarın maça geliyon mu" in context
    assert seen["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert [f["text"] for f in db.facts()] == ["Cuma günü sınavı var"]
    assert "maç seviyor" in db.person(pid)["card"]
    assert [m["role"] for m in db.recent_chat()] == ["user", "assistant"]


def test_analyze_updates_card(monkeypatch):
    from casper import brain, db, llm

    pid = db.create_person("Ayşe")
    db.add_messages(pid, "instagram", "Ayşe", [
        {"sender": "Ayşe", "from_me": False, "ts": time.time() - 100, "text": "çok özledim"},
        {"sender": "ben", "from_me": True, "ts": time.time() - 50, "text": "ben de"},
    ])
    monkeypatch.setattr(llm, "ask", lambda **kw: "## Kısaca\nİyi gidiyor.\n<kart>\nAyşe: yakın arkadaş.\n</kart>")
    text = brain.analyze_person(pid)
    assert "<kart>" not in text and "İyi gidiyor" in text
    assert db.person(pid)["card"] == "Ayşe: yakın arkadaş."
    assert db.analyses_for(pid)[0]["text"] == text


def test_watcher_classify_and_match():
    from casper import db, watcher, winscreen

    pid = db.create_person("Ahmet")
    db.add_alias(pid, "whatsapp", "Ahmet Kaya")
    w = winscreen.Window(1, "WhatsApp", "WhatsApp.Root.exe", 1, (0, 0, 10, 10))
    assert watcher.classify(w) == "whatsapp"
    assert watcher.classify(winscreen.Window(1, "Instagram • Mesajlar — Mozilla Firefox", "firefox.exe", 1, (0, 0, 1, 1))) == "instagram"
    assert watcher.classify(winscreen.Window(1, "Belgeler", "explorer.exe", 1, (0, 0, 1, 1))) == ""
    lines = [{"text": "Ahmet Kaya", "x": 0.4, "y": 0.05, "right": 0.5}, {"text": "naber", "x": 0.35, "y": 0.5, "right": 0.4}]
    assert watcher.match_person("WhatsApp", lines) == pid
